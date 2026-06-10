"""
Lexer for Quanta language
"""

import re
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass


class TokenType(Enum):
    """Token types"""
    # Keywords
    FUNC = "FUNC"
    CLASS = "CLASS"
    VAR = "VAR"
    CONST = "CONST"
    LET = "LET"
    GATE = "GATE"
    QBIT = "QBIT"
    BIT = "BIT"
    FOR = "FOR"
    WHILE = "WHILE"
    IF = "IF"
    ELSE = "ELSE"
    RETURN = "RETURN"
    IN = "IN"
    CTRL = "CTRL"
    INV = "INV"
    NOISEMODEL = "NOISEMODEL"
    
    # Types
    INT = "INT"
    FLOAT = "FLOAT"
    BOOL = "BOOL"
    STR = "STR"
    LIST = "LIST"
    DICT = "DICT"
    QVAR = "QVAR"
    CVAR = "CVAR"
    QINT = "QINT"
    QUINT = "QUINT"
    BINT = "BINT"
    QDEC = "QDEC"
    QUDEC = "QUDEC"
    QFLOAT = "QFLOAT"
    QREAL = "QREAL"
    UINT = "UINT"
    DEC = "DEC"
    UDEC = "UDEC"
    
    # Literals
    IDENT = "IDENT"
    NUMBER = "NUMBER"
    STRING = "STRING"
    FSTRING = "FSTRING"
    BOOLEAN = "BOOLEAN"
    
    # Operators
    EQ = "="
    EQEQ = "=="
    NE = "!="
    LE = "<="
    GE = ">="
    LT = "<"
    GT = ">"
    AND = "&&"
    OR = "||"
    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    PERCENT = "%"
    DOT = "."
    HADAMARD = "⊙"
    KRON = "⊗"
    
    # Delimiters
    LBRACE = "{"
    RBRACE = "}"
    LPAREN = "("
    RPAREN = ")"
    LBRACKET = "["
    RBRACKET = "]"
    COMMA = ","
    COLON = ":"
    SEMICOLON = ";"
    
    # Special
    EOF = "EOF"
    NEWLINE = "NEWLINE"
    DOC_COMMENT = "DOC_COMMENT"


@dataclass
class Token:
    """Represents a token"""
    type: TokenType
    value: str
    line: int
    column: int


