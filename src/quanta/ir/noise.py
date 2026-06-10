"""
Noise model configuration for error/noise simulation.

Translates Quanta NoiseModel declarations into Qiskit noise model parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Any


@dataclass
class NoiseModel:
    depolarizing: float = 0.0
    readout: float = 0.0
    thermal_relaxation: float = 0.0
    t1_us: Optional[float] = None
    t2_us: Optional[float] = None
    gate_error_1q: float = 0.0
    gate_error_2q: float = 0.0
    custom_errors: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_quanta(cls, params: Dict[str, float]) -> NoiseModel:
        return cls(
            depolarizing=params.get("depolarizing", 0.0),
            readout=params.get("readout", 0.0),
            thermal_relaxation=params.get("thermal_relaxation", 0.0),
            t1_us=params.get("t1", None),
            t2_us=params.get("t2", None),
            gate_error_1q=params.get("gate_error_1q", 0.0),
            gate_error_2q=params.get("gate_error_2q", 0.0),
        )

    def to_qiskit(self) -> Any:
        try:
            from qiskit_aer.noise import NoiseModel as QiskitNoiseModel, errors
            from qiskit_aer.noise.errors import depolarizing_error, thermal_relaxation_error, readout_error

            model = QiskitNoiseModel()

            if self.depolarizing > 0:
                error_1q = depolarizing_error(self.depolarizing, 1)
                error_2q = depolarizing_error(self.depolarizing, 2)
                model.add_all_qubit_quantum_error(error_1q, ["x", "y", "z", "h", "s", "sdg", "t", "tdg", "rx", "ry", "rz"])
                model.add_all_qubit_quantum_error(error_2q, ["cx", "cz", "swap"])

            if self.readout > 0:
                error = readout_error([[1 - self.readout, self.readout],
                                       [self.readout, 1 - self.readout]])
                model.add_all_qubit_readout_error(error)

            if self.t1_us is not None and self.t2_us is not None:
                t1_ns = self.t1_us * 1000
                t2_ns = self.t2_us * 1000
                error = thermal_relaxation_error(t1_ns, t2_ns, 0.0)
                model.add_all_qubit_quantum_error(error, ["x", "y", "z", "h", "s", "sdg", "t", "tdg", "rx", "ry", "rz"])

            if self.gate_error_1q > 0:
                error_1q = depolarizing_error(self.gate_error_1q, 1)
                model.add_all_qubit_quantum_error(
                    error_1q, ["rx", "ry", "rz", "h", "x", "y", "z", "s", "t"]
                )

            if self.gate_error_2q > 0:
                error_2q = depolarizing_error(self.gate_error_2q, 2)
                model.add_all_qubit_quantum_error(error_2q, ["cx", "cz", "swap"])

            for gate, prob in self.custom_errors.items():
                if prob > 0:
                    error = depolarizing_error(prob, 1)
                    model.add_all_qubit_quantum_error(error, [gate])

            return model

        except ImportError:
            return None

    def is_noisy(self) -> bool:
        return any([
            self.depolarizing > 0,
            self.readout > 0,
            self.thermal_relaxation > 0,
            self.gate_error_1q > 0,
            self.gate_error_2q > 0,
            bool(self.custom_errors),
        ])
