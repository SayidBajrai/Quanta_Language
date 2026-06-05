"""
Compile-time index selection expansion and desugaring for fancy indexing.
"""

from typing import Dict, List, Optional, Union
import math

from ..ast.nodes import (
    Program, Stmt, Expr,
    GateDecl, FuncDecl, ForStmt, WhileStmt, IfStmt, ExprStmt,
    CallExpr, IndexExpr, IndexItem, SingleIndex, SliceIndex, SliceFull,
    VarExpr, LiteralExpr, ListExpr, GroupExpr, BinaryExpr, UnaryExpr,
)
from ..errors import QuantaSemanticError, QuantaTypeError
from ..types.tensor import linear_index


def eval_const_int(expr: Expr, constants: Optional[Dict[str, int]] = None) -> int:
    """Evaluate an expression to a compile-time integer."""
    constants = constants or {}
    if isinstance(expr, LiteralExpr):
        try:
            return int(expr.value)
        except (ValueError, TypeError) as e:
            raise QuantaTypeError(f"Expected integer literal, got {expr.value!r}") from e
    if isinstance(expr, VarExpr):
        if expr.name in constants:
            return constants[expr.name]
        if expr.name == "pi":
            return int(math.pi)
        if expr.name == "e":
            return int(math.e)
        raise QuantaTypeError(f"Index must be a compile-time integer, got variable '{expr.name}'")
    if isinstance(expr, GroupExpr):
        return eval_const_int(expr.expr, constants)
    if isinstance(expr, UnaryExpr) and expr.op == "-":
        return -eval_const_int(expr.right, constants)
    if isinstance(expr, UnaryExpr) and expr.op == "+":
        return eval_const_int(expr.right, constants)
    if isinstance(expr, BinaryExpr):
        left = eval_const_int(expr.left, constants)
        right = eval_const_int(expr.right, constants)
        if expr.op == "+":
            return left + right
        if expr.op == "-":
            return left - right
        if expr.op == "*":
            return left * right
        if expr.op == "//":
            return left // right
        if expr.op == "/":
            return left // right
        if expr.op == "%":
            return left % right
    raise QuantaTypeError("Index must be a compile-time integer expression")


def expand_slice(start: int, stop: int, step: int) -> List[int]:
    """Expand a Python-style slice to a list of indices."""
    if step == 0:
        raise QuantaSemanticError("Slice step cannot be zero")
    return list(range(start, stop, step))


def _expand_dim_index(
    item: IndexItem,
    dim_size: int,
    register_name: str,
    constants: Optional[Dict[str, int]] = None,
) -> List[int]:
    if isinstance(item, SliceFull):
        return list(range(dim_size))
    if isinstance(item, SingleIndex):
        idx = eval_const_int(item.expr, constants)
        if idx < 0 or idx >= dim_size:
            raise QuantaSemanticError(
                f"Index {idx} out of range for {register_name} dimension size {dim_size}"
            )
        return [idx]
    if isinstance(item, SliceIndex):
        start = eval_const_int(item.start, constants) if item.start else 0
        stop = eval_const_int(item.stop, constants) if item.stop else dim_size
        step = eval_const_int(item.step, constants) if item.step else 1
        return expand_slice(start, stop, step)
    raise QuantaTypeError(f"Unknown index item type: {type(item).__name__}")


def expand_multidim_index_items(
    items: List[IndexItem],
    shape: List[int],
    register_name: str = "",
    constants: Optional[Dict[str, int]] = None,
) -> List[int]:
    """Expand per-dimension tensor indexing to flat row-major register indices."""
    if len(items) != len(shape):
        raise QuantaSemanticError(
            f"Tensor index dimension mismatch for {register_name or 'register'}: "
            f"expected {len(shape)} indices, got {len(items)}"
        )
    per_dim = [
        _expand_dim_index(item, shape[i], register_name, constants) for i, item in enumerate(items)
    ]
    from itertools import product

    flat: List[int] = []
    for coords in product(*per_dim):
        flat.append(linear_index(coords, shape))
    return flat


