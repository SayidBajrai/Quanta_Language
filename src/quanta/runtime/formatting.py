"""
Unified object-to-string formatting for Quanta runtime (Print / f-strings).

All quantum format specifiers route through QuantumFormatter.format().
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

from ..ast.nodes import (
    Expr,
    FStringExpr,
    IndexExpr,
    LiteralExpr,
    VarExpr,
)

if TYPE_CHECKING:
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector

AMPLITUDE_EPSILON = 1e-6
PURITY_PURE_THRESHOLD = 0.99
ENTANGLEMENT_THRESHOLD = 0.01
SUMMARY_PREVIEW_MAX_QBITS = 4

# Normalized specifier aliases -> canonical name
SPECIFIER_ALIASES: Dict[str, str] = {
    "": "symbolic",
    "s": "symbolic",
    "symbolic": "symbolic",
    "sym": "symbolic",
    "probabilities": "probabilities",
    "prob": "probabilities",
    "p": "probabilities",
    "density": "density",
    "rho": "density",
    "dm": "density",
    "entropy": "entropy",
    "ent": "entropy",
    "amplitudes": "amplitudes",
    "amp": "amplitudes",
    "amps": "amplitudes",
    "summary": "summary",
    "sum": "summary",
    "bloch": "bloch",
    "bloch_vector": "bloch_vector",
    "blochvector": "bloch_vector",
    "bv": "bloch_vector",
    "circuit": "circuit",
    "circ": "circuit",
    "pathway": "pathway",
    "path": "pathway",
    "pathway_circuit": "pathway",
}


@dataclass
class CircuitTraceEntry:
    """One recorded gate or macro invocation in execution history."""

    name: str
    display: str
    global_qbits: List[int]
    children: List["CircuitTraceEntry"] = field(default_factory=list)
    is_macro: bool = False


@dataclass
class FormatContext:
    """Runtime context for object string conversion."""

    circuit: "QuantumCircuit"
    qbit_map: Dict[Tuple[str, int], int]
    classical_map: Dict[Tuple[str, int], int]
    reg_sizes: Dict[str, int]
    reg_kind: Dict[str, str]
    eval_ctx: Dict[str, Any]
    eval_expr: Callable[[Expr, Dict[str, Any]], Any]
    execution_trace: List[CircuitTraceEntry] = field(default_factory=list)


@dataclass
class SubsystemState:
    """Analyzed quantum subsystem for formatting."""

    indices: List[int]
    n_qbits: int
    sv: "Statevector"
    rho: Any  # DensityMatrix
    purity: float
    entropy: float
    is_full_register: bool


def normalize_specifier(specifier: Optional[str]) -> str:
    """Map user-facing format specifier to a canonical name."""
    if specifier is None:
        return "symbolic"
    key = specifier.strip().lower()
    return SPECIFIER_ALIASES.get(key, key)


def _rationalize_amplitude(amp: complex, tol: float = 1e-9) -> Optional[Tuple[float, Optional[int], str]]:
    if abs(amp) < tol:
        return None
    phase = math.atan2(amp.imag, amp.real)
    mag = abs(amp)
    inv_sqrt2 = 1.0 / math.sqrt(2)
    if abs(mag - inv_sqrt2) < tol:
        phase_str = ""
        if abs(phase - math.pi) < tol:
            phase_str = "-"
        elif abs(phase - math.pi / 2) < tol:
            phase_str = "i"
        elif abs(phase + math.pi / 2) < tol:
            phase_str = "-i"
        elif abs(phase) >= tol:
            phase_str = f"e^(i{phase:.2g})"
        return (mag, 2, phase_str)
    if abs(mag - 0.5) < tol:
        return (mag, None, "-" if abs(phase - math.pi) < tol else "")
    if abs(mag - 1.0) < tol:
        return (mag, None, "-" if abs(phase - math.pi) < tol else "")
    return (mag, None, f"e^(i{phase:.2g})" if abs(phase) > tol else "")


def _format_ket(n: int, num_qubits: int) -> str:
    bits = format(n, f"0{num_qubits}b")
    return "|" + bits + "⟩"


def _coeff_to_string(mag: float, sqrt_denom: Optional[int], phase_str: str) -> str:
    if sqrt_denom == 2:
        coeff = "1/√2"
    elif sqrt_denom is not None:
        coeff = f"1/√{sqrt_denom}"
    elif abs(mag - 1.0) < 1e-9:
        coeff = phase_str if phase_str else "1"
    else:
        coeff = f"{mag:.4g}"
        if phase_str:
            coeff = phase_str + coeff
    if coeff == "1":
        return ""
    return coeff


def statevector_to_symbolic(statevector: "Statevector", num_qubits_show: Optional[int] = None) -> str:
    """Convert a statevector to a human-readable symbolic string."""
    sv = statevector
    dim = sv.dim
    num_qubits = num_qubits_show if num_qubits_show is not None else int(round(math.log2(dim)))
    if dim == 0:
        return "|0⟩"
    data = sv.data
    term_data: List[Tuple[str, str]] = []
    shared_coeff: Optional[str] = None
    uniform_coeff = True

    for n in range(dim):
        amp = data[n]
        if abs(amp) < 1e-9:
            continue
        ket = _format_ket(n, num_qubits)
        r = _rationalize_amplitude(amp)
        if r is None:
            term_data.append((f"({amp.real:.4g}{amp.imag:+.4g}i)", ket))
            uniform_coeff = False
            shared_coeff = None
            continue
        mag, sqrt_denom, phase_str = r
        coeff = _coeff_to_string(mag, sqrt_denom, phase_str)
        if uniform_coeff:
            if shared_coeff is None and coeff:
                shared_coeff = coeff
            elif shared_coeff is not None and coeff != shared_coeff:
                uniform_coeff = False
                shared_coeff = None
        term_data.append((coeff, ket))

    if not term_data:
        return "0"
    if len(term_data) == 1:
        coeff, ket = term_data[0]
        return f"{coeff}{ket}" if coeff else ket

    if uniform_coeff and shared_coeff:
        inner = " + ".join(ket for _, ket in term_data)
        return f"{shared_coeff} ({inner})"

    parts = []
    for coeff, ket in term_data:
        parts.append(f"{coeff}{ket}" if coeff else ket)
    return " + ".join(parts)


def _von_neumann_entropy(rho, base: int = 2) -> float:
    """Von Neumann entropy S(ρ) in bits (base 2) by default."""
    import numpy as np

    evals = np.linalg.eigvalsh(rho.data)
    evals = evals[evals > 1e-12]
    if len(evals) == 0:
        return 0.0
    log_fn = math.log2 if base == 2 else math.log
    return float(-sum(p * log_fn(p) for p in evals))


def _bipartition_entropy(sv: "Statevector", indices: List[int]) -> float:
    """Entanglement entropy across a balanced bipartition of register indices."""
    if len(indices) <= 1:
        return 0.0
    from qiskit.quantum_info import partial_trace

    split = len(indices) // 2
    keep = indices[:split] if split > 0 else indices[:1]
    trace_out = [i for i in range(sv.num_qubits) if i not in keep]
    if not trace_out:
        return 0.0
    rho = partial_trace(sv, trace_out)
    return _von_neumann_entropy(rho)


def _check_entangled_with_rest(sv: "Statevector", indices: List[int]) -> bool:
    if sv.num_qubits <= 1 or not indices:
        return False
    if len(indices) >= sv.num_qubits:
        return False
    try:
        from qiskit.quantum_info import partial_trace

        other = [i for i in range(sv.num_qubits) if i not in indices]
        rho = partial_trace(sv, other)
        purity = float((rho @ rho).trace().real)
        return purity < PURITY_PURE_THRESHOLD
    except Exception:
        return False


def _get_reduced_statevector(sv: "Statevector", indices: List[int]) -> Tuple["Statevector", int]:
    """Return (statevector to display, num_qubits for ket labels)."""
    if len(indices) >= sv.num_qubits:
        return sv, sv.num_qubits
    if _check_entangled_with_rest(sv, indices):
        return sv, sv.num_qubits
    from qiskit.quantum_info import partial_trace, purity
    import numpy as np

    other = [i for i in range(sv.num_qubits) if i not in indices]
    rho = partial_trace(sv, other)
    if purity(rho) > PURITY_PURE_THRESHOLD:
        evals, evecs = np.linalg.eigh(rho.data)
        idx_max = int(np.argmax(evals))
        reduced_sv = type(sv)(evecs[:, idx_max])
        return reduced_sv, len(indices)
    return sv, sv.num_qubits


def _resolve_qbit_indices(expr: Expr, ctx: FormatContext) -> List[int]:
    if isinstance(expr, VarExpr) and expr.name in ctx.reg_kind:
        kind = ctx.reg_kind[expr.name]
        if kind in ("qbit", "qint", "quint", "qdec", "qudec", "qfloat", "qreal"):
            size = ctx.reg_sizes.get(expr.name, 1)
            return [ctx.qbit_map[(expr.name, i)] for i in range(size)]
    if isinstance(expr, IndexExpr) and isinstance(expr.base, VarExpr):
        idx = ctx.eval_expr(expr.index, ctx.eval_ctx)
        if isinstance(idx, int):
            key = (expr.base.name, idx)
            if key in ctx.qbit_map:
                return [ctx.qbit_map[key]]
    return []


def _analyze_subsystem(expr: Expr, ctx: FormatContext) -> Optional[SubsystemState]:
    from qiskit.quantum_info import Statevector, partial_trace, purity, DensityMatrix

    indices = _resolve_qbit_indices(expr, ctx)
    if not indices:
        return None
    sv = Statevector(ctx.circuit)
    is_full = len(indices) >= sv.num_qubits
    if is_full:
        rho = DensityMatrix(sv)
    else:
        other = [i for i in range(sv.num_qubits) if i not in indices]
        rho = partial_trace(sv, other)
    p = float(purity(rho).real)
    if is_full and len(indices) > 1:
        ent = _bipartition_entropy(sv, indices)
    elif is_full:
        ent = 0.0 if p > PURITY_PURE_THRESHOLD else _von_neumann_entropy(rho)
    else:
        ent = _von_neumann_entropy(rho)
    return SubsystemState(
        indices=indices,
        n_qbits=len(indices),
        sv=sv,
        rho=rho,
        purity=p,
        entropy=ent,
        is_full_register=is_full,
    )


def _nonzero_amplitudes(sv: "Statevector", n_qbits: int) -> List[Tuple[int, complex]]:
    amps = []
    for n in range(sv.dim):
        amp = sv.data[n]
        if abs(amp) >= AMPLITUDE_EPSILON:
            amps.append((n, amp))
    return sorted(amps, key=lambda x: x[0])


def _dominant_amplitudes(sv: "Statevector", n_qbits: int, top: int = 3) -> List[Tuple[str, float]]:
    amps = _nonzero_amplitudes(sv, n_qbits)
    ranked = sorted(amps, key=lambda x: abs(x[1]), reverse=True)[:top]
    return [(_format_ket(n, n_qbits), abs(amp)) for n, amp in ranked]


def _classify_state_type(state: SubsystemState, display_sv: "Statevector") -> str:
    if state.purity < PURITY_PURE_THRESHOLD:
        return "mixed"
    if state.n_qbits <= 1:
        nz = len(_nonzero_amplitudes(display_sv, state.n_qbits))
        return "superposition" if nz > 1 else "product"
    bipartite_ent = _bipartition_entropy(state.sv, state.indices) if state.is_full_register else state.entropy
    if bipartite_ent > ENTANGLEMENT_THRESHOLD:
        return "entangled"
    if _check_entangled_with_rest(state.sv, state.indices):
        return "partially entangled"
    nz = len(_nonzero_amplitudes(display_sv, state.n_qbits))
    if nz > 1:
        return "superposition"
    return "product"


def _detect_entangled_groups(state: SubsystemState) -> Tuple[str, Optional[float]]:
    """Heuristic entanglement group detection."""
    if state.n_qbits <= 1:
        return "none detected", None
    if state.purity < PURITY_PURE_THRESHOLD:
        return "none detected (mixed state)", None
    bipartite_ent = (
        _bipartition_entropy(state.sv, state.indices)
        if state.is_full_register
        else state.entropy
    )
    if bipartite_ent > ENTANGLEMENT_THRESHOLD:
        if state.n_qbits == 2:
            return f"[{state.indices[0]},{state.indices[1]}]", bipartite_ent
        half = state.n_qbits // 2
        group_a = state.indices[:half]
        group_b = state.indices[half:]
        if len(group_a) > 1 and len(group_b) > 1:
            return f"[{','.join(str(i) for i in group_a)}]—[{','.join(str(i) for i in group_b)}]", bipartite_ent
        return f"[{','.join(str(i) for i in state.indices)}]", bipartite_ent
    return "none detected", None


def _canonical_gate_name(name: str) -> str:
    mapping = {
        "h": "H",
        "x": "X",
        "y": "Y",
        "z": "Z",
        "cnot": "CNOT",
        "cx": "CNOT",
        "cz": "CZ",
        "swap": "SWAP",
        "rz": "RZ",
        "ry": "RY",
        "rx": "RX",
    }
    return mapping.get(name.lower(), name)


def _format_trace_arg(
    expr: Expr, ctx: FormatContext, eval_ctx: Dict[str, Any]
) -> Tuple[str, List[int]]:
    """Return display label and global qubit indices for a gate argument."""
    if isinstance(expr, IndexExpr) and isinstance(expr.base, VarExpr) and expr.is_simple():
        idx = ctx.eval_expr(expr.index, eval_ctx)
        if isinstance(idx, int):
            key = (expr.base.name, idx)
            if key in ctx.qbit_map:
                return f"{expr.base.name}[{idx}]", [ctx.qbit_map[key]]
    if isinstance(expr, VarExpr):
        if ctx.reg_kind.get(expr.name) in ("qbit", "qint", "quint", "qdec", "qudec", "qfloat", "qreal"):
            size = ctx.reg_sizes.get(expr.name, 1)
            indices = [ctx.qbit_map[(expr.name, i)] for i in range(size)]
            if size == 1:
                return f"{expr.name}[0]", indices
            return expr.name, indices
        return expr.name, []
    return str(expr), []


def gate_trace_display(
    name: str, args: List[Expr], ctx: FormatContext, eval_ctx: Dict[str, Any]
) -> Tuple[str, List[int]]:
    """Build canonical gate display string and affected global qubit indices."""
    display_args: List[str] = []
    qubits: List[int] = []
    for arg in args:
        label, indices = _format_trace_arg(arg, ctx, eval_ctx)
        display_args.append(label)
        qubits.extend(indices)
    canon = _canonical_gate_name(name)
    display = f"{canon}({', '.join(display_args)})"
    return display, qubits


def _bloch_components(rho) -> Tuple[float, float, float]:
    from qiskit.quantum_info import Pauli

    x = float(rho.expectation_value(Pauli("X")).real)
    y = float(rho.expectation_value(Pauli("Y")).real)
    z = float(rho.expectation_value(Pauli("Z")).real)
    return x, y, z


def _bloch_angles(x: float, y: float, z: float) -> Tuple[float, float]:
    z_clamped = max(-1.0, min(1.0, z))
    theta = math.degrees(math.acos(z_clamped))
    phi = math.degrees(math.atan2(y, x))
    if phi < 0:
        phi += 360.0
    return theta, phi


def _format_bloch_vector_tuple(x: float, y: float, z: float) -> str:
    return f"({x:.4f}, {y:.4f}, {z:.4f})"


def _trace_entry_touches(entry: CircuitTraceEntry, indices: set) -> bool:
    if set(entry.global_qbits) & indices:
        return True
    return any(_trace_entry_touches(child, indices) for child in entry.children)


def _filter_execution_trace(
    trace: List[CircuitTraceEntry], indices: List[int]
) -> List[CircuitTraceEntry]:
    index_set = set(indices)
    return [entry for entry in trace if _trace_entry_touches(entry, index_set)]


def _count_leaf_gates(entries: List[CircuitTraceEntry]) -> int:
    total = 0
    for entry in entries:
        if entry.children:
            total += _count_leaf_gates(entry.children)
        else:
            total += 1
    return total


def _circuit_depth(entries: List[CircuitTraceEntry]) -> int:
    depth = 0
    for entry in entries:
        if entry.children:
            depth += _circuit_depth(entry.children)
        else:
            depth += 1
    return depth


def _format_trace_lines(entries: List[CircuitTraceEntry]) -> List[str]:
    lines: List[str] = []
    for step, entry in enumerate(entries, start=1):
        lines.append(f"{step}. {entry.display}")
        for i, child in enumerate(entry.children):
            connector = "├─" if i < len(entry.children) - 1 else "└─"
            lines.append(f"   {connector} {child.display}")
    return lines


def _compressed_preview(display_sv: "Statevector", n_qbits: int) -> str:
    nz = _nonzero_amplitudes(display_sv, n_qbits)
    dim = 2 ** n_qbits
    if len(nz) == dim:
        mag = abs(nz[0][1])
        if all(abs(abs(a) - mag) < 1e-6 for _, a in nz):
            denom = int(round(1 / (mag * mag)))
            if denom > 1 and abs(mag - 1 / math.sqrt(denom)) < 1e-6:
                return f"1/√{denom} (uniform superposition)"
            return f"{mag:.4g} (uniform superposition)"
    if len(nz) <= 8:
        return statevector_to_symbolic(display_sv, n_qbits)
    return f"{len(nz)}-component superposition ({n_qbits} qbits)"


class QuantumFormatter:
    """Single dispatcher for all quantum object format specifiers."""

    @staticmethod
    def format(expr: Expr, ctx: FormatContext, specifier: Optional[str] = None) -> str:
        spec = normalize_specifier(specifier)
        handlers = {
            "symbolic": QuantumFormatter._format_symbolic,
            "probabilities": QuantumFormatter._format_probabilities,
            "density": QuantumFormatter._format_density,
            "entropy": QuantumFormatter._format_entropy,
            "amplitudes": QuantumFormatter._format_amplitudes,
            "summary": QuantumFormatter._format_summary,
            "bloch": QuantumFormatter._format_bloch,
            "bloch_vector": QuantumFormatter._format_bloch_vector,
            "circuit": QuantumFormatter._format_circuit,
            "pathway": QuantumFormatter._format_pathway,
        }
        handler = handlers.get(spec, QuantumFormatter._format_symbolic)
        return handler(expr, ctx)

    @staticmethod
    def _require_state(expr: Expr, ctx: FormatContext) -> Optional[SubsystemState]:
        return _analyze_subsystem(expr, ctx)

    @staticmethod
    def _format_symbolic(expr: Expr, ctx: FormatContext) -> str:
        state = QuantumFormatter._require_state(expr, ctx)
        if state is None:
            return "<quantum register>"
        reduced, n_show = _get_reduced_statevector(state.sv, state.indices)
        return statevector_to_symbolic(reduced, n_show)

    @staticmethod
    def _format_probabilities(expr: Expr, ctx: FormatContext) -> str:
        state = QuantumFormatter._require_state(expr, ctx)
        if state is None:
            return "<probabilities unavailable>"
        probs = state.sv.probabilities_dict(qargs=state.indices)
        lines = []
        for bitstr, prob in sorted(probs.items(), key=lambda x: int(x[0], 2)):
            if prob < 1e-9:
                continue
            n = int(bitstr, 2)
            ket = _format_ket(n, state.n_qbits)
            pct = prob * 100
            if abs(pct - round(pct)) < 0.05:
                lines.append(f"{ket} : {pct:.0f}%")
            else:
                lines.append(f"{ket} : {pct:.2f}%")
        return "\n".join(lines) if lines else "<empty>"

    @staticmethod
    def _format_complex_cell(value: complex) -> str:
        if abs(value.imag) < 1e-9:
            real = value.real
            if abs(real) < 1e-9:
                return "0"
            return f"{real:.4g}"
        return f"{value.real:.4g}{value.imag:+.4g}i"

    @staticmethod
    def _format_density_matrix(data) -> str:
        rows = [
            [QuantumFormatter._format_complex_cell(v) for v in row]
            for row in data
        ]
        if not rows:
            return "[]"
        col_widths = [0] * len(rows[0])
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(cell))
        formatted_rows = []
        for row in rows:
            cells = [cell.rjust(col_widths[i]) for i, cell in enumerate(row)]
            formatted_rows.append("[" + ", ".join(cells) + "]")
        return "[\n" + ",\n".join(f" {r}" for r in formatted_rows) + "\n]"

    @staticmethod
    def _format_density(expr: Expr, ctx: FormatContext) -> str:
        state = QuantumFormatter._require_state(expr, ctx)
        if state is None:
            return "<density matrix unavailable>"
        return QuantumFormatter._format_density_matrix(state.rho.data)

    @staticmethod
    def _format_entropy(expr: Expr, ctx: FormatContext) -> str:
        state = QuantumFormatter._require_state(expr, ctx)
        if state is None:
            return "<entropy unavailable>"
        return f"{state.entropy:.4f}"

    @staticmethod
    def _format_amplitudes(expr: Expr, ctx: FormatContext) -> str:
        state = QuantumFormatter._require_state(expr, ctx)
        if state is None:
            return "<amplitudes unavailable>"
        reduced, n_show = _get_reduced_statevector(state.sv, state.indices)
        lines = []
        for n, amp in _nonzero_amplitudes(reduced, n_show):
            ket = _format_ket(n, n_show)
            lines.append(f"{ket} : {abs(amp):.4f}")
        return "\n".join(lines) if lines else "<empty>"

    @staticmethod
    def _format_summary(expr: Expr, ctx: FormatContext) -> str:
        state = QuantumFormatter._require_state(expr, ctx)
        if state is None:
            return "<summary unavailable>"
        reduced, n_show = _get_reduced_statevector(state.sv, state.indices)
        state_type = _classify_state_type(state, reduced)
        purity_label = "pure" if state.purity > PURITY_PURE_THRESHOLD else "mixed"
        ent_groups, max_ent = _detect_entangled_groups(state)
        basis_count = len(_nonzero_amplitudes(reduced, n_show))
        dominant = _dominant_amplitudes(reduced, n_show, top=3)
        preview = (
            statevector_to_symbolic(reduced, n_show)
            if n_show <= SUMMARY_PREVIEW_MAX_QBITS
            else _compressed_preview(reduced, n_show)
        )

        lines = [
            "QUBIT INFO",
            f"- size: {state.n_qbits}",
            f"- type: {state_type}",
            f"- purity: {purity_label}",
            f"- entropy: {state.entropy:.4f}",
            "",
            "ENTANGLEMENT",
            f"- entangled_groups: {ent_groups}",
        ]
        if max_ent is not None:
            lines.append(f"- max_entanglement: {max_ent:.4f}")
        lines.extend([
            "",
            "STATE COMPLEXITY",
            f"- basis_states: {basis_count}",
            "- dominant_states:",
        ])
        if dominant:
            for ket, mag in dominant:
                lines.append(f"  {ket} : {mag:.4f}")
        else:
            lines.append("  (none)")
        lines.extend([
            "",
            "PREVIEW",
            preview,
        ])
        return "\n".join(lines)

    @staticmethod
    def _format_bloch(expr: Expr, ctx: FormatContext) -> str:
        state = QuantumFormatter._require_state(expr, ctx)
        if state is None:
            return "<bloch unavailable>"
        if state.n_qbits != 1:
            return "Bloch representation requires single qubit or reduced subsystem"
        x, y, z = _bloch_components(state.rho)
        theta, phi = _bloch_angles(x, y, z)
        lines = [
            "BLOCH SPHERE",
            f"- θ (theta): {theta:.0f}°",
            f"- φ (phi): {phi:.0f}°",
            f"- vector: {_format_bloch_vector_tuple(x, y, z)}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _format_bloch_vector(expr: Expr, ctx: FormatContext) -> str:
        state = QuantumFormatter._require_state(expr, ctx)
        if state is None:
            return "<bloch_vector unavailable>"
        if state.n_qbits != 1:
            return "Bloch representation requires single qubit or reduced subsystem"
        x, y, z = _bloch_components(state.rho)
        return _format_bloch_vector_tuple(x, y, z)

    @staticmethod
    def _format_circuit(expr: Expr, ctx: FormatContext) -> str:
        indices = _resolve_qbit_indices(expr, ctx)
        if not indices:
            return "<circuit trace unavailable>"
        filtered = _filter_execution_trace(ctx.execution_trace, indices)
        trace_lines = _format_trace_lines(filtered)
        total_gates = _count_leaf_gates(filtered)
        depth = _circuit_depth(filtered)
        lines = [
            "CIRCUIT EXECUTION TRACE",
            "--------------------------------",
        ]
        if trace_lines:
            lines.extend(trace_lines)
        else:
            lines.append("(no gates recorded)")
        lines.extend([
            "",
            f"TOTAL GATES: {total_gates}",
            f"DEPTH: {depth}",
            f"QUBITS: {len(indices)}",
        ])
        return "\n".join(lines)

    @staticmethod
    def _format_pathway(expr: Expr, ctx: FormatContext) -> str:
        indices = _resolve_qbit_indices(expr, ctx)
        if not indices:
            return "<pathway trace unavailable>"
        filtered = _filter_execution_trace(ctx.execution_trace, indices)
        lines = [
            "PATHWAY TRACE",
            "--------------------------------",
        ]
        if not filtered:
            lines.append("(no gates recorded)")
            return "\n".join(lines)
        for step, entry in enumerate(filtered, start=1):
            lines.append(f"Step {step}: {entry.display}")
            if entry.children:
                for child in entry.children:
                    lines.append(f"  \u2514 {child.display}")
        lines.extend([
            "",
            f"TOTAL STEPS: {len(filtered)}",
            f"QUBITS: {len(indices)}",
        ])
        return "\n".join(lines)


def format_quantum(expr: Expr, ctx: FormatContext, specifier: Optional[str] = None) -> str:
    """Format a quantum register expression (delegates to QuantumFormatter)."""
    return QuantumFormatter.format(expr, ctx, specifier)


def _classical_register_value(name: str, ctx: FormatContext) -> str:
    size = ctx.reg_sizes.get(name, 1)
    bits = [ctx.classical_map.get((name, i), 0) for i in range(size)]
    if ctx.reg_kind.get(name) == "bint":
        value = sum(b << i for i, b in enumerate(bits))
        return str(value)
    return str(bits)


def object_to_string(expr: Expr, ctx: FormatContext, specifier: Optional[str] = None) -> str:
    """
    Python str(obj) equivalent for Quanta expressions.
    Used by Print(obj) and f-string interpolation.
    """
    if isinstance(expr, FStringExpr):
        return format_fstring(expr, ctx)

    if isinstance(expr, LiteralExpr):
        return str(expr.value)

    if isinstance(expr, VarExpr):
        if expr.name in ctx.reg_kind:
            kind = ctx.reg_kind[expr.name]
            if kind in ("bit", "bint"):
                return _classical_register_value(expr.name, ctx)
            return QuantumFormatter.format(expr, ctx, specifier)
        value = ctx.eval_ctx.get(expr.name)
        return str(value) if value is not None else ""

    if isinstance(expr, IndexExpr) and isinstance(expr.base, VarExpr):
        idx = ctx.eval_expr(expr.index, ctx.eval_ctx)
        if isinstance(idx, int):
            key = (expr.base.name, idx)
            if key in ctx.classical_map:
                return str(ctx.classical_map[key])
            if key in ctx.qbit_map:
                return QuantumFormatter.format(expr, ctx, specifier)
        return ""

    value = ctx.eval_expr(expr, ctx.eval_ctx)
    return str(value) if value is not None else ""


def format_fstring(fstring: FStringExpr, ctx: FormatContext) -> str:
    """Evaluate an f-string using the same conversion path as Print(obj)."""
    parts: List[str] = []
    for part in fstring.parts:
        if part.literal is not None:
            parts.append(part.literal)
        elif part.expr is not None:
            parts.append(object_to_string(part.expr, ctx, part.specifier))
    return "".join(parts)


def format_print_argument(expr: Expr, ctx: FormatContext) -> str:
    """Format any Print() argument (object or f-string)."""
    return object_to_string(expr, ctx)
