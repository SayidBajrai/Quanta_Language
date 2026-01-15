"""
Semantic analyzer for Quanta
"""

from typing import Dict, Optional, List
from ..ast.nodes import (
    Program, Stmt, Expr,
    VarDecl, ConstDecl, LetDecl, QuantumDecl, FuncDecl, GateDecl, ClassDecl,
    ForStmt, IfStmt, ReturnStmt, ExprStmt,
    CallExpr, IndexExpr, BinaryExpr, UnaryExpr,
    VarExpr, LiteralExpr, ListExpr, GroupExpr, AssignExpr,
)
from ..errors import QuantaSemanticError, QuantaTypeError


class Symbol:
    """Represents a symbol in the symbol table"""
    
    def __init__(self, name: str, symbol_type: str, value: Any = None):
        self.name = name
        self.type = symbol_type
        self.value = value


class SemanticAnalyzer:
    """Performs semantic analysis on AST"""
    
    def __init__(self):
        self.symbols: Dict[str, Symbol] = {}
        self.functions: Dict[str, FuncDecl] = {}
        self.gates: Dict[str, GateDecl] = {}
        self.constants: Dict[str, ConstDecl] = {}
    
    def analyze(self, ast: Program):
        """Perform semantic analysis on program"""
        # First pass: collect declarations
        for stmt in ast.statements:
            if isinstance(stmt, QuantumDecl):
                self.symbols[stmt.name] = Symbol(stmt.name, f"{stmt.kind}[{stmt.size or 1}]")
            elif isinstance(stmt, FuncDecl):
                self.functions[stmt.name] = stmt
            elif isinstance(stmt, GateDecl):
                self.gates[stmt.name] = stmt
            elif isinstance(stmt, ConstDecl):
                self.constants[stmt.name] = stmt
                self.symbols[stmt.name] = Symbol(stmt.name, "const", stmt.value)
            elif isinstance(stmt, LetDecl):
                self.symbols[stmt.name] = Symbol(stmt.name, "let", stmt.value)
        
        # Second pass: validate statements
        for stmt in ast.statements:
            self._validate_statement(stmt)
    
    def _validate_statement(self, stmt: Stmt):
        """Validate a statement"""
        if isinstance(stmt, VarDecl):
            if stmt.value:
                self._validate_expression(stmt.value)
        elif isinstance(stmt, ConstDecl):
            self._validate_expression(stmt.value)
        elif isinstance(stmt, LetDecl):
            self._validate_expression(stmt.value)
        elif isinstance(stmt, QuantumDecl):
            pass  # Already registered
        elif isinstance(stmt, FuncDecl):
            self._validate_function(stmt)
        elif isinstance(stmt, GateDecl):
            self._validate_gate(stmt)
        elif isinstance(stmt, ForStmt):
            self._validate_for(stmt)
        elif isinstance(stmt, IfStmt):
            self._validate_if(stmt)
        elif isinstance(stmt, ExprStmt):
            self._validate_expression(stmt.expr)
        elif isinstance(stmt, ReturnStmt):
            if stmt.value:
                self._validate_expression(stmt.value)
    
    def _validate_function(self, func: FuncDecl):
        """Validate function declaration"""
        # Check for recursion (v1 restriction)
        # Functions with quantum ops must be inlinable
        for stmt in func.body:
            self._validate_statement(stmt)
    
    def _validate_gate(self, gate: GateDecl):
        """Validate gate declaration"""
        # Gates cannot return values
        for stmt in gate.body:
            self._validate_statement(stmt)
    
    def _validate_for(self, stmt: ForStmt):
        """Validate for loop"""
        # Iterable must be compile-time evaluable
        self._validate_expression(stmt.iterable)
        for body_stmt in stmt.body:
            self._validate_statement(body_stmt)
    
    def _validate_if(self, stmt: IfStmt):
        """Validate if statement"""
        self._validate_expression(stmt.condition)
        for then_stmt in stmt.then_body:
            self._validate_statement(then_stmt)
        for else_stmt in stmt.else_body:
            self._validate_statement(else_stmt)
    
    def _validate_expression(self, expr: Expr):
        """Validate an expression"""
        if isinstance(expr, CallExpr):
            self._validate_call(expr)
        elif isinstance(expr, IndexExpr):
            self._validate_index(expr)
        elif isinstance(expr, BinaryExpr):
            self._validate_expression(expr.left)
            self._validate_expression(expr.right)
        elif isinstance(expr, UnaryExpr):
            self._validate_expression(expr.right)
        elif isinstance(expr, VarExpr):
            if expr.name not in self.symbols and expr.name not in self.functions:
                raise QuantaSemanticError(f"Undefined variable or function: {expr.name}")
        elif isinstance(expr, ListExpr):
            for elem in expr.elements:
                self._validate_expression(elem)
        elif isinstance(expr, GroupExpr):
            self._validate_expression(expr.expr)
        elif isinstance(expr, AssignExpr):
            self._validate_expression(expr.value)
    
    def _validate_call(self, expr: CallExpr):
        """Validate function/gate call"""
        # Validate modifiers
        if "ctrl" in expr.modifiers or "inv" in expr.modifiers:
            if isinstance(expr.callee, VarExpr):
                name = expr.callee.name
                if name == "Measure" or name == "MEASURE":
                    raise QuantaSemanticError("Modifiers (ctrl/inv) are not allowed on Measure")
        
        if isinstance(expr.callee, VarExpr):
            name = expr.callee.name
            if name in self.gates:
                # Gate call - validate arguments match
                gate = self.gates[name]
                if len(expr.args) != len(gate.params):
                    raise QuantaSemanticError(
                        f"Gate '{name}' expects {len(gate.params)} arguments, "
                        f"got {len(expr.args)}"
                    )
                for arg in expr.args:
                    self._validate_expression(arg)
            elif name in self.functions:
                # Function call - validate arguments match
                func = self.functions[name]
                if len(expr.args) != len(func.params):
                    raise QuantaSemanticError(
                        f"Function '{name}' expects {len(func.params)} arguments, "
                        f"got {len(expr.args)}"
                    )
                for arg in expr.args:
                    self._validate_expression(arg)
            else:
                # Assume it's a built-in gate or stdlib function - validate arguments
                for arg in expr.args:
                    self._validate_expression(arg)
        else:
            # Complex callee - validate recursively
            self._validate_expression(expr.callee)
            for arg in expr.args:
                self._validate_expression(arg)
    
    def _validate_index(self, expr: IndexExpr):
        """Validate index expression"""
        self._validate_expression(expr.base)
        self._validate_expression(expr.index)
        # Index must be compile-time evaluable for quantum registers
        if isinstance(expr.index, LiteralExpr):
            try:
                int(expr.index.value)
            except (ValueError, TypeError):
                raise QuantaTypeError("Quantum register index must be a compile-time integer")
