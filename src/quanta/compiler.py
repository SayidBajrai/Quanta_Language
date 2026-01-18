"""
Main compiler pipeline
"""

from .lexer.lexer import Lexer
from .parser.parser import Parser
from .sema.validation import SemanticAnalyzer
from .sema.transform import ASTTransformer
from .lower.qasm3 import QASM3Generator
from .errors import QuantaError, QuantaCompilationError


class Compiler:
    """Main compiler class that orchestrates the compilation pipeline"""
    
    def __init__(self):
        self.lexer = Lexer()
        self.parser = Parser()
        self.transformer = ASTTransformer()
        self.semantic_analyzer = SemanticAnalyzer()
        self.codegen = QASM3Generator()
    
    def compile(self, source: str) -> str:
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
            self.semantic_analyzer.analyze(ast)
            
            # Code generation
            qasm = self.codegen.generate(ast)
            
            return qasm
        except Exception as e:
            if isinstance(e, QuantaError):
                raise
            # Wrap unexpected errors
            raise QuantaCompilationError(f"Unexpected compilation error: {str(e)}") from e
