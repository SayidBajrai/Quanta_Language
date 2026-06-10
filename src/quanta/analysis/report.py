"""
Analysis report dataclass — returned by quanta.analyze().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from ..ir.ir_nodes import QCircuit, QGate
from ..ir.analysis import (
    count_qubits, count_gates, count_t_gates, count_two_qubit_gates,
    count_gates_by_type, circuit_depth, estimate_runtime, estimate_runtime_ns,
)
from ..ir.pathway import trace_circuit_simple


@dataclass
class AnalysisReport:
    qubit_count: int = 0
    gate_count: int = 0
    depth: int = 0
    t_count: int = 0
    two_qubit_gate_count: int = 0
    estimated_runtime: str = ""
    estimated_runtime_ns: float = 0.0
    gate_breakdown: Dict[str, int] = field(default_factory=dict)
    hardware_fits: Dict[str, bool] = field(default_factory=dict)
    circuit_pathway: str = ""
    registers: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_circuit(cls, circuit: QCircuit,
                     hardware_backends: Optional[List[str]] = None,
                     qubit_filter: Optional[List[int]] = None) -> AnalysisReport:
        report = cls(
            qubit_count=count_qubits(circuit),
            gate_count=count_gates(circuit),
            depth=circuit_depth(circuit),
            t_count=count_t_gates(circuit),
            two_qubit_gate_count=count_two_qubit_gates(circuit),
            estimated_runtime=estimate_runtime(circuit),
            estimated_runtime_ns=estimate_runtime_ns(circuit),
            gate_breakdown=count_gates_by_type(circuit),
            circuit_pathway=trace_circuit_simple(circuit, qubit_filter),
            registers=[
                {"name": r.name, "kind": r.kind, "size": r.size,
                 "total_qubits": r.total_qubits, "start_index": r.start_index}
                for r in circuit.registers
            ],
        )

        if hardware_backends:
            from .backends import check_fit
            report.hardware_fits = {
                backend: check_fit(circuit, backend)
                for backend in hardware_backends
            }

        return report

    def to_dict(self) -> Dict[str, Any]:
        return {
            "qubit_count": self.qubit_count,
            "gate_count": self.gate_count,
            "depth": self.depth,
            "t_count": self.t_count,
            "two_qubit_gate_count": self.two_qubit_gate_count,
            "estimated_runtime": self.estimated_runtime,
            "estimated_runtime_ns": self.estimated_runtime_ns,
            "gate_breakdown": self.gate_breakdown,
            "hardware_fits": self.hardware_fits,
            "registers": self.registers,
        }

    def hardware_fit(self, backend: str) -> bool:
        return self.hardware_fits.get(backend, False)

    def __str__(self) -> str:
        lines = [
            "=== Resource Analysis ===",
            f"Qubits: {self.qubit_count}",
            f"Gates: {self.gate_count}",
            f"Depth: {self.depth}",
            f"T-count: {self.t_count}",
            f"2Q gates: {self.two_qubit_gate_count}",
            f"Estimated runtime: {self.estimated_runtime}",
            "",
            "Gate Breakdown:",
        ]
        for gate, count in sorted(self.gate_breakdown.items(), key=lambda x: -x[1]):
            lines.append(f"  {gate}: {count}")
        if self.hardware_fits:
            lines.append("")
            lines.append("Hardware Fit:")
            for backend, fits in sorted(self.hardware_fits.items()):
                status = "YES" if fits else "NO"
                lines.append(f"  {backend}: {status}")
        if self.circuit_pathway:
            lines.append("")
            lines.append("=== Circuit Analysis ===")
            lines.append(self.circuit_pathway)
        return "\n".join(lines)

    def _repr_html_(self) -> str:
        rows = "".join(
            f"<tr><td>{k}</td><td>{v}</td></tr>"
            for k, v in self.to_dict().items()
            if k not in ("gate_breakdown", "hardware_fits", "registers", "circuit_pathway")
        )
        return f"<table>{rows}</table>"
