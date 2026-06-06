"""
Quantum arithmetic gate sequences for frontend simulation and QASM lowering.

Uses the CDKM ripple-carry adder (Cuccaro et al., quant-ph/0410184) with a single
ancilla qubit per in-place addition.
"""

from __future__ import annotations

from typing import Callable, List, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from qiskit import QuantumCircuit

QUANTUM_ARITHMETIC_OPS = frozenset(
    {
        "QAdd", "QSub", "QMult", "QDiv", "QMod",
        "QFTAdd", "QTreeAdd", "QExpEncMult", "QTreeMult",
    }
)


def apply_maj(circuit: "QuantumCircuit", a: int, b: int, c: int) -> None:
    circuit.cx(a, b)
    circuit.cx(a, c)
    circuit.ccx(c, b, a)


def apply_uma(circuit: "QuantumCircuit", a: int, b: int, c: int) -> None:
    circuit.ccx(c, b, a)
    circuit.cx(a, c)
    circuit.cx(c, b)


def apply_cdkm_inplace_add(
    circuit: "QuantumCircuit",
    a_qubits: List[int],
    b_qubits: List[int],
    anc_qubit: int,
) -> None:
    """In-place add: |a⟩|b⟩ → |a⟩|a+b mod 2^n⟩ using one ancilla (must start in |0⟩)."""
    n = len(a_qubits)
    if n == 0:
        return
    if n != len(b_qubits):
        raise ValueError("QAdd: register widths must match")
    apply_maj(circuit, a_qubits[0], b_qubits[0], anc_qubit)
    for i in range(n - 1):
        apply_maj(circuit, a_qubits[i + 1], b_qubits[i + 1], a_qubits[i])
    for i in reversed(range(n - 1)):
        apply_uma(circuit, a_qubits[i + 1], b_qubits[i + 1], a_qubits[i])
    apply_uma(circuit, a_qubits[0], b_qubits[0], anc_qubit)


def apply_draper_inplace_add(
    circuit: "QuantumCircuit",
    a_qubits: List[int],
    b_qubits: List[int],
) -> None:
    """In-place QFT add: |a⟩|b⟩ → |a⟩|a+b mod 2^n⟩ (Draper adder, no ancilla)."""
    from qiskit.circuit.library import DraperQFTAdder

    n = len(a_qubits)
    if n == 0 or n != len(b_qubits):
        return
    adder = DraperQFTAdder(n)
    circuit.append(adder, a_qubits + b_qubits)


def apply_qftadd(
    circuit: "QuantumCircuit",
    operand_qubits: List[List[int]],
) -> None:
    """
    Variadic QFTAdd via Draper adder.

    QFTAdd(a, b) — in-place into b.
    QFTAdd(a, b, c) — c = a + b (dest starts at |0⟩, operands preserved).
    """
    if len(operand_qubits) < 2:
        return
    if len(operand_qubits) == 2:
        apply_draper_inplace_add(circuit, operand_qubits[0], operand_qubits[1])
        return
    dest = operand_qubits[-1]
    for src in operand_qubits[:-1]:
        apply_draper_inplace_add(circuit, src, dest)


def apply_qadd(
    circuit: "QuantumCircuit",
    operand_qubits: List[List[int]],
    anc_qubit: int,
) -> None:
    """
    Variadic QAdd: last register is destination (starts at |0⟩), earlier registers are inputs.

    QAdd(a, b) — in-place into b.
    QAdd(a, b, c) — c = a + b, preserving a and b.
    """
    if len(operand_qubits) < 2:
        return
    if len(operand_qubits) == 2:
        apply_cdkm_inplace_add(circuit, operand_qubits[0], operand_qubits[1], anc_qubit)
        return
    inputs = operand_qubits[:-1]
    dest = operand_qubits[-1]
    for src in inputs:
        apply_cdkm_inplace_add(circuit, src, dest, anc_qubit)


def apply_negate_mod(
    circuit: "QuantumCircuit",
    reg_qubits: List[int],
    one_qubits: List[int],
    anc_qubit: int,
) -> None:
    """In-place two's complement: |x⟩ → |-x mod 2^n⟩."""
    for q in reg_qubits:
        circuit.x(q)
    apply_cdkm_inplace_add(circuit, one_qubits, reg_qubits, anc_qubit)


def apply_inplace_sub(
    circuit: "QuantumCircuit",
    minuend: List[int],
    subtrahend: List[int],
    one_qubits: List[int],
    anc_qubit: int,
) -> None:
    """|a⟩|b⟩ → |a⟩|a-b mod 2^n⟩ (subtrahend overwritten)."""
    apply_negate_mod(circuit, subtrahend, one_qubits, anc_qubit)
    apply_cdkm_inplace_add(circuit, minuend, subtrahend, anc_qubit)


