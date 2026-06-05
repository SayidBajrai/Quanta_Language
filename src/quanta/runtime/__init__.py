"""Runtime execution module"""


def run_circuit(*args, **kwargs):
    """Execute a quantum circuit (lazy-loads Qiskit Aer backend)."""
    from .qiskit import run_circuit as _run_circuit

    return _run_circuit(*args, **kwargs)


__all__ = ["run_circuit"]
