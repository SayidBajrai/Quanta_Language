"""
Parser for Quanta language - builds AST from tokens
"""

from typing import List, Optional
from ..lexer.lexer import Token, TokenType
from ..ast.nodes import (
    Program, Stmt, Expr,
    VarDecl, ConstDecl, LetDecl, ClassicalNumericDecl, QuantumDecl, FuncDecl, GateDecl, ClassDecl, ParamSpec,
    ForStmt, WhileStmt, IfStmt, ReturnStmt, ExprStmt,
    CallExpr, IndexExpr, IndexItem, SingleIndex, SliceIndex, SliceFull, BinaryExpr, UnaryExpr,
    VarExpr, LiteralExpr, FStringExpr, FStringPart, ListExpr, GroupExpr, AssignExpr,
)
from ..errors import QuantaSyntaxError
from ..types.tensor import TensorType
from ..types.numeric import (
    apply_numeric_defaults,
    build_tensor_type,
    dynamic_numeric_params,
    finalize_numeric_params,
)
from ..types.kinds import CLASSICAL_RETURN_TYPES, is_classical_return_type
from ..docs.comment_parser import ParsedDocComment, parse_doc_comment


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
            # Skip NEWLINE tokens
            while self._check(TokenType.NEWLINE):
                self._advance()
            
            if self._is_at_end():
                break
                
            stmt = self._parse_statement()
            if stmt:
                statements.append(stmt)
        
        return Program(statements)
    
    def _parse_statement(self) -> Optional[Stmt]:
        """Parse a statement"""
        # Skip NEWLINE tokens
        while self._match(TokenType.NEWLINE):
            pass
        
        # If we encounter a closing brace, return None to signal end of block
        if self._check(TokenType.RBRACE):
            return None

        doc = self._parse_leading_doc_comments()

        if self._match(TokenType.FUNC):
            return self._parse_function(doc=doc)
        elif self._match(TokenType.GATE):
            return self._parse_gate(doc=doc)
        elif self._match(TokenType.CLASS):
            return self._parse_class()
        elif self._match(TokenType.VAR):
            return self._parse_var_decl()
        elif self._match(TokenType.CONST):
            return self._parse_const_decl()
        elif self._match(TokenType.LET):
            return self._parse_let_decl()
        elif self._check(TokenType.FLOAT, TokenType.INT, TokenType.BOOL, TokenType.STR):
            return self._parse_typed_var_decl()
        elif self._check(TokenType.UINT, TokenType.DEC, TokenType.UDEC):
            return self._parse_classical_numeric_decl()
        elif self._check(TokenType.QBIT, TokenType.BIT, TokenType.BINT):
            return self._parse_qbit_decl()
        elif self._check(
            TokenType.QINT, TokenType.QUINT, TokenType.QDEC, TokenType.QUDEC,
            TokenType.QFLOAT, TokenType.QREAL,
        ):
            return self._parse_numeric_quantum_decl()
        elif self._match(TokenType.FOR):
            return self._parse_for()
        elif self._match(TokenType.WHILE):
            return self._parse_while()
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

    def _parse_leading_doc_comments(self) -> Optional[ParsedDocComment]:
        """Collect consecutive /// doc-comment lines immediately before a declaration."""
        lines: List[str] = []
        while True:
            while self._match(TokenType.NEWLINE):
                pass
            if self._check(TokenType.DOC_COMMENT):
                lines.append(self._advance().value)
            else:
                break
        if not lines:
            return None
        return parse_doc_comment(lines)

    def _parse_quantum_kind_token(self) -> str:
        """Parse a quantum type keyword into a kind string."""
        kind_token = self._advance()
        mapping = {
            TokenType.QBIT: "qbit",
            TokenType.BIT: "bit",
            TokenType.QINT: "qint",
            TokenType.QUINT: "quint",
            TokenType.BINT: "bint",
            TokenType.QDEC: "qdec",
            TokenType.QUDEC: "qudec",
            TokenType.QFLOAT: "qfloat",
            TokenType.QREAL: "qreal",
        }
        return mapping.get(kind_token.type, "qbit")

    def _reject_bracket_numeric_syntax(self, kind: str) -> None:
        if self._check(TokenType.LBRACKET):
            raise QuantaSyntaxError(
                f"{kind} uses parenthesis syntax, e.g. {kind}(8); bracket syntax is not supported"
            )

    def _parse_compile_time_int(self, label: str) -> int:
        expr = self._parse_expression()
        value = self._eval_compile_time_number(expr)
        if value is not None and float(value).is_integer():
            return int(value)
        raise QuantaSyntaxError(f"{label} must be a compile-time integer literal")

    def _parse_compile_time_float(self, label: str) -> float:
        expr = self._parse_expression()
        value = self._eval_compile_time_number(expr)
        if value is not None:
            return float(value)
        raise QuantaSyntaxError(f"{label} must be a compile-time numeric literal")

    def _eval_compile_time_number(self, expr: Expr) -> Optional[float]:
        if isinstance(expr, LiteralExpr):
            try:
                return float(expr.value)
            except (ValueError, TypeError):
                return None
        if isinstance(expr, UnaryExpr) and expr.op == "-":
            inner = self._eval_compile_time_number(expr.right)
            return -inner if inner is not None else None
        if isinstance(expr, GroupExpr):
            return self._eval_compile_time_number(expr.expr)
        return None

    def _parse_numeric_type_params(self, kind: str) -> dict:
        """Parse optional ``kind(...)`` parameters; bare ``kind`` uses canonical defaults."""
        self._reject_bracket_numeric_syntax(kind)
        if not self._match(TokenType.LPAREN):
            return apply_numeric_defaults(kind)
        if kind == "qreal":
            return self._parse_qreal_paren_params()
        if kind in ("qdec", "qudec", "dec", "udec", "qfloat"):
            return self._parse_two_int_paren_params(kind)
        return self._parse_single_int_paren_params(kind)

    def _parse_qreal_paren_params(self) -> dict:
        if self._match(TokenType.RPAREN):
            return apply_numeric_defaults("qreal")
        lo = self._parse_compile_time_float("qreal min bound")
        if self._match(TokenType.RPAREN):
            raise QuantaSyntaxError("qreal requires min and max interval bounds")
        self._consume(TokenType.COMMA, "Expected ',' in qreal(min, max[, qbits])")
        hi = self._parse_compile_time_float("qreal max bound")
        if self._match(TokenType.RPAREN):
            return finalize_numeric_params("qreal", {"real_min": lo, "real_max": hi})
        self._consume(TokenType.COMMA, "Expected ',' in qreal(min, max, qbits)")
        qbits = self._parse_compile_time_int("qreal qbits")
        self._consume(TokenType.RPAREN, "Expected ')' after qreal parameters")
        return finalize_numeric_params(
            "qreal", {"real_min": lo, "real_max": hi, "size": qbits}
        )

    def _parse_two_int_paren_params(self, kind: str) -> dict:
        if self._match(TokenType.RPAREN):
            return apply_numeric_defaults(kind)
        a = self._parse_compile_time_int(f"{kind} int_bits")
        self._consume(TokenType.COMMA, f"Expected ',' in {kind}(int_bits, frac_bits)")
        b = self._parse_compile_time_int(f"{kind} frac_bits")
        self._consume(TokenType.RPAREN, f"Expected ')' after {kind} parameters")
        return finalize_numeric_params(kind, {"size": a, "size2": b})

    def _parse_single_int_paren_params(self, kind: str) -> dict:
        if self._match(TokenType.RPAREN):
            return dynamic_numeric_params()
        width = self._parse_compile_time_int(f"{kind} bit width")
        self._consume(TokenType.RPAREN, f"Expected ')' after {kind} parameters")
        return finalize_numeric_params(kind, {"size": width})

    def _parse_qbit_type_prefix(self) -> tuple:
        """Parse qbit/bit tensor types such as qbit[2] or bit."""
        kind = self._parse_quantum_kind_token()
        shape = self._parse_tensor_dimensions()
        size = None
        if shape:
            if all(d is not None for d in shape):
                size = 1
                for dim in shape:
                    size *= dim  # type: ignore[operator]
            elif len(shape) == 1 and shape[0] is not None:
                size = shape[0]
        if size is None:
            size = 1
        return kind, size, shape or [1]

    def _parse_numeric_type_prefix(self) -> tuple:
        """Parse numeric quantum type prefixes such as qint(4) or qreal(-1,1,8)."""
        kind = self._parse_quantum_kind_token()
        params = self._parse_numeric_type_params(kind)
        return (
            kind,
            params["size"],
            params["shape"],
            params["size2"],
            params.get("real_min"),
            params.get("real_max"),
        )

    def _parse_quantum_type_prefix(self) -> tuple:
        """Parse a quantum type prefix for function parameters."""
        if self._check(TokenType.QBIT, TokenType.BIT):
            kind, size, shape = self._parse_qbit_type_prefix()
            return kind, size, shape, None, None, None
        kind, size, shape, size2, real_min, real_max = self._parse_numeric_type_prefix()
        return kind, size, shape, size2, real_min, real_max

    def _parse_param_spec(self, default_kind: str = "qbit") -> ParamSpec:
        """Parse a function parameter, optionally typed."""
        if self._check(
            TokenType.QBIT, TokenType.BIT, TokenType.QINT, TokenType.QUINT, TokenType.BINT,
            TokenType.QDEC, TokenType.QUDEC, TokenType.QFLOAT, TokenType.QREAL,
        ):
            kind, size, shape, _, _, _ = self._parse_quantum_type_prefix()
            name = self._consume(TokenType.IDENT, "Expected parameter name").value
            return ParamSpec(kind, name, size, shape)
        if self._check(
            TokenType.INT, TokenType.FLOAT, TokenType.BOOL, TokenType.STR,
            TokenType.LIST, TokenType.DICT, TokenType.VAR, TokenType.QVAR, TokenType.CVAR,
        ):
            kind = self._advance().value
            name = self._consume(TokenType.IDENT, "Expected parameter name").value
            return ParamSpec(kind, name)
        name = self._consume(TokenType.IDENT, "Expected parameter name").value
        return ParamSpec(default_kind, name)

    def _parse_function(self, doc: Optional[ParsedDocComment] = None) -> FuncDecl:
        """Parse function declaration: func [type] name(params) { ... }"""
        return_type = None
        return_kind = None
        return_size = None

        if self._match(TokenType.VAR):
            return_type = "var"
        elif self._check(
            TokenType.QBIT, TokenType.BIT, TokenType.QINT, TokenType.QUINT, TokenType.BINT,
            TokenType.QDEC, TokenType.QUDEC, TokenType.QFLOAT, TokenType.QREAL,
        ):
            return_kind, return_size, _, _, _, _ = self._parse_quantum_type_prefix()
            return_type = return_kind
        elif self._check_type():
            return_type = self._advance().value

        name = self._consume(TokenType.IDENT, "Expected function name").value

        self._consume(TokenType.LPAREN, "Expected '(' after function name")
        default_param_kind = "cvar" if is_classical_return_type(return_type) else "qvar"
        params: List[str] = []
        param_specs: List[ParamSpec] = []
        if not self._check(TokenType.RPAREN):
            while True:
                pspec = self._parse_param_spec(default_kind=default_param_kind)
                param_specs.append(pspec)
                params.append(pspec.name)
                if not self._match(TokenType.COMMA):
                    break
        self._consume(TokenType.RPAREN, "Expected ')' after parameters")

        self._consume(TokenType.LBRACE, "Expected '{' before function body")
        body = []
        while not self._check(TokenType.RBRACE) and not self._is_at_end():
            stmt = self._parse_statement()
            if stmt:
                body.append(stmt)
        self._consume(TokenType.RBRACE, "Expected '}' after function body")

        return FuncDecl(
            name,
            params,
            return_type,
            body,
            param_specs=param_specs,
            return_kind=return_kind,
            return_size=return_size,
            doc=doc,
        )
    
    def _parse_gate(self, doc: Optional[ParsedDocComment] = None) -> GateDecl:
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
        
        return GateDecl(name, params, body, doc=doc)
    
    def _parse_class(self) -> ClassDecl:
        """Parse class declaration"""
        name = self._consume(TokenType.IDENT, "Expected class name").value
        self._consume(TokenType.LBRACE, "Expected '{' after class name")
        
        members = []
        while not self._check(TokenType.RBRACE) and not self._is_at_end():
            while self._match(TokenType.NEWLINE):
                pass
            doc = self._parse_leading_doc_comments()
            if self._match(TokenType.FUNC):
                members.append(self._parse_function(doc=doc))
            elif self._match(TokenType.VAR):
                members.append(self._parse_var_decl())
            else:
                self._advance()  # Skip unknown
        
        self._consume(TokenType.RBRACE, "Expected '}' after class body")
        return ClassDecl(name, members)
    
    def _parse_tensor_dimensions(self) -> List[Optional[int]]:
        """Parse repeated [n] or [] dimension suffixes on a type."""
        dims: List[Optional[int]] = []
        while self._match(TokenType.LBRACKET):
            if self._check(TokenType.RBRACKET):
                self._advance()
                dims.append(None)
            else:
                size_expr = self._parse_expression()
                dim: Optional[int] = None
                if isinstance(size_expr, LiteralExpr):
                    try:
                        dim = int(size_expr.value)
                    except (ValueError, TypeError):
                        dim = None
                dims.append(dim)
                self._consume(TokenType.RBRACKET, "Expected ']' after tensor dimension")
        return dims

    def _parse_type_annotation(self) -> TensorType:
        """Parse a full tensor type annotation such as float[3][4] or int[][]."""
        base = self._advance().value
        dims = self._parse_tensor_dimensions()
        return TensorType(base, tuple(dims))

    def _parse_typed_var_decl(self) -> VarDecl:
        """Parse typed variable declaration (e.g. float x = expr)."""
        tensor_type = self._parse_type_annotation()
        name = self._consume(TokenType.IDENT, "Expected variable name").value
        value = None
        if self._match(TokenType.EQ):
            value = self._parse_expression()
        self._match(TokenType.SEMICOLON)
        return VarDecl(name, tensor_type.format(), value, tensor_type)

    def _parse_var_decl(self) -> VarDecl:
        """Parse variable declaration"""
        name = self._consume(TokenType.IDENT, "Expected variable name").value
        
        tensor_type = None
        type_hint = None
        if self._check_type():
            tensor_type = self._parse_type_annotation()
            type_hint = tensor_type.format()
        
        value = None
        if self._match(TokenType.EQ):
            value = self._parse_expression()
        
        # Semicolon is optional
        self._match(TokenType.SEMICOLON)
        return VarDecl(name, type_hint, value, tensor_type)
    
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
    
    def _parse_classical_numeric_decl(self) -> ClassicalNumericDecl:
        kind_token = self._advance()
        kind = {TokenType.UINT: "uint", TokenType.DEC: "dec", TokenType.UDEC: "udec"}[kind_token.type]
        params = self._parse_numeric_type_params(kind)
        finalized = finalize_numeric_params(kind, params)
        name = self._consume(TokenType.IDENT, "Expected variable name").value
        value = None
        if self._match(TokenType.EQ):
            value = self._parse_expression()
        self._match(TokenType.SEMICOLON)
        return ClassicalNumericDecl(
            kind,
            finalized["size"],
            name,
            value,
            finalized["size2"],
            tensor_type=build_tensor_type(kind, params),
        )

    def _parse_qbit_decl(self) -> QuantumDecl:
        """Parse qbit/bit tensor declarations using bracket syntax."""
        kind = self._parse_quantum_kind_token()
        shape = self._parse_tensor_dimensions()
        size = None
        if shape:
            if all(d is not None for d in shape):
                size = 1
                for dim in shape:
                    size *= dim  # type: ignore[operator]
            elif len(shape) == 1 and shape[0] is not None:
                size = shape[0]
        if size is None:
            size = 1
        tensor_type = TensorType.from_quantum(kind, tuple(shape or [1]))
        name = self._consume(TokenType.IDENT, "Expected register name").value
        value = None
        if self._match(TokenType.EQ):
            value = self._parse_expression()
        self._match(TokenType.SEMICOLON)
        return QuantumDecl(
            kind, size, name, value,
            shape=shape or [1],
            tensor_type=tensor_type,
        )

    def _parse_numeric_quantum_decl(self) -> QuantumDecl:
        """Parse numeric quantum declarations using parenthesis syntax."""
        kind = self._parse_quantum_kind_token()
        params = self._parse_numeric_type_params(kind)
        finalized = finalize_numeric_params(kind, params)
        tensor_type = build_tensor_type(kind, params)
        name = self._consume(TokenType.IDENT, "Expected register name").value
        value = None
        if self._match(TokenType.EQ):
            value = self._parse_expression()
        self._match(TokenType.SEMICOLON)
        return QuantumDecl(
            kind,
            finalized["size"],
            name,
            value,
            shape=finalized["shape"],
            tensor_type=tensor_type,
            size2=finalized["size2"],
            real_min=finalized.get("real_min"),
            real_max=finalized.get("real_max"),
        )
    
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

    def _parse_while(self) -> WhileStmt:
        """Parse while loop (braces optional for single-statement body)."""
        self._consume(TokenType.LPAREN, "Expected '(' after 'while'")
        condition = self._parse_expression()
        self._consume(TokenType.RPAREN, "Expected ')' after while condition")

        if self._match(TokenType.LBRACE):
            body: List[Stmt] = []
            while not self._check(TokenType.RBRACE) and not self._is_at_end():
                stmt = self._parse_statement()
                if stmt:
                    body.append(stmt)
            self._consume(TokenType.RBRACE, "Expected '}' after while body")
        else:
            stmt = self._parse_statement()
            body = [stmt] if stmt else []

        return WhileStmt(condition, body)
    
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
        # Skip NEWLINE tokens before expressions
        while self._check(TokenType.NEWLINE):
            self._advance()
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
        expr = self._parse_kron()
        while self._match(TokenType.PLUS, TokenType.MINUS):
            op = self._previous().value
            right = self._parse_kron()
            expr = BinaryExpr(expr, op, right)
        return expr

    def _parse_kron(self) -> Expr:
        """Parse Kronecker product (A ⊗ B)"""
        expr = self._parse_hadamard()
        while self._match(TokenType.KRON):
            right = self._parse_hadamard()
            expr = CallExpr(VarExpr("TensorProduct"), [expr, right])
        return expr

    def _parse_hadamard(self) -> Expr:
        """Parse elementwise product (A ⊙ B)"""
        expr = self._parse_factor()
        while self._match(TokenType.HADAMARD):
            right = self._parse_factor()
            expr = CallExpr(VarExpr("ElementwiseProduct"), [expr, right])
        return expr
    
    def _parse_factor(self) -> Expr:
        """Parse multiplication/division ( * is cross product on 3D vectors at runtime)"""
        expr = self._parse_dot()
        while self._match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op = self._previous().value
            right = self._parse_dot()
            expr = BinaryExpr(expr, op, right)
        return expr

    def _parse_dot(self) -> Expr:
        """Parse dot product (a . b)"""
        expr = self._parse_unary()
        while self._match(TokenType.DOT):
            right = self._parse_unary()
            expr = CallExpr(VarExpr("DotProduct"), [expr, right])
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
                items = self._parse_index_selection()
                self._consume(TokenType.RBRACKET, "Expected ']' after index")
                expr = IndexExpr(expr, items)
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
        # Skip NEWLINE tokens before primary expressions
        while self._check(TokenType.NEWLINE):
            self._advance()
        if self._match(TokenType.NUMBER):
            return LiteralExpr(self._previous().value)
        if self._match(TokenType.FSTRING):
            return self._parse_fstring(self._previous().value)
        if self._match(TokenType.STRING):
            return LiteralExpr(self._previous().value)
        if self._match(TokenType.BOOLEAN):
            return LiteralExpr(self._previous().value)
        if self._match(TokenType.IDENT):
            return VarExpr(self._previous().value)
        if self._check(TokenType.INT) and self._check_next(TokenType.LPAREN):
            name = self._advance().value
            self._consume(TokenType.LPAREN, "Expected '(' after int")
            return self._finish_call(VarExpr(name), [], None)
        if self._match(TokenType.LPAREN):
            expr = self._parse_expression()
            self._consume(TokenType.RPAREN, "Expected ')' after expression")
            return GroupExpr(expr)
        if self._match(TokenType.LBRACKET):
            return self._parse_list()
        
        raise QuantaSyntaxError(f"Unexpected token: {self._peek().value}", self._peek().line, self._peek().column)
    
    def _parse_fstring(self, template: str) -> FStringExpr:
        """Parse an f-string template into literal and interpolated parts."""
        parts: List[FStringPart] = []
        i = 0
        literal_start = 0
        while i < len(template):
            ch = template[i]
            if ch == "{" and i + 1 < len(template) and template[i + 1] == "{":
                if literal_start < i:
                    parts.append(FStringPart(literal=template[literal_start:i] + "{"))
                i += 2
                literal_start = i
                continue
            if ch == "}" and i + 1 < len(template) and template[i + 1] == "}":
                if literal_start < i:
                    parts.append(FStringPart(literal=template[literal_start:i] + "}"))
                i += 2
                literal_start = i
                continue
            if ch == "{":
                if literal_start < i:
                    parts.append(FStringPart(literal=template[literal_start:i]))
                end = template.find("}", i + 1)
                if end == -1:
                    raise QuantaSyntaxError("Unterminated f-string expression")
                inner = template[i + 1:end]
                if ":" in inner:
                    expr_src, specifier = inner.split(":", 1)
                    specifier = specifier.strip() or None
                else:
                    expr_src, specifier = inner, None
                expr = self._parse_embedded_expression(expr_src.strip())
                parts.append(FStringPart(expr=expr, specifier=specifier))
                i = end + 1
                literal_start = i
                continue
            i += 1
        if literal_start < len(template):
            parts.append(FStringPart(literal=template[literal_start:]))
        if not parts:
            parts.append(FStringPart(literal=""))
        return FStringExpr(parts)

    def _parse_embedded_expression(self, source: str) -> Expr:
        """Parse a single expression embedded inside an f-string."""
        if not source:
            raise QuantaSyntaxError("Empty f-string expression")
        from ..lexer.lexer import Lexer

        lexer = Lexer()
        tokens = lexer.tokenize(source)
        subparser = Parser()
        subparser.tokens = tokens
        subparser.current = 0
        return subparser._parse_expression()

    def _parse_index_item(self) -> IndexItem:
        """Parse one index item: i, :, i:j, i:j:k, or :j or ::k."""
        if self._check(TokenType.COLON):
            self._advance()
            if self._check(TokenType.RBRACKET) or self._check(TokenType.COMMA):
                return SliceFull()
            if self._match(TokenType.COLON):
                step = self._parse_expression()
                if self._match(TokenType.COLON):
                    end = self._parse_expression()
                    return SliceIndex(LiteralExpr("0"), end, step)
                return SliceIndex(LiteralExpr("0"), LiteralExpr("0"), step)
            end = self._parse_expression()
            if self._match(TokenType.COLON):
                step = self._parse_expression()
                return SliceIndex(LiteralExpr("0"), end, step)
            return SliceIndex(LiteralExpr("0"), end, LiteralExpr("1"))

        first = self._parse_expression()
        if self._match(TokenType.COLON):
            if self._check(TokenType.COLON):
                self._advance()
                step = self._parse_expression()
                self._consume(TokenType.COLON, "Expected ':' before end in slice")
                end = self._parse_expression()
                return SliceIndex(first, end, step)
            end = self._parse_expression()
            return SliceIndex(first, end, LiteralExpr("1"))
        return SingleIndex(first)

    def _parse_index_selection(self) -> List[IndexItem]:
        """Parse comma-separated index selection inside brackets."""
        items = [self._parse_index_item()]
        while self._match(TokenType.COMMA):
            items.append(self._parse_index_item())
        return items

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
            return ListExpr(elements, is_range_syntax=True)
        else:
            # Regular list
            elements = [first]
            while self._match(TokenType.COMMA):
                elements.append(self._parse_expression())
            self._consume(TokenType.RBRACKET, "Expected ']' after list")
            return ListExpr(elements)
    
    def _check_type(self) -> bool:
        """Check if current token is a type"""
        return self._check(
            TokenType.INT, TokenType.FLOAT, TokenType.BOOL, TokenType.STR,
            TokenType.LIST, TokenType.DICT, TokenType.VAR, TokenType.QVAR, TokenType.CVAR,
            TokenType.QINT, TokenType.QUINT, TokenType.BINT,
            TokenType.QBIT, TokenType.BIT, TokenType.QDEC, TokenType.QUDEC, TokenType.QFLOAT, TokenType.QREAL,
            TokenType.UINT, TokenType.DEC, TokenType.UDEC,
        )
    
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

    def _check_next(self, *types: TokenType) -> bool:
        """Check if the next token matches any of the given types."""
        if self.current + 1 >= len(self.tokens):
            return False
        return self.tokens[self.current + 1].type in types
    
    def _previous(self) -> Token:
        """Get previous token"""
        return self.tokens[self.current - 1]
    
    def _is_at_end(self) -> bool:
        """Check if at end of tokens"""
        return self._peek().type == TokenType.EOF
