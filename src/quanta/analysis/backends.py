"""
Hardware backend database — connectivity graphs, native gate sets, qubit counts.
"""

from typing import Dict, List, Optional, Any
from ..ir.ir_nodes import QCircuit


_BACKENDS: Dict[str, Dict[str, Any]] = {
    "ibm_brisbane": {
        "name": "IBM Brisbane",
        "qubits": 127,
        "native_gates": {"ecr", "id", "rz", "sx", "x", "measure"},
        "native_2q": "ecr",
        "topology": "heavy_hex",
        "t1_us": 150.0,
        "t2_us": 100.0,
        "gate_error_1q": 0.0003,
        "gate_error_2q": 0.008,
        "readout_error": 0.015,
    },
    "ibm_sherbrooke": {
        "name": "IBM Sherbrooke",
        "qubits": 127,
        "native_gates": {"ecr", "id", "rz", "sx", "x", "measure"},
        "native_2q": "ecr",
        "topology": "heavy_hex",
        "t1_us": 250.0,
        "t2_us": 180.0,
        "gate_error_1q": 0.0002,
        "gate_error_2q": 0.006,
        "readout_error": 0.01,
    },
    "ibm_kyoto": {
        "name": "IBM Kyoto",
        "qubits": 127,
        "native_gates": {"ecr", "id", "rz", "sx", "x", "measure"},
        "native_2q": "ecr",
        "topology": "heavy_hex",
        "t1_us": 200.0,
        "t2_us": 140.0,
        "gate_error_1q": 0.00025,
        "gate_error_2q": 0.007,
        "readout_error": 0.012,
    },
    "ionq_aria": {
        "name": "IonQ Aria",
        "qubits": 25,
        "native_gates": {"gpi", "gpi2", "ms", "measure"},
        "native_2q": "ms",
        "topology": "all_to_all",
        "gate_error_1q": 0.003,
        "gate_error_2q": 0.004,
        "readout_error": 0.005,
    },
    "ionq_forte": {
        "name": "IonQ Forte",
        "qubits": 35,
        "native_gates": {"gpi", "gpi2", "ms", "measure"},
        "native_2q": "ms",
        "topology": "all_to_all",
        "gate_error_1q": 0.002,
        "gate_error_2q": 0.003,
        "readout_error": 0.004,
    },
    "qasm_simulator": {
        "name": "QASM Simulator",
        "qubits": 63,
        "native_gates": {"h", "x", "y", "z", "s", "sdg", "t", "tdg",
                          "cx", "cz", "swap", "ccx",
                          "rx", "ry", "rz", "id", "measure"},
        "native_2q": "cx",
        "topology": "all_to_all",
    },
}


def get_backend(name: str) -> Optional[Dict[str, Any]]:
    return _BACKENDS.get(name)


def list_backends() -> List[str]:
    return sorted(_BACKENDS.keys())


def check_fit(circuit: QCircuit, backend_name: str) -> bool:
    backend = get_backend(backend_name)
    if backend is None:
        return False
    if circuit.total_qubits > backend["qubits"]:
        return False
    return True


def backend_info(backend_name: str) -> str:
    backend = get_backend(backend_name)
    if backend is None:
        return f"Unknown backend: {backend_name}"
    lines = [
        f"Backend: {backend['name']}",
        f"  Qubits: {backend['qubits']}",
        f"  Topology: {backend['topology']}",
        f"  Native gates: {', '.join(sorted(backend['native_gates']))}",
        f"  Native 2Q: {backend.get('native_2q', 'N/A')}",
    ]
    if "t1_us" in backend:
        lines.extend([
            f"  T1: {backend['t1_us']} μs",
            f"  T2: {backend['t2_us']} μs",
            f"  1Q error: {backend['gate_error_1q']:.2%}",
            f"  2Q error: {backend['gate_error_2q']:.2%}",
            f"  Readout error: {backend['readout_error']:.2%}",
        ])
    return "\n".join(lines)
