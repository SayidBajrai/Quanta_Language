"""
AST transformations for operator overloading and desugaring
"""

from typing import Dict, List, Optional, Set, Tuple, Union

from ..types.tensor import TensorType
from ..ast.nodes import (
    Program,
    Stmt,
    Expr,
    VarDecl,
    ClassicalNumericDecl,
    QuantumDecl,
    FuncDecl,
    GateDecl,
    ClassDecl,
    ForStmt,
    IfStmt,
    ReturnStmt,
    ExprStmt,
    CallExpr,
    IndexExpr,
    BinaryExpr,
    UnaryExpr,
    VarExpr,
    LiteralExpr,
    FStringExpr,
    ListExpr,
    GroupExpr,
    AssignExpr,
)
from ..ast.visitor import Visitor
from .qint_utils import (
    bitwidth_for_constant,
    infer_qint_width,
    is_integer_literal,
    is_qint_operand,
    is_qint_one,
    is_qint_zero,
    literal_int_value,
    expr_var_name,
    parse_qint_width,
)


_QINT_OP_TO_FUNC = {
    "+": "QAdd",
    "*": "QMult",
    "-": "QSub",
    "/": "QDiv",
    "%": "QMod",
}

_QINT_CALL_INITIALIZERS = frozenset(
    {"QFTAdd", "QTreeAdd", "QExpEncMult", "QTreeMult"}
)


