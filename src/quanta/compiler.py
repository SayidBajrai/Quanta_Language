"""
Main compiler pipeline
"""

from .lexer.lexer import Lexer
from .parser.parser import Parser
from .sema.validation import SemanticAnalyzer
from .sema.transform import ASTTransformer
from .sema.indexing import IndexExpander, collect_registers
from .lower.qasm3 import QASM3Generator
from .lower.qasm3_structured import StructuredQASMGenerator
from .ir.builder import IRBuilder
from .ir.ir_nodes import QCircuit
from .ir.optimizer import optimize as optimize_ir
from .errors import QuantaError, QuantaCompilationError


class Compiler:
    """Main compiler class that orchestrates the compilation pipeline"""

    def __init__(self):
        self.lexer = Lexer()
        self.parser = Parser()
        self.transformer = ASTTransformer()
        self.semantic_analyzer = SemanticAnalyzer()
        self.codegen = QASM3Generator()
        self.structured_codegen = StructuredQASMGenerator()
        self.ir_builder = IRBuilder()

    def compile(self, source: str, keep_structure: bool = False,
                depth_reduction: bool = False, optimize_target: str = "") -> str:
        try:
            tokens = self.lexer.tokenize(source)
            ast = self.parser.parse(tokens)
            ast = self.transformer.transform(ast)
            self.semantic_analyzer.analyze(ast, keep_structure=keep_structure)

            registers = collect_registers(ast)
            ast = IndexExpander(registers).expand_program(ast)

            if depth_reduction or optimize_target:
                circuit = self.ir_builder.build(ast)
                circuit = optimize_ir(circuit, depth_reduction=depth_reduction,
                                      hardware_target=optimize_target)
                qasm = self._emit_qasm_from_ir(circuit, keep_structure)
            elif keep_structure:
                qasm = self.structured_codegen.generate(ast)
            else:
                qasm = self.codegen.generate(ast)

            return qasm
        except Exception as e:
            if isinstance(e, QuantaError):
                raise
            raise QuantaCompilationError(f"Unexpected compilation error: {str(e)}") from e

    def build_ir(self, source: str) -> QCircuit:
        try:
            tokens = self.lexer.tokenize(source)
            ast = self.parser.parse(tokens)
            ast = self.transformer.transform(ast)
            self.semantic_analyzer.analyze(ast, keep_structure=False)
            registers = collect_registers(ast)
            ast = IndexExpander(registers).expand_program(ast)
            return self.ir_builder.build(ast)
        except Exception as e:
            if isinstance(e, QuantaError):
                raise
            raise QuantaCompilationError(f"Unexpected compilation error: {str(e)}") from e

    def _emit_qasm_from_ir(self, circuit: QCircuit, keep_structure: bool = False) -> str:
        lines = ["OPENQASM 3;", 'include "stdgates.inc";', ""]
        for reg in circuit.registers:
            if reg.name.startswith("__qarith"):
                lines.append(f"qubit[{reg.total_qubits}] {reg.name};")
            else:
                kind = "qubit" if reg.kind in ("qbit", "qint", "quint", "qdec", "qudec", "qfloat", "qreal") else "bit"
                lines.append(f"{kind}[{reg.total_qubits}] {reg.name};")
        lines.append("")
        for g in circuit.gates:
            line = self._gate_to_qasm(g, circuit)
            if line:
                lines.append(line)
        return "\n".join(lines)

    def _gate_to_qasm(self, g, circuit) -> str:
        if g.name == "_remove":
            return ""
        qubit_strs = []
        for q in g.qubits:
            qubit_strs.append(f"$q{q}")
        for c in g.ctrl_qubits:
            qubit_strs.append(f"$c{c}")
        qubits = ", ".join(qubit_strs)
        for reg in circuit.registers:
            for i in range(reg.total_qubits):
                q_idx = reg.start_index + i
                qubits = qubits.replace(f"$q{q_idx}", f"{reg.name}[{i}]")
                qubits = qubits.replace(f"$c{q_idx}", f"{reg.name}[{i}]")

        prefix = ""
        if g.is_inverse:
            prefix = "inv @ "
        if g.ctrl_qubits:
            prefix = f"ctrl[{len(g.ctrl_qubits)}] @ " + prefix

        if g.is_measure:
            return f"measure {qubits} -> {qubits};"
        if g.name == "reset":
            return f"reset {qubits};"

        if g.params:
            param_str = ", ".join(f"{p:.10g}" for p in g.params)
            return f"{prefix}{g.name}({param_str}) {qubits};"
        return f"{prefix}{g.name} {qubits};"