def _copy_register(circuit: "QuantumCircuit", src: List[int], dest: List[int]) -> None:
    for s, d in zip(src, dest):
        circuit.cx(s, d)


def _subtract_preserving_subtrahend(
    circuit: "QuantumCircuit",
    dest: List[int],
    subtrahend: List[int],
    temp: List[int],
    one_qubits: List[int],
    anc_qubit: int,
) -> None:
    """dest ← dest - subtrahend, preserving subtrahend."""
    _copy_register(circuit, subtrahend, temp)
    apply_negate_mod(circuit, temp, one_qubits, anc_qubit)
    apply_cdkm_inplace_add(circuit, temp, dest, anc_qubit)
    apply_negate_mod(circuit, temp, one_qubits, anc_qubit)
    _copy_register(circuit, subtrahend, temp)


def apply_qsub(
    circuit: "QuantumCircuit",
    operand_qubits: List[List[int]],
    temp_qubits: List[int],
    one_qubits: List[int],
    anc_qubit: int,
) -> None:
    """
    Variadic QSub: last register is destination.

    QSub(a, b) — in-place: b ← a - b.
    QSub(a, b, c) — c ← a - b, preserving a and b.
    QSub(a, b, d, r) — r ← a - b - d.
    """
    if len(operand_qubits) < 2:
        return
    if len(operand_qubits) == 2:
        apply_inplace_sub(circuit, operand_qubits[0], operand_qubits[1], one_qubits, anc_qubit)
        return

    inputs = operand_qubits[:-1]
    dest = operand_qubits[-1]
    _copy_register(circuit, inputs[0], dest)
    for sub in inputs[1:]:
        _subtract_preserving_subtrahend(circuit, dest, sub, temp_qubits, one_qubits, anc_qubit)


def _controlled_shift_copy(
    circuit: "QuantumCircuit",
    control: int,
    src: List[int],
    temp: List[int],
    shift: int,
) -> None:
    n = len(src)
    for j in range(n):
        src_idx = j - shift
        if src_idx >= 0:
            circuit.mcx([control, src[src_idx]], temp[j])


def _shift_add_multiply(
    circuit: "QuantumCircuit",
    multiplicand: List[int],
    multiplier: List[int],
    dest: List[int],
    temp: List[int],
    anc_qubit: int,
) -> None:
    """dest += multiplicand * multiplier (mod 2^n) via shift-and-add; dest accumulates."""
    n = min(len(multiplicand), len(multiplier), len(dest), len(temp))
    for i in range(n):
        _controlled_shift_copy(circuit, multiplier[i], multiplicand[:n], temp[:n], i)
        apply_controlled_cdkm_inplace_add(
            circuit, multiplier[i], temp[:n], dest[:n], anc_qubit
        )
        _controlled_shift_copy(circuit, multiplier[i], multiplicand[:n], temp[:n], i)


def apply_qmult(
    circuit: "QuantumCircuit",
    operand_qubits: List[List[int]],
    temp_qubits: List[int],
    one_qubits: List[int],
    anc_qubit: int,
) -> None:
    """
    Variadic QMult: last register is destination (starts at |0⟩), mod 2^n for equal widths.

    QMult(a, b, out) — out ← a * b mod 2^n.
    QMult(a, b, c, out) — out ← a * b * c mod 2^n.
    """
    if len(operand_qubits) < 3:
        return

    factors = operand_qubits[:-1]
    dest = operand_qubits[-1]
    n = len(dest)
    for factor in factors:
        if len(factor) != n:
            raise ValueError("QMult: equal-width operands required for simulation")

    _shift_add_multiply(circuit, factors[0], factors[1], dest, temp_qubits, anc_qubit)
    for factor in factors[2:]:
        _shift_add_multiply(circuit, dest, factor, dest, temp_qubits, anc_qubit)


def apply_controlled_cdkm_inplace_add(
    circuit: "QuantumCircuit",
    control: int,
    a_qubits: List[int],
    b_qubits: List[int],
    anc_qubit: int,
) -> None:
    """Controlled in-place add: if control=1, b ← a + b."""
    from qiskit.circuit.library import CDKMRippleCarryAdder

    n = len(a_qubits)
    if n == 0 or n != len(b_qubits):
        return
    adder = CDKMRippleCarryAdder(n, kind="fixed").control(1)
    circuit.append(adder, [control] + a_qubits + b_qubits + [anc_qubit])


class _GateEmitter(Protocol):
    def cx(self, control: str, target: str) -> None: ...
    def ccx(self, c1: str, c2: str, target: str) -> None: ...
    def mcx(self, controls: List[str], target: str) -> None: ...