class ASTTransformer(Visitor):
    """Transforms AST to desugar operator overloading and other syntactic sugar"""

    def __init__(self):
        self.symbols: Dict[str, str] = {}
        self.temp_counter = 0
        self.const_counter = 0
        self._free_temps: List[str] = []
        self._declared_temps: Set[str] = set()
        self._const_cache: Dict[Tuple[int, int], str] = {}

    def transform(self, ast: Program) -> Program:
        """Transform AST by desugaring operator overloading"""
        for stmt in ast.statements:
            if isinstance(stmt, QuantumDecl):
                if stmt.tensor_type:
                    self.symbols[stmt.name] = stmt.tensor_type.format()
                elif stmt.shape and any(d is None for d in stmt.shape):
                    self.symbols[stmt.name] = f"{stmt.kind}()"
                else:
                    self.symbols[stmt.name] = f"{stmt.kind}({stmt.size or 1})"
            elif isinstance(stmt, ClassicalNumericDecl):
                if stmt.tensor_type:
                    self.symbols[stmt.name] = stmt.tensor_type.format()
            elif isinstance(stmt, VarDecl) and stmt.type_hint:
                self.symbols[stmt.name] = stmt.type_hint

        transformed_statements: List[Stmt] = []
        for stmt in ast.statements:
            transformed = self._transform_statement(stmt)
            if isinstance(transformed, list):
                transformed_statements.extend(transformed)
            elif transformed:
                transformed_statements.append(transformed)

        return Program(transformed_statements)

    def _transform_statement(self, stmt: Stmt) -> Union[Stmt, List[Stmt]]:
        if isinstance(stmt, ClassicalNumericDecl):
            return stmt

        if isinstance(stmt, VarDecl):
            if stmt.value and isinstance(stmt.value, BinaryExpr):
                if stmt.value.op in _QINT_OP_TO_FUNC:
                    stmt_type = stmt.type_hint or ""
                    if stmt_type.startswith("quint") or stmt_type.startswith("qint"):
                        return self._transform_qint_assignment(stmt)
            return stmt

        if isinstance(stmt, QuantumDecl):
            if (
                stmt.kind in ("quint", "qint")
                and stmt.value
                and isinstance(stmt.value, CallExpr)
                and isinstance(stmt.value.callee, VarExpr)
                and stmt.value.callee.name in _QINT_CALL_INITIALIZERS
            ):
                return self._transform_qint_call_initializer(stmt, stmt.value)
            if stmt.value and isinstance(stmt.value, BinaryExpr):
                if stmt.value.op in _QINT_OP_TO_FUNC and stmt.kind in ("quint", "qint"):
                    return self._transform_qint_quantum_decl(stmt)
            if stmt.value:
                transformed = self._transform_expression(stmt.value)
                if transformed != stmt.value:
                    stmt.value = transformed
            return stmt

        if isinstance(stmt, ExprStmt):
            transformed = self._transform_expression(stmt.expr)
            if transformed != stmt.expr:
                stmt.expr = transformed
            return stmt

        if isinstance(stmt, ForStmt):
            for body_stmt in stmt.body:
                transformed = self._transform_statement(body_stmt)
                if isinstance(transformed, list):
                    idx = stmt.body.index(body_stmt)
                    stmt.body[idx : idx + 1] = transformed
            return stmt

        if isinstance(stmt, IfStmt):
            for then_stmt in stmt.then_body:
                transformed = self._transform_statement(then_stmt)
                if isinstance(transformed, list):
                    idx = stmt.then_body.index(then_stmt)
                    stmt.then_body[idx : idx + 1] = transformed
            for else_stmt in stmt.else_body:
                transformed = self._transform_statement(else_stmt)
                if isinstance(transformed, list):
                    idx = stmt.else_body.index(else_stmt)
                    stmt.else_body[idx : idx + 1] = transformed
            return stmt

        return stmt

    def _transform_expression(self, expr: Expr) -> Expr:
        if isinstance(expr, BinaryExpr):
            return self._transform_binary_expr(expr)
        if isinstance(expr, CallExpr):
            new_args = [self._transform_expression(arg) for arg in expr.args]
            if new_args != expr.args:
                expr.args = new_args
            return expr
        if isinstance(expr, IndexExpr):
            expr.base = self._transform_expression(expr.base)
            for item in expr.items:
                if hasattr(item, "expr") and item.expr is not None:
                    item.expr = self._transform_expression(item.expr)
                if hasattr(item, "start") and item.start is not None:
                    item.start = self._transform_expression(item.start)
                if hasattr(item, "stop") and item.stop is not None:
                    item.stop = self._transform_expression(item.stop)
                if hasattr(item, "step") and item.step is not None:
                    item.step = self._transform_expression(item.step)
            return expr
        if isinstance(expr, UnaryExpr):
            expr.right = self._transform_expression(expr.right)
            return expr
        if isinstance(expr, GroupExpr):
            expr.expr = self._transform_expression(expr.expr)
            return expr
        if isinstance(expr, FStringExpr):
            for part in expr.parts:
                if part.expr is not None:
                    part.expr = self._transform_expression(part.expr)
            return expr
        return expr

    def _transform_binary_expr(self, expr: BinaryExpr) -> Expr:
        left = self._transform_expression(expr.left)
        right = self._transform_expression(expr.right)
        expr.left = left
        expr.right = right

        if expr.op in _QINT_OP_TO_FUNC and is_qint_operand(left, self.symbols) and is_qint_operand(
            right, self.symbols
        ):
            return expr
        return expr

    def _acquire_temp(self) -> str:
        if self._free_temps:
            return self._free_temps.pop()
        name = f"_temp_{self.temp_counter}"
        self.temp_counter += 1
        return name

    def _release_temp(self, name: str) -> None:
        if name.startswith("_temp_"):
            self._free_temps.append(name)

    def _fresh_remainder(self) -> str:
        name = f"_remainder_{self.temp_counter}"
        self.temp_counter += 1
        return name

    def _has_dynamic_qint_shape(self, shape: Optional[List[Optional[int]]]) -> bool:
        return bool(shape and any(d is None for d in shape))

    def _resolve_size(
        self,
        declared_size: Optional[int],
        type_hint: Optional[str],
        expr: Expr,
        dynamic_shape: bool = False,
    ) -> int:
        if dynamic_shape:
            return infer_qint_width(expr, self.symbols)
        hint_width = parse_qint_width(type_hint)
        if hint_width is not None:
            return hint_width
        if declared_size is not None:
            return declared_size
        return infer_qint_width(expr, self.symbols)

    def _qint_symbol_type(self, size: int) -> str:
        return f"quint({size})"

    def _make_qint_decl(self, name: str, size: int, init: Optional[Expr] = None) -> QuantumDecl:
        return QuantumDecl(
            "quint", size, name, init, shape=[size], tensor_type=TensorType("quint", (size,))
        )

    def _ensure_temp_decl(self, name: str, size: int, stmts: List[Stmt]) -> None:
        if name in self._declared_temps:
            return
        self._declared_temps.add(name)
        self.symbols[name] = self._qint_symbol_type(size)
        stmts.append(self._make_qint_decl(name, size))

    def _materialize_constant(self, value: int, width: int) -> Tuple[List[Stmt], Expr]:
        key = (value, width)
        if key in self._const_cache:
            return [], VarExpr(self._const_cache[key])

        name = f"_qconst_{self.const_counter}"
        self.const_counter += 1
        self._const_cache[key] = name
        self.symbols[name] = self._qint_symbol_type(width)
        decl = self._make_qint_decl(name, width, LiteralExpr(value))
        return [decl], VarExpr(name)

    def _materialize_operand(
        self,
        operand: Expr,
        size: int,
        temps_to_release: List[str],
    ) -> Tuple[List[Stmt], Expr]:
        if is_integer_literal(operand):
            value = literal_int_value(operand)
            assert value is not None
            masked = value % (1 << size) if size > 0 else value
            return self._materialize_constant(masked, size)

        if isinstance(operand, BinaryExpr) and operand.op in _QINT_OP_TO_FUNC:
            temp = self._acquire_temp()
            stmts: List[Stmt] = []
            self._ensure_temp_decl(temp, size, stmts)
            sub_stmts = self._desugar_qint_expr(operand, temp, size, temps_to_release)
            stmts.extend(sub_stmts)
            temps_to_release.append(temp)
            return stmts, VarExpr(temp)

        return [], operand

    def _collect_same_op_operands(self, expr: Expr, op: str) -> List[Expr]:
        if isinstance(expr, GroupExpr):
            return self._collect_same_op_operands(expr.expr, op)
        if isinstance(expr, BinaryExpr) and expr.op == op:
            return (
                self._collect_same_op_operands(expr.left, op)
                + self._collect_same_op_operands(expr.right, op)
            )
        return [expr]

    def _simplify_operands(self, op: str, operands: List[Expr]) -> Tuple[Optional[List[Expr]], Optional[int]]:
        """Return simplified operands and optional zero-init value for dest."""
        if op == "+":
            filtered = [o for o in operands if not is_qint_zero(o)]
            if not filtered:
                return [], 0
            return filtered, None

        if op == "*":
            if any(is_qint_zero(o) for o in operands):
                return [], 0
            filtered = [o for o in operands if not is_qint_one(o)]
            if not filtered:
                return [], 1
            return filtered, None

        return operands, None

    def _desugar_qint_expr(
        self,
        expr: Expr,
        dest_name: str,
        size: int,
        temps_to_release: Optional[List[str]] = None,
    ) -> List[Stmt]:
        """Desugar a qint arithmetic expression respecting operator precedence."""
        if temps_to_release is None:
            temps_to_release = []

        if isinstance(expr, GroupExpr):
            return self._desugar_qint_expr(expr.expr, dest_name, size, temps_to_release)

        if not isinstance(expr, BinaryExpr) or expr.op not in _QINT_OP_TO_FUNC:
            return []

        op = expr.op

        if op == "/":
            left_stmts, left = self._materialize_operand(expr.left, size, temps_to_release)
            right_stmts, right = self._materialize_operand(expr.right, size, temps_to_release)
            remainder_name = self._fresh_remainder()
            call = CallExpr(
                VarExpr("QDiv"),
                [left, right, VarExpr(dest_name), VarExpr(remainder_name)],
            )
            remainder_decl = self._make_qint_decl(remainder_name, size)
            self.symbols[remainder_name] = self._qint_symbol_type(size)
            dest_decl = self._make_qint_decl(dest_name, size)
            self.symbols[dest_name] = self._qint_symbol_type(size)
            return left_stmts + right_stmts + [dest_decl, remainder_decl, ExprStmt(call)]

        op_name = _QINT_OP_TO_FUNC[op]
        operands_raw = self._collect_same_op_operands(expr, op)
        simplified_raw, zero_init = self._simplify_operands(op, operands_raw)

        stmts: List[Stmt] = []
        operands: List[Expr] = []
        for operand in simplified_raw or []:
            sub_stmts, ref = self._materialize_operand(operand, size, temps_to_release)
            stmts.extend(sub_stmts)
            operands.append(ref)

        dest_decl = self._make_qint_decl(dest_name, size)
        self.symbols[dest_name] = self._qint_symbol_type(size)

        if zero_init is not None:
            if zero_init == 0:
                dest_decl = self._make_qint_decl(dest_name, size, LiteralExpr(0))
            elif zero_init == 1 and operands and len(operands) == 1:
                only = operands[0]
                only_name = expr_var_name(only)
                if only_name == dest_name:
                    for temp in temps_to_release:
                        self._release_temp(temp)
                    return self._finish_desugar(stmts, dest_name, dest_decl)
                call = CallExpr(VarExpr("QAdd"), [only, VarExpr(dest_name)])
                for temp in temps_to_release:
                    self._release_temp(temp)
                return self._finish_desugar(stmts, dest_name, dest_decl, ExprStmt(call))
            for temp in temps_to_release:
                self._release_temp(temp)
            return self._finish_desugar(stmts, dest_name, dest_decl)

        if not simplified_raw:
            for temp in temps_to_release:
                self._release_temp(temp)
            return stmts + [self._make_qint_decl(dest_name, size, LiteralExpr(0))]

        if len(operands) == 1:
            only = operands[0]
            only_name = expr_var_name(only)
            if only_name == dest_name:
                for temp in temps_to_release:
                    self._release_temp(temp)
                return self._finish_desugar(stmts, dest_name, dest_decl)
            call = CallExpr(VarExpr("QAdd"), [only, VarExpr(dest_name)])
            for temp in temps_to_release:
                self._release_temp(temp)
            return self._finish_desugar(stmts, dest_name, dest_decl, ExprStmt(call))

        call = CallExpr(VarExpr(op_name), operands + [VarExpr(dest_name)])
        for temp in temps_to_release:
            self._release_temp(temp)
        return self._finish_desugar(stmts, dest_name, dest_decl, ExprStmt(call))

    def _finish_desugar(
        self,
        stmts: List[Stmt],
        dest_name: str,
        dest_decl: QuantumDecl,
        call_stmt: Optional[ExprStmt] = None,
    ) -> List[Stmt]:
        result = list(stmts)
        if dest_name.startswith("_temp_") and dest_name in self._declared_temps:
            pass
        else:
            result.append(dest_decl)
        if call_stmt is not None:
            result.append(call_stmt)
        return result

    def _transform_qint_assignment(self, stmt: VarDecl) -> List[Stmt]:
        if not isinstance(stmt.value, BinaryExpr):
            return [stmt]
        size = self._resolve_size(None, stmt.type_hint, stmt.value)
        return self._desugar_qint_expr(stmt.value, stmt.name, size)

    def _resolve_size_from_qint_args(self, args: List[Expr]) -> int:
        for arg in args:
            if isinstance(arg, VarExpr):
                width = parse_qint_width(self.symbols.get(arg.name, ""))
                if width is not None:
                    return width
        return 1

    def _transform_qint_call_initializer(
        self, stmt: QuantumDecl, call: CallExpr
    ) -> List[Stmt]:
        """Desugar qint c = Op(a, b) into decl + Op(a, b, c) for arithmetic calls."""
        size = stmt.size or self._resolve_size_from_qint_args(call.args)
        dest_decl = self._make_qint_decl(stmt.name, size)
        self.symbols[stmt.name] = self._qint_symbol_type(size)
        new_call = CallExpr(
            call.callee,
            list(call.args) + [VarExpr(stmt.name)],
            modifiers=call.modifiers,
        )
        return [dest_decl, ExprStmt(new_call)]

    def _transform_qint_quantum_decl(self, stmt: QuantumDecl) -> List[Stmt]:
        if not isinstance(stmt.value, BinaryExpr):
            return [stmt]
        dynamic = self._has_dynamic_qint_shape(stmt.shape)
        size = self._resolve_size(stmt.size, None, stmt.value, dynamic_shape=dynamic)
        stmt.size = size
        if stmt.shape is not None:
            for i in range(len(stmt.shape)):
                stmt.shape[i] = size if len(stmt.shape) == 1 else stmt.shape[i]
        return self._desugar_qint_expr(stmt.value, stmt.name, size)

    def _get_expression_type(self, expr: Expr) -> Optional[str]:
        if isinstance(expr, VarExpr):
            return self.symbols.get(expr.name)
        if isinstance(expr, IndexExpr) and isinstance(expr.base, VarExpr):
            base_type = self.symbols.get(expr.base.name)
            if base_type and base_type.startswith("qint"):
                return base_type
        return None

    def visit_program(self, node: Program):
        pass

    def visit_var_decl(self, node: VarDecl):
        pass

    def visit_quantum_decl(self, node: QuantumDecl):
        pass

    def visit_func_decl(self, node: FuncDecl):
        pass

    def visit_gate_decl(self, node: GateDecl):
        pass

    def visit_class_decl(self, node: ClassDecl):
        pass

    def visit_for_stmt(self, node: ForStmt):
        pass

    def visit_if_stmt(self, node: IfStmt):
        pass

    def visit_return_stmt(self, node: ReturnStmt):
        pass

    def visit_expr_stmt(self, node: ExprStmt):
        pass

    def visit_call_expr(self, node: CallExpr):
        pass

    def visit_index_expr(self, node: IndexExpr):
        pass

    def visit_binary_expr(self, node: BinaryExpr):
        pass

    def visit_unary_expr(self, node: UnaryExpr):
        pass

    def visit_var_expr(self, node: VarExpr):
        pass

    def visit_literal_expr(self, node: LiteralExpr):
        pass

    def visit_list_expr(self, node: ListExpr):
        pass

    def visit_group_expr(self, node: GroupExpr):
        pass

    def visit_assign_expr(self, node: AssignExpr):
        pass
