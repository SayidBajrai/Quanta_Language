"""
Parser for Quanta language - builds AST from tokens
"""

from typing import List, Optional
from ..lexer.lexer import Token, TokenType
from ..ast.nodes import (
    Program, Stmt, Expr,
    VarDecl, ConstDecl, LetDecl, QuantumDecl, FuncDecl, GateDecl, ClassDecl,
    ForStmt, IfStmt, ReturnStmt, ExprStmt,
    CallExpr, IndexExpr, BinaryExpr, UnaryExpr,
    VarExpr, LiteralExpr, ListExpr, GroupExpr, AssignExpr,
)
from ..errors import QuantaSyntaxError


class Parser:
    """Parses tokens into an Abstract Syntax Tree"""
    
    def __init__(self):
        self.tokens: List[Token] = []
        self.current = 0
    
    def parse(self, tokens: List[Token]) -> Program:
        """Parse tokens into AST"""
        self.tokens = tokens
        self.current = 0
        
        statements = []
        while not self._is_at_end():
            stmt = self._parse_statement()
            if stmt:
                statements.append(stmt)
        
        return Program(statements)
    
    def _parse_statement(self) -> Optional[Stmt]:
        """Parse a statement"""
        if self._match(TokenType.FUNC):
            return self._parse_function()
        elif self._match(TokenType.GATE):
            return self._parse_gate()
        elif self._match(TokenType.CLASS):
            return self._parse_class()
        elif self._match(TokenType.VAR):
            return self._parse_var_decl()
        elif self._match(TokenType.CONST):
            return self._parse_const_decl()
        elif self._match(TokenType.LET):
            return self._parse_let_decl()
        elif self._check(TokenType.QUBIT) or self._check(TokenType.BIT):
            return self._parse_quantum_decl()
        elif self._match(TokenType.FOR):
            return self._parse_for()
        elif self._match(TokenType.IF):
            return self._parse_if()
        elif self._match(TokenType.RETURN):
            return self._parse_return()
        else:
            # Expression statement
            expr = self._parse_expression()
            if expr:
                # Semicolon is optional
                self._match(TokenType.SEMICOLON)
                return ExprStmt(expr)
        return None
    
    def _parse_function(self) -> FuncDecl:
        """Parse function declaration"""
        name = self._consume(TokenType.IDENT, "Expected function name").value
        
        # Parse return type if present
        return_type = None
        if self._check_type():
            return_type = self._advance().value
        
        # Parse parameters
        self._consume(TokenType.LPAREN, "Expected '(' after function name")
        params = []
        if not self._check(TokenType.RPAREN):
            while True:
                params.append(self._consume(TokenType.IDENT, "Expected parameter name").value)
                if not self._match(TokenType.COMMA):
                    break
        self._consume(TokenType.RPAREN, "Expected ')' after parameters")
        
        # Parse body
        self._consume(TokenType.LBRACE, "Expected '{' before function body")
        body = []
        while not self._check(TokenType.RBRACE) and not self._is_at_end():
            stmt = self._parse_statement()
            if stmt:
                body.append(stmt)
        self._consume(TokenType.RBRACE, "Expected '}' after function body")
        
        return FuncDecl(name, params, return_type, body)
    
    def _parse_gate(self) -> GateDecl:
        """Parse gate macro declaration"""
        name = self._consume(TokenType.IDENT, "Expected gate name").value
        
        # Parse parameters
        self._consume(TokenType.LPAREN, "Expected '(' after gate name")
        params = []
        if not self._check(TokenType.RPAREN):
            while True:
                params.append(self._consume(TokenType.IDENT, "Expected parameter name").value)
                if not self._match(TokenType.COMMA):
                    break
        self._consume(TokenType.RPAREN, "Expected ')' after parameters")
        
        # Parse body
        self._consume(TokenType.LBRACE, "Expected '{' before gate body")
        body = []
        while not self._check(TokenType.RBRACE) and not self._is_at_end():
            stmt = self._parse_statement()
            if stmt:
                body.append(stmt)
        self._consume(TokenType.RBRACE, "Expected '}' after gate body")
        
        return GateDecl(name, params, body)
    
    def _parse_class(self) -> ClassDecl:
        """Parse class declaration"""
        name = self._consume(TokenType.IDENT, "Expected class name").value
        self._consume(TokenType.LBRACE, "Expected '{' after class name")
        
        members = []
        while not self._check(TokenType.RBRACE) and not self._is_at_end():
            if self._match(TokenType.FUNC):
                members.append(self._parse_function())
            elif self._match(TokenType.VAR):
                members.append(self._parse_var_decl())
            else:
                self._advance()  # Skip unknown
        
        self._consume(TokenType.RBRACE, "Expected '}' after class body")
        return ClassDecl(name, members)
    
    def _parse_var_decl(self) -> VarDecl:
        """Parse variable declaration"""
        name = self._consume(TokenType.IDENT, "Expected variable name").value
        
        type_hint = None
        if self._check_type():
            type_hint = self._advance().value
        
        value = None
        if self._match(TokenType.EQ):
            value = self._parse_expression()
        
        # Semicolon is optional
        self._match(TokenType.SEMICOLON)
        return VarDecl(name, type_hint, value)
    
    def _parse_const_decl(self) -> ConstDecl:
        """Parse constant declaration"""
        name = self._consume(TokenType.IDENT, "Expected constant name").value
        self._consume(TokenType.EQ, "Expected '=' after constant name")
        value = self._parse_expression()
        self._match(TokenType.SEMICOLON)
        return ConstDecl(name, value)
    
    def _parse_let_decl(self) -> LetDecl:
        """Parse let declaration"""
        name = self._consume(TokenType.IDENT, "Expected variable name").value
        self._consume(TokenType.EQ, "Expected '=' after variable name")
        value = self._parse_expression()
        self._match(TokenType.SEMICOLON)
        return LetDecl(name, value)
    
    def _parse_quantum_decl(self) -> QuantumDecl:
        """Parse quantum register declaration"""
        kind_token = self._advance()
        kind = "qubit" if kind_token.type == TokenType.QUBIT else "bit"
        
        size = None
        if self._match(TokenType.LBRACKET):
            size_expr = self._parse_expression()
            if isinstance(size_expr, LiteralExpr) and size_expr.value.isdigit():
                size = int(size_expr.value)
            self._consume(TokenType.RBRACKET, "Expected ']' after size")
        
        name = self._consume(TokenType.IDENT, "Expected register name").value
        self._match(TokenType.SEMICOLON)  # Optional semicolon
        
        return QuantumDecl(kind, size, name)
    
    def _parse_for(self) -> ForStmt:
        """Parse for loop"""
        self._consume(TokenType.LPAREN, "Expected '(' after 'for'")
        iterator = self._consume(TokenType.IDENT, "Expected iterator variable").value
        self._consume(TokenType.IN, "Expected 'in' after iterator")
        iterable = self._parse_expression()
        self._consume(TokenType.RPAREN, "Expected ')' after for clause")
        
        self._consume(TokenType.LBRACE, "Expected '{' before for body")
        body = []
        while not self._check(TokenType.RBRACE) and not self._is_at_end():
            stmt = self._parse_statement()
            if stmt:
                body.append(stmt)
        self._consume(TokenType.RBRACE, "Expected '}' after for body")
        
        return ForStmt(iterator, iterable, body)
    
    def _parse_if(self) -> IfStmt:
        """Parse if statement"""
        self._consume(TokenType.LPAREN, "Expected '(' after 'if'")
        condition = self._parse_expression()
        self._consume(TokenType.RPAREN, "Expected ')' after condition")
        
        self._consume(TokenType.LBRACE, "Expected '{' before if body")
        then_body = []
        while not self._check(TokenType.RBRACE) and not self._is_at_end():
            stmt = self._parse_statement()
            if stmt:
                then_body.append(stmt)
        self._consume(TokenType.RBRACE, "Expected '}' after if body")
        
        else_body = []
        if self._match(TokenType.ELSE):
            self._consume(TokenType.LBRACE, "Expected '{' before else body")
            while not self._check(TokenType.RBRACE) and not self._is_at_end():
                stmt = self._parse_statement()
                if stmt:
                    else_body.append(stmt)
            self._consume(TokenType.RBRACE, "Expected '}' after else body")
        
        return IfStmt(condition, then_body, else_body)
    
    def _parse_return(self) -> ReturnStmt:
        """Parse return statement"""
        value = None
        if not self._check(TokenType.SEMICOLON):
            value = self._parse_expression()
        self._match(TokenType.SEMICOLON)  # Optional semicolon
        return ReturnStmt(value)
    
    def _parse_expression(self) -> Expr:
        """Parse an expression"""
        return self._parse_assignment()
    
    def _parse_assignment(self) -> Expr:
        """Parse assignment expression"""
        expr = self._parse_or()
        
        if self._match(TokenType.EQ):
            value = self._parse_assignment()
            if isinstance(expr, VarExpr):
                return AssignExpr(expr.name, value)
            raise QuantaSyntaxError("Invalid assignment target")
        
        return expr
    
    def _parse_or(self) -> Expr:
        """Parse OR expression"""
        expr = self._parse_and()
        while self._match(TokenType.OR):
            op = self._previous().value
            right = self._parse_and()
            expr = BinaryExpr(expr, op, right)
        return expr
    
    def _parse_and(self) -> Expr:
        """Parse AND expression"""
        expr = self._parse_equality()
        while self._match(TokenType.AND):
            op = self._previous().value
            right = self._parse_equality()
            expr = BinaryExpr(expr, op, right)
        return expr
    
    def _parse_equality(self) -> Expr:
        """Parse equality expression"""
        expr = self._parse_comparison()
        while self._match(TokenType.EQEQ, TokenType.NE):
            op = self._previous().value
            right = self._parse_comparison()
            expr = BinaryExpr(expr, op, right)
        return expr
    
    def _parse_comparison(self) -> Expr:
        """Parse comparison expression"""
        expr = self._parse_term()
        while self._match(TokenType.GT, TokenType.GE, TokenType.LT, TokenType.LE):
            op = self._previous().value
            right = self._parse_term()
            expr = BinaryExpr(expr, op, right)
        return expr
    
    def _parse_term(self) -> Expr:
        """Parse addition/subtraction"""
        expr = self._parse_factor()
        while self._match(TokenType.PLUS, TokenType.MINUS):
            op = self._previous().value
            right = self._parse_factor()
            expr = BinaryExpr(expr, op, right)
        return expr
    
    def _parse_factor(self) -> Expr:
        """Parse multiplication/division"""
        expr = self._parse_unary()
        while self._match(TokenType.STAR, TokenType.SLASH):
            op = self._previous().value
            right = self._parse_unary()
            expr = BinaryExpr(expr, op, right)
        return expr
    
    def _parse_unary(self) -> Expr:
        """Parse unary expression"""
        if self._match(TokenType.MINUS, TokenType.NE):
            op = self._previous().value
            right = self._parse_unary()
            return UnaryExpr(op, right)
        return self._parse_call()
    
    def _parse_call(self) -> Expr:
        """Parse function/gate call with modifiers"""
        # Parse modifiers (ctrl, inv) before the call
        modifiers = []
        ctrl_count = None
        
        while True:
            if self._match(TokenType.CTRL):
                modifiers.append("ctrl")
                # Check for ctrl[n] syntax
                if self._match(TokenType.LBRACKET):
                    count_expr = self._parse_expression()
                    if isinstance(count_expr, LiteralExpr) and count_expr.value.isdigit():
                        ctrl_count = int(count_expr.value)
                    self._consume(TokenType.RBRACKET, "Expected ']' after ctrl count")
            elif self._match(TokenType.INV):
                modifiers.append("inv")
            else:
                break
        
        expr = self._parse_primary()
        
        while True:
            if self._match(TokenType.LPAREN):
                expr = self._finish_call(expr, modifiers, ctrl_count)
                modifiers = []  # Reset after call
                ctrl_count = None
            elif self._match(TokenType.LBRACKET):
                index = self._parse_expression()
                self._consume(TokenType.RBRACKET, "Expected ']' after index")
                expr = IndexExpr(expr, index)
            else:
                break
        
        return expr
    
    def _finish_call(self, callee: Expr, modifiers: List[str], ctrl_count: Optional[int]) -> CallExpr:
        """Finish parsing a call expression"""
        args = []
        if not self._check(TokenType.RPAREN):
            while True:
                args.append(self._parse_expression())
                if not self._match(TokenType.COMMA):
                    break
        self._consume(TokenType.RPAREN, "Expected ')' after arguments")
        return CallExpr(callee, args, modifiers, ctrl_count)
    
    def _parse_primary(self) -> Expr:
        """Parse primary expression"""
        if self._match(TokenType.NUMBER):
            return LiteralExpr(self._previous().value)
        if self._match(TokenType.STRING):
            return LiteralExpr(self._previous().value)
        if self._match(TokenType.BOOLEAN):
            return LiteralExpr(self._previous().value)
        if self._match(TokenType.IDENT):
            return VarExpr(self._previous().value)
        if self._match(TokenType.LPAREN):
            expr = self._parse_expression()
            self._consume(TokenType.RPAREN, "Expected ')' after expression")
            return GroupExpr(expr)
        if self._match(TokenType.LBRACKET):
            return self._parse_list()
        
        raise QuantaSyntaxError(f"Unexpected token: {self._peek().value}", self._peek().line, self._peek().column)
    
    def _parse_list(self) -> ListExpr:
        """Parse list literal (including range syntax [start:end] or [start:step:end])"""
        # Check if empty list
        if self._check(TokenType.RBRACKET):
            self._advance()
            return ListExpr([])
        
        # Try to parse first element or check for range syntax
        first = self._parse_expression()
        
        # Check for range syntax [start:end] or [start:step:end]
        if self._match(TokenType.COLON):
            # Range syntax
            if self._check(TokenType.COLON):
                # [start:step:end] format
                self._advance()  # consume second colon
                step = self._parse_expression()
                self._consume(TokenType.COLON, "Expected ':' before end")
                end = self._parse_expression()
                elements = [first, step, end]  # Will be expanded at compile time
            else:
                # [start:end] format (default step = 1)
                end = self._parse_expression()
                step = LiteralExpr("1")
                elements = [first, step, end]  # Will be expanded at compile time
            
            self._consume(TokenType.RBRACKET, "Expected ']' after range")
            return ListExpr(elements)
        else:
            # Regular list
            elements = [first]
            while self._match(TokenType.COMMA):
                elements.append(self._parse_expression())
            self._consume(TokenType.RBRACKET, "Expected ']' after list")
            return ListExpr(elements)
    
    def _check_type(self) -> bool:
        """Check if current token is a type"""
        return self._check(TokenType.INT, TokenType.FLOAT, TokenType.BOOL, TokenType.STR, 
                          TokenType.LIST, TokenType.DICT, TokenType.VAR)
    
    def _match(self, *types: TokenType) -> bool:
        """Match and consume if any type matches"""
        for token_type in types:
            if self._check(token_type):
                self._advance()
                return True
        return False
    
    def _check(self, *types: TokenType) -> bool:
        """Check if current token is any of the types"""
        if self._is_at_end():
            return False
        return self._peek().type in types
    
    def _advance(self) -> Token:
        """Advance to next token"""
        if not self._is_at_end():
            self.current += 1
        return self._previous()
    
    def _consume(self, token_type: TokenType, message: str) -> Token:
        """Consume token of expected type"""
        if self._check(token_type):
            return self._advance()
        raise QuantaSyntaxError(message, self._peek().line, self._peek().column)
    
    def _peek(self) -> Token:
        """Peek at current token"""
        return self.tokens[self.current]
    
    def _previous(self) -> Token:
        """Get previous token"""
        return self.tokens[self.current - 1]
    
    def _is_at_end(self) -> bool:
        """Check if at end of tokens"""
        return self._peek().type == TokenType.EOF