def _emit_maj(emit: _GateEmitter, a: str, b: str, c: str) -> None:
    emit.cx(a, b)
    emit.cx(a, c)
    emit.ccx(c, b, a)


def _emit_uma(emit: _GateEmitter, a: str, b: str, c: str) -> None:
    emit.ccx(c, b, a)
    emit.cx(a, c)
    emit.cx(c, b)


def emit_cdkm_inplace_add_lines(
    a_bits: List[str],
    b_bits: List[str],
    anc_bit: str,
    emit_cx: Callable[[str, str], None],
    emit_ccx: Callable[[str, str, str], None],
) -> List[str]:
    """Return OpenQASM gate lines for an in-place CDKM add."""
    n = len(a_bits)
    if n == 0:
        return []
    lines: List[str] = []

    def cx(c: str, t: str) -> None:
        lines.append(f"cx {c}, {t};")

    def ccx(c1: str, c2: str, t: str) -> None:
        lines.append(f"ccx {c1}, {c2}, {t};")

    class _LineEmitter:
        def cx(self, control: str, target: str) -> None:
            cx(control, target)

        def ccx(self, c1: str, c2: str, target: str) -> None:
            ccx(c1, c2, target)

    le = _LineEmitter()
    _emit_maj(le, a_bits[0], b_bits[0], anc_bit)
    for i in range(n - 1):
        _emit_maj(le, a_bits[i + 1], b_bits[i + 1], a_bits[i])
    for i in reversed(range(n - 1)):
        _emit_uma(le, a_bits[i + 1], b_bits[i + 1], a_bits[i])
    _emit_uma(le, a_bits[0], b_bits[0], anc_bit)
    return lines


def _emit_decomposed_circuit_lines(
    qc: "QuantumCircuit",
    name_map: dict[int, str],
    emit_line: Callable[[str], None],
) -> None:
    """Emit OpenQASM lines from a decomposed/transpiled Qiskit circuit."""
    import math

    for inst in qc.data:
        qubits = [name_map[qc.find_bit(q).index] for q in inst.qubits]
        op = inst.operation.name
        params = inst.operation.params
        if op == "cx" and len(qubits) == 2:
            emit_line(f"cx {qubits[0]}, {qubits[1]};")
        elif op == "h" and len(qubits) == 1:
            emit_line(f"h {qubits[0]};")
        elif op == "rz" and len(qubits) == 1 and params:
            angle = float(params[0])
            if abs(angle) < 1e-12:
                continue
            if abs(angle - math.pi) < 1e-10:
                emit_line(f"rz(pi) {qubits[0]};")
            elif abs(angle + math.pi) < 1e-10:
                emit_line(f"rz(-pi) {qubits[0]};")
            else:
                emit_line(f"rz({angle}) {qubits[0]};")
        elif op == "x" and len(qubits) == 1:
            emit_line(f"x {qubits[0]};")
        elif op == "swap" and len(qubits) == 2:
            emit_line(f"swap {qubits[0]}, {qubits[1]};")
        elif op == "ccx" and len(qubits) == 3:
            emit_line(f"ccx {qubits[0]}, {qubits[1]}, {qubits[2]};")
        elif op == "z" and len(qubits) == 1:
            emit_line(f"z {qubits[0]};")
        elif op in ("mcx", "mcx_vchain", "mcx_recursive") and len(qubits) >= 2:
            controls = ", ".join(qubits[:-1])
            emit_line(f"mcx [{controls}], {qubits[-1]};")


def apply_grover_oracle(
    circuit: "QuantumCircuit", qubits: List[int], target: int
) -> None:
    """Phase-flip oracle marking computational basis state |target⟩."""
    n = len(qubits)
    if n == 0:
        return
    for i in range(n):
        if not ((target >> i) & 1):
            circuit.x(qubits[i])
    if n == 1:
        circuit.z(qubits[0])
    else:
        circuit.h(qubits[-1])
        circuit.mcx(qubits[:-1], qubits[-1])
        circuit.h(qubits[-1])
    for i in range(n):
        if not ((target >> i) & 1):
            circuit.x(qubits[i])


def apply_grover_diffusion(circuit: "QuantumCircuit", qubits: List[int]) -> None:
    """Grover diffusion operator (reflection about uniform superposition)."""
    if not qubits:
        return
    for q in qubits:
        circuit.h(q)
    for q in qubits:
        circuit.x(q)
    if len(qubits) == 1:
        circuit.z(qubits[0])
    else:
        circuit.h(qubits[-1])
        circuit.mcx(qubits[:-1], qubits[-1])
        circuit.h(qubits[-1])
    for q in qubits:
        circuit.x(q)
    for q in qubits:
        circuit.h(q)


