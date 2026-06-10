"""
Quantum circuit optimization passes.

Passes modify a QCircuit in-place to reduce gate count and circuit depth.
"""

from typing import List, Tuple
from collections import defaultdict
from .ir_nodes import QCircuit, QGate


def fuse_adjacent_gates(circuit: QCircuit) -> int:
    removed = 0
    i = 0
    while i < len(circuit.gates) - 1:
        g1 = circuit.gates[i]
        g2 = circuit.gates[i + 1]
        fused = _try_fuse(g1, g2)
        if fused is not None:
            if fused.name == "_remove":
                circuit.gates.pop(i + 1)
                circuit.gates.pop(i)
                removed += 2
            else:
                circuit.gates[i] = fused
                circuit.gates.pop(i + 1)
                removed += 1
        else:
            i += 1
    return removed


def _try_fuse(g1: QGate, g2: QGate) -> QGate | None:
    if g1.is_measure or g2.is_measure:
        return None

    if g1.qubits == g2.qubits and g1.name == g2.name:
        if g1.name in ("h", "x", "y", "z", "s", "sdg"):
            return QGate("_remove", comment="fused identity")
        if g1.name in ("rx", "ry", "rz") and g1.params and g2.params:
            new_val = g1.params[0] + g2.params[0]
            if abs(new_val) < 1e-9:
                return QGate("_remove", comment="fused to zero rotation")
            return QGate(g1.name, g1.qubits, (new_val,),
                        comment=f"fused {g1.name}({g1.params[0]:.3g}+{g2.params[0]:.3g})")
        if g1.name == "cx" and len(g1.qubits) == 2:
            return QGate("_remove", comment="fused identity CNOT")

    return None


def commute_and_fuse(circuit: QCircuit, max_passes: int = 3) -> int:
    total_removed = 0
    for _ in range(max_passes):
        removed = _commute_pass(circuit)
        if removed == 0:
            break
        total_removed += removed
    return total_removed


def _commute_pass(circuit: QCircuit) -> int:
    removed = 0
    i = 0
    while i < len(circuit.gates) - 1:
        g1 = circuit.gates[i]
        g2 = circuit.gates[i + 1]
        if _can_commute(g1, g2):
            if _try_fuse(g1, g2) is not None:
                removed += 1
        elif _commute_benefits(g1, g2):
            circuit.gates[i], circuit.gates[i + 1] = g2, g1
            removed += 1
        i += 1
    removed += fuse_adjacent_gates(circuit)
    return removed


def _can_commute(g1: QGate, g2: QGate) -> bool:
    q1 = set(g1.all_qubits())
    q2 = set(g2.all_qubits())
    if q1 & q2:
        if g1.name in ("rz",) and g2.name in ("rz",):
            return True
        return False
    return True


def _commute_benefits(g1: QGate, g2: QGate) -> bool:
    if g1.name == g2.name and g1.qubits == g2.qubits:
        return True
    if g1.name in ("h",) and g2.name in ("h",) and g1.qubits == g2.qubits:
        return True
    return False


def reduce_depth(circuit: QCircuit) -> int:
    qubit_times = defaultdict(int)
    improvements = 0
    for i, g in enumerate(circuit.gates):
        all_qs = list(g.all_qubits())
        current_max = max((qubit_times.get(q, 0) for q in all_qs), default=0)
        min_possible = current_max + 1
        if min_possible < current_max:
            improvements += 1
        for q in all_qs:
            qubit_times[q] = min_possible
    return improvements


def optimize(circuit: QCircuit, depth_reduction: bool = False,
             hardware_target: str = "") -> QCircuit:
    fuse_adjacent_gates(circuit)
    commute_and_fuse(circuit)
    if depth_reduction:
        reduce_depth(circuit)
    if hardware_target:
        lower_to_hardware(circuit, hardware_target)
    return circuit


def lower_to_hardware(circuit: QCircuit, target: str) -> QCircuit:
    from ..analysis.backends import get_backend
    backend = get_backend(target)
    if backend is None:
        raise ValueError(f"Unknown hardware backend: {target}")
    native = backend["native_gates"]
    new_gates: List[QGate] = []
    for g in circuit.gates:
        if g.is_measure:
            new_gates.append(g)
            continue
        if g.name in native:
            new_gates.append(g)
        else:
            expanded = _lower_gate(g, native, backend.get("native_2q", "cx"))
            new_gates.extend(expanded)
    circuit.gates = new_gates
    return circuit


def _lower_gate(g: QGate, native_set: set, native_2q: str) -> List[QGate]:
    if g.name == "cx" and "ecr" in native_set:
        # IBM: CNOT -> ECR + single-qubit rotations
        q0, q1 = g.qubits
        return [
            QGate("rz", (q1,), (-1.5707963267948966,), comment="ECR lower"),
            QGate("sx", (q1,), (), comment="ECR lower"),
            QGate("rz", (q1,), (1.5707963267948966,), comment="ECR lower"),
            QGate("ecr", (q0, q1), (), comment="ECR lower"),
            QGate("rz", (q0,), (-1.5707963267948966,), comment="ECR lower"),
            QGate("sx", (q0,), (), comment="ECR lower"),
        ]
    if g.name == "swap" and native_2q in native_set:
        q0, q1 = g.qubits
        return [
            QGate(native_2q, (q0, q1), (), comment="SWAP via 3x 2Q"),
            QGate(native_2q, (q1, q0), (), comment="SWAP via 3x 2Q"),
            QGate(native_2q, (q0, q1), (), comment="SWAP via 3x 2Q"),
        ]
    return [g]
