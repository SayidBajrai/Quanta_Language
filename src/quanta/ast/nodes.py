"""
AST node definitions for Quanta language
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..types.tensor import TensorType
    from ..docs.comment_parser import ParsedDocComment


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
    
    def __init__(
        self,
        name: str,
        type_hint: Optional[str],
        value: Optional[Expr],
        tensor_type: Optional["TensorType"] = None,
    ):
        self.name = name
        self.type_hint = type_hint
        self.tensor_type = tensor_type
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


class ClassicalNumericDecl(Stmt):
    """Classical numeric register: uint(bits), dec(int, frac), udec(int, frac)."""

    def __init__(
        self,
        kind: str,
        size: Optional[int],
        name: str,
        value: Optional[Expr] = None,
        size2: Optional[int] = None,
        tensor_type: Optional["TensorType"] = None,
    ):
        self.kind = kind
        self.size = size
        self.size2 = size2
        self.name = name
        self.value = value
        self.tensor_type = tensor_type


class QuantumDecl(Stmt):
    """Quantum register declaration (qbit, qint, quint, qdec, qreal, …)."""
    
    def __init__(
        self,
        kind: str,
        size: Optional[int],
        name: str,
        value: Optional[Expr] = None,
        shape: Optional[List[Optional[int]]] = None,
        tensor_type: Optional["TensorType"] = None,
        size2: Optional[int] = None,
        real_min: Optional[float] = None,
        real_max: Optional[float] = None,
    ):
        self.kind = kind
        self.shape = shape if shape is not None else ([size] if size is not None else [1])
        self.size2 = size2
        self.tensor_type = tensor_type
        self.name = name
        self.value = value
        self.real_min = real_min
        self.real_max = real_max

        if size is not None:
            self.size = size
        else:
            self.size = (
                self._product(self.shape)
                if self.shape and all(d is not None for d in self.shape)
                else 1
            )

    @staticmethod
    def _product(shape: List[Optional[int]]) -> int:
        total = 1
        for dim in shape:
            if dim is None:
                return 1
            total *= dim
        return total


class ParamSpec(Node):
    """Typed parameter for functions (e.g. qbit[2] anc)."""

    def __init__(
        self,
        kind: str,
        name: str,
        size: Optional[int] = 1,
        shape: Optional[List[Optional[int]]] = None,
    ):
        self.kind = kind
        self.name = name
        self.shape = shape if shape is not None else ([size] if size is not None else [1])
        self.size = size if size is not None else (
            self._product(self.shape) if self.shape and all(d is not None for d in self.shape) else 1
        )

    @staticmethod
    def _product(shape: List[Optional[int]]) -> int:
        total = 1
        for dim in shape:
            if dim is None:
                return 1
            total *= dim
        return total


class FuncDecl(Stmt):
    """Function declaration"""
    
    def __init__(
        self,
        name: str,
        params: List[str],
        return_type: Optional[str],
        body: List[Stmt],
        param_specs: Optional[List["ParamSpec"]] = None,
        return_kind: Optional[str] = None,
        return_size: Optional[int] = None,
        doc: Optional["ParsedDocComment"] = None,
    ):
        self.name = name
        self.params = params
        self.return_type = return_type
        self.return_kind = return_kind
        self.return_size = return_size
        self.param_specs = param_specs or [ParamSpec("qvar", p) for p in params]
        self.body = body
        self.doc = doc


class GateDecl(Stmt):
    """Gate macro declaration (compile-time circuit composition)"""
    
    def __init__(
        self,
        name: str,
        params: List[str],
        body: List[Stmt],
        doc: Optional["ParsedDocComment"] = None,
    ):
        self.name = name
        self.params = params
        self.body = body
        self.doc = doc


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


class WhileStmt(Stmt):
    """While loop statement"""

    def __init__(self, condition: Expr, body: List[Stmt]):
        self.condition = condition
        self.body = body


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

    def __init__(
        self,
        callee: Expr,
        args: List[Expr],
        modifiers: Optional[List[str]] = None,
        ctrl_count: Optional[int] = None,
        resolved_func: Optional["FuncDecl"] = None,
    ):
        self.callee = callee
        self.args = args
        self.modifiers = modifiers or []  # List of "ctrl" and/or "inv"
        self.ctrl_count = ctrl_count  # Number of control qbits for ctrl[n]
        self.resolved_func = resolved_func  # Set by semantic analysis for overloads


class IndexItem(Node):
    """Base class for a single entry in an index selection (q[i] or q[a:b])"""
    pass


class SingleIndex(IndexItem):
    """Single index: q[0] or q[i]"""
    
    def __init__(self, expr: Expr):
        self.expr = expr


class SliceIndex(IndexItem):
    """Slice index: q[start:stop] or q[start:step:stop]"""
    
    def __init__(self, start: Expr, stop: Expr, step: Optional[Expr] = None):
        self.start = start
        self.stop = stop
        self.step = step


class SliceFull(IndexItem):
    """Full-dimension slice: q[:]"""
    pass


class IndexExpr(Expr):
    """Index expression (array/register access)"""
    
    def __init__(self, base: Expr, items: List[IndexItem]):
        self.base = base
        self.items = items
    
    @property
    def index(self) -> Expr:
        """Backward-compatible single-index accessor (first item only)."""
        if len(self.items) == 1 and isinstance(self.items[0], SingleIndex):
            return self.items[0].expr
        raise AttributeError("IndexExpr has multiple index items; use .items instead")
    
    def is_simple(self) -> bool:
        """True when this is a single scalar index (no slice, no comma list)."""
        return len(self.items) == 1 and isinstance(self.items[0], SingleIndex)

    def is_tensor_slice(self) -> bool:
        """True when selection uses slices or full-dimension ':' specs."""
        return any(isinstance(i, (SliceIndex, SliceFull)) for i in self.items)


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


class FStringPart(Node):
    """One segment of an f-string: literal text or interpolated expression."""

    def __init__(
        self,
        literal: Optional[str] = None,
        expr: Optional[Expr] = None,
        specifier: Optional[str] = None,
    ):
        self.literal = literal
        self.expr = expr
        self.specifier = specifier


class FStringExpr(Expr):
    """Formatted string literal: f\"text {expr} more\""""

    def __init__(self, parts: List[FStringPart]):
        self.parts = parts


class ListExpr(Expr):
    """List literal expression"""
    
    def __init__(self, elements: List[Expr], is_range_syntax: bool = False):
        self.elements = elements
        self.is_range_syntax = is_range_syntax


class GroupExpr(Expr):
    """Grouped expression (parentheses)"""
    
    def __init__(self, expr: Expr):
        self.expr = expr


class AssignExpr(Expr):
    """Assignment expression"""
    
    def __init__(self, name: str, value: Expr):
        self.name = name
        self.value = value


class NoiseModelDecl(Stmt):
    """Noise model declaration: NoiseModel { depolarizing = 0.01, readout = 0.03 }"""

    def __init__(self, params: Dict[str, float]):
        self.params = params