def apply_grover(
    circuit: "QuantumCircuit", qubits: List[int], target: int
) -> None:
    """One Grover iteration: oracle + diffusion."""
    apply_grover_oracle(circuit, qubits, target)
    apply_grover_diffusion(circuit, qubits)


def emit_grover_lines(
    reg_bits: List[str],
    target: int,
    emit_line: Callable[[str], None],
) -> None:
    """Emit OpenQASM for one Grover iteration."""
    from qiskit import QuantumCircuit, transpile

    n = len(reg_bits)
    if n == 0:
        return
    qc = QuantumCircuit(n)
    apply_grover(qc, list(range(n)), target)
    qc = transpile(
        qc,
        basis_gates=["cx", "h", "x", "z", "ccx"],
        optimization_level=0,
    )
    name_map = {i: reg_bits[i] for i in range(n)}
    _emit_decomposed_circuit_lines(qc, name_map, emit_line)


def _append_library_lines(
    operation,
    qubit_groups: List[List[str]],
    emit_line: Callable[[str], None],
    basis: tuple[str, ...] = ("cx", "h", "rz", "x", "ccx", "swap"),
) -> None:
    """Decompose a Qiskit library operation into OpenQASM lines."""
    from qiskit import QuantumCircuit, transpile

    total = sum(len(group) for group in qubit_groups)
    qc = QuantumCircuit(total)
    flat: List[int] = []
    name_map: dict[int, str] = {}
    idx = 0
    for group in qubit_groups:
        for name in group:
            name_map[idx] = name
            flat.append(idx)
            idx += 1
    qc.append(operation, flat)
    qc = transpile(qc, basis_gates=list(basis), optimization_level=0)
    _emit_decomposed_circuit_lines(qc, name_map, emit_line)


def _read_register_value(circuit: "QuantumCircuit", qubits: List[int]) -> int:
    from qiskit.quantum_info import Statevector

    sv = Statevector(circuit)
    return sum(
        (1 << i for i, q in enumerate(qubits) if sv.probabilities([q])[1] > 0.5)
    )


def _write_register_value(circuit: "QuantumCircuit", qubits: List[int], value: int) -> None:
    current = _read_register_value(circuit, qubits)
    diff = current ^ value
    for i, q in enumerate(qubits):
        if (diff >> i) & 1:
            circuit.x(q)


def apply_vbe_inplace_add(
    circuit: "QuantumCircuit",
    a_qubits: List[int],
    b_qubits: List[int],
    helper_qubits: List[int],
) -> None:
    """In-place add via VBE ripple-carry adder (tree-style parallel carry)."""
    from qiskit.circuit.library import VBERippleCarryAdder

    n = len(a_qubits)
    if n == 0 or n != len(b_qubits):
        return
    adder = VBERippleCarryAdder(n, kind="fixed")
    helper_count = adder.num_qubits - 2 * n
    if len(helper_qubits) < helper_count:
        return
    circuit.append(adder, a_qubits + b_qubits + helper_qubits[:helper_count])


def apply_qtreeadd(
    circuit: "QuantumCircuit",
    operand_qubits: List[List[int]],
    helper_qubits: List[int],
) -> None:
    """Variadic QTreeAdd via VBE adder."""
    if len(operand_qubits) < 2:
        return
    if len(operand_qubits) == 2:
        apply_vbe_inplace_add(
            circuit, operand_qubits[0], operand_qubits[1], helper_qubits
        )
        return
    dest = operand_qubits[-1]
    for src in operand_qubits[:-1]:
        apply_vbe_inplace_add(circuit, src, dest, helper_qubits)


def apply_rgqf_multiply(
    circuit: "QuantumCircuit",
    a_qubits: List[int],
    b_qubits: List[int],
    out_qubits: List[int],
) -> None:
    """Multiply a * b into out (out must start in |0...0>)."""
    from qiskit.circuit.library import RGQFTMultiplier

    n = len(a_qubits)
    if n == 0 or n != len(b_qubits) or len(out_qubits) < 2 * n:
        return
    mult = RGQFTMultiplier(n)
    circuit.append(mult, a_qubits + b_qubits + out_qubits[: 2 * n])


def apply_hrs_multiply(
    circuit: "QuantumCircuit",
    a_qubits: List[int],
    b_qubits: List[int],
    out_qubits: List[int],
    helper_qubit: int,
) -> None:
    """Multiply a * b into out via HRS tree multiplier."""
    from qiskit.circuit.library import HRSCumulativeMultiplier

    n = len(a_qubits)
    if n == 0 or n != len(b_qubits) or len(out_qubits) < 2 * n:
        return
    mult = HRSCumulativeMultiplier(n)
    circuit.append(mult, a_qubits + b_qubits + out_qubits[: 2 * n] + [helper_qubit])


