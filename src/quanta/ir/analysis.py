"""
Analysis passes on QCircuit — gate counting, depth estimation, T-count, etc.
"""

from typing import Dict, List, Set, Tuple
from collections import defaultdict
from .ir_nodes import QCircuit, QGate


def count_qubits(circuit: QCircuit) -> int:
    return circuit.total_qubits


def count_gates(circuit: QCircuit) -> int:
    return len([g for g in circuit.gates if not g.is_measure])


def count_t_gates(circuit: QCircuit) -> int:
    t_count = 0
    for g in circuit.gates:
        if g.is_measure:
            continue
        if g.name in ("t", "tdg"):
            t_count += 1
        elif g.name in ("rz", "crz") and g.params:
            p = abs(g.params[0])
            if abs(p - 0.7853981633974483) < 1e-6 or abs(p + 0.7853981633974483) < 1e-6:
                t_count += 1
    return t_count


def count_two_qubit_gates(circuit: QCircuit) -> int:
    return len([g for g in circuit.gates
                if not g.is_measure and len(g.qubits) >= 2])


def count_gates_by_type(circuit: QCircuit) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for g in circuit.gates:
        if not g.is_measure:
            counts[g.name] += 1
    return dict(counts)


def circuit_depth(circuit: QCircuit) -> int:
    qubit_times: Dict[int, int] = defaultdict(int)
    for g in circuit.gates:
        all_qs = list(g.qubits)
        max_time = max((qubit_times.get(q, 0) for q in all_qs), default=0)
        new_time = max_time + 1
        for q in all_qs:
            qubit_times[q] = new_time
    return max(qubit_times.values()) if qubit_times else 0


def critical_path(circuit: QCircuit) -> List[QGate]:
    qubit_last: Dict[int, int] = {}
    gate_pred: Dict[int, int] = {}
    gate_depth: Dict[int, int] = {}

    for i, g in enumerate(circuit.gates):
        all_qs = list(g.qubits)
        max_prev = 0
        for q in all_qs:
            if q in qubit_last:
                prev_gate = qubit_last[q]
                if gate_depth.get(prev_gate, 0) > max_prev:
                    max_prev = gate_depth[prev_gate]
        gate_depth[i] = max_prev + 1
        for q in all_qs:
            qubit_last[q] = i

    max_depth = max(gate_depth.values()) if gate_depth else 0
    if max_depth == 0:
        return []

    last_gates = [i for i, d in gate_depth.items() if d == max_depth]
    current = last_gates[0]
    path = [current]
    remaining = max_depth - 1

    while remaining > 0:
        found = False
        all_qs = list(circuit.gates[current].qubits)
        for q in all_qs:
            for j in range(current - 1, -1, -1):
                if q in circuit.gates[j].qubits and gate_depth.get(j, 0) == remaining:
                    path.append(j)
                    current = j
                    remaining -= 1
                    found = True
                    break
            if found:
                break
        if not found:
            break

    return [circuit.gates[i] for i in reversed(path)]


def estimate_runtime_ns(circuit: QCircuit) -> float:
    n_1q = 0
    n_2q = 0
    for g in circuit.gates:
        if g.is_measure:
            continue
        if len(g.qubits) >= 2:
            n_2q += 1
        else:
            n_1q += 1
    return n_1q * 20.0 + n_2q * 100.0


def estimate_runtime(circuit: QCircuit) -> str:
    ns = estimate_runtime_ns(circuit)
    if ns < 1000:
        return f"{ns:.0f} ns"
    elif ns < 1_000_000:
        return f"{ns / 1000:.1f} μs"
    elif ns < 1_000_000_000:
        return f"{ns / 1_000_000:.1f} ms"
    else:
        return f"{ns / 1_000_000_000:.2f} s"
