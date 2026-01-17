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
    QUBIT = "QUBIT"
    BIT = "BIT"
    FOR = "FOR"
    IF = "IF"
    ELSE = "ELSE"
    RETURN = "RETURN"
    IN = "IN"
    CTRL = "CTRL"
    INV = "INV"
    
    # Types
    INT = "INT"
    FLOAT = "FLOAT"
    BOOL = "BOOL"
    STR = "STR"
    LIST = "LIST"
    DICT = "DICT"
    
    # Literals
    IDENT = "IDENT"
    NUMBER = "NUMBER"
    STRING = "STRING"
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
        "const": TokenType.CONST,
        "let": TokenType.LET,
        "gate": TokenType.GATE,
        "qubit": TokenType.QUBIT,
        "bit": TokenType.BIT,
        "for": TokenType.FOR,
        "if": TokenType.IF,
        "else": TokenType.ELSE,
        "return": TokenType.RETURN,
        "in": TokenType.IN,
        "ctrl": TokenType.CTRL,
        "inv": TokenType.INV,
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
        elif char == '"':
            return self._string()
        elif char.isdigit():
            return self._number(char)
        elif char.isalpha() or char == "_":
            return self._identifier(char)
        
        return None
    
    def _string(self) -> Token:
        """Scan a string literal"""
        start_line = self.line
        start_col = self.column - 1
        value = ""
        
        while self._peek() != '"' and not self._is_at_end():
            if self._peek() == "\n":
                self.line += 1
                self.column = 0
            value += self._advance()
        
        if self._is_at_end():
            from ..errors import QuantaSyntaxError
            raise QuantaSyntaxError("Unterminated string", start_line, start_col)
        
        self._advance()  # Consume closing quote
        return Token(TokenType.STRING, value, start_line, start_col)
    
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
