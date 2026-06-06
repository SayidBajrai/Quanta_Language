"""
Frontend runtime interpreter for Quanta.

Simulates Quanta source with statevector, captures Print() output.
**Frontend Debug Execution Only. Not compatible with hardware backend.**

Real quantum hardware cannot reveal amplitudes; this is statevector simulation only.
"""

from __future__ import annotations

import math
from typing import Dict, List, Any, Tuple, Optional

try:
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector
    QISKIT_AVAILABLE = True
except ImportError:
    QISKIT_AVAILABLE = False

from ..ast.nodes import (
    Program, Stmt, Expr,
    VarDecl, ConstDecl, LetDecl, QuantumDecl, FuncDecl, GateDecl, ClassDecl,
    ForStmt, IfStmt, ExprStmt, ReturnStmt,
    CallExpr, IndexExpr, BinaryExpr, UnaryExpr,
    VarExpr, LiteralExpr, ListExpr, GroupExpr, FStringExpr, AssignExpr,
)
from ..errors import QuantaError
from .formatting import (
    CircuitTraceEntry,
    FormatContext,
    _canonical_gate_name,
    format_print_argument,
    gate_trace_display,
    statevector_to_symbolic,
)
from .quantum_arithmetic import (
    QUANTUM_ARITHMETIC_OPS,
    apply_grover,
    apply_qadd,
    apply_qdiv,
    apply_qexpencmult,
    apply_qftadd,
    apply_qmod,
    apply_qmult,
    apply_qsub,
    apply_qtreeadd,
    apply_qtreemult,
)
from .quantum_metrics import compute_fidelity
from .tensor_algebra import (
    cross_product,
    dot_product,
    elementwise_product,
    tensor_product,
    tensor_shape,
    tensor_elementwise_binop,
)
from .tensors import (
    eval_literal_value,
    get_tensor_index,
    reshape_runtime,
)
from ..types.tensor import TensorType, allocate_tensor, infer_shape, validate_shape
from ..sema.typecheck import tensor_type_from_decl, tensor_type_from_quantum

# Re-export for backward compatibility
__all__ = ["get_prints", "statevector_to_symbolic"]

SIMULATION_QBIT_LIMIT = 20

_CLASSICAL_RETURN_TYPES = frozenset({"int", "float", "bool", "str", "var", "list", "dict"})


_SIMULATED_ARITHMETIC = frozenset({
    "QAdd", "QSub", "QMult", "QFTAdd", "QTreeAdd",
    "QExpEncMult", "QTreeMult", "QDiv", "QMod",
})


def _ast_uses_simulated_arithmetic(statements: List[Stmt]) -> bool:
    for stmt in statements:
        if isinstance(stmt, ExprStmt) and isinstance(stmt.expr, CallExpr):
            callee = stmt.expr.callee
            if isinstance(callee, VarExpr) and callee.name in _SIMULATED_ARITHMETIC:
                return True
    return False


def _arithmetic_scratch_width(statements: List[Stmt], reg_sizes: Dict[str, int]) -> int:
    max_w = 0
    for stmt in statements:
        if isinstance(stmt, ExprStmt) and isinstance(stmt.expr, CallExpr):
            callee = stmt.expr.callee
            if isinstance(callee, VarExpr) and callee.name in _SIMULATED_ARITHMETIC:
                for arg in stmt.expr.args:
                    if isinstance(arg, VarExpr) and arg.name in reg_sizes:
                        max_w = max(max_w, reg_sizes[arg.name])
    return max_w


