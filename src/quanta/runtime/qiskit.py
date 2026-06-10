"""
Qiskit runtime integration
"""

from typing import Dict, Any, Optional
try:
    from qiskit import QuantumCircuit
    from qiskit.qasm3 import loads
    from qiskit_aer import AerSimulator
    QISKIT_AVAILABLE = True
except ImportError:
    QISKIT_AVAILABLE = False


def run_circuit(qasm: str, shots: int = 1024, backend: Optional[str] = None,
                noise_model: Any = None) -> Dict[str, Any]:
    """
    Execute QASM circuit using Qiskit.

    Args:
        qasm: OpenQASM 3 code as string
        shots: Number of measurement shots
        backend: Backend name (default: 'qasm_simulator')
        noise_model: Optional Qiskit NoiseModel or Quanta NoiseModel

    Returns:
        Dictionary with measurement results
    """
    if not QISKIT_AVAILABLE:
        raise ImportError(
            "Qiskit is required for circuit execution. "
            "Install with: pip install qiskit qiskit-aer"
        )

    try:
        circuit = loads(qasm)

        if backend is None:
            backend = "qasm_simulator"

        sim_kwargs = {}
        if noise_model is not None:
            if hasattr(noise_model, 'to_qiskit'):
                noise_model = noise_model.to_qiskit()
            if noise_model is not None:
                sim_kwargs['noise_model'] = noise_model

        if backend == "qasm_simulator":
            simulator = AerSimulator(**sim_kwargs)
            job = simulator.run(circuit, shots=shots)
        else:
            simulator = AerSimulator(**sim_kwargs)
            job = simulator.run(circuit, shots=shots)

        result = job.result()
        counts = result.get_counts()

        return {
            "counts": counts,
            "shots": shots,
            "backend": backend,
        }
    except Exception as e:
        return {
            "error": str(e),
            "shots": shots,
            "backend": backend,
        }
