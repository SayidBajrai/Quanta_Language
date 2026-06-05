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
    
    def compile(self, source: str, keep_structure: bool = False) -> str:
        """
        Compile Quanta source to OpenQASM 3.
        
        Pipeline:
        1. Lexical analysis
        2. Parsing
        3. AST transformation (operator overloading, etc.)
        4. Semantic analysis
        5. Code generation
        """
        try:
            # Lexical analysis
            tokens = self.lexer.tokenize(source)
            
            # Parsing
            ast = self.parser.parse(tokens)
            
            # AST transformation (desugaring operator overloading)
            ast = self.transformer.transform(ast)
            
            # Semantic analysis
            self.semantic_analyzer.analyze(ast, keep_structure=keep_structure)

            # Desugar fancy indexing (q[0,2,5], q[0:4,7], etc.)
            registers = collect_registers(ast)
            ast = IndexExpander(registers).expand_program(ast)
            
            # Code generation
            if keep_structure:
                qasm = self.structured_codegen.generate(ast)
            else:
                qasm = self.codegen.generate(ast)
            
            return qasm
        except Exception as e:
            if isinstance(e, QuantaError):
                raise
            # Wrap unexpected errors
            raise QuantaCompilationError(f"Unexpected compilation error: {str(e)}") from e
