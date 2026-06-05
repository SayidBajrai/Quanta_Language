"""
Frontend runtime interpreter for Quanta.

Simulates Quanta source with statevector, captures Print() output.
**Frontend Debug Execution Only. Not compatible with hardware backend.**

Real quantum hardware cannot reveal amplitudes; this is statevector simulation only.
"""

from __future__ import annotations

import math
from typing import Dict, List, Any, Optional, Tuple
from fractions import Fraction

try:
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector
    QISKIT_AVAILABLE = True
except ImportError:
    QISKIT_AVAILABLE = False

from ..ast.nodes import (
    Program, Stmt, Expr,
    VarDecl, ConstDecl, LetDecl, QuantumDecl, FuncDecl, GateDecl, ClassDecl,
    ForStmt, IfStmt, ReturnStmt, ExprStmt,
    CallExpr, IndexExpr, BinaryExpr, UnaryExpr,
    VarExpr, LiteralExpr, ListExpr, GroupExpr, AssignExpr,
)
from ..errors import QuantaError

# Max qubits for statevector simulation (2^n memory)
SIMULATION_QUBIT_LIMIT = 20


def _rationalize_amplitude(amp: complex, tol: float = 1e-9) -> Optional[Tuple[float, Optional[int], str]]:
    """
    Try to express amplitude as rational/sqrt form.
    Returns (magnitude, sqrt_denom or None, phase_str) or None if not recognizable.
    """
    if abs(amp) < tol:
        return None
    phase = math.atan2(amp.imag, amp.real)
    mag = abs(amp)
    # Check for 1/sqrt(2)
    inv_sqrt2 = 1.0 / math.sqrt(2)
    if abs(mag - inv_sqrt2) < tol:
        phase_str = ""
        if abs(phase - 0) < tol:
            pass
        elif abs(phase - math.pi) < tol:
            phase_str = "-"
        elif abs(phase - math.pi/2) < tol:
            phase_str = "i"
        elif abs(phase + math.pi/2) < tol:
            phase_str = "-i"
        else:
            phase_str = f"e^(i{phase:.2g})"
        return (mag, 2, phase_str)
    # Check for 1/2
    if abs(mag - 0.5) < tol:
        phase_str = "-" if abs(phase - math.pi) < tol else ""
        return (mag, None, phase_str)
    if abs(mag - 1.0) < tol:
        phase_str = "-" if abs(phase - math.pi) < tol else ""
        return (mag, None, phase_str)
    return (mag, None, f"e^(i{phase:.2g})" if abs(phase) > tol else "")


def _format_ket(n: int, num_qubits: int) -> str:
    """Format basis state as |n⟩ in binary."""
    b = format(n, f"0{num_qubits}b")
    return "|" + b + ">"


def statevector_to_symbolic(statevector: "Statevector", num_qubits_show: Optional[int] = None) -> str:
    """
    Convert statevector to symbolic form like 1/√2 * |0> + 1/√2 * |1>.
    statevector is the full state; num_qubits_show is only used for ket width when showing full state.
    """
    if not QISKIT_AVAILABLE:
        return "<statevector (qiskit not available)>"
    sv = statevector
    dim = sv.dim
    num_qubits = num_qubits_show if num_qubits_show is not None else int(round(math.log2(dim)))
    if dim == 0:
        return "|0>"
    data = sv.data
    terms = []
    for n in range(dim):
        amp = data[n]
        if abs(amp) < 1e-9:
            continue
        r = _rationalize_amplitude(amp)
        if r is None:
            terms.append(f"({amp.real:.4g}+{amp.imag:.4g}i)*{_format_ket(n, num_qubits)}")
            continue
        mag, sqrt_denom, phase_str = r
        if sqrt_denom == 2:
            coeff = "1/sqrt(2)"
        elif sqrt_denom is not None:
            coeff = f"1/sqrt({sqrt_denom})"
        else:
            if abs(mag - 1.0) < 1e-9:
                coeff = "" if not phase_str else phase_str
            else:
                coeff = f"{mag:.4g}"
                if phase_str:
                    coeff = phase_str + coeff
        if coeff and not coeff.endswith("*"):
            coeff = coeff + " * "
        ket = _format_ket(n, num_qubits)
        terms.append(f"{coeff}{ket}")
    if not terms:
        return "0"
    return " + ".join(terms)