def _zero_register(circuit: "QuantumCircuit", qubits: List[int]) -> None:
    _write_register_value(circuit, qubits, 0)


def _multiply_mod_into_dest(
    circuit: "QuantumCircuit",
    a_qubits: List[int],
    b_qubits: List[int],
    dest_qubits: List[int],
    product_qubits: List[int],
    helper_qubit: int | None,
    use_hrs: bool,
) -> None:
    n = len(dest_qubits)
    _zero_register(circuit, product_qubits[: 2 * n])
    if use_hrs:
        apply_hrs_multiply(
            circuit, a_qubits, b_qubits, product_qubits, helper_qubit or product_qubits[0]
        )
    else:
        apply_rgqf_multiply(circuit, a_qubits, b_qubits, product_qubits)
    _write_register_value(circuit, dest_qubits, 0)
    for i in range(n):
        circuit.cx(product_qubits[i], dest_qubits[i])


def apply_qexpencmult(
    circuit: "QuantumCircuit",
    operand_qubits: List[List[int]],
    product_qubits: List[int],
) -> None:
    """Variadic QExpEncMult (RGQFT multiplier, mod 2^n into dest)."""
    if len(operand_qubits) < 3:
        return
    factors = operand_qubits[:-1]
    dest = operand_qubits[-1]
    n = len(dest)
    _multiply_mod_into_dest(
        circuit, factors[0], factors[1], dest, product_qubits, None, use_hrs=False
    )
    for factor in factors[2:]:
        _multiply_mod_into_dest(
            circuit, dest, factor, dest, product_qubits, None, use_hrs=False
        )


def apply_qtreemult(
    circuit: "QuantumCircuit",
    operand_qubits: List[List[int]],
    product_qubits: List[int],
    helper_qubit: int,
) -> None:
    """Variadic QTreeMult (HRS multiplier, mod 2^n into dest)."""
    if len(operand_qubits) < 3:
        return
    factors = operand_qubits[:-1]
    dest = operand_qubits[-1]
    _multiply_mod_into_dest(
        circuit, factors[0], factors[1], dest, product_qubits, helper_qubit, use_hrs=True
    )
    for factor in factors[2:]:
        _multiply_mod_into_dest(
            circuit, dest, factor, dest, product_qubits, helper_qubit, use_hrs=True
        )


def apply_qdiv(
    circuit: "QuantumCircuit",
    dividend: List[int],
    divisor: List[int],
    quotient: List[int],
    remainder: List[int],
    temp: List[int],
    one: List[int],
    anc: int,
) -> None:
    """QDiv via repeated subtraction (statevector-assisted for basis-state inputs)."""
    n = len(dividend)
    _copy_register(circuit, dividend, remainder)
    rem_val = _read_register_value(circuit, remainder)
    div_val = _read_register_value(circuit, divisor)
    if div_val == 0:
        return
    q_val, _ = divmod(rem_val, div_val)
    for _ in range(q_val):
        _subtract_preserving_subtrahend(circuit, remainder, divisor, temp, one, anc)
    _write_register_value(circuit, quotient, q_val)


def apply_qmod(
    circuit: "QuantumCircuit",
    operand_qubits: List[List[int]],
    temp: List[int],
    one: List[int],
    anc: int,
) -> None:
    """Variadic QMod via repeated subtraction (statevector-assisted)."""
    if len(operand_qubits) < 3:
        return
    inputs = operand_qubits[:-1]
    dest = operand_qubits[-1]
    _copy_register(circuit, inputs[0], dest)
    for divisor in inputs[1:]:
        while True:
            rem_val = _read_register_value(circuit, dest)
            div_val = _read_register_value(circuit, divisor)
            if div_val == 0 or rem_val < div_val:
                break
            _subtract_preserving_subtrahend(circuit, dest, divisor, temp, one, anc)


def emit_vbe_inplace_add_lines(
    a_bits: List[str],
    b_bits: List[str],
    helper_bits: List[str],
    emit_line: Callable[[str], None],
) -> None:
    from qiskit.circuit.library import VBERippleCarryAdder

    n = len(a_bits)
    if n == 0 or n != len(b_bits):
        return
    adder = VBERippleCarryAdder(n, kind="fixed")
    helper_count = adder.num_qubits - 2 * n
    if len(helper_bits) < helper_count:
        return
    _append_library_lines(
        adder, [a_bits, b_bits, helper_bits[:helper_count]], emit_line
    )


