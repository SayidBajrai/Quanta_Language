"""
Public API for Quanta compiler
"""

from typing import Dict, Any, Optional
from .compiler import Compiler
from .runtime.qiskit import run_circuit
from .runtime import frontend_sim


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


def get_prints(quanta_code: str) -> str:
    """
    Parse Quanta source, run in statevector simulator, and return the string
    that would be printed by all Print() / print() calls.

    **Frontend Debug Execution Only. Not compatible with hardware backend.**
    Real quantum hardware cannot reveal amplitudes; this is statevector simulation only.

    - print(classical): immediate evaluation, append to output.
    - print(quantum): inspect statevector, append symbolic summary (no state collapse).
    - Entangled subsystems: full state is shown with a note.

    Raises:
        RuntimeError: If total qubits > 20 (simulation limit).
        QuantaError: On parse/semantic errors.

    Returns:
        Terminal output as a single string (lines joined by newline).
    """
    return frontend_sim.get_prints(quanta_code)