def expand_index_items(
    items: List[IndexItem],
    register_size: Optional[int],
    register_name: str = "",
    constants: Optional[Dict[str, int]] = None,
    shape: Optional[List[int]] = None,
) -> List[int]:
    """
    Expand index selection items to a flat ordered list of integer indices.
    Validates duplicates and bounds when register_size is known.
    """
    if shape is not None and len(shape) > 1:
        return expand_multidim_index_items(items, shape, register_name, constants)

    result: List[int] = []
    for item in items:
        if isinstance(item, SingleIndex):
            idx = eval_const_int(item.expr, constants)
            result.append(idx)
        elif isinstance(item, SliceIndex):
            start = eval_const_int(item.start, constants) if item.start else 0
            stop = eval_const_int(item.stop, constants) if item.stop else (register_size or 0)
            step = eval_const_int(item.step, constants) if item.step else 1
            result.extend(expand_slice(start, stop, step))
        elif isinstance(item, SliceFull):
            if register_size is None:
                raise QuantaSemanticError("Cannot expand full slice without known register size")
            result.extend(range(register_size))
        else:
            raise QuantaTypeError(f"Unknown index item type: {type(item).__name__}")

    seen: set = set()
    for idx in result:
        if idx in seen:
            raise QuantaSemanticError(f"Duplicate qbit index: {idx}")
        seen.add(idx)

    if register_size is not None:
        for idx in result:
            if idx < 0 or idx >= register_size:
                label = register_name or "register"
                raise QuantaSemanticError(
                    f"Index {idx} out of range for {label}[{register_size}]"
                )

    return result


def get_register_shape(expr: IndexExpr, registers: Dict[str, tuple]) -> Optional[List[int]]:
    base = expr.base
    while isinstance(base, IndexExpr):
        base = base.base
    if isinstance(base, VarExpr) and base.name in registers:
        entry = registers[base.name]
        if len(entry) >= 3:
            return list(entry[2])
        kind, size = entry[0], entry[1]
        return [size]
    return None


def effective_arg_count(arg: Expr, registers: Dict[str, tuple]) -> int:
    """How many call operands a (possibly fancy) index argument expands to."""
    if isinstance(arg, IndexExpr) and needs_index_expansion(arg, registers):
        reg_name, reg_size = get_register_size(arg, registers)
        shape = get_register_shape(arg, registers)
        return len(expand_index_items(arg.items, reg_size, reg_name or "", shape=shape))
    return 1


def needs_index_expansion(expr: IndexExpr, registers: Optional[Dict[str, tuple]] = None) -> bool:
    """True when index selection requires compile-time expansion."""
    shape = get_register_shape(expr, registers) if registers else None
    if shape is not None and len(shape) > 1:
        return len(expr.items) > 1 or expr.is_tensor_slice()
    return len(expr.items) > 1 or any(
        isinstance(i, (SliceIndex, SliceFull)) for i in expr.items
    )


def make_single_index_expr(base: Expr, idx: int) -> IndexExpr:
    """Create IndexExpr(base, [idx]) for desugared single-index access."""
    return IndexExpr(base, [SingleIndex(LiteralExpr(str(idx)))])


def get_register_size(
    expr: IndexExpr, registers: Dict[str, tuple]
) -> tuple:
    """Return (register_label, size) for a qbit/bit indexed base, or (None, None)."""
    base = expr.base
    while isinstance(base, IndexExpr):
        base = base.base
    if isinstance(base, VarExpr) and base.name in registers:
        entry = registers[base.name]
        kind = entry[0]
        size = entry[1]
        shape = entry[2] if len(entry) >= 3 else (size,)
        label = kind + "".join(f"[{d}]" for d in shape)
        return label, size
    return None, None


