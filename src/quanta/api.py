"""
Public API for Quanta compiler
"""

from typing import Dict, Any, Optional
from .compiler import Compiler
from .runtime.qiskit import run_circuit


def compile(source: str) -> str:
    """
    Compile Quanta source code to OpenQASM 3.
    
    Args:
        source: Quanta source code as a string
        
    Returns:
        OpenQASM 3 code as a string
        
    Raises:
        QuantaError: If compilation fails
    """
    compiler = Compiler()
    return compiler.compile(source)


def run(source: str, shots: int = 1024, backend: Optional[str] = None) -> Dict[str, Any]:
    """
    Compile and run Quanta source code.
    
    Args:
        source: Quanta source code as a string
        shots: Number of measurement shots
        backend: Qiskit backend name (default: 'qasm_simulator')
        
    Returns:
        Dictionary with measurement results
    """
    qasm = compile(source)
    return run_circuit(qasm, shots=shots, backend=backend)
