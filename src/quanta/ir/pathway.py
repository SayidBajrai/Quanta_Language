"""
Pathway tracer: generates human-readable state evolution traces from a QCircuit.

Used for the {q:pathway} and {q:circuit} format specifiers.
"""

from typing import List, Dict, Set, Tuple, Optional
from .ir_nodes import QCircuit, QGate


def trace_pathway(circuit: QCircuit, qubit_filter: Optional[List[int]] = None) -> str:
    traced_qubits: Set[int] = set()
    groups: List[Tuple[int, str, List[int], str]] = []

    for g in circuit.gates:
        if g.is_measure:
            continue
        gate_qubits = set(g.qubits)
        if qubit_filter is not None:
            if not gate_qubits & set(qubit_filter):
                continue
        else:
            traced_qubits |= gate_qubits

        qubit_list = sorted(gate_qubits)
        desc = _gate_to_dirac(g, qubit_list)
        step = len(groups) + 1
        groups.append((step, g.comment or g.name, qubit_list, desc))

    lines = _format_pathway_lines(groups, traced_qubits)
    return "\n".join(lines)


def _gate_to_dirac(g: QGate, qubits: List[int]) -> str:
    q_labels = [f"q_{q}" for q in qubits]
    gate = g.name.upper()
    qubit_str = ", ".join(q_labels)

    if g.name == "h":
        return f"{qubit_str}: |0\u27e9 \u2192 (|0\u27e9 + |1\u27e9) / \u221a2"
    elif g.name == "x":
        return f"{qubit_str}: |0\u27e9 \u2192 |1\u27e9"
    elif g.name == "z":
        return f"{qubit_str}: |\u03c8\u27e9 \u2192 Z|\u03c8\u27e9"
    elif g.name == "y":
        return f"{qubit_str}: |\u03c8\u27e9 \u2192 Y|\u03c8\u27e9"
    elif g.name in ("cx", "cnot"):
        if len(qubits) >= 2:
            return f"{qubit_str}: entangled CNOT operation"
        return f"{qubit_str}: CNOT"
    elif g.name in ("cz",):
        return f"{qubit_str}: CZ phase flip"
    elif g.name in ("swap",):
        return f"{qubit_str}: SWAP"
    elif g.name in ("rx", "ry", "rz") and g.params:
        return f"{qubit_str}: rotation {g.name.upper()}({g.params[0]:.3g})"
    elif g.name == "measure":
        return f"{qubit_str}: measurement"
    elif g.name == "reset":
        return f"{qubit_str}: reset to |0\u27e9"
    elif g.name in ("ccx", "toffoli"):
        return f"{qubit_str}: Toffoli (CCX)"
    else:
        return f"{qubit_str}: {gate}"


def _format_pathway_lines(
    groups: List[Tuple[int, str, List[int], str]],
    all_qubits: Set[int],
) -> List[str]:
    lines: List[str] = []
    ent_groups: Dict[int, Set[int]] = {}

    for step, name, qbs, desc in groups:
        lines.append("")
        lines.append(f"Step {step}: {name}")
        lines.append(desc)

        gate_set = set(qbs)
        merged: Set[int] = set(qbs)
        to_merge: List[int] = []
        for gid, group in list(ent_groups.items()):
            if group & gate_set:
                merged |= group
                to_merge.append(gid)

        if merged - gate_set:
            other_q = sorted(merged - gate_set)
            other_labels = [f"q_{q}" for q in other_q]
            if len(other_labels) == 1:
                lines[-1] = lines[-1] + f" (entangled; includes {other_labels[0]})"
            else:
                lines[-1] = lines[-1] + f" (entangled; includes {', '.join(other_labels)})"

        new_group_id = max(ent_groups.keys(), default=-1) + 1
        for gid in to_merge:
            del ent_groups[gid]
        ent_groups[new_group_id] = merged

        all_qubits |= gate_set

    return lines


def trace_circuit_simple(circuit: QCircuit, qubit_filter: Optional[List[int]] = None) -> str:
    lines: List[str] = []
    filter_set = set(qubit_filter) if qubit_filter else None

    for step, g in enumerate(circuit.gates, start=1):
        gate_qubits = set(g.qubits)
        if filter_set and not gate_qubits & filter_set:
            continue

        qubit_list = sorted(gate_qubits)
        q_labels = ", ".join(f"q_{q}" for q in qubit_list)
        desc = f"{g.name}({q_labels})"
        if g.params:
            desc = f"{g.name}({', '.join(f'{p:.3g}' for p in g.params)}) {q_labels}"
        if g.comment:
            desc += f"  ; {g.comment}"
        if g.is_inverse:
            desc = f"inv({desc})"
        if g.ctrl_qubits:
            ctrl_labels = ", ".join(f"q_{q}" for q in g.ctrl_qubits)
            desc = f"ctrl({ctrl_labels})@{desc}"

        lines.append(f"Step {step}: {desc}")

    return "\n".join(lines)
