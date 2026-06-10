"""
Quantum Intermediate Representation (QIR)

The canonical IR between AST semantic analysis and QASM code generation.
Optimization and analysis passes operate on this representation.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict


@dataclass
class QReg:
    name: str
    kind: str
    size: int
    total_qubits: int = 0
    start_index: int = 0


@dataclass
class QGate:
    name: str
    qubits: Tuple[int, ...] = ()
    params: Tuple[float, ...] = ()
    ctrl_qubits: Tuple[int, ...] = ()
    is_inverse: bool = False
    is_measure: bool = False
    comment: str = ""

    def num_qubits(self) -> int:
        return len(self.qubits)

    def is_two_qubit(self) -> bool:
        return len(self.qubits) >= 2

    def is_rotation(self) -> bool:
        return len(self.params) > 0

    def touches_qubit(self, q: int) -> bool:
        return q in self.qubits or q in self.ctrl_qubits

    def all_qubits(self) -> Tuple[int, ...]:
        return self.qubits + self.ctrl_qubits


@dataclass
class QCircuit:
    registers: List[QReg] = field(default_factory=list)
    gates: List[QGate] = field(default_factory=list)
    qubit_map: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    total_qubits: int = 0

    def add_register(self, name: str, kind: str, size: int) -> int:
        total = size
        if kind in ("qint", "quint"):
            pass
        elif kind in ("qdec", "qudec"):
            import math
            total = size + (size * 2)
        start = self.total_qubits
        self.registers.append(QReg(name, kind, size, total_qubits=total, start_index=start))
        self.qubit_map[name] = (start, start + total)
        self.total_qubits += total
        return start

    def resolve_qubit(self, name: str, index: int) -> int:
        start, end = self.qubit_map[name]
        q = start + index
        if q >= end:
            raise IndexError(f"Qubit index {index} out of range for register '{name}'")
        return q

    def add_gate(self, gate: QGate) -> None:
        self.gates.append(gate)


@dataclass
class QOp:
    name: str
    operands: List[str]


@dataclass
class QIR:
    registers: List[tuple]
    operations: List[QOp]

    def __init__(self):
        self.registers = []
        self.operations = []
