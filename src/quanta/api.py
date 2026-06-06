"""
Public API for Quanta compiler
"""

from typing import Dict, Any, Optional, List
from .compiler import Compiler
from .stdlib.builtins import FunctionSummary, get_function_docs_dict, get_function_summary, list_function_summaries


def compile(source: str, keep_structure: bool = False) -> str:
    """
    Compile Quanta source code to OpenQASM 3.
    
    Args:
        source: Quanta source code as a string
        keep_structure: When True, emit structured OpenQASM with ``def``/``gate``
            definitions and preserved control flow instead of fully flattening
            arithmetic and discarding function structure.
        
    Returns:
        OpenQASM 3 code as a string
        
    Raises:
        QuantaError: If compilation fails
    """
    compiler = Compiler()
    return compiler.compile(source, keep_structure=keep_structure)


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
    from .runtime.qiskit import run_circuit

    qasm = compile(source)
    return run_circuit(qasm, shots=shots, backend=backend)


def get_prints(quanta_code: str) -> str:
    """
    Parse Quanta source, run in statevector simulator, and return the string
    that would be printed by all Print() calls.

    **Frontend Debug Execution Only. Not compatible with hardware backend.**
    Real quantum hardware cannot reveal amplitudes; this is statevector simulation only.

    - Print(classical): immediate evaluation, append to output.
    - Print(quantum): inspect statevector, append symbolic summary (no state collapse).
    - Entangled subsystems: full state is shown with a note.

    Raises:
        RuntimeError: If total qbits > 20 (simulation limit).
        QuantaError: On parse/semantic errors.

    Returns:
        Terminal output as a single string (lines joined by newline).
    """
    from .runtime import frontend_sim

    return frontend_sim.get_prints(quanta_code)


def get_user_function_docs(
    source: str, name: Optional[str] = None
) -> Dict[str, Any] | FunctionSummary | None:
    """
    Return documentation extracted from user ``///`` comments on ``func`` and ``gate`` declarations.

    Args:
        source: Quanta source code containing documented declarations.
        name: Optional function or gate name. When omitted, returns a dict of all
            user-defined summaries keyed by name.

    Returns:
        If ``name`` is given: a :class:`~quanta.stdlib.builtins.FunctionSummary`, or
        ``None`` if no documented declaration with that name exists in ``source``.
        If ``name`` is omitted: a JSON-serializable ``dict`` mapping names to summary
        objects (each includes ``hover``).
    """
    from .lexer.lexer import Lexer
    from .parser.parser import Parser
    from .docs.extract import extract_docs_from_ast

    ast = Parser().parse(Lexer().tokenize(source))
    docs = extract_docs_from_ast(ast)
    if name is None:
        return {entry_name: summary.to_dict() for entry_name, summary in docs.items()}
    return docs.get(name)


def get_function_docs(
    name: Optional[str] = None,
    source: Optional[str] = None,
) -> Dict[str, Any] | FunctionSummary | None:
    """
    Return built-in / stdlib function documentation for IDE hover and completion.

    Args:
        name: Function name (e.g. ``"QAdd"``, ``"Print"``). When omitted, returns
            a dict of all registered summaries keyed by name.
        source: Optional Quanta source. When ``name`` is not a built-in, user ``///``
            documentation is extracted from this source as a fallback.

    Returns:
        If ``name`` is given: a :class:`~quanta.stdlib.builtins.FunctionSummary`, or
        ``None`` if the name is not a known built-in (or user-defined in ``source``).
        If ``name`` is omitted: a JSON-serializable ``dict`` mapping names to
        summary objects (each includes ``signature``, ``summary``, ``params``,
        ``returns``, and a pre-rendered ``hover`` string).
    """
    if name is None:
        return get_function_docs_dict()
    builtin = get_function_summary(name)
    if builtin is not None:
        return builtin
    if source is not None:
        user_doc = get_user_function_docs(source, name)
        if isinstance(user_doc, FunctionSummary):
            return user_doc
    return None


def list_functions(category: Optional[str] = None) -> List[FunctionSummary]:
    """
    List all documented built-in / stdlib functions.

    Args:
        category: Optional filter — ``"gate"``, ``"high_level_gate"``,
            ``"quantum_arithmetic"``, ``"stdlib"``, or ``"tensor"``.

    Returns:
        Sorted list of :class:`~quanta.stdlib.builtins.FunctionSummary` entries.
    """
    return list_function_summaries(category)