def emit_qtreeadd_lines(
    register_bits: List[List[str]],
    helper_bits: List[str],
    emit_line: Callable[[str], None],
) -> None:
    if len(register_bits) < 2:
        return
    if len(register_bits) == 2:
        emit_vbe_inplace_add_lines(
            register_bits[0], register_bits[1], helper_bits, emit_line
        )
        return
    dest = register_bits[-1]
    for src in register_bits[:-1]:
        emit_vbe_inplace_add_lines(src, dest, helper_bits, emit_line)


def emit_rgqf_multiply_lines(
    a_bits: List[str],
    b_bits: List[str],
    out_bits: List[str],
    emit_line: Callable[[str], None],
) -> None:
    from qiskit.circuit.library import RGQFTMultiplier

    n = len(a_bits)
    if n == 0 or len(out_bits) < 2 * n:
        return
    mult = RGQFTMultiplier(n)
    _append_library_lines(mult, [a_bits, b_bits, out_bits[: 2 * n]], emit_line)


def emit_hrs_multiply_lines(
    a_bits: List[str],
    b_bits: List[str],
    out_bits: List[str],
    helper_bit: str,
    emit_line: Callable[[str], None],
) -> None:
    from qiskit.circuit.library import HRSCumulativeMultiplier

    n = len(a_bits)
    if n == 0 or len(out_bits) < 2 * n:
        return
    mult = HRSCumulativeMultiplier(n)
    _append_library_lines(
        mult, [a_bits, b_bits, out_bits[: 2 * n], [helper_bit]], emit_line
    )


def _emit_multiply_mod_into_dest_lines(
    a_bits: List[str],
    b_bits: List[str],
    dest_bits: List[str],
    product_bits: List[str],
    helper_bit: str | None,
    use_hrs: bool,
    emit_line: Callable[[str], None],
) -> None:
    n = len(dest_bits)
    if use_hrs and helper_bit is not None:
        emit_hrs_multiply_lines(a_bits, b_bits, product_bits, helper_bit, emit_line)
    else:
        emit_rgqf_multiply_lines(a_bits, b_bits, product_bits, emit_line)
    for i in range(n):
        emit_line(f"cx {product_bits[i]}, {dest_bits[i]};")


def emit_qexpencmult_lines(
    register_bits: List[List[str]],
    product_bits: List[str],
    emit_line: Callable[[str], None],
) -> None:
    if len(register_bits) < 3:
        return
    factors = register_bits[:-1]
    dest = register_bits[-1]
    _emit_multiply_mod_into_dest_lines(
        factors[0], factors[1], dest, product_bits, None, False, emit_line
    )
    for factor in factors[2:]:
        _emit_multiply_mod_into_dest_lines(
            dest, factor, dest, product_bits, None, False, emit_line
        )


def emit_qtreemult_lines(
    register_bits: List[List[str]],
    product_bits: List[str],
    helper_bit: str,
    emit_line: Callable[[str], None],
) -> None:
    if len(register_bits) < 3:
        return
    factors = register_bits[:-1]
    dest = register_bits[-1]
    _emit_multiply_mod_into_dest_lines(
        factors[0], factors[1], dest, product_bits, helper_bit, True, emit_line
    )
    for factor in factors[2:]:
        _emit_multiply_mod_into_dest_lines(
            dest, factor, dest, product_bits, helper_bit, True, emit_line
        )


def _emit_preserving_subtract_lines(
    dest_bits: List[str],
    sub_bits: List[str],
    temp_bits: List[str],
    one_bits: List[str],
    anc_bit: str,
    emit_line: Callable[[str], None],
) -> None:
    cx = _cx_emit(emit_line)
    ccx = _ccx_emit(emit_line)
    emit_copy_lines(sub_bits, temp_bits, emit_line)
    emit_negate_mod_lines(temp_bits, one_bits, anc_bit, emit_line)
    for line in emit_cdkm_inplace_add_lines(temp_bits, dest_bits, anc_bit, cx, ccx):
        emit_line(line)
    emit_negate_mod_lines(temp_bits, one_bits, anc_bit, emit_line)
    emit_copy_lines(sub_bits, temp_bits, emit_line)


