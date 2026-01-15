"""
Error classes for Quanta compiler
"""


class QuantaError(Exception):
    """Base exception for all Quanta errors"""
    
    def __init__(self, message: str, line: int = None, column: int = None):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(self._format_message())
    
    def _format_message(self) -> str:
        msg = self.message
        if self.line is not None:
            msg += f" (line {self.line}"
            if self.column is not None:
                msg += f", column {self.column}"
            msg += ")"
        return msg


class QuantaSyntaxError(QuantaError):
    """Syntax error during parsing"""
    pass


class QuantaTypeError(QuantaError):
    """Type error during semantic analysis"""
    pass


class QuantaSemanticError(QuantaError):
    """Semantic error (e.g., undefined variable, invalid quantum operation)"""
    pass


class QuantaCompilationError(QuantaError):
    """General compilation error"""
    pass
