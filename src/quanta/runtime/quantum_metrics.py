"""
Quantum state metrics for Quanta frontend simulation.

Provides subsystem state extraction and fidelity computation between registers.
"""

from __future__ import annotations

from typing import Any, Optional, Tuple, Union, TYPE_CHECKING

import numpy as np

from ..ast.nodes import Expr, IndexExpr, VarExpr
from ..errors import QuantaError
from .formatting import (
    PURITY_PURE_THRESHOLD,
    FormatContext,
    _resolve_qbit_indices,
)

if TYPE_CHECKING:
    from qiskit.quantum_info import DensityMatrix, Statevector

SubsystemState = Union["Statevector", "DensityMatrix"]


def get_subsystem_state(
    expr: Expr, ctx: FormatContext
) -> Tuple[Optional[SubsystemState], int]:
    """
    Extract the current reduced state of a qbit/qint register expression.

    Returns (state, n_qubits) where state is a Statevector (pure) or
    DensityMatrix (mixed). Returns (None, 0) when the expression does not
    resolve to a quantum register.
    """
    from qiskit.quantum_info import DensityMatrix, Statevector, partial_trace, purity

    indices = _resolve_qbit_indices(expr, ctx)
    if not indices:
        return None, 0

    sv = Statevector(ctx.circuit)
    n_sub = len(indices)

    if n_sub == sv.num_qubits:
        return sv, n_sub

    other = [i for i in range(sv.num_qubits) if i not in indices]
    rho = partial_trace(sv, other)

    if purity(rho) > PURITY_PURE_THRESHOLD:
        evals, evecs = np.linalg.eigh(rho.data)
        idx_max = int(np.argmax(evals))
        return Statevector(evecs[:, idx_max]), n_sub

    return DensityMatrix(rho), n_sub


def _pure_state_fidelity(a: "Statevector", b: "Statevector") -> float:
    if a.dim != b.dim:
        raise QuantaError(
            f"Fidelity requires registers of the same size "
            f"(got {int(np.log2(a.dim))} and {int(np.log2(b.dim))} qubits)"
        )
    overlap = np.vdot(a.data, b.data)
    return float(abs(overlap) ** 2)


def compute_fidelity(expr_a: Expr, expr_b: Expr, ctx: FormatContext) -> float:
    """
    Compute quantum state fidelity F(ρₐ, ρ_b) between two register expressions.

    For pure states: F = |⟨ψₐ|ψ_b⟩|².
    For mixed states: uses Qiskit state_fidelity on reduced density matrices.
    """
    from qiskit.quantum_info import DensityMatrix, Statevector, state_fidelity

    state_a, n_a = get_subsystem_state(expr_a, ctx)
    state_b, n_b = get_subsystem_state(expr_b, ctx)

    if state_a is None or state_b is None:
        raise QuantaError("Fidelity arguments must be qbit or qint registers")

    if n_a != n_b:
        raise QuantaError(
            f"Fidelity requires registers of the same size "
            f"(got {n_a} and {n_b} qubits)"
        )

    if isinstance(state_a, Statevector) and isinstance(state_b, Statevector):
        result = _pure_state_fidelity(state_a, state_b)
    else:
        rho_a = state_a if isinstance(state_a, DensityMatrix) else DensityMatrix(state_a)
        rho_b = state_b if isinstance(state_b, DensityMatrix) else DensityMatrix(state_b)
        result = float(state_fidelity(rho_a, rho_b))

    return round(result, 4)


def fidelity_from_registers(
    expr_a: Expr, expr_b: Expr, ctx: FormatContext
) -> float:
    """Alias for compute_fidelity (spec-facing name)."""
    return compute_fidelity(expr_a, expr_b, ctx)
