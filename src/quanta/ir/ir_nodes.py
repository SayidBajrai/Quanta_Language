"""
Quantum Intermediate Representation (QIR-lite)
"""

from dataclasses import dataclass
from typing import List


@dataclass
class QOp:
    """Quantum operation in IR"""
    name: str
    operands: List[str]


@dataclass
class QIR:
    """Quantum Intermediate Representation"""
    registers: List[tuple]  # (kind, size, name)
    operations: List[QOp]
    
    def __init__(self):
        self.registers = []
        self.operations = []