class Lexer:
    """Tokenizes Quanta source code"""
    
    KEYWORDS = {
        "func": TokenType.FUNC,
        "class": TokenType.CLASS,
        "var": TokenType.VAR,
        "qvar": TokenType.QVAR,
        "cvar": TokenType.CVAR,
        "const": TokenType.CONST,
        "let": TokenType.LET,
        "gate": TokenType.GATE,
        "qbit": TokenType.QBIT,
        "bit": TokenType.BIT,
        "qint": TokenType.QINT,
        "quint": TokenType.QUINT,
        "bint": TokenType.BINT,
        "qdec": TokenType.QDEC,
        "qudec": TokenType.QUDEC,
        "qfloat": TokenType.QFLOAT,
        "qreal": TokenType.QREAL,
        "uint": TokenType.UINT,
        "dec": TokenType.DEC,
        "udec": TokenType.UDEC,
        "for": TokenType.FOR,
        "while": TokenType.WHILE,
        "if": TokenType.IF,
        "else": TokenType.ELSE,
        "return": TokenType.RETURN,
        "in": TokenType.IN,
        "ctrl": TokenType.CTRL,
        "inv": TokenType.INV,
        "NoiseModel": TokenType.NOISEMODEL,
        "int": TokenType.INT,
        "float": TokenType.FLOAT,
        "bool": TokenType.BOOL,
        "str": TokenType.STR,
        "list": TokenType.LIST,
        "dict": TokenType.DICT,
        "true": TokenType.BOOLEAN,
        "false": TokenType.BOOLEAN,
    }
    
    def __init__(self):
        self.source = ""
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
    
    def tokenize(self, source: str) -> List[Token]:
        """Tokenize source code"""
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens = []
        
        while not self._is_at_end():
            self._skip_whitespace()
            if self._is_at_end():
                break
            
            if self._match("///"):
                self.tokens.append(self._doc_comment())
                continue

            if self._match("//"):
                self._skip_line_comment()
                continue
            
            token = self._scan_token()
            if token:
                self.tokens.append(token)
        
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return self.tokens
    
    def _scan_token(self) -> Optional[Token]:
        """Scan a single token"""
        char = self._advance()
        start_line = self.line
        start_col = self.column - 1
        
        # Single character tokens
        if char == "{":
            return self._make_token(TokenType.LBRACE, "{")
        elif char == "}":
            return self._make_token(TokenType.RBRACE, "}")
        elif char == "(":
            return self._make_token(TokenType.LPAREN, "(")
        elif char == ")":
            return self._make_token(TokenType.RPAREN, ")")
        elif char == "[":
            return self._make_token(TokenType.LBRACKET, "[")
        elif char == "]":
            return self._make_token(TokenType.RBRACKET, "]")
        elif char == ",":
            return self._make_token(TokenType.COMMA, ",")
        elif char == ":":
            return self._make_token(TokenType.COLON, ":")
        elif char == ";":
            return self._make_token(TokenType.SEMICOLON, ";")
        elif char == "+":
            return self._make_token(TokenType.PLUS, "+")
        elif char == "-":
            return self._make_token(TokenType.MINUS, "-")
        elif char == "*":
            return self._make_token(TokenType.STAR, "*")
        elif char == "/":
            return self._make_token(TokenType.SLASH, "/")
        elif char == ".":
            if self._peek().isdigit():
                return self._number(".")
            return self._make_token(TokenType.DOT, ".")
        elif char == "⊙":
            return self._make_token(TokenType.HADAMARD, "⊙")
        elif char == "⊗":
            return self._make_token(TokenType.KRON, "⊗")
        elif char == "%":
            return self._make_token(TokenType.PERCENT, "%")
        elif char == "=":
            if self._match("="):
                return self._make_token(TokenType.EQEQ, "==")
            return self._make_token(TokenType.EQ, "=")
        elif char == "!":
            if self._match("="):
                return self._make_token(TokenType.NE, "!=")
        elif char == "<":
            if self._match("="):
                return self._make_token(TokenType.LE, "<=")
            return self._make_token(TokenType.LT, "<")
        elif char == ">":
            if self._match("="):
                return self._make_token(TokenType.GE, ">=")
            return self._make_token(TokenType.GT, ">")
        elif char == "&":
            if self._match("&"):
                return self._make_token(TokenType.AND, "&&")
        elif char == "|":
            if self._match("|"):
                return self._make_token(TokenType.OR, "||")
        elif char == "\n":
            return self._make_token(TokenType.NEWLINE, "\n")
        elif char == "f" and self._peek() == '"':
            self._advance()  # consume opening quote
            return self._string(token_type=TokenType.FSTRING)
        elif char == '"':
            return self._string()
        elif char.isdigit():
            return self._number(char)
        elif char.isalpha() or char == "_":
            return self._identifier(char)
        
        return None
    
    _ESCAPE_CHARS = {
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "a": "\a",
        "b": "\b",
        "f": "\f",
        "v": "\v",
        "0": "\0",
        "\\": "\\",
        '"': '"',
        "'": "'",
        "{": "{",
        "}": "}",
    }

    def _read_hex_digits(self, count: int, line: int, column: int) -> str:
        """Read exactly `count` hexadecimal digits for \\x / \\u / \\U escapes."""
        from ..errors import QuantaSyntaxError

        digits = ""
        for _ in range(count):
            if self._is_at_end() or self._peek().lower() not in "0123456789abcdef":
                raise QuantaSyntaxError("Invalid hex escape sequence", line, column)
            digits += self._advance()
        return digits

    def _decode_string_escape(self) -> str:
        """Decode a backslash escape sequence; the backslash is already consumed."""
        from ..errors import QuantaSyntaxError

        if self._is_at_end():
            raise QuantaSyntaxError("Incomplete escape sequence", self.line, self.column)

        esc_line = self.line
        esc_col = self.column
        ch = self._advance()
        if ch in self._ESCAPE_CHARS:
            return self._ESCAPE_CHARS[ch]
        if ch == "x":
            code = int(self._read_hex_digits(2, esc_line, esc_col), 16)
            return chr(code)
        if ch == "u":
            code = int(self._read_hex_digits(4, esc_line, esc_col), 16)
            return chr(code)
        if ch == "U":
            code = int(self._read_hex_digits(8, esc_line, esc_col), 16)
            return chr(code)
        raise QuantaSyntaxError(f"Unknown escape sequence \\{ch}", esc_line, esc_col)

    def _string(self, token_type: TokenType = TokenType.STRING) -> Token:
        """Scan a string or f-string literal."""
        start_line = self.line
        start_col = self.column - 1
        value = ""

        while self._peek() != '"' and not self._is_at_end():
            if self._peek() == "\\":
                self._advance()
                value += self._decode_string_escape()
                continue
            if self._peek() == "\n":
                self.line += 1
                self.column = 0
            value += self._advance()

        if self._is_at_end():
            from ..errors import QuantaSyntaxError
            raise QuantaSyntaxError("Unterminated string", start_line, start_col)

        self._advance()  # Consume closing quote
        return Token(token_type, value, start_line, start_col)
    
    def _number(self, first_char: str = "") -> Token:
        """Scan a number literal"""
        start_line = self.line
        start_col = self.column - 1
        value = first_char  # Include the first character that was already advanced
        
        while self._peek().isdigit():
            value += self._advance()
        
        if self._peek() == "." and self._peek_next().isdigit():
            value += self._advance()
            while self._peek().isdigit():
                value += self._advance()
        
        return Token(TokenType.NUMBER, value, start_line, start_col)
    
    def _identifier(self, first_char: str = "") -> Token:
        """Scan an identifier or keyword"""
        start_line = self.line
        start_col = self.column - 1
        value = first_char  # Include the first character that was already advanced
        
        while self._peek().isalnum() or self._peek() == "_":
            value += self._advance()
        
        token_type = self.KEYWORDS.get(value, TokenType.IDENT)
        if token_type == TokenType.BOOLEAN:
            return Token(TokenType.BOOLEAN, value, start_line, start_col)
        
        return Token(token_type, value, start_line, start_col)
    
    def _skip_whitespace(self):
        """Skip whitespace characters"""
        while not self._is_at_end():
            char = self._peek()
            if char in " \t\r":
                self._advance()
            else:
                break
    
    def _skip_line_comment(self):
        """Skip a line comment"""
        while self._peek() != "\n" and not self._is_at_end():
            self._advance()

    def _doc_comment(self) -> Token:
        """Scan a documentation comment (/// ...) and emit a DOC_COMMENT token."""
        start_line = self.line
        start_col = self.column - 3
        text = ""
        while self._peek() != "\n" and not self._is_at_end():
            text += self._advance()
        if text.startswith(" "):
            text = text[1:]
        return Token(TokenType.DOC_COMMENT, text, start_line, start_col)
    
    def _advance(self) -> str:
        """Advance position and return character"""
        if self._is_at_end():
            return "\0"
        char = self.source[self.pos]
        self.pos += 1
        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char
    
    def _peek(self) -> str:
        """Peek at current character"""
        if self._is_at_end():
            return "\0"
        return self.source[self.pos]
    
    def _peek_next(self) -> str:
        """Peek at next character"""
        if self.pos + 1 >= len(self.source):
            return "\0"
        return self.source[self.pos + 1]
    
    def _match(self, expected: str) -> bool:
        """Match and consume if expected"""
        if self._is_at_end():
            return False
        if self.source[self.pos : self.pos + len(expected)] != expected:
            return False
        for _ in expected:
            self._advance()
        return True
    
    def _is_at_end(self) -> bool:
        """Check if at end of source"""
        return self.pos >= len(self.source)
    
    def _make_token(self, token_type: TokenType, value: str) -> Token:
        """Create a token"""
        return Token(token_type, value, self.line, self.column - len(value))