def get_prints(quanta_code: str) -> str:
    """
    Parse Quanta source, run in statevector simulator, and return the string
    that would be printed by all Print() calls.

    **Frontend Debug Execution Only. Not compatible with hardware backend.**
    Real quantum hardware cannot reveal amplitudes; this is statevector simulation only.

    - Print(classical): immediate evaluation, append to output.
    - Print(quantum): inspect statevector, append symbolic summary (no state collapse).
    - Print(obj) and Print(f"{obj}") share the same object-to-string conversion path.
    """
    from ..lexer.lexer import Lexer
    from ..parser.parser import Parser
    from ..sema.transform import ASTTransformer
    from ..sema.validation import SemanticAnalyzer
    from ..sema.indexing import IndexExpander, collect_registers

    if not QISKIT_AVAILABLE:
        raise ImportError(
            "Qiskit is required for get_prints (statevector simulation). "
            "Install with: pip install qiskit"
        )

    lexer = Lexer()
    parser = Parser()
    transformer = ASTTransformer()
    sema = SemanticAnalyzer()

    tokens = lexer.tokenize(quanta_code)
    ast = parser.parse(tokens)
    ast = transformer.transform(ast)
    sema.analyze(ast)
    registers = collect_registers(ast)
    ast = IndexExpander(registers).expand_program(ast)

    qbit_map: Dict[Tuple[str, int], int] = {}
    classical_map: Dict[Tuple[str, int], int] = {}
    reg_sizes: Dict[str, int] = {}
    reg_shapes: Dict[str, List[int]] = {}
    reg_kind: Dict[str, str] = {}
    var_types: Dict[str, TensorType] = {}
    tensor_shapes: Dict[str, List[int]] = {}
    global_qbit = 0
    for stmt in ast.statements:
        if isinstance(stmt, QuantumDecl):
            if stmt.kind == "qdec" and stmt.size is not None and stmt.size2 is not None:
                size = stmt.size + stmt.size2
            elif stmt.kind == "qfloat" and stmt.size is not None and stmt.size2 is not None:
                size = 1 + stmt.size + stmt.size2
            else:
                size = stmt.size or 1
            shape = [d if d is not None else 1 for d in (stmt.shape or [size])]
            reg_sizes[stmt.name] = size
            reg_shapes[stmt.name] = shape
            reg_kind[stmt.name] = stmt.kind
            if stmt.kind in ("qbit", "qint", "qdec", "qfloat"):
                for i in range(size):
                    qbit_map[(stmt.name, i)] = global_qbit
                    global_qbit += 1
            elif stmt.kind in ("bit", "bint"):
                for i in range(size):
                    classical_map[(stmt.name, i)] = 0
                    if stmt.value and isinstance(stmt.value, LiteralExpr):
                        try:
                            init_val = int(stmt.value.value)
                            classical_map[(stmt.name, i)] = (init_val >> i) & 1
                        except (ValueError, TypeError):
                            pass

    arithmetic_ancilla: Optional[int] = None
    arithmetic_temp: List[int] = []
    arithmetic_one: List[int] = []
    arithmetic_vbe_helper: List[int] = []
    arithmetic_product: List[int] = []
    if _ast_uses_simulated_arithmetic(ast.statements):
        uses = {
            name: any(
                isinstance(s, ExprStmt)
                and isinstance(s.expr, CallExpr)
                and isinstance(s.expr.callee, VarExpr)
                and s.expr.callee.name == name
                for s in ast.statements
            )
            for name in _SIMULATED_ARITHMETIC
        }
        scratch_w = _arithmetic_scratch_width(ast.statements, reg_sizes) or 1
        arithmetic_ancilla = global_qbit
        global_qbit += 1
        needs_temp = uses["QSub"] or uses["QMult"] or uses["QDiv"] or uses["QMod"]
        if needs_temp:
            arithmetic_temp = list(range(global_qbit, global_qbit + scratch_w))
            global_qbit += scratch_w
        if uses["QSub"] or uses["QDiv"] or uses["QMod"]:
            arithmetic_one = list(range(global_qbit, global_qbit + scratch_w))
            global_qbit += scratch_w
        if uses["QTreeAdd"]:
            arithmetic_vbe_helper = list(range(global_qbit, global_qbit + 2))
            global_qbit += 2
        if uses["QExpEncMult"] or uses["QTreeMult"]:
            arithmetic_product = list(range(global_qbit, global_qbit + scratch_w * 2))
            global_qbit += scratch_w * 2

    if global_qbit > SIMULATION_QBIT_LIMIT:
        raise RuntimeError(
            f"Simulation qbit limit exceeded: {global_qbit} qbits "
            f"(max {SIMULATION_QBIT_LIMIT}). Statevector uses 2^n memory."
        )

    circuit = QuantumCircuit(global_qbit)
    output_lines: List[str] = []
    execution_trace: List[CircuitTraceEntry] = []
    gates = {stmt.name: stmt for stmt in ast.statements if isinstance(stmt, GateDecl)}

    def lookup_resolved_func(call: CallExpr) -> Optional[FuncDecl]:
        return call.resolved_func
    constants_eval: Dict[str, Any] = {"pi": math.pi, "e": math.e}
    for stmt in ast.statements:
        if isinstance(stmt, VarDecl):
            var_types[stmt.name] = tensor_type_from_decl(stmt)
        if isinstance(stmt, QuantumDecl):
            var_types[stmt.name] = tensor_type_from_quantum(stmt)

    def eval_expr(expr: Expr, ctx: Dict[str, Any]) -> Any:
        if isinstance(expr, LiteralExpr):
            v = expr.value
            if isinstance(v, str) and v.isdigit():
                return int(v)
            if isinstance(v, str) and v.replace(".", "").replace("-", "").isdigit():
                return float(v)
            return v
        if isinstance(expr, FStringExpr):
            fmt_ctx = FormatContext(
                circuit=circuit,
                qbit_map=qbit_map,
                classical_map=classical_map,
                reg_sizes=reg_sizes,
                reg_kind=reg_kind,
                eval_ctx=ctx,
                eval_expr=eval_expr,
                execution_trace=execution_trace,
            )
            return format_print_argument(expr, fmt_ctx)
        if isinstance(expr, VarExpr):
            return ctx.get(expr.name)
        if isinstance(expr, GroupExpr):
            return eval_expr(expr.expr, ctx)
        if isinstance(expr, AssignExpr):
            value = eval_expr(expr.value, ctx)
            ctx[expr.name] = value
            if isinstance(value, list):
                tensor_shapes[expr.name] = infer_shape(value)
            return value
        if isinstance(expr, BinaryExpr):
            l = eval_expr(expr.left, ctx)
            r = eval_expr(expr.right, ctx)
            if isinstance(l, list) or isinstance(r, list):
                return tensor_elementwise_binop(l, r, expr.op)
            if expr.op == "+":
                return l + r
            if expr.op == "-":
                return l - r
            if expr.op == "*":
                return l * r
            if expr.op == "/":
                return l / r
            if expr.op == "==":
                return l == r
            if expr.op == "!=":
                return l != r
            if expr.op == "<":
                return l < r
            if expr.op == ">":
                return l > r
            if expr.op == "<=":
                return l <= r
            if expr.op == ">=":
                return l >= r
            if expr.op == "&&":
                return l and r
            if expr.op == "||":
                return l or r
        if isinstance(expr, UnaryExpr):
            r = eval_expr(expr.right, ctx)
            if expr.op == "-":
                return -r
            if expr.op == "!":
                return not r
        if isinstance(expr, ListExpr):
            el = expr.elements
            if expr.is_range_syntax and len(el) == 3:
                start = eval_expr(el[0], ctx)
                step = eval_expr(el[1], ctx)
                end = eval_expr(el[2], ctx)
                return list(range(int(start), int(end), int(step)))
            return [eval_expr(e, ctx) for e in el]
        if isinstance(expr, IndexExpr):
            root = expr.base
            while isinstance(root, IndexExpr):
                root = root.base
            if isinstance(root, VarExpr) and root.name in ctx:
                value = ctx.get(root.name)
                shape = tensor_shapes.get(root.name)
                if isinstance(value, list) and shape:
                    return get_tensor_index(value, expr, shape)
            base = eval_expr(expr.base, ctx)
            if isinstance(expr.base, VarExpr) and expr.base.name in reg_kind:
                if expr.is_simple():
                    idx = eval_expr(expr.index, ctx)
                    if isinstance(idx, int):
                        if (expr.base.name, idx) in classical_map:
                            return classical_map[(expr.base.name, idx)]
                        if (expr.base.name, idx) in qbit_map:
                            return (expr.base.name, idx)
                return None
            if not expr.is_simple():
                return None
            idx = eval_expr(expr.index, ctx)
            if isinstance(idx, int) and isinstance(base, str):
                if (base, idx) in classical_map:
                    return classical_map[(base, idx)]
                if (base, idx) in qbit_map:
                    return (base, idx)
            return None
        if isinstance(expr, CallExpr) and isinstance(expr.callee, VarExpr):
            name = expr.callee.name
            if name == "Reshape" and len(expr.args) >= 2:
                tensor = eval_expr(expr.args[0], ctx)
                new_shape = [int(eval_expr(a, ctx)) for a in expr.args[1:]]
                return reshape_runtime(tensor, new_shape)
            if name == "Fidelity" and len(expr.args) == 2:
                fmt_ctx = FormatContext(
                    circuit=circuit,
                    qbit_map=qbit_map,
                    classical_map=classical_map,
                    reg_sizes=reg_sizes,
                    reg_kind=reg_kind,
                    eval_ctx=ctx,
                    eval_expr=eval_expr,
                    execution_trace=execution_trace,
                )
                return compute_fidelity(expr.args[0], expr.args[1], fmt_ctx)
            if name == "DotProduct" and len(expr.args) == 2:
                return dot_product(eval_expr(expr.args[0], ctx), eval_expr(expr.args[1], ctx))
            if name == "CrossProduct" and len(expr.args) == 2:
                return cross_product(eval_expr(expr.args[0], ctx), eval_expr(expr.args[1], ctx))
            if name == "ElementwiseProduct" and len(expr.args) == 2:
                return elementwise_product(
                    eval_expr(expr.args[0], ctx), eval_expr(expr.args[1], ctx)
                )
            if name == "TensorProduct" and len(expr.args) == 2:
                return tensor_product(eval_expr(expr.args[0], ctx), eval_expr(expr.args[1], ctx))
            if name == "Shape" and len(expr.args) == 1:
                return tensor_shape(eval_expr(expr.args[0], ctx))
            func = lookup_resolved_func(expr)
            if func is not None:
                return call_user_function(func, expr.args, ctx)
        return None

    def _substitute_param_arg(arg: Expr, param_bind: Dict[str, Expr]) -> Expr:
        if isinstance(arg, VarExpr) and arg.name in param_bind:
            return param_bind[arg.name]
        return arg

    def _is_classical_function(func: FuncDecl) -> bool:
        return func.return_type in _CLASSICAL_RETURN_TYPES

    def _run_classical_function_body(func: FuncDecl, arg_exprs: List[Expr], outer_ctx: Dict[str, Any]) -> Any:
        local_ctx = dict(outer_ctx)
        for param_name, arg_expr in zip(func.params, arg_exprs):
            local_ctx[param_name] = eval_expr(arg_expr, outer_ctx)

        for stmt in func.body:
            if isinstance(stmt, ReturnStmt):
                return eval_expr(stmt.value, local_ctx) if stmt.value else None
            if isinstance(stmt, VarDecl):
                if stmt.value is not None:
                    local_ctx[stmt.name] = eval_expr(stmt.value, local_ctx)
                continue
            if isinstance(stmt, ExprStmt):
                if isinstance(stmt.expr, AssignExpr):
                    eval_expr(stmt.expr, local_ctx)
                    continue
                if isinstance(stmt.expr, CallExpr) and isinstance(stmt.expr.callee, VarExpr):
                    nested = lookup_resolved_func(stmt.expr)
                    if nested is not None:
                        call_user_function(nested, stmt.expr.args, local_ctx)
                        continue
                run_statement(stmt, local_ctx)
                continue
            run_statement(stmt, local_ctx)
        return None

    def _run_quantum_function_body(func: FuncDecl, arg_exprs: List[Expr], ctx: Dict[str, Any]) -> None:
        param_bind = {
            func.params[i]: arg_exprs[i]
            for i in range(min(len(func.params), len(arg_exprs)))
        }
        for stmt in func.body:
            if isinstance(stmt, ReturnStmt):
                return
            if isinstance(stmt, ExprStmt) and isinstance(stmt.expr, CallExpr):
                sub_call = stmt.expr
                sub_callee = sub_call.callee
                sub_args = [_substitute_param_arg(a, param_bind) for a in sub_call.args]
                if isinstance(sub_callee, VarExpr):
                    nested = sub_call.resolved_func
                    if nested is not None:
                        call_user_function(nested, sub_args, ctx)
                    elif sub_callee.name in gates or sub_callee.name in (
                        "H", "X", "Y", "Z", "CNot", "CNOT", "CZ", "Swap", "SWAP", "RZ", "RY", "RX",
                    ):
                        apply_gate(sub_callee.name, sub_args, ctx)
                continue
            run_statement(stmt, ctx)

    def call_user_function(func: FuncDecl, arg_exprs: List[Expr], ctx: Dict[str, Any]) -> Any:
        if _is_classical_function(func):
            return _run_classical_function_body(func, arg_exprs, ctx)
        _run_quantum_function_body(func, arg_exprs, ctx)
        return None

    def _append_trace(
        entry: CircuitTraceEntry, trace_children: Optional[List[CircuitTraceEntry]] = None
    ) -> None:
        if trace_children is not None:
            trace_children.append(entry)
        else:
            execution_trace.append(entry)

    def apply_gate(
        name: str,
        args: List[Expr],
        ctx: Dict[str, Any],
        trace_children: Optional[List[CircuitTraceEntry]] = None,
    ) -> None:
        name_lower = name.lower()
        qubits = []
        params = []
        for a in args:
            if isinstance(a, VarExpr) and reg_kind.get(a.name, "") in ("qbit", "qint", "qdec", "qfloat"):
                sz = reg_sizes.get(a.name, 1)
                qubits.extend([qbit_map[(a.name, i)] for i in range(sz)])
            elif isinstance(a, IndexExpr) and isinstance(a.base, VarExpr):
                idx = eval_expr(a.index, ctx)
                if isinstance(idx, int):
                    key = (a.base.name, idx)
                    if key in qbit_map:
                        qubits.append(qbit_map[key])
            elif isinstance(a, LiteralExpr):
                try:
                    params.append(float(a.value))
                except (ValueError, TypeError):
                    pass

        if name in gates:
            gate_def = gates[name]
            fmt_ctx = FormatContext(
                circuit=circuit,
                qbit_map=qbit_map,
                classical_map=classical_map,
                reg_sizes=reg_sizes,
                reg_kind=reg_kind,
                eval_ctx=ctx,
                eval_expr=eval_expr,
                execution_trace=execution_trace,
            )
            display, trace_qubits = gate_trace_display(name, args, fmt_ctx, ctx)
            children: List[CircuitTraceEntry] = []
            macro_entry = CircuitTraceEntry(
                name=name,
                display=display,
                global_qbits=trace_qubits,
                children=children,
                is_macro=True,
            )
            _append_trace(macro_entry, trace_children)
            param_bind = {gate_def.params[i]: args[i] for i in range(len(args))}
            for s in gate_def.body:
                if isinstance(s, ExprStmt) and isinstance(s.expr, CallExpr):
                    sub_callee = s.expr.callee
                    sub_args = [
                        param_bind.get(a.name, a) if isinstance(a, VarExpr) else a
                        for a in s.expr.args
                    ]
                    if isinstance(sub_callee, VarExpr):
                        apply_gate(sub_callee.name, sub_args, ctx, children)
            return

        fmt_ctx = FormatContext(
            circuit=circuit,
            qbit_map=qbit_map,
            classical_map=classical_map,
            reg_sizes=reg_sizes,
            reg_kind=reg_kind,
            eval_ctx=ctx,
            eval_expr=eval_expr,
            execution_trace=execution_trace,
        )
        display, trace_qubits = gate_trace_display(name, args, fmt_ctx, ctx)
        if trace_qubits:
            qubits = trace_qubits
        gate_entry = CircuitTraceEntry(
            name=_canonical_gate_name(name),
            display=display,
            global_qbits=qubits,
        )
        _append_trace(gate_entry, trace_children)

        if name_lower in ("h", "x", "y", "z") and len(qubits) >= 1:
            for q in qubits:
                if name_lower == "h":
                    circuit.h(q)
                elif name_lower == "x":
                    circuit.x(q)
                elif name_lower == "y":
                    circuit.y(q)
                elif name_lower == "z":
                    circuit.z(q)
        elif name_lower in ("cx", "cnot") and len(qubits) == 2:
            circuit.cx(qubits[0], qubits[1])
        elif name_lower == "cz" and len(qubits) == 2:
            circuit.cz(qubits[0], qubits[1])
        elif name_lower == "swap" and len(qubits) == 2:
            circuit.swap(qubits[0], qubits[1])
        elif name_lower in ("rz", "ry", "rx") and len(params) >= 1 and len(qubits) >= 1:
            theta = params[0]
            for q in qubits:
                if name_lower == "rz":
                    circuit.rz(theta, q)
                elif name_lower == "ry":
                    circuit.ry(theta, q)
                elif name_lower == "rx":
                    circuit.rx(theta, q)

    def resolve_register_qubits(arg: Expr) -> Optional[List[int]]:
        if isinstance(arg, VarExpr) and arg.name in reg_kind:
            if reg_kind[arg.name] in ("qbit", "qint", "qdec", "qfloat"):
                size = reg_sizes.get(arg.name, 1)
                return [qbit_map[(arg.name, i)] for i in range(size)]
        return None

    def resolve_target_int(arg: Expr, ctx: Dict[str, Any]) -> Optional[int]:
        if isinstance(arg, LiteralExpr):
            try:
                return int(arg.value)
            except (ValueError, TypeError):
                return None
        value = eval_expr(arg, ctx)
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return None

    def apply_grover_call(args: List[Expr], ctx: Dict[str, Any]) -> None:
        if len(args) != 2:
            return
        qubits = resolve_register_qubits(args[0])
        target = resolve_target_int(args[1], ctx)
        if qubits is None or target is None:
            return
        apply_grover(circuit, qubits, target)

    def apply_qadd_call(args: List[Expr]) -> None:
        if arithmetic_ancilla is None:
            return
        operand_qubits: List[List[int]] = []
        for arg in args:
            qubits = resolve_register_qubits(arg)
            if qubits is None:
                return
            operand_qubits.append(qubits)
        if len(operand_qubits) >= 2:
            apply_qadd(circuit, operand_qubits, arithmetic_ancilla)

    def apply_qsub_call(args: List[Expr]) -> None:
        if arithmetic_ancilla is None or not arithmetic_temp or not arithmetic_one:
            return
        operand_qubits: List[List[int]] = []
        for arg in args:
            qubits = resolve_register_qubits(arg)
            if qubits is None:
                return
            operand_qubits.append(qubits)
        if len(operand_qubits) >= 2:
            apply_qsub(
                circuit,
                operand_qubits,
                arithmetic_temp,
                arithmetic_one,
                arithmetic_ancilla,
            )

    def apply_qmult_call(args: List[Expr]) -> None:
        if arithmetic_ancilla is None or not arithmetic_temp:
            return
        operand_qubits: List[List[int]] = []
        for arg in args:
            qubits = resolve_register_qubits(arg)
            if qubits is None:
                return
            operand_qubits.append(qubits)
        if len(operand_qubits) >= 3:
            apply_qmult(
                circuit,
                operand_qubits,
                arithmetic_temp,
                arithmetic_one or arithmetic_temp,
                arithmetic_ancilla,
            )

    def apply_qftadd_call(args: List[Expr]) -> None:
        operand_qubits: List[List[int]] = []
        for arg in args:
            qubits = resolve_register_qubits(arg)
            if qubits is None:
                return
            operand_qubits.append(qubits)
        if len(operand_qubits) >= 2:
            apply_qftadd(circuit, operand_qubits)

    def apply_qtreeadd_call(args: List[Expr]) -> None:
        if not arithmetic_vbe_helper:
            return
        operand_qubits: List[List[int]] = []
        for arg in args:
            qubits = resolve_register_qubits(arg)
            if qubits is None:
                return
            operand_qubits.append(qubits)
        if len(operand_qubits) >= 2:
            apply_qtreeadd(circuit, operand_qubits, arithmetic_vbe_helper)

    def apply_qexpencmult_call(args: List[Expr]) -> None:
        if not arithmetic_product:
            return
        operand_qubits: List[List[int]] = []
        for arg in args:
            qubits = resolve_register_qubits(arg)
            if qubits is None:
                return
            operand_qubits.append(qubits)
        if len(operand_qubits) >= 3:
            apply_qexpencmult(circuit, operand_qubits, arithmetic_product)

    def apply_qtreemult_call(args: List[Expr]) -> None:
        if not arithmetic_product or arithmetic_ancilla is None:
            return
        operand_qubits: List[List[int]] = []
        for arg in args:
            qubits = resolve_register_qubits(arg)
            if qubits is None:
                return
            operand_qubits.append(qubits)
        if len(operand_qubits) >= 3:
            apply_qtreemult(
                circuit, operand_qubits, arithmetic_product, arithmetic_ancilla
            )

    def apply_qdiv_call(args: List[Expr]) -> None:
        if arithmetic_ancilla is None or not arithmetic_temp or not arithmetic_one:
            return
        if len(args) != 4:
            return
        qubits = [resolve_register_qubits(arg) for arg in args]
        if any(q is None for q in qubits):
            return
        apply_qdiv(
            circuit,
            qubits[0],
            qubits[1],
            qubits[2],
            qubits[3],
            arithmetic_temp,
            arithmetic_one,
            arithmetic_ancilla,
        )

    def apply_qmod_call(args: List[Expr]) -> None:
        if arithmetic_ancilla is None or not arithmetic_temp or not arithmetic_one:
            return
        operand_qubits: List[List[int]] = []
        for arg in args:
            qubits = resolve_register_qubits(arg)
            if qubits is None:
                return
            operand_qubits.append(qubits)
        if len(operand_qubits) >= 3:
            apply_qmod(
                circuit,
                operand_qubits,
                arithmetic_temp,
                arithmetic_one,
                arithmetic_ancilla,
            )

    arithmetic_one_initialized = False

    def ensure_arithmetic_one_initialized() -> None:
        nonlocal arithmetic_one_initialized
        if arithmetic_one and not arithmetic_one_initialized:
            circuit.x(arithmetic_one[0])
            arithmetic_one_initialized = True

    def run_statement(stmt: Stmt, ctx: Dict[str, Any]) -> None:
        if isinstance(stmt, QuantumDecl):
            if stmt.kind == "qdec" and stmt.size is not None and stmt.size2 is not None:
                size = stmt.size + stmt.size2
            elif stmt.kind == "qfloat" and stmt.size is not None and stmt.size2 is not None:
                size = 1 + stmt.size + stmt.size2
            else:
                size = stmt.size or 1
            if stmt.kind in ("qbit", "qint", "qdec", "qfloat") and stmt.value:
                if isinstance(stmt.value, LiteralExpr):
                    try:
                        val = int(stmt.value.value)
                        for i in range(size):
                            if (val >> i) & 1:
                                circuit.x(qbit_map[(stmt.name, i)])
                    except (ValueError, TypeError):
                        pass
        elif isinstance(stmt, VarDecl):
            tensor_type = tensor_type_from_decl(stmt)
            if stmt.value is not None:
                v = eval_expr(stmt.value, ctx)
                if v is not None:
                    if tensor_type.rank > 0 and isinstance(v, list):
                        if tensor_type.is_dynamic:
                            shape = validate_shape(v, tensor_type.dimensions, stmt.name)
                            tensor_shapes[stmt.name] = list(shape)
                        else:
                            tensor_shapes[stmt.name] = infer_shape(v)
                        ctx[stmt.name] = v
                    else:
                        ctx[stmt.name] = v
            elif tensor_type.rank > 0 and tensor_type.shape():
                allocated = allocate_tensor(tensor_type.base, list(tensor_type.shape()))
                ctx[stmt.name] = allocated
                tensor_shapes[stmt.name] = list(tensor_type.shape())
        elif isinstance(stmt, ConstDecl):
            v = eval_expr(stmt.value, ctx)
            if v is not None:
                ctx[stmt.name] = v
                constants_eval[stmt.name] = v
        elif isinstance(stmt, LetDecl):
            v = eval_expr(stmt.value, ctx)
            if v is not None:
                ctx[stmt.name] = v
        elif isinstance(stmt, ExprStmt):
            expr = stmt.expr
            if isinstance(expr, AssignExpr):
                eval_expr(expr, ctx)
                return
            if isinstance(expr, CallExpr) and isinstance(expr.callee, VarExpr):
                name = expr.callee.name
                if name == "Print":
                    if not expr.args:
                        output_lines.append("")
                        return
                    fmt_ctx = FormatContext(
                        circuit=circuit,
                        qbit_map=qbit_map,
                        classical_map=classical_map,
                        reg_sizes=reg_sizes,
                        reg_kind=reg_kind,
                        eval_ctx=ctx,
                        eval_expr=eval_expr,
                        execution_trace=execution_trace,
                    )
                    arg = expr.args[0]
                    if isinstance(arg, FStringExpr):
                        output_lines.append(format_print_argument(arg, fmt_ctx))
                    elif isinstance(arg, VarExpr) and arg.name in reg_kind:
                        output_lines.append(format_print_argument(arg, fmt_ctx))
                    elif isinstance(arg, IndexExpr):
                        root = arg.base
                        while isinstance(root, IndexExpr):
                            root = root.base
                        if isinstance(root, VarExpr) and root.name in reg_kind:
                            output_lines.append(format_print_argument(arg, fmt_ctx))
                        else:
                            val = eval_expr(arg, ctx)
                            output_lines.append(str(val) if val is not None else "")
                    else:
                        val = eval_expr(arg, ctx)
                        output_lines.append(
                            str(val) if val is not None else format_print_argument(arg, fmt_ctx)
                        )
                    return
                if name == "Measure" and len(expr.args) == 2:
                    qarg, carg = expr.args[0], expr.args[1]
                    qkey = None
                    ckey = None
                    if isinstance(qarg, IndexExpr) and isinstance(qarg.base, VarExpr):
                        qi = eval_expr(qarg.index, ctx)
                        if isinstance(qi, int):
                            qkey = (qarg.base.name, qi)
                    if isinstance(carg, IndexExpr) and isinstance(carg.base, VarExpr):
                        ci = eval_expr(carg.index, ctx)
                        if isinstance(ci, int):
                            ckey = (carg.base.name, ci)
                    if (
                        qkey is not None
                        and ckey is not None
                        and qkey in qbit_map
                        and ckey in classical_map
                    ):
                        sv = Statevector(circuit)
                        qidx = qbit_map[qkey]
                        probs = sv.probabilities([qidx])
                        import random

                        r = random.random()
                        outcome = 1 if r < probs[1] else 0
                        classical_map[ckey] = outcome
                        return
                if name == "QAdd":
                    apply_qadd_call(expr.args)
                    return
                if name == "QSub":
                    ensure_arithmetic_one_initialized()
                    apply_qsub_call(expr.args)
                    return
                if name == "QMult":
                    apply_qmult_call(expr.args)
                    return
                if name == "QFTAdd":
                    apply_qftadd_call(expr.args)
                    return
                if name == "QTreeAdd":
                    apply_qtreeadd_call(expr.args)
                    return
                if name == "QExpEncMult":
                    apply_qexpencmult_call(expr.args)
                    return
                if name == "QTreeMult":
                    apply_qtreemult_call(expr.args)
                    return
                if name == "QDiv":
                    ensure_arithmetic_one_initialized()
                    apply_qdiv_call(expr.args)
                    return
                if name == "QMod":
                    ensure_arithmetic_one_initialized()
                    apply_qmod_call(expr.args)
                    return
                if name == "Grover":
                    apply_grover_call(expr.args, ctx)
                    return
                func = lookup_resolved_func(expr)
                if func is not None:
                    call_user_function(func, expr.args, ctx)
                    return
                if name in ("H", "X", "Y", "Z", "CNot", "CNOT", "CZ", "Swap", "SWAP", "RZ", "RY", "RX"):
                    apply_gate(name, expr.args, ctx)
                elif name in gates:
                    apply_gate(name, expr.args, ctx)
        elif isinstance(stmt, ForStmt):
            it = eval_expr(stmt.iterable, ctx)
            if isinstance(it, list):
                for val in it:
                    ctx[stmt.iterator] = val
                    for s in stmt.body:
                        run_statement(s, ctx)
        elif isinstance(stmt, IfStmt):
            cond = eval_expr(stmt.condition, ctx)
            if cond:
                for s in stmt.then_body:
                    run_statement(s, ctx)
            else:
                for s in stmt.else_body:
                    run_statement(s, ctx)

    ctx: Dict[str, Any] = dict(constants_eval)
    for stmt in ast.statements:
        if isinstance(stmt, (FuncDecl, GateDecl, ClassDecl)):
            continue
        run_statement(stmt, ctx)

    return "\n".join(output_lines)
