"""
AST node definitions for Quanta language
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Any


class Node(ABC):
    """Base class for all AST nodes"""
    pass


class Stmt(Node):
    """Base class for statements"""
    pass


class Expr(Node):
    """Base class for expressions"""
    pass


class Program(Node):
    """Root node representing a complete program"""
    
    def __init__(self, statements: List[Stmt]):
        self.statements = statements


class VarDecl(Stmt):
    """Variable declaration"""
    
    def __init__(self, name: str, type_hint: Optional[str], value: Optional[Expr]):
        self.name = name
        self.type_hint = type_hint
        self.value = value


class ConstDecl(Stmt):
    """Constant declaration (compile-time literal)"""
    
    def __init__(self, name: str, value: Expr):
        self.name = name
        self.value = value


class LetDecl(Stmt):
    """Let declaration (immutable value)"""
    
    def __init__(self, name: str, value: Expr):
        self.name = name
        self.value = value


class QuantumDecl(Stmt):
    """Quantum register declaration (qubit/bit)"""
    
    def __init__(self, kind: str, size: Optional[int], name: str):
        self.kind = kind  # "qubit" or "bit"
        self.size = size
        self.name = name


class FuncDecl(Stmt):
    """Function declaration"""
    
    def __init__(self, name: str, params: List[str], return_type: Optional[str], body: List[Stmt]):
        self.name = name
        self.params = params
        self.return_type = return_type
        self.body = body


class GateDecl(Stmt):
    """Gate macro declaration (compile-time circuit composition)"""
    
    def __init__(self, name: str, params: List[str], body: List[Stmt]):
        self.name = name
        self.params = params
        self.body = body


class ClassDecl(Stmt):
    """Class declaration"""
    
    def __init__(self, name: str, members: List[Stmt]):
        self.name = name
        self.members = members


class ForStmt(Stmt):
    """For loop statement"""
    
    def __init__(self, iterator: str, iterable: Expr, body: List[Stmt]):
        self.iterator = iterator
        self.iterable = iterable
        self.body = body


class IfStmt(Stmt):
    """If statement"""
    
    def __init__(self, condition: Expr, then_body: List[Stmt], else_body: List[Stmt]):
        self.condition = condition
        self.then_body = then_body
        self.else_body = else_body


class ReturnStmt(Stmt):
    """Return statement"""
    
    def __init__(self, value: Optional[Expr]):
        self.value = value


class ExprStmt(Stmt):
    """Expression statement"""
    
    def __init__(self, expr: Expr):
        self.expr = expr


class CallExpr(Expr):
    """Function/gate call expression"""
    
    def __init__(self, callee: Expr, args: List[Expr], modifiers: Optional[List[str]] = None, ctrl_count: Optional[int] = None):
        self.callee = callee
        self.args = args
        self.modifiers = modifiers or []  # List of "ctrl" and/or "inv"
        self.ctrl_count = ctrl_count  # Number of control qubits for ctrl[n]


class IndexExpr(Expr):
    """Index expression (array/register access)"""
    
    def __init__(self, base: Expr, index: Expr):
        self.base = base
        self.index = index


class BinaryExpr(Expr):
    """Binary expression"""
    
    def __init__(self, left: Expr, op: str, right: Expr):
        self.left = left
        self.op = op
        self.right = right


class UnaryExpr(Expr):
    """Unary expression"""
    
    def __init__(self, op: str, right: Expr):
        self.op = op
        self.right = right


class VarExpr(Expr):
    """Variable reference"""
    
    def __init__(self, name: str):
        self.name = name


class LiteralExpr(Expr):
    """Literal expression (number, string, boolean)"""
    
    def __init__(self, value: Any):
        self.value = value


class ListExpr(Expr):
    """List literal expression"""
    
    def __init__(self, elements: List[Expr]):
        self.elements = elements


class GroupExpr(Expr):
    """Grouped expression (parentheses)"""
    
    def __init__(self, expr: Expr):
        self.expr = expr


class AssignExpr(Expr):
    """Assignment expression"""
    
    def __init__(self, name: str, value: Expr):
        self.name = name
        self.value = value