def emit_qdiv_lines(
    dividend_bits: List[str],
    divisor_bits: List[str],
    quotient_bits: List[str],
    remainder_bits: List[str],
    temp_bits: List[str],
    one_bits: List[str],
    anc_bit: str,
    emit_line: Callable[[str], None],
    *,
    dividend_value: int | None = None,
    divisor_value: int | None = None,
) -> None:
    """Emit QDiv via repeated subtraction (expanded when literal operands are known)."""
    emit_line(f"// QDiv repeated subtraction ({len(dividend_bits)} bits)")
    emit_copy_lines(dividend_bits, remainder_bits, emit_line)
    if divisor_value in (None, 0) or dividend_value is None:
        emit_line("// QDiv gate expansion requires non-zero literal divisor and dividend")
        return
    q_val, _ = divmod(dividend_value, divisor_value)
    for _ in range(q_val):
        _emit_preserving_subtract_lines(
            remainder_bits, divisor_bits, temp_bits, one_bits, anc_bit, emit_line
        )
    for i, bit in enumerate(quotient_bits):
        if (q_val >> i) & 1:
            emit_line(f"x {bit};")


def emit_qmod_lines(
    register_bits: List[List[str]],
    temp_bits: List[str],
    one_bits: List[str],
    anc_bit: str,
    emit_line: Callable[[str], None],
    *,
    init_values: dict[str, int] | None = None,
) -> None:
    if len(register_bits) < 3:
        return
    emit_line(f"// QMod repeated subtraction ({len(register_bits[0])} bits)")
    inputs = register_bits[:-1]
    dest_bits = register_bits[-1]
    emit_copy_lines(inputs[0], dest_bits, emit_line)
    if not init_values:
        emit_line("// QMod gate expansion requires literal register initializers")
        return

    def reg_name(bits: List[str]) -> str:
        return bits[0].split("[")[0]

    value = init_values.get(reg_name(inputs[0]), 0)
    for divisor_bits in inputs[1:]:
        divisor = init_values.get(reg_name(divisor_bits), 0)
        if divisor == 0:
            continue
        while value >= divisor:
            _emit_preserving_subtract_lines(
                dest_bits, divisor_bits, temp_bits, one_bits, anc_bit, emit_line
            )
            value -= divisor


def emit_draper_inplace_add_lines(
    a_bits: List[str],
    b_bits: List[str],
    emit_line: Callable[[str], None],
) -> None:
    """Emit OpenQASM for one in-place Draper QFT add."""
    from qiskit import QuantumCircuit, transpile
    from qiskit.circuit.library import DraperQFTAdder

    n = len(a_bits)
    if n == 0 or n != len(b_bits):
        return
    adder = DraperQFTAdder(n)
    qc = QuantumCircuit(n * 2)
    qc.append(adder, list(range(n * 2)))
    qc = transpile(qc, basis_gates=["cx", "h", "rz"], optimization_level=0)
    name_map = {i: a_bits[i] for i in range(n)}
    name_map.update({n + i: b_bits[i] for i in range(n)})
    _emit_decomposed_circuit_lines(qc, name_map, emit_line)


def emit_qftadd_lines(
    register_bits: List[List[str]],
    emit_line: Callable[[str], None],
) -> None:
    """Emit OpenQASM for variadic QFTAdd."""
    if len(register_bits) < 2:
        return
    if len(register_bits) == 2:
        emit_draper_inplace_add_lines(
            register_bits[0], register_bits[1], emit_line
        )
        return
    dest = register_bits[-1]
    for src in register_bits[:-1]:
        emit_draper_inplace_add_lines(src, dest, emit_line)


def emit_qadd_lines(
    register_bits: List[List[str]],
    anc_bit: str,
    emit_line: Callable[[str], None],
) -> None:
    """Emit OpenQASM for variadic QAdd."""
    if len(register_bits) < 2:
        return

    def emit_cx(c: str, t: str) -> None:
        emit_line(f"cx {c}, {t};")

    def emit_ccx(c1: str, c2: str, t: str) -> None:
        emit_line(f"ccx {c1}, {c2}, {t};")

    if len(register_bits) == 2:
        for line in emit_cdkm_inplace_add_lines(
            register_bits[0], register_bits[1], anc_bit, emit_cx, emit_ccx
        ):
            emit_line(line)
        return

    dest = register_bits[-1]
    for src in register_bits[:-1]:
        for line in emit_cdkm_inplace_add_lines(src, dest, anc_bit, emit_cx, emit_ccx):
            emit_line(line)


def emit_negate_mod_lines(
    reg_bits: List[str],
    one_bits: List[str],
    anc_bit: str,
    emit_line: Callable[[str], None],
) -> None:
    for bit in reg_bits:
        emit_line(f"x {bit};")
    for line in emit_cdkm_inplace_add_lines(one_bits, reg_bits, anc_bit, _cx_emit(emit_line), _ccx_emit(emit_line)):
        emit_line(line)


def _cx_emit(emit_line: Callable[[str], None]) -> Callable[[str, str], None]:
    return lambda c, t: emit_line(f"cx {c}, {t};")


def _ccx_emit(emit_line: Callable[[str], None]) -> Callable[[str, str, str], None]:
    return lambda c1, c2, t: emit_line(f"ccx {c1}, {c2}, {t};")


