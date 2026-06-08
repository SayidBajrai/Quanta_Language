"""
Reserved identifiers that must not be used as user-defined names in Quanta.

These names collide with OpenQASM 3 keywords or standard gate names emitted by
the compiler (e.g. a register named ``x`` would produce invalid ``x x;`` lines).
"""

from __future__ import annotations

from typing import Optional

from ..errors import QuantaSemanticError
from ..lower.qasm3 import GATE_MAP

# OpenQASM 3 keywords and declaration introducers (matched case-insensitively).
_OPENQASM_KEYWORDS = frozenset({
    "openqasm",
    "include",
    "def",
    "gate",
    "opaque",
    "extern",
    "box",
    "let",
    "const",
    "input",
    "output",
    "bit",
    "int",
    "uint",
    "float",
    "angle",
    "complex",
    "array",
    "duration",
    "stretch",
    "cal",
    "defcal",
    "defcalgrammar",
    "break",
    "continue",
    "if",
    "else",
    "for",
    "in",
    "while",
    "return",
    "switch",
    "case",
    "default",
    "barrier",
    "delay",
    "pow",
    "inv",
    "ctrl",
})

# Additional stdgates / builtin names lowered to QASM (beyond GATE_MAP values).
_EXTRA_QASM_GATE_NAMES = frozenset({
    "h",
    "x",
    "y",
    "z",
    "s",
    "sdg",
    "t",
    "tdg",
    "sx",
    "sxdg",
    "id",
    "cx",
    "cy",
    "cz",
    "ch",
    "swap",
    "cswap",
    "ccx",
    "cu",
    "cp",
    "crx",
    "cry",
    "crz",
    "rx",
    "ry",
    "rz",
    "u",
    "u1",
    "u2",
    "u3",
    "p",
    "measure",
    "reset",
})

_QASM_GATE_NAMES = _EXTRA_QASM_GATE_NAMES | {
    qasm_name.lower() for qasm_name in GATE_MAP.values()
}


def reserved_qasm_reason(name: str) -> Optional[str]:
    """Return a human-readable reason if ``name`` is reserved, else ``None``."""
    normalized = name.lower()
    if normalized in _QASM_GATE_NAMES:
        return f"conflicts with OpenQASM gate '{normalized}'"
    if normalized in _OPENQASM_KEYWORDS:
        return f"conflicts with OpenQASM keyword '{normalized}'"
    return None


def validate_qasm_identifier(name: str, kind: str = "identifier") -> None:
    """Raise :class:`QuantaSemanticError` when ``name`` cannot be emitted to QASM."""
    reason = reserved_qasm_reason(name)
    if reason:
        raise QuantaSemanticError(f"'{name}' cannot be used as a {kind}: {reason}")
