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


def run_circuit(qasm: str, shots: int = 1024, backend: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute QASM circuit using Qiskit.
    
    Args:
        qasm: OpenQASM 3 code as string
        shots: Number of measurement shots
        backend: Backend name (default: 'qasm_simulator')
        
    Returns:
        Dictionary with measurement results
    """
    if not QISKIT_AVAILABLE:
        raise ImportError(
            "Qiskit is required for circuit execution. "
            "Install with: pip install qiskit qiskit-aer"
        )
    
    try:
        # Parse QASM 3
        circuit = loads(qasm)
        
        # Get backend
        if backend is None:
            backend = "qasm_simulator"
        
        if backend == "qasm_simulator":
            simulator = AerSimulator()
            job = simulator.run(circuit, shots=shots)
        else:
            # For other backends, you'd configure them here
            simulator = AerSimulator()
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
