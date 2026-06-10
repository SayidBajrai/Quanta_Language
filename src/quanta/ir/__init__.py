"""
Intermediate Representation (IR) module

Exports the full IR toolkit: nodes, builder, analysis, optimization, pathway, and noise.
"""

from .ir_nodes import QOp, QIR, QReg, QGate, QCircuit
from .builder import IRBuilder
from .analysis import (
    count_qubits, count_gates, count_t_gates, count_two_qubit_gates,
    count_gates_by_type, circuit_depth, estimate_runtime, estimate_runtime_ns,
)
from .optimizer import (
    fuse_adjacent_gates, commute_and_fuse, reduce_depth,
    optimize, lower_to_hardware,
)
from .pathway import trace_pathway, trace_circuit_simple
from .noise import NoiseModel

__all__ = [
    "QOp", "QIR", "QReg", "QGate", "QCircuit",
    "IRBuilder",
    "count_qubits", "count_gates", "count_t_gates", "count_two_qubit_gates",
    "count_gates_by_type", "circuit_depth", "estimate_runtime", "estimate_runtime_ns",
    "fuse_adjacent_gates", "commute_and_fuse", "reduce_depth",
    "optimize", "lower_to_hardware",
    "trace_pathway", "trace_circuit_simple",
    "NoiseModel",
]