class IndexExpander:
    """Desugar fancy indexing into single-index IndexExpr nodes and expanded calls."""

    def __init__(self, registers: Dict[str, tuple]):
        self.registers = registers

    def expand_program(self, program: Program) -> Program:
        new_statements: List[Stmt] = []
        for stmt in program.statements:
            expanded = self._expand_statement(stmt)
            if isinstance(expanded, list):
                new_statements.extend(expanded)
            else:
                new_statements.append(expanded)
        return Program(new_statements)

    def _expand_statement(self, stmt: Stmt) -> Union[Stmt, List[Stmt]]:
        if isinstance(stmt, ExprStmt) and isinstance(stmt.expr, CallExpr):
            return self._expand_call_stmt(stmt)
        if isinstance(stmt, GateDecl):
            stmt.body = self._expand_stmt_list(stmt.body)
            return stmt
        if isinstance(stmt, FuncDecl):
            new_body: List[Stmt] = []
            for s in stmt.body:
                r = self._expand_statement(s)
                if isinstance(r, list):
                    new_body.extend(r)
                else:
                    new_body.append(r)
            stmt.body = new_body
            return stmt
        if isinstance(stmt, ForStmt):
            stmt.body = self._expand_stmt_list(stmt.body)
            return stmt
        if isinstance(stmt, WhileStmt):
            stmt.body = self._expand_stmt_list(stmt.body)
            return stmt
        if isinstance(stmt, IfStmt):
            stmt.then_body = self._expand_stmt_list(stmt.then_body)
            stmt.else_body = self._expand_stmt_list(stmt.else_body)
            return stmt
        return stmt

    def _expand_stmt_list(self, stmts: List[Stmt]) -> List[Stmt]:
        result: List[Stmt] = []
        for s in stmts:
            r = self._expand_statement(s)
            if isinstance(r, list):
                result.extend(r)
            else:
                result.append(r)
        return result

    def _expand_call_stmt(self, stmt: ExprStmt) -> Union[ExprStmt, List[Stmt]]:
        call = stmt.expr
        if not isinstance(call, CallExpr):
            return stmt

        if isinstance(call.callee, VarExpr) and call.callee.name == "Measure":
            if len(call.args) == 2:
                qarg, carg = call.args[0], call.args[1]
                if (isinstance(qarg, IndexExpr) and needs_index_expansion(qarg, self.registers)) or (
                    isinstance(carg, IndexExpr) and needs_index_expansion(carg, self.registers)
                ):
                    return self._expand_measure_call(call)

        new_args = self._expand_call_args(call.args)
        call.args = new_args
        return stmt

    def _expand_measure_call(self, call: CallExpr) -> Union[ExprStmt, List[Stmt]]:
        if len(call.args) != 2:
            return ExprStmt(call)

        qarg, carg = call.args[0], call.args[1]
        q_indices = self._resolve_arg_indices(qarg)
        c_indices = self._resolve_arg_indices(carg)

        if q_indices is None or c_indices is None:
            call.args = self._expand_call_args(call.args)
            return ExprStmt(call)

        if len(q_indices) != len(c_indices):
            raise QuantaSemanticError(
                f"Measure index lists must have the same length "
                f"(got {len(q_indices)} qbit indices and {len(c_indices)} classical indices)"
            )

        stmts: List[Stmt] = []
        q_base = qarg.base if isinstance(qarg, IndexExpr) else qarg
        c_base = carg.base if isinstance(carg, IndexExpr) else carg
        while isinstance(q_base, IndexExpr):
            q_base = q_base.base
        while isinstance(c_base, IndexExpr):
            c_base = c_base.base

        for qi, ci in zip(q_indices, c_indices):
            new_call = CallExpr(
                call.callee,
                [make_single_index_expr(q_base, qi), make_single_index_expr(c_base, ci)],
                call.modifiers,
                call.ctrl_count,
            )
            stmts.append(ExprStmt(new_call))
        return stmts

    def _resolve_arg_indices(self, arg: Expr) -> Optional[List[int]]:
        if not isinstance(arg, IndexExpr) or not needs_index_expansion(arg, self.registers):
            return None
        reg_name, reg_size = get_register_size(arg, self.registers)
        shape = get_register_shape(arg, self.registers)
        return expand_index_items(arg.items, reg_size, reg_name or "", shape=shape)

    def _expand_call_args(self, args: List[Expr]) -> List[Expr]:
        new_args: List[Expr] = []
        for arg in args:
            if isinstance(arg, IndexExpr) and needs_index_expansion(arg, self.registers):
                reg_name, reg_size = get_register_size(arg, self.registers)
                shape = get_register_shape(arg, self.registers)
                indices = expand_index_items(arg.items, reg_size, reg_name or "", shape=shape)
                base = arg.base
                while isinstance(base, IndexExpr):
                    base = base.base
                for idx in indices:
                    new_args.append(make_single_index_expr(base, idx))
            elif isinstance(arg, IndexExpr):
                shape = get_register_shape(arg, self.registers)
                if shape is not None and len(shape) > 1 and len(arg.items) == len(shape):
                    if all(isinstance(i, SingleIndex) for i in arg.items):
                        reg_name, reg_size = get_register_size(arg, self.registers)
                        indices = expand_index_items(arg.items, reg_size, reg_name or "", shape=shape)
                        base = arg.base
                        while isinstance(base, IndexExpr):
                            base = base.base
                        new_args.append(make_single_index_expr(base, indices[0]))
                        continue
                arg = self._normalize_index_expr(arg)
                new_args.append(arg)
            else:
                new_args.append(arg)
        return new_args

    def _normalize_index_expr(self, expr: IndexExpr) -> IndexExpr:
        """Ensure nested bases use normalized single-index items."""
        if isinstance(expr.base, IndexExpr):
            expr.base = self._normalize_index_expr(expr.base)
        return expr


def collect_registers(program: Program) -> Dict[str, tuple]:
    """Collect register name -> (kind, flat_size, shape) from program declarations."""
    registers: Dict[str, tuple] = {}
    for stmt in program.statements:
        from ..ast.nodes import QuantumDecl
        if isinstance(stmt, QuantumDecl):
            shape = list(stmt.shape or [stmt.size or 1])
            flat_size = stmt.size or 1
            registers[stmt.name] = (stmt.kind, flat_size, shape)
    return registers