def emit_copy_lines(
    src_bits: List[str],
    dest_bits: List[str],
    emit_line: Callable[[str], None],
) -> None:
    for s, d in zip(src_bits, dest_bits):
        emit_line(f"cx {s}, {d};")


def emit_qsub_lines(
    register_bits: List[List[str]],
    temp_bits: List[str],
    one_bits: List[str],
    anc_bit: str,
    emit_line: Callable[[str], None],
) -> None:
    """Emit OpenQASM for variadic QSub."""
    if len(register_bits) < 2:
        return

    cx = _cx_emit(emit_line)
    ccx = _ccx_emit(emit_line)

    if len(register_bits) == 2:
        emit_line(f"// QSub in-place via two's complement + CDKM add")
        a_bits, b_bits = register_bits
        for bit in b_bits:
            emit_line(f"x {bit};")
        for line in emit_cdkm_inplace_add_lines(one_bits, b_bits, anc_bit, cx, ccx):
            emit_line(line)
        for line in emit_cdkm_inplace_add_lines(a_bits, b_bits, anc_bit, cx, ccx):
            emit_line(line)
        return

    inputs = register_bits[:-1]
    dest_bits = register_bits[-1]
    emit_copy_lines(inputs[0], dest_bits, emit_line)
    for sub_bits in inputs[1:]:
        emit_copy_lines(sub_bits, temp_bits, emit_line)
        emit_negate_mod_lines(temp_bits, one_bits, anc_bit, emit_line)
        for line in emit_cdkm_inplace_add_lines(temp_bits, dest_bits, anc_bit, cx, ccx):
            emit_line(line)
        emit_negate_mod_lines(temp_bits, one_bits, anc_bit, emit_line)
        emit_copy_lines(sub_bits, temp_bits, emit_line)


def emit_controlled_cdkm_add_lines(
    control_bit: str,
    a_bits: List[str],
    b_bits: List[str],
    anc_bit: str,
    emit_line: Callable[[str], None],
) -> None:
    """Emit controlled CDKM add by decomposing Qiskit's controlled adder."""
    from qiskit import QuantumCircuit
    from qiskit.circuit.library import CDKMRippleCarryAdder

    n = len(a_bits)
    if n == 0:
        return
    adder = CDKMRippleCarryAdder(n, kind="fixed").control(1)
    total = 1 + n * 2 + 1
    qc = QuantumCircuit(total)
    qc.append(adder, list(range(total)))
    name_map = {0: control_bit}
    idx = 1
    for bit in a_bits:
        name_map[idx] = bit
        idx += 1
    for bit in b_bits:
        name_map[idx] = bit
        idx += 1
    name_map[idx] = anc_bit
    for inst in qc.decompose(reps=4).data:
        qubits = [name_map[qc.find_bit(q).index] for q in inst.qubits]
        op = inst.operation.name
        if op == "cx" and len(qubits) == 2:
            emit_line(f"cx {qubits[0]}, {qubits[1]};")
        elif op == "ccx" and len(qubits) == 3:
            emit_line(f"ccx {qubits[0]}, {qubits[1]}, {qubits[2]};")
        elif op in ("mcx", "mcx_vchain") and len(qubits) >= 2:
            controls = ", ".join(qubits[:-1])
            emit_line(f"mcx [{controls}], {qubits[-1]};")


def emit_qmult_lines(
    register_bits: List[List[str]],
    temp_bits: List[str],
    one_bits: List[str],
    anc_bit: str,
    emit_line: Callable[[str], None],
) -> None:
    """Emit OpenQASM for QMult (shift-and-add, mod 2^n)."""
    if len(register_bits) < 3:
        return
    factors = register_bits[:-1]
    dest_bits = register_bits[-1]
    n = min(len(dest_bits), len(temp_bits))

    for factor_bits in factors:
        fn = min(len(factor_bits), n)
        for i in range(fn):
            emit_line(f"// QMult shift-add bit {i}")
            for j in range(fn):
                src_idx = j - i
                if src_idx >= 0 and j < len(temp_bits):
                    emit_line(
                        f"mcx [{factor_bits[i]}, {factor_bits[src_idx]}], {temp_bits[j]};"
                    )
            emit_controlled_cdkm_add_lines(
                factor_bits[i], temp_bits[:fn], dest_bits[:fn], anc_bit, emit_line
            )
            for j in range(fn):
                src_idx = j - i
                if src_idx >= 0 and j < len(temp_bits):
                    emit_line(
                        f"mcx [{factor_bits[i]}, {factor_bits[src_idx]}], {temp_bits[j]};"
                    )
