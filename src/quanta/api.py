"""
Public API for Quanta compiler
"""

from typing import Dict, Any, Optional, List
from .compiler import Compiler
from .stdlib.builtins import FunctionSummary, get_function_docs_dict, get_function_summary, list_function_summaries
from .analysis.report import AnalysisReport


def compile(source: str, keep_structure: bool = False,
            depth_reduction: bool = False, optimize_target: str = "",
            analyze: bool = False) -> Any:
    """
    Compile Quanta source code to OpenQASM 3.

    Args:
        source: Quanta source code as a string
        keep_structure: When True, emit structured OpenQASM with ``def``/``gate``
            definitions and preserved control flow.
        depth_reduction: When True, run gate fusion, commutation, and depth reduction
            optimization passes on the IR before code generation.
        optimize_target: Target hardware backend for native gate lowering
            (e.g. ``"ibm_brisbane"``, ``"ionq_aria"``).
        analyze: When True, return a CompileResult with both QASM and metrics.

    Returns:
        OpenQASM 3 code as a string, or CompileResult if analyze=True
    """
    compiler = Compiler()

    if analyze or depth_reduction or optimize_target:
        circuit = compiler.build_ir(source)
        if depth_reduction or optimize_target:
            from .ir.optimizer import optimize as optimize_ir
            circuit = optimize_ir(circuit, depth_reduction=depth_reduction,
                                   hardware_target=optimize_target)
        qasm = compiler._emit_qasm_from_ir(circuit, keep_structure)
        if analyze:
            report = AnalysisReport.from_circuit(circuit)
            return CompileResult(qasm, report)
        return qasm

    return compiler.compile(source, keep_structure=keep_structure,
                            depth_reduction=depth_reduction,
                            optimize_target=optimize_target)


class CompileResult:
    """Result of compilation with analysis enabled."""

    def __init__(self, qasm: str, metrics: AnalysisReport):
        self.qasm = qasm
        self.metrics = metrics

    def __repr__(self) -> str:
        return f"CompileResult(qasm=..., metrics={self.metrics})"


def analyze(source: str, hardware_backends: Optional[List[str]] = None) -> AnalysisReport:
    """
    Analyze Quanta source code and return resource estimation metrics.

    Builds the IR, expands all macros, and performs gate counting, depth
    estimation, T-count analysis, and hardware backend fitting.

    Args:
        source: Quanta source code as a string
        hardware_backends: Optional list of backend names to check fit against
            (e.g. ``["ibm_brisbane", "ionq_aria"]``).

    Returns:
        AnalysisReport with resource metrics
    """
    compiler = Compiler()
    circuit = compiler.build_ir(source)
    return AnalysisReport.from_circuit(circuit, hardware_backends=hardware_backends)


def run(source: str, shots: int = 1024, backend: Optional[str] = None,
        noisy: bool = False,
        depolarizing: float = 0.0, readout_error: float = 0.0,
        t1: Optional[float] = None, t2: Optional[float] = None) -> Dict[str, Any]:
    """
    Compile and run Quanta source code.

    Args:
        source: Quanta source code as a string
        shots: Number of measurement shots
        backend: Qiskit backend name (default: 'qasm_simulator')
        noisy: When True, build a noise model from parameters or from NoiseModel
            declaration in source code.
        depolarizing: Depolarizing error rate (0.0 to 1.0)
        readout_error: Readout error rate (0.0 to 1.0)
        t1: T1 relaxation time in microseconds
        t2: T2 dephasing time in microseconds

    Returns:
        Dictionary with measurement results
    """
    from .runtime.qiskit import run_circuit as _run_circuit

    qasm = compile(source)

    if not noisy:
        return _run_circuit(qasm, shots=shots, backend=backend)

    from .ir.noise import NoiseModel
    noise_model = NoiseModel(
        depolarizing=depolarizing,
        readout=readout_error,
        t1_us=t1,
        t2_us=t2,
    )

    parsed_noise = _extract_noisemodel_from_source(source)
    if parsed_noise is not None:
        if parsed_noise.depolarizing > 0:
            noise_model.depolarizing = parsed_noise.depolarizing
        if parsed_noise.readout > 0:
            noise_model.readout = parsed_noise.readout
        if parsed_noise.t1_us is not None:
            noise_model.t1_us = parsed_noise.t1_us
        if parsed_noise.t2_us is not None:
            noise_model.t2_us = parsed_noise.t2_us
        if parsed_noise.gate_error_1q > 0:
            noise_model.gate_error_1q = parsed_noise.gate_error_1q
        if parsed_noise.gate_error_2q > 0:
            noise_model.gate_error_2q = parsed_noise.gate_error_2q

    if not noise_model.is_noisy():
        return _run_circuit(qasm, shots=shots, backend=backend)

    return _run_circuit(qasm, shots=shots, backend=backend, noise_model=noise_model)


def _extract_noisemodel_from_source(source: str):
    try:
        from .lexer.lexer import Lexer
        from .parser.parser import Parser
        from .ast.nodes import NoiseModelDecl
        from .ir.noise import NoiseModel

        ast = Parser().parse(Lexer().tokenize(source))
        for stmt in ast.statements:
            if isinstance(stmt, NoiseModelDecl):
                return NoiseModel.from_quanta(stmt.params)
    except Exception:
        pass
    return None


def get_prints(quanta_code: str) -> str:
    from .runtime import frontend_sim
    return frontend_sim.get_prints(quanta_code)


def get_user_function_docs(
    source: str, name: Optional[str] = None
) -> Dict[str, Any] | FunctionSummary | None:
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
    return list_function_summaries(category)
