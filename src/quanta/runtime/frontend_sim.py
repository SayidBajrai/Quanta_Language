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
    ForStmt, IfStmt, ExprStmt,
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


def get_prints(quanta_code: str) -> str:
    """
    Parse Quanta source, run in statevector simulator, and return the string
    that would be printed by all Print() / print() calls.

    **Frontend Debug Execution Only. Not compatible with hardware backend.**
    Real quantum hardware cannot reveal amplitudes; this is statevector simulation only.

    - print(classical): immediate evaluation, append to output.
    - print(quantum): inspect statevector, append symbolic summary (no state collapse).
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

    if global_qbit > SIMULATION_QBIT_LIMIT:
        raise RuntimeError(
            f"Simulation qbit limit exceeded: {global_qbit} qbits "
            f"(max {SIMULATION_QBIT_LIMIT}). Statevector uses 2^n memory."
        )

    circuit = QuantumCircuit(global_qbit)
    output_lines: List[str] = []
    execution_trace: List[CircuitTraceEntry] = []
    gates = {stmt.name: stmt for stmt in ast.statements if isinstance(stmt, GateDecl)}
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
                if name in ("Print", "print"):
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