def _check_entangled(statevector: "Statevector", qubit_indices: List[int]) -> bool:
    """Check if the given qubits are entangled with the rest."""
    if statevector.num_qubits <= 1 or not qubit_indices:
        return False
    try:
        from qiskit.quantum_info import partial_trace
        other = [i for i in range(statevector.num_qubits) if i not in qubit_indices]
        if not other:
            return False
        rho = partial_trace(statevector, other)
        # Check purity: Tr(rho^2) < 1 means mixed (entangled)
        rho2 = rho @ rho
        purity = float(rho2.trace().real)
        return purity < 0.99
    except Exception:
        return False


def get_prints(quanta_code: str) -> str:
    """
    Parse Quanta source, run in statevector simulator, and return the string
    that would be printed by all Print() / print() calls.

    **Frontend Debug Execution Only. Not compatible with hardware backend.**
    Real quantum hardware cannot reveal amplitudes; this is statevector simulation only.

    - print(classical): immediate evaluation, append to output.
    - print(quantum): inspect statevector, append symbolic summary (no state collapse).

    Raises:
        RuntimeError: If total qubits > SIMULATION_QUBIT_LIMIT (default 20).
        QuantaError: On parse/semantic errors.
    """
    from ..lexer.lexer import Lexer
    from ..parser.parser import Parser
    from ..sema.transform import ASTTransformer
    from ..sema.validation import SemanticAnalyzer

    if not QISKIT_AVAILABLE:
        raise ImportError(
            "Qiskit is required for get_prints (statevector simulation). "
            "Install with: pip install qiskit"
        )

    lexer = Lexer()
    parser = Parser()
    transformer = ASTTransformer()
    sema = SemanticAnalyzer()

    tokens = lexer.tokenize(quanta_code)
    ast = parser.parse(tokens)
    ast = transformer.transform(ast)
    sema.analyze(ast)

    # Build qubit map and check limit
    qubit_map: Dict[Tuple[str, int], int] = {}  # (reg_name, index) -> global qubit index
    classical_map: Dict[Tuple[str, int], int] = {}  # (reg_name, index) -> value 0/1
    reg_sizes: Dict[str, int] = {}
    reg_kind: Dict[str, str] = {}  # "qubit" | "bit" | "qint" | "bint"
    global_qubit = 0
    for stmt in ast.statements:
        if isinstance(stmt, QuantumDecl):
            if stmt.kind == "qdec" and stmt.size is not None and stmt.size2 is not None:
                size = stmt.size + stmt.size2
            elif stmt.kind == "qfloat" and stmt.size is not None and stmt.size2 is not None:
                size = 1 + stmt.size + stmt.size2
            else:
                size = stmt.size or 1
            reg_sizes[stmt.name] = size
            reg_kind[stmt.name] = stmt.kind
            if stmt.kind in ("qubit", "qint", "qdec", "qfloat"):
                for i in range(size):
                    qubit_map[(stmt.name, i)] = global_qubit
                    global_qubit += 1
            elif stmt.kind in ("bit", "bint"):
                for i in range(size):
                    classical_map[(stmt.name, i)] = 0

    if global_qubit > SIMULATION_QUBIT_LIMIT:
        raise RuntimeError(
            f"Simulation qubit limit exceeded: {global_qubit} qubits "
            f"(max {SIMULATION_QUBIT_LIMIT}). Statevector uses 2^n memory."
        )

    circuit = QuantumCircuit(global_qubit)
    output_lines: List[str] = []
    gates = {stmt.name: stmt for stmt in ast.statements if isinstance(stmt, GateDecl)}
    constants_eval: Dict[str, Any] = {"pi": math.pi, "e": math.e}

    def eval_expr(expr: Expr, ctx: Dict[str, Any]) -> Any:
        if isinstance(expr, LiteralExpr):
            v = expr.value
            if isinstance(v, str) and v.isdigit():
                return int(v)
            if isinstance(v, str) and v.replace(".", "").replace("-", "").isdigit():
                return float(v)
            return v
        if isinstance(expr, VarExpr):
            return ctx.get(expr.name)
        if isinstance(expr, GroupExpr):
            return eval_expr(expr.expr, ctx)
        if isinstance(expr, BinaryExpr):
            l = eval_expr(expr.left, ctx)
            r = eval_expr(expr.right, ctx)
            if expr.op == "+": return l + r
            if expr.op == "-": return l - r
            if expr.op == "*": return l * r
            if expr.op == "/": return l / r
            if expr.op == "==": return l == r
            if expr.op == "!=": return l != r
            if expr.op == "<": return l < r
            if expr.op == ">": return l > r
            if expr.op == "<=": return l <= r
            if expr.op == ">=": return l >= r
            if expr.op == "&&": return l and r
            if expr.op == "||": return l or r
        if isinstance(expr, UnaryExpr):
            r = eval_expr(expr.right, ctx)
            if expr.op == "-": return -r
            if expr.op == "!": return not r
        if isinstance(expr, ListExpr):
            el = expr.elements
            if len(el) == 3:
                # Range [start:end] or [start:step:end]
                start = eval_expr(el[0], ctx)
                step = eval_expr(el[1], ctx)
                end = eval_expr(el[2], ctx)
                return list(range(int(start), int(end), int(step)))
            return [eval_expr(e, ctx) for e in el]
        if isinstance(expr, IndexExpr):
            base = eval_expr(expr.base, ctx)
            idx = eval_expr(expr.index, ctx)
            if isinstance(idx, int) and isinstance(base, str):
                if (base, idx) in classical_map:
                    return classical_map[(base, idx)]
                if (base, idx) in qubit_map:
                    return (base, idx)
            return None
        return None

    def apply_gate(name: str, args: List[Expr], ctx: Dict[str, Any]) -> None:
        name_lower = name.lower()
        qubits = []
        params = []
        for a in args:
            if isinstance(a, VarExpr) and reg_kind.get(a.name, "") in ("qubit", "qint", "qdec", "qfloat"):
                # Full register: all indices
                sz = reg_sizes.get(a.name, 1)
                qubits.extend([qubit_map[(a.name, i)] for i in range(sz)])
            elif isinstance(a, IndexExpr) and isinstance(a.base, VarExpr):
                idx = eval_expr(a.index, ctx)
                if isinstance(idx, int):
                    key = (a.base.name, idx)
                    if key in qubit_map:
                        qubits.append(qubit_map[key])
                    elif key in classical_map:
                        pass  # classical, skip
            elif isinstance(a, LiteralExpr):
                try:
                    params.append(float(a.value))
                except (ValueError, TypeError):
                    pass
        if name_lower in ("h", "x", "y", "z") and len(qubits) >= 1:
            for q in qubits:
                if name_lower == "h": circuit.h(q)
                elif name_lower == "x": circuit.x(q)
                elif name_lower == "y": circuit.y(q)
                elif name_lower == "z": circuit.z(q)
        elif name_lower in ("cx", "cnot") and len(qubits) == 2:
            circuit.cx(qubits[0], qubits[1])
        elif name_lower == "cz" and len(qubits) == 2:
            circuit.cz(qubits[0], qubits[1])
        elif name_lower == "swap" and len(qubits) == 2:
            circuit.swap(qubits[0], qubits[1])
        elif name_lower in ("rz", "ry", "rx") and len(params) >= 1 and len(qubits) >= 1:
            theta = params[0]
            for q in qubits:
                if name_lower == "rz": circuit.rz(theta, q)
                elif name_lower == "ry": circuit.ry(theta, q)
                elif name_lower == "rx": circuit.rx(theta, q)
        elif name in gates:
            gate_def = gates[name]
            param_bind = {gate_def.params[i]: args[i] for i in range(len(args))}
            for s in gate_def.body:
                if isinstance(s, ExprStmt) and isinstance(s.expr, CallExpr):
                    sub_callee = s.expr.callee
                    sub_args = [
                        param_bind.get(a.name, a) if isinstance(a, VarExpr) else a
                        for a in s.expr.args
                    ]
                    if isinstance(sub_callee, VarExpr):
                        apply_gate(sub_callee.name, sub_args, ctx)

    def run_statement(stmt: Stmt, ctx: Dict[str, Any]) -> None:
        if isinstance(stmt, QuantumDecl):
            size = stmt.size or 1
            if stmt.kind in ("qubit", "qint") and stmt.value:
                if isinstance(stmt.value, LiteralExpr):
                    try:
                        val = int(stmt.value.value)
                        for i in range(size):
                            if (val >> i) & 1:
                                circuit.x(qubit_map[(stmt.name, i)])
                    except (ValueError, TypeError):
                        pass
        elif isinstance(stmt, VarDecl) and stmt.value:
            v = eval_expr(stmt.value, ctx)
            if v is not None:
                ctx[stmt.name] = v
        elif isinstance(stmt, ConstDecl):
            v = eval_expr(stmt.value, ctx)
            if v is not None:
                ctx[stmt.name] = v
                constants_eval[stmt.name] = v
        elif isinstance(stmt, LetDecl):
            v = eval_expr(stmt.value, ctx)
            if v is not None:
                ctx[stmt.name] = v
        elif isinstance(stmt, ExprStmt):
            expr = stmt.expr
            if isinstance(expr, CallExpr) and isinstance(expr.callee, VarExpr):
                name = expr.callee.name
                if name in ("Print", "print"):
                    if not expr.args:
                        output_lines.append("")
                        return
                    arg = expr.args[0]
                    if isinstance(arg, VarExpr):
                        if arg.name in reg_kind:
                            kind = reg_kind[arg.name]
                            if kind in ("bit", "bint"):
                                size = reg_sizes.get(arg.name, 1)
                                vals = [classical_map.get((arg.name, i), 0) for i in range(size)]
                                output_lines.append(str(vals))
                            else:
                                indices = [qubit_map[(arg.name, i)] for i in range(reg_sizes.get(arg.name, 1))]
                                sv = Statevector(circuit)
                                if _check_entangled(sv, indices) and len(indices) < sv.num_qubits:
                                    full = statevector_to_symbolic(sv, num_qubits_show=sv.num_qubits)
                                    output_lines.append(f"Subsystem entangled. |q,q2> = {full}")
                                else:
                                    if len(indices) < sv.num_qubits:
                                        from qiskit.quantum_info import partial_trace, purity
                                        other = [i for i in range(sv.num_qubits) if i not in indices]
                                        rho = partial_trace(sv, other)
                                        p = purity(rho)
                                        if p > 0.99:
                                            import numpy as np
                                            evals, evecs = np.linalg.eigh(rho.data)
                                            idx_max = np.argmax(evals)
                                            reduced_sv = Statevector(evecs[:, idx_max])
                                            output_lines.append(statevector_to_symbolic(reduced_sv, len(indices)))
                                        else:
                                            output_lines.append(
                                                "Subsystem entangled. " + statevector_to_symbolic(sv, sv.num_qubits)
                                            )
                                    else:
                                        output_lines.append(statevector_to_symbolic(sv, sv.num_qubits))
                        else:
                            output_lines.append(str(ctx.get(arg.name, "")))
                        return
                    if isinstance(arg, IndexExpr) and isinstance(arg.base, VarExpr):
                        idx = eval_expr(arg.index, ctx)
                        if isinstance(idx, int):
                            key = (arg.base.name, idx)
                            if key in classical_map:
                                output_lines.append(str(classical_map[key]))
                                return
                            if key in qubit_map:
                                sv = Statevector(circuit)
                                one_idx = [qubit_map[key]]
                                if _check_entangled(sv, one_idx):
                                    full = statevector_to_symbolic(sv, sv.num_qubits)
                                    output_lines.append(f"Subsystem entangled. Full state: {full}")
                                else:
                                    from qiskit.quantum_info import partial_trace, purity
                                    other = [i for i in range(sv.num_qubits) if i not in one_idx]
                                    rho = partial_trace(sv, other)
                                    if purity(rho) > 0.99:
                                        import numpy as np
                                        evals, evecs = np.linalg.eigh(rho.data)
                                        idx_max = np.argmax(evals)
                                        reduced_sv = Statevector(evecs[:, idx_max])
                                        output_lines.append(statevector_to_symbolic(reduced_sv, 1))
                                    else:
                                        output_lines.append(statevector_to_symbolic(sv, sv.num_qubits))
                                return
                    v = eval_expr(arg, ctx)
                    output_lines.append(str(v))
                    return
                if name == "Measure" and len(expr.args) == 2:
                    # Measure qubit(s) -> classical bit(s): single Measure(q[i], c[i]) or full register Measure(q, c)
                    qarg, carg = expr.args[0], expr.args[1]
                    if isinstance(qarg, VarExpr) and isinstance(carg, VarExpr):
                        q_name, c_name = qarg.name, carg.name
                        q_sz = reg_sizes.get(q_name, 0)
                        c_sz = reg_sizes.get(c_name, 0)
                        for i in range(min(q_sz, c_sz)):
                            qkey = (q_name, i)
                            ckey = (c_name, i)
                            if qkey in qubit_map and ckey in classical_map:
                                sv = Statevector(circuit)
                                qidx = qubit_map[qkey]
                                probs = sv.probabilities([qidx])
                                import random
                                r = random.random()
                                outcome = 1 if r < probs[1] else 0
                                classical_map[ckey] = outcome
                        return
                    qkey = ckey = None
                    if isinstance(qarg, IndexExpr) and isinstance(qarg.base, VarExpr):
                        qi = eval_expr(qarg.index, ctx)
                        if isinstance(qi, int):
                            qkey = (qarg.base.name, qi)
                    if isinstance(carg, IndexExpr) and isinstance(carg.base, VarExpr):
                        ci = eval_expr(carg.index, ctx)
                        if isinstance(ci, int):
                            ckey = (carg.base.name, ci)
                    if qkey is not None and ckey is not None and qkey in qubit_map and ckey in classical_map:
                        sv = Statevector(circuit)
                        qidx = qubit_map[qkey]
                        probs = sv.probabilities([qidx])
                        import random
                        r = random.random()
                        outcome = 1 if r < probs[1] else 0
                        classical_map[ckey] = outcome
                        return
                if name in ("H", "X", "Y", "Z", "CNot", "CNOT", "CZ", "Swap", "SWAP", "RZ", "RY", "RX"):
                    apply_gate(name, expr.args, ctx)
                elif name in gates:
                    apply_gate(name, expr.args, ctx)
        elif isinstance(stmt, ForStmt):
            it = eval_expr(stmt.iterable, ctx)
            if isinstance(it, list):
                for val in it:
                    ctx[stmt.iterator] = val
                    for s in stmt.body:
                        run_statement(s, ctx)
        elif isinstance(stmt, IfStmt):
            cond = eval_expr(stmt.condition, ctx)
            if cond:
                for s in stmt.then_body:
                    run_statement(s, ctx)
            else:
                for s in stmt.else_body:
                    run_statement(s, ctx)

    ctx: Dict[str, Any] = dict(constants_eval)
    for stmt in ast.statements:
        if isinstance(stmt, (FuncDecl, GateDecl, ClassDecl)):
            continue
        run_statement(stmt, ctx)

    return "\n".join(output_lines)
