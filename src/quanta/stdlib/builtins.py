"""
Built-in and standard-library function summaries for IDE hover / completion.

Each entry describes a Quanta callable: its signature, parameters, return type,
and a short summary. Consumed by tooling (LSP, editor extensions) via
``quanta.get_function_docs()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class FunctionParam:
    """One parameter in a function signature."""

    name: str
    type: str
    description: str = ""


@dataclass(frozen=True)
class FunctionSummary:
    """Documentation for a single Quanta built-in or stdlib function."""

    name: str
    summary: str
    signature: str
    params: tuple[FunctionParam, ...] = ()
    returns: Optional[str] = None
    category: str = "stdlib"
    min_args: Optional[int] = None
    max_args: Optional[int] = None
    notes: tuple[str, ...] = ()

    def format_hover(self) -> str:
        """Render a multi-line hover string for IDE tooltips."""
        lines = [self.signature, "", self.summary]
        if self.params:
            lines.extend(["", "Parameters:"])
            for param in self.params:
                detail = f" — {param.description}" if param.description else ""
                lines.append(f"  {param.name} ({param.type}){detail}")
        if self.returns:
            lines.extend(["", f"Returns: {self.returns}"])
        for note in self.notes:
            lines.extend(["", f"Note: {note}"])
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, object]:
        """Serialize for JSON / LSP consumers."""
        return {
            "name": self.name,
            "summary": self.summary,
            "signature": self.signature,
            "params": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                }
                for p in self.params
            ],
            "returns": self.returns,
            "category": self.category,
            "min_args": self.min_args,
            "max_args": self.max_args,
            "notes": list(self.notes),
            "hover": self.format_hover(),
        }


def _qint(name: str, desc: str = "") -> FunctionParam:
    return FunctionParam(name, "qint[n]", desc)


def _qbit(name: str, desc: str = "") -> FunctionParam:
    return FunctionParam(name, "qbit / qbit[]", desc)


def _variadic_qint_op(
    name: str,
    *,
    summary: str,
    op: str,
    min_args: int = 2,
    dest_desc: str = "Destination register (starts at |0⟩ for 3+ operands)",
) -> FunctionSummary:
    return FunctionSummary(
        name=name,
        summary=summary,
        signature=f"{name}(inputs..., dest)",
        params=(
            FunctionParam(
                "inputs",
                "qint[n]",
                f"One or more input qint registers; result is {op} mod 2^n",
            ),
            _qint("dest", dest_desc),
        ),
        returns="void (in-place / writes to dest)",
        category="quantum_arithmetic",
        min_args=min_args,
        notes=(
            "All operands must have matching bit widths.",
            f"Two-arg form: {name}(a, b) updates b in-place.",
        ),
    )


FUNCTION_SUMMARIES: Dict[str, FunctionSummary] = {}


def _register(*docs: FunctionSummary) -> None:
    for doc in docs:
        FUNCTION_SUMMARIES[doc.name] = doc


# --- Quantum arithmetic -------------------------------------------------------

_register(
    _variadic_qint_op(
        "QAdd",
        summary="Ripple-carry quantum addition. Best for small to medium bit widths.",
        op="(q1 + q2 + …)",
    ),
    _variadic_qint_op(
        "QSub",
        summary="Ripple-borrow quantum subtraction (modular two's complement).",
        op="(q1 - q2 - …)",
    ),
    FunctionSummary(
        name="QMult",
        summary="Shift-and-add quantum multiplication.",
        signature="QMult(inputs..., dest)",
        params=(
            FunctionParam("inputs", "qint[n]", "Multiplicand registers"),
            _qint("dest", "Product register; width must be ≥ sum of input widths"),
        ),
        returns="void",
        category="quantum_arithmetic",
        min_args=3,
        notes=("Output width must be at least the input width.",),
    ),
    _variadic_qint_op(
        "QFTAdd",
        summary="QFT-based (Draper) quantum addition. Lower depth; good for large widths and modular arithmetic.",
        op="(q1 + q2 + …)",
    ),
    _variadic_qint_op(
        "QTreeAdd",
        summary="Tree-based parallel quantum addition. Reduced depth for multi-operand sums.",
        op="(q1 + q2 + …)",
    ),
    FunctionSummary(
        name="QExpEncMult",
        summary="Exponent-encoded quantum multiplication using O(log n) qubits.",
        signature="QExpEncMult(inputs..., dest)",
        params=(
            FunctionParam("inputs", "qint[n]", "Operand registers"),
            _qint("dest", "Product register"),
        ),
        returns="void",
        category="quantum_arithmetic",
        min_args=3,
        notes=("Requires measurement and classical post-processing for decoding.",),
    ),
    FunctionSummary(
        name="QTreeMult",
        summary="Tree-based (Wallace/Dadda-style) quantum multiplication with reduced T-count.",
        signature="QTreeMult(inputs..., dest)",
        params=(
            FunctionParam("inputs", "qint[n]", "Operand registers"),
            _qint("dest", "Product register"),
        ),
        returns="void",
        category="quantum_arithmetic",
        min_args=3,
    ),
    FunctionSummary(
        name="QDiv",
        summary="Quantum integer division with quotient and remainder via repeated subtraction.",
        signature="QDiv(dividend, divisor, quotient, remainder)",
        params=(
            _qint("dividend", "Dividend register"),
            _qint("divisor", "Divisor register (must be non-zero)"),
            _qint("quotient", "Output quotient; same width as dividend"),
            _qint("remainder", "Output remainder; same width as dividend"),
        ),
        returns="void",
        category="quantum_arithmetic",
        min_args=4,
        max_args=4,
    ),
    FunctionSummary(
        name="QMod",
        summary="Quantum modular reduction via repeated subtraction.",
        signature="QMod(inputs..., dest)",
        params=(
            FunctionParam("inputs", "qint[n]", "Dividend then divisor register(s)"),
            _qint("dest", "Remainder register"),
        ),
        returns="void",
        category="quantum_arithmetic",
        min_args=3,
    ),
    FunctionSummary(
        name="Compare",
        summary="Quantum comparison: sets flag to |1⟩ when a ≥ b.",
        signature="Compare(a, b, flag)",
        params=(
            _qint("a", "First operand"),
            _qint("b", "Second operand"),
            FunctionParam("flag", "qint[1] | qbit", "Output: |1⟩ if a ≥ b, else |0⟩"),
        ),
        returns="void",
        category="quantum_arithmetic",
        min_args=3,
        max_args=3,
        notes=("Result is usable as a quantum control signal.",),
    ),
    FunctionSummary(
        name="Grover",
        summary="Grover iteration: oracle phase-flip for x == target plus diffusion.",
        signature="Grover(x, target)",
        params=(
            _qint("x", "Search register (should be in uniform superposition)"),
            FunctionParam("target", "int | bint", "Classical target value to amplify"),
        ),
        returns="void",
        category="quantum_arithmetic",
        min_args=2,
        max_args=2,
    ),
)

# --- High-level gates ---------------------------------------------------------

_register(
    FunctionSummary(
        name="Bell",
        summary="Prepare a maximally entangled Bell pair: |00⟩ → (|00⟩ + |11⟩)/√2.",
        signature="Bell(q0, q1) | Bell(q[0:2])",
        params=(
            _qbit("q0", "First qubit"),
            _qbit("q1", "Second qubit"),
        ),
        returns="void",
        category="high_level_gate",
        min_args=1,
        max_args=2,
    ),
    FunctionSummary(
        name="GHZ",
        summary="Prepare a GHZ state on two or more qubits.",
        signature="GHZ(q0, q1, ...) | GHZ(q) | GHZ(q[start:end])",
        params=(
            FunctionParam("qubits", "qbit / qbit[]", "Two or more qubits or a register slice"),
        ),
        returns="void",
        category="high_level_gate",
        min_args=1,
    ),
    FunctionSummary(
        name="WState",
        summary="Prepare a three-qubit W state.",
        signature="WState(q0, q1, q2) | WState(q[0:3])",
        params=(
            FunctionParam("qubits", "qbit / qbit[]", "Exactly three qubits or a length-3 slice"),
        ),
        returns="void",
        category="high_level_gate",
        min_args=1,
        max_args=3,
    ),
    FunctionSummary(
        name="SwapGate",
        summary="Swap the quantum states of two qubits.",
        signature="SwapGate(a, b)",
        params=(
            _qbit("a", "First qubit"),
            _qbit("b", "Second qubit"),
        ),
        returns="void",
        category="high_level_gate",
        min_args=2,
        max_args=2,
    ),
    FunctionSummary(
        name="QFT",
        summary="Apply the Quantum Fourier Transform to a register.",
        signature="QFT(q0, q1, ...) | QFT(q)",
        params=(
            FunctionParam("qubits", "qbit / qbit[]", "Qubits to transform (LSB ordering)"),
        ),
        returns="void",
        category="high_level_gate",
        min_args=1,
    ),
    FunctionSummary(
        name="InverseQFT",
        summary="Apply the inverse Quantum Fourier Transform.",
        signature="InverseQFT(q0, q1, ...) | InverseQFT(q)",
        params=(
            FunctionParam("qubits", "qbit / qbit[]", "Qubits to transform in reverse QFT order"),
        ),
        returns="void",
        category="high_level_gate",
        min_args=1,
    ),
)

# --- Primitive gates ------------------------------------------------------------

_register(
    FunctionSummary(
        name="H",
        summary="Hadamard gate.",
        signature="H(q)",
        params=(_qbit("q", "Target qubit"),),
        returns="void",
        category="gate",
        min_args=1,
        max_args=1,
    ),
    FunctionSummary(
        name="X",
        summary="Pauli-X (NOT) gate.",
        signature="X(q)",
        params=(_qbit("q", "Target qubit"),),
        returns="void",
        category="gate",
        min_args=1,
        max_args=1,
    ),
    FunctionSummary(
        name="Y",
        summary="Pauli-Y gate.",
        signature="Y(q)",
        params=(_qbit("q", "Target qubit"),),
        returns="void",
        category="gate",
        min_args=1,
        max_args=1,
    ),
    FunctionSummary(
        name="Z",
        summary="Pauli-Z gate.",
        signature="Z(q)",
        params=(_qbit("q", "Target qubit"),),
        returns="void",
        category="gate",
        min_args=1,
        max_args=1,
    ),
    FunctionSummary(
        name="S",
        summary="S gate (phase π/2).",
        signature="S(q)",
        params=(_qbit("q", "Target qubit"),),
        returns="void",
        category="gate",
        min_args=1,
        max_args=1,
    ),
    FunctionSummary(
        name="CNot",
        summary="Controlled-NOT gate.",
        signature="CNot(control, target)",
        params=(
            _qbit("control", "Control qubit"),
            _qbit("target", "Target qubit"),
        ),
        returns="void",
        category="gate",
        min_args=2,
        max_args=2,
    ),
    FunctionSummary(
        name="CZ",
        summary="Controlled-Z gate.",
        signature="CZ(control, target)",
        params=(
            _qbit("control", "Control qubit"),
            _qbit("target", "Target qubit"),
        ),
        returns="void",
        category="gate",
        min_args=2,
        max_args=2,
    ),
    FunctionSummary(
        name="Swap",
        summary="Swap gate.",
        signature="Swap(a, b)",
        params=(
            _qbit("a", "First qubit"),
            _qbit("b", "Second qubit"),
        ),
        returns="void",
        category="gate",
        min_args=2,
        max_args=2,
    ),
    FunctionSummary(
        name="RZ",
        summary="Rotation around Z axis.",
        signature="RZ(angle, q)",
        params=(
            FunctionParam("angle", "float | expr", "Rotation angle in radians"),
            _qbit("q", "Target qubit"),
        ),
        returns="void",
        category="gate",
        min_args=2,
        max_args=2,
    ),
    FunctionSummary(
        name="RY",
        summary="Rotation around Y axis.",
        signature="RY(angle, q)",
        params=(
            FunctionParam("angle", "float | expr", "Rotation angle in radians"),
            _qbit("q", "Target qubit"),
        ),
        returns="void",
        category="gate",
        min_args=2,
        max_args=2,
    ),
    FunctionSummary(
        name="RX",
        summary="Rotation around X axis.",
        signature="RX(angle, q)",
        params=(
            FunctionParam("angle", "float | expr", "Rotation angle in radians"),
            _qbit("q", "Target qubit"),
        ),
        returns="void",
        category="gate",
        min_args=2,
        max_args=2,
    ),
    FunctionSummary(
        name="CCX",
        summary="Toffoli (CCNOT) gate.",
        signature="CCX(c1, c2, target)",
        params=(
            _qbit("c1", "First control qubit"),
            _qbit("c2", "Second control qubit"),
            _qbit("target", "Target qubit"),
        ),
        returns="void",
        category="gate",
        min_args=3,
        max_args=3,
    ),
    FunctionSummary(
        name="Measure",
        summary="Measure qubit(s) into classical bit(s).",
        signature="Measure(q, c)",
        params=(
            FunctionParam("q", "qbit / qbit[]", "Quantum register or indexed qubit"),
            FunctionParam("c", "bit / bit[]", "Classical register or indexed bit"),
        ),
        returns="void",
        category="gate",
        min_args=2,
        max_args=2,
        notes=("ctrl and inv modifiers are not allowed on Measure.",),
    ),
)

# --- Standard library ---------------------------------------------------------

_register(
    FunctionSummary(
        name="Print",
        summary="Print a value to the frontend simulator output (statevector only).",
        signature="Print(value)",
        params=(
            FunctionParam(
                "value",
                "any",
                "Classical value, quantum register, or f-string with format specifiers",
            ),
        ),
        returns="void",
        category="stdlib",
        min_args=1,
        notes=(
            "Frontend simulator only; does not run on hardware backends.",
            "Use f-strings for format specifiers, e.g. Print(f\"{q:summary}\").",
        ),
    ),
    FunctionSummary(
        name="len",
        summary="Return the size of a register or array (compile-time).",
        signature="len(x)",
        params=(
            FunctionParam("x", "qbit[] | bit[] | list | tensor", "Register or collection"),
        ),
        returns="int",
        category="stdlib",
        min_args=1,
        max_args=1,
    ),
    FunctionSummary(
        name="range",
        summary="Generate a compile-time integer range for for-loops.",
        signature="range(end) | range(start, end) | range(start, step, end)",
        params=(
            FunctionParam("start", "int", "Start index (default 0)"),
            FunctionParam("step", "int", "Step size (default 1)"),
            FunctionParam("end", "int", "End index (exclusive)"),
        ),
        returns="list[int]",
        category="stdlib",
        min_args=1,
        max_args=3,
    ),
    FunctionSummary(
        name="reset",
        summary="Reset qubit(s) to |0⟩.",
        signature="reset(q)",
        params=(
            FunctionParam("q", "qbit / qbit[]", "Qubit or register to reset"),
        ),
        returns="void",
        category="stdlib",
        min_args=1,
        max_args=1,
    ),
    FunctionSummary(
        name="int",
        summary="Convert a value to an integer (compile-time).",
        signature="int(x)",
        params=(
            FunctionParam("x", "float | expr", "Value to convert"),
        ),
        returns="int",
        category="stdlib",
        min_args=1,
        max_args=1,
    ),
    FunctionSummary(
        name="assert",
        summary="Compile-time assertion; fails compilation if condition is false.",
        signature="assert(condition)",
        params=(
            FunctionParam("condition", "bool | expr", "Condition that must be true"),
        ),
        returns="void",
        category="stdlib",
        min_args=1,
        max_args=1,
    ),
    FunctionSummary(
        name="error",
        summary="Emit a compile-time error and stop compilation.",
        signature='error("message")',
        params=(
            FunctionParam("message", "str", "Error message"),
        ),
        returns="void",
        category="stdlib",
        min_args=1,
        max_args=1,
    ),
    FunctionSummary(
        name="warn",
        summary="Emit a compile-time warning without stopping compilation.",
        signature='warn("message")',
        params=(
            FunctionParam("message", "str", "Warning message"),
        ),
        returns="void",
        category="stdlib",
        min_args=1,
        max_args=1,
    ),
    FunctionSummary(
        name="sin",
        summary="Sine function (compile-time / classical).",
        signature="sin(x)",
        params=(FunctionParam("x", "float | expr", "Angle in radians"),),
        returns="float",
        category="stdlib",
        min_args=1,
        max_args=1,
    ),
    FunctionSummary(
        name="cos",
        summary="Cosine function (compile-time / classical).",
        signature="cos(x)",
        params=(FunctionParam("x", "float | expr", "Angle in radians"),),
        returns="float",
        category="stdlib",
        min_args=1,
        max_args=1,
    ),
    FunctionSummary(
        name="acos",
        summary="Inverse cosine (compile-time / classical).",
        signature="acos(x)",
        params=(FunctionParam("x", "float | expr", "Value in [-1, 1]"),),
        returns="float",
        category="stdlib",
        min_args=1,
        max_args=1,
    ),
    FunctionSummary(
        name="arccos",
        summary="Alias for acos.",
        signature="arccos(x)",
        params=(FunctionParam("x", "float | expr", "Value in [-1, 1]"),),
        returns="float",
        category="stdlib",
        min_args=1,
        max_args=1,
    ),
    FunctionSummary(
        name="Fidelity",
        summary="Compute state fidelity between two quantum registers (frontend simulator only).",
        signature="Fidelity(a, b)",
        params=(
            FunctionParam("a", "qbit[] | qint[n]", "First quantum register"),
            FunctionParam("b", "qbit[] | qint[n]", "Second register (same width as a)"),
        ),
        returns="float",
        category="stdlib",
        min_args=2,
        max_args=2,
        notes=("Frontend simulator only.",),
    ),
)

# --- Tensor algebra (classical / frontend) ------------------------------------

_register(
    FunctionSummary(
        name="Shape",
        summary="Return the shape tuple of a tensor.",
        signature="Shape(tensor)",
        params=(
            FunctionParam("tensor", "tensor", "Classical tensor"),
        ),
        returns="tuple[int, ...]",
        category="tensor",
        min_args=1,
        max_args=1,
    ),
    FunctionSummary(
        name="Reshape",
        summary="Reshape a tensor to new dimensions (frontend simulator).",
        signature="Reshape(tensor, d1, d2, ...)",
        params=(
            FunctionParam("tensor", "tensor", "Source tensor"),
            FunctionParam("dims", "int...", "New dimension sizes"),
        ),
        returns="tensor",
        category="tensor",
        min_args=2,
    ),
    FunctionSummary(
        name="DotProduct",
        summary="Dot product of two equal-length vectors.",
        signature="DotProduct(a, b)",
        params=(
            FunctionParam("a", "tensor", "First vector"),
            FunctionParam("b", "tensor", "Second vector (same length as a)"),
        ),
        returns="scalar",
        category="tensor",
        min_args=2,
        max_args=2,
    ),
    FunctionSummary(
        name="CrossProduct",
        summary="Cross product of two 3D vectors.",
        signature="CrossProduct(a, b)",
        params=(
            FunctionParam("a", "float[3]", "First 3-vector"),
            FunctionParam("b", "float[3]", "Second 3-vector"),
        ),
        returns="float[3]",
        category="tensor",
        min_args=2,
        max_args=2,
    ),
    FunctionSummary(
        name="ElementwiseProduct",
        summary="Elementwise (Hadamard) product of two tensors with identical shape.",
        signature="ElementwiseProduct(a, b)",
        params=(
            FunctionParam("a", "tensor", "First tensor"),
            FunctionParam("b", "tensor", "Second tensor (same shape as a)"),
        ),
        returns="tensor",
        category="tensor",
        min_args=2,
        max_args=2,
    ),
    FunctionSummary(
        name="TensorProduct",
        summary="Kronecker (tensor) product of two tensors.",
        signature="TensorProduct(a, b)",
        params=(
            FunctionParam("a", "tensor", "First tensor"),
            FunctionParam("b", "tensor", "Second tensor"),
        ),
        returns="tensor",
        category="tensor",
        min_args=2,
        max_args=2,
    ),
)


def get_function_summary(name: str) -> Optional[FunctionSummary]:
    """Return documentation for a built-in by name, or None if unknown."""
    return FUNCTION_SUMMARIES.get(name)


def list_function_summaries(
    category: Optional[str] = None,
) -> List[FunctionSummary]:
    """Return all registered summaries, optionally filtered by category."""
    docs = list(FUNCTION_SUMMARIES.values())
    if category is not None:
        docs = [d for d in docs if d.category == category]
    return sorted(docs, key=lambda d: d.name)


def get_function_docs_dict() -> Dict[str, Dict[str, object]]:
    """Return all summaries as a JSON-serializable dict keyed by function name."""
    return {name: doc.to_dict() for name, doc in FUNCTION_SUMMARIES.items()}
