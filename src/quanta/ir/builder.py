"""
IR Builder: converts the validated AST (post semantic analysis, post index expansion)
into a flat QCircuit of expanded primitive gates.

This is the canonical place where macros (Bell, QFT, etc.) are expanded to
primitive gates, and where the IR becomes available for analysis and optimization.
"""

from typing import List, Dict, Optional, Tuple, Set, Any
from ..ast.nodes import (
    Program, Stmt, Expr,
    VarDecl, ConstDecl, LetDecl, ClassicalNumericDecl, QuantumDecl, FuncDecl, GateDecl, ClassDecl,
    ForStmt, WhileStmt, IfStmt, ReturnStmt, ExprStmt,
    CallExpr, IndexExpr, SingleIndex, SliceIndex, BinaryExpr, UnaryExpr,
    VarExpr, LiteralExpr, ListExpr, GroupExpr, AssignExpr,
    Node, NoiseModelDecl,
)
from ..ast.visitor import Visitor
from .ir_nodes import QCircuit, QGate, QReg


GATE_MAP: Dict[str, str] = {
    "H": "h", "X": "x", "Y": "y", "Z": "z",
    "CNot": "cx", "CNOT": "cx", "CZ": "cz",
    "Swap": "swap", "SWAP": "swap",
    "RZ": "rz", "RY": "ry", "RX": "rx",
    "Measure": "measure", "S": "s", "CCX": "ccx", "CCNot": "ccx",
}

QUANTUM_ARITHMETIC_OPS = {
    "QAdd", "QMult", "Compare", "Grover",
    "QFTAdd", "QTreeAdd", "QExpEncMult", "QTreeMult",
    "QSub", "QDiv", "QMod",
}

HIGH_LEVEL_GATES = {
    "Bell", "GHZ", "WState", "SwapGate", "QFT", "InverseQFT",
}

ROTATION_GATES = {"RZ", "RY", "RX", "rz", "ry", "rx"}


class IRBuilder(Visitor):
    def __init__(self):
        self.circuit: QCircuit = QCircuit()
        self.registers: Dict[str, tuple] = {}
        self.gates: Dict[str, GateDecl] = {}
        self.register_init: Dict[str, int] = {}
        self.qadd_ancilla = "__qarith_anc"
        self.qarith_temp = "__qarith_temp"
        self.qarith_one = "__qarith_one"
        self.qarith_vbe_helper = "__qarith_vbe_helper"
        self.qarith_product = "__qarith_product"

    def build(self, ast: Program) -> QCircuit:
        self.circuit = QCircuit()

        for stmt in ast.statements:
            if isinstance(stmt, GateDecl):
                self.gates[stmt.name] = stmt
            if isinstance(stmt, QuantumDecl) and stmt.kind in ("qint", "quint"):
                size = stmt.size or 1
                self.registers[stmt.name] = (stmt.kind, size)
                if stmt.value and isinstance(stmt.value, LiteralExpr):
                    try:
                        self.register_init[stmt.name] = int(stmt.value.value)
                    except (ValueError, TypeError):
                        pass

        uses = self._collect_arithmetic_ops(ast)
        scratch_w = 0
        for stmt in ast.statements:
            stmts = [stmt]
            if isinstance(stmt, FuncDecl):
                stmts = list(stmt.body)
            for s in stmts:
                if isinstance(s, ExprStmt) and isinstance(s.expr, CallExpr):
                    if not isinstance(s.expr.callee, VarExpr):
                        continue
                    if s.expr.callee.name in uses and uses[s.expr.callee.name]:
                        for arg in s.expr.args:
                            if isinstance(arg, VarExpr) and arg.name in self.registers:
                                scratch_w = max(scratch_w, self.registers[arg.name][1])
        uses_scratch = any(uses.values())
        if uses_scratch and scratch_w == 0:
            scratch_w = 1

        if uses_scratch:
            self.registers[self.qadd_ancilla] = ("qbit", 1)
            self.circuit.add_register(self.qadd_ancilla, "qbit", 1)
            if uses["QSub"] or uses["QMult"] or uses["QDiv"] or uses["QMod"]:
                self.registers[self.qarith_temp] = ("qbit", scratch_w)
                self.registers[self.qarith_one] = ("qbit", scratch_w)
                self.circuit.add_register(self.qarith_temp, "qbit", scratch_w)
                self.circuit.add_register(self.qarith_one, "qbit", scratch_w)
                one_start = self.circuit.qubit_map[self.qarith_one][0]
                self.circuit.add_gate(QGate("x", (one_start,), comment="init arithmetic one"))
            if uses["QTreeAdd"]:
                self.registers[self.qarith_vbe_helper] = ("qbit", 2)
                self.circuit.add_register(self.qarith_vbe_helper, "qbit", 2)
            if uses["QExpEncMult"] or uses["QTreeMult"]:
                self.registers[self.qarith_product] = ("qbit", scratch_w * 2)
                self.circuit.add_register(self.qarith_product, "qbit", scratch_w * 2)

        for stmt in ast.statements:
            if not isinstance(stmt, GateDecl):
                self.visit(stmt)

        return self.circuit

    def visit(self, node: Node) -> Any:
        if isinstance(node, Program):
            return self.visit_program(node)
        elif isinstance(node, VarDecl):
            return self.visit_var_decl(node)
        elif isinstance(node, ConstDecl):
            return self.visit_const_decl(node)
        elif isinstance(node, LetDecl):
            return self.visit_let_decl(node)
        elif isinstance(node, ClassicalNumericDecl):
            return self.visit_classical_numeric_decl(node)
        elif isinstance(node, QuantumDecl):
            return self.visit_quantum_decl(node)
        elif isinstance(node, FuncDecl):
            return self.visit_func_decl(node)
        elif isinstance(node, GateDecl):
            return self.visit_gate_decl(node)
        elif isinstance(node, ClassDecl):
            return self.visit_class_decl(node)
        elif isinstance(node, ForStmt):
            return self.visit_for_stmt(node)
        elif isinstance(node, WhileStmt):
            return self.visit_while_stmt(node)
        elif isinstance(node, IfStmt):
            return self.visit_if_stmt(node)
        elif isinstance(node, ReturnStmt):
            return self.visit_return_stmt(node)
        elif isinstance(node, ExprStmt):
            return self.visit_expr_stmt(node)
        elif isinstance(node, CallExpr):
            return self.visit_call_expr(node)
        elif isinstance(node, IndexExpr):
            return self.visit_index_expr(node)
        elif isinstance(node, BinaryExpr):
            return self.visit_binary_expr(node)
        elif isinstance(node, UnaryExpr):
            return self.visit_unary_expr(node)
        elif isinstance(node, VarExpr):
            return self.visit_var_expr(node)
        elif isinstance(node, LiteralExpr):
            return self.visit_literal_expr(node)
        elif isinstance(node, ListExpr):
            return self.visit_list_expr(node)
        elif isinstance(node, GroupExpr):
            return self.visit_group_expr(node)
        elif isinstance(node, AssignExpr):
            return self.visit_assign_expr(node)
        elif isinstance(node, NoiseModelDecl):
            return self.visit_noisemodel_decl(node)
        else:
            raise NotImplementedError(f"No visit method for {type(node).__name__}")

    @staticmethod
    def _collect_arithmetic_ops(ast: Program) -> Dict[str, bool]:
        uses = {
            "QAdd": False, "QSub": False, "QMult": False, "QFTAdd": False,
            "QTreeAdd": False, "QExpEncMult": False, "QTreeMult": False,
            "QDiv": False, "QMod": False,
        }
        for stmt in ast.statements:
            stmts = [stmt]
            if isinstance(stmt, FuncDecl):
                stmts = list(stmt.body)
            for s in stmts:
                if isinstance(s, ExprStmt) and isinstance(s.expr, CallExpr):
                    if not isinstance(s.expr.callee, VarExpr):
                        continue
                    name = s.expr.callee.name
                    if name in uses:
                        uses[name] = True
        return uses

    def visit_program(self, node: Program) -> None:
        for stmt in node.statements:
            self.visit(stmt)

    def visit_var_decl(self, node: VarDecl) -> None:
        pass

    def visit_const_decl(self, node: ConstDecl) -> None:
        pass

    def visit_let_decl(self, node: LetDecl) -> None:
        pass

    def visit_classical_numeric_decl(self, node: ClassicalNumericDecl) -> None:
        pass

    def visit_quantum_decl(self, node: QuantumDecl) -> None:
        from ..types.numeric import flat_qubit_count, init_bit_pattern, qreal_nearest_index

        size = flat_qubit_count(node.kind, node.size, node.size2)
        self.registers[node.name] = (node.kind, size)
        start_idx = self.circuit.add_register(node.name, node.kind, size)

        raw_init = self._compile_time_number(node.value) if node.value else None
        if raw_init is not None:
            try:
                if node.kind == "qreal":
                    lo = node.real_min if node.real_min is not None else 0.0
                    hi = node.real_max if node.real_max is not None else 1.0
                    pattern = qreal_nearest_index(float(raw_init), node.size or 1, lo, hi)
                elif node.kind in ("qdec", "qudec"):
                    pattern = init_bit_pattern(
                        float(raw_init), node.kind, node.size or 1, node.size2 or 0
                    )
                elif node.kind == "qint":
                    pattern = init_bit_pattern(int(raw_init), "qint", node.size or 1)
                else:
                    pattern = init_bit_pattern(int(raw_init), node.kind, node.size or 1)
                for i in range(size):
                    if (pattern >> i) & 1:
                        self.circuit.add_gate(
                            QGate("x", (start_idx + i,), comment=f"init {node.name}[{i}]")
                        )
            except (ValueError, TypeError):
                pass

    def visit_func_decl(self, node: FuncDecl) -> None:
        pass

    def visit_gate_decl(self, node: GateDecl) -> None:
        pass

    def visit_class_decl(self, node: ClassDecl) -> None:
        pass

    def visit_noisemodel_decl(self, node: NoiseModelDecl) -> None:
        pass

    def visit_while_stmt(self, node: WhileStmt) -> None:
        pass

    def visit_for_stmt(self, node: ForStmt) -> None:
        if isinstance(node.iterable, ListExpr):
            for body_stmt in node.body:
                self.visit(body_stmt)
        else:
            for body_stmt in node.body:
                self.visit(body_stmt)

    def visit_if_stmt(self, node: IfStmt) -> None:
        for stmt in node.then_body:
            self.visit(stmt)
        for stmt in node.else_body:
            self.visit(stmt)

    def visit_return_stmt(self, node: ReturnStmt) -> None:
        pass

    def visit_expr_stmt(self, node: ExprStmt) -> None:
        self.visit(node.expr)

    def visit_call_expr(self, node: CallExpr) -> None:
        if not isinstance(node.callee, VarExpr):
            return
        name = node.callee.name

        if name in QUANTUM_ARITHMETIC_OPS:
            self._handle_quantum_arithmetic(name, node.args)
            return

        if name in ("Print", "Fidelity", "Reshape", "DotProduct", "CrossProduct",
                     "ElementwiseProduct", "TensorProduct", "Shape"):
            return

        if name in ("len", "range", "assert", "error", "warn"):
            return

        if name in HIGH_LEVEL_GATES:
            rw = self._get_register_wise_info(node.args)
            if name == "Bell" and len(node.args) == 2 and rw is not None:
                self._generate_bell_register_wise(node.args, rw[0], rw[1])
                return
            if name == "GHZ" and len(node.args) >= 2 and rw is not None:
                self._generate_ghz_register_wise(node.args, rw[0], rw[1])
                return
            expanded = self._expand_qubit_args(node.args)
            if expanded is not None:
                self._handle_high_level_gate(name, expanded, node.modifiers, node.ctrl_count)
            return

        if name == "Measure" and len(node.args) == 2:
            self._handle_measure(node.args)
            return

        if name == "reset" and len(node.args) == 1:
            q_idx = self._resolve_qubit(node.args[0])
            if q_idx is not None:
                self.circuit.add_gate(QGate("reset", (q_idx,), comment="reset"))
            return

        if name in GATE_MAP:
            self._emit_gate(name, node.args, node.modifiers, node.ctrl_count)
            return

    def visit_index_expr(self, node: IndexExpr) -> str:
        base = self._expr_name(node.base)
        if len(node.items) == 1 and isinstance(node.items[0], SingleIndex):
            index = self._eval_expr(node.items[0].expr)
            return f"{base}[{index}]"
        return base

    def visit_binary_expr(self, node: BinaryExpr) -> str:
        left = self._eval_expr(node.left)
        right = self._eval_expr(node.right)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            import operator
            ops = {"+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv, "%": operator.mod}
            op_func = ops.get(node.op)
            if op_func:
                try:
                    return op_func(left, right)
                except ZeroDivisionError:
                    pass
        return f"({left} {node.op} {right})"

    def visit_unary_expr(self, node: UnaryExpr) -> Any:
        right = self._eval_expr(node.right)
        if node.op == "-" and isinstance(right, (int, float)):
            return -right
        return f"{node.op}{right}"

    def visit_var_expr(self, node: VarExpr) -> str:
        return node.name

    def visit_literal_expr(self, node: LiteralExpr) -> Any:
        return node.value

    def visit_list_expr(self, node: ListExpr) -> str:
        return str([self._eval_expr(e) for e in node.elements])

    def visit_group_expr(self, node: GroupExpr) -> Any:
        return self._eval_expr(node.expr)

    def visit_assign_expr(self, node: AssignExpr) -> str:
        return f"{node.name} = {self._eval_expr(node.value)}"

    def _expr_name(self, expr: Expr) -> str:
        if isinstance(expr, VarExpr):
            return expr.name
        if isinstance(expr, IndexExpr) and isinstance(expr.base, VarExpr):
            return expr.base.name
        return str(self._eval_expr(expr))

    def _eval_expr(self, expr: Expr) -> Any:
        result = self.visit(expr)
        if isinstance(result, str):
            try:
                if "." in result:
                    return float(result)
                return int(result)
            except (ValueError, TypeError):
                return result
        return result

    def _compile_time_number(self, expr: Expr) -> Optional[float]:
        if isinstance(expr, LiteralExpr):
            try:
                return float(expr.value)
            except (ValueError, TypeError):
                return None
        if isinstance(expr, GroupExpr):
            return self._compile_time_number(expr.expr)
        if isinstance(expr, UnaryExpr) and expr.op == "-":
            inner = self._compile_time_number(expr.right)
            return -inner if inner is not None else None
        return None

    def _resolve_qubit(self, expr: Expr) -> Optional[int]:
        if isinstance(expr, VarExpr):
            if expr.name in self.circuit.qubit_map:
                return self.circuit.qubit_map[expr.name][0]
            return None
        if isinstance(expr, IndexExpr) and isinstance(expr.base, VarExpr):
            base_name = expr.base.name
            if base_name not in self.circuit.qubit_map:
                return None
            if len(expr.items) == 1 and isinstance(expr.items[0], SingleIndex):
                idx_val = self._eval_expr(expr.items[0].expr)
                if isinstance(idx_val, (int, float)):
                    return self.circuit.resolve_qubit(base_name, int(idx_val))
        return None

    def _resolve_qubits(self, expr: Expr) -> List[int]:
        if isinstance(expr, VarExpr):
            name = expr.name
            if name in self.circuit.qubit_map:
                start, end = self.circuit.qubit_map[name]
                return list(range(start, end))
        if isinstance(expr, IndexExpr) and isinstance(expr.base, VarExpr):
            base_name = expr.base.name
            if base_name not in self.circuit.qubit_map:
                return []
            if len(expr.items) == 1 and isinstance(expr.items[0], SingleIndex):
                idx_val = self._eval_expr(expr.items[0].expr)
                if isinstance(idx_val, (int, float)):
                    return [self.circuit.resolve_qubit(base_name, int(idx_val))]
        return []

    def _emit_gate(self, name: str, args: List[Expr], modifiers: List[str], ctrl_count: Optional[int]):
        qasm_name = GATE_MAP[name]
        is_inverse = "inv" in modifiers
        ctrl = ctrl_count or ("ctrl" in modifiers and 1 or 0)

        if is_inverse and name in ("S",):
            qasm_name = "sdg"

        qubits: List[int] = []
        for arg in args:
            q = self._resolve_qubit(arg)
            if q is not None:
                qubits.append(q)

        if not qubits:
            return

        param = 0.0
        if name in ROTATION_GATES and len(args) >= 2:
            p = self._eval_expr(args[0])
            try:
                param = float(p)
            except (ValueError, TypeError):
                param = 0.0

        comment = f"{name}"
        if is_inverse:
            comment = f"inv({name})"
        if ctrl > 0:
            comment = f"ctrl({name})"

        self.circuit.add_gate(QGate(
            qasm_name, tuple(qubits), (param,) if param != 0.0 else (),
            is_inverse=is_inverse, comment=comment,
        ))

    def _handle_measure(self, args: List[Expr]):
        q_arg = args[0]
        c_arg = args[1]

        if isinstance(q_arg, VarExpr) and isinstance(c_arg, VarExpr):
            q_name = q_arg.name
            c_name = c_arg.name
            if q_name in self.registers and c_name in self.registers:
                q_kind, q_size = self.registers[q_name]
                c_kind, c_size = self.registers[c_name]
                if q_kind in ("qbit", "qint", "quint", "qdec", "qudec", "qfloat", "qreal") and \
                   c_kind in ("bit", "bint"):
                    size = min(q_size, c_size)
                    for i in range(size):
                        q_idx = self.circuit.resolve_qubit(q_name, i)
                        self.circuit.add_gate(QGate("measure", (q_idx,), is_measure=True,
                                            comment=f"measure {q_name}[{i}]"))
                    return

        q_idx = self._resolve_qubit(q_arg)
        if q_idx is not None:
            self.circuit.add_gate(QGate("measure", (q_idx,), is_measure=True,
                                        comment=f"measure"))

    def _expand_qubit_args(self, args: List[Expr]) -> Optional[List[Expr]]:
        result: List[Expr] = []
        for arg in args:
            if isinstance(arg, VarExpr):
                if arg.name not in self.registers:
                    return None
                kind, size = self.registers[arg.name]
                if kind not in ("qbit", "qint", "quint", "qdec", "qudec", "qfloat", "qreal"):
                    return None
                for i in range(size):
                    result.append(IndexExpr(VarExpr(arg.name), [SingleIndex(LiteralExpr(i))]))
            elif isinstance(arg, IndexExpr) and len(arg.items) == 1 and isinstance(arg.items[0], SliceIndex):
                slice_item = arg.items[0]
                start = self._eval_to_int(slice_item.start)
                end = self._eval_to_int(slice_item.stop)
                step = self._eval_to_int(slice_item.step) if slice_item.step is not None else 1
                if start is None or end is None or step is None or step == 0:
                    return None
                for i in range(start, end, step):
                    result.append(IndexExpr(arg.base, [SingleIndex(LiteralExpr(i))]))
            elif isinstance(arg, IndexExpr):
                result.append(arg)
            else:
                return None
        return result

    def _eval_to_int(self, expr: Expr) -> Optional[int]:
        import math
        if isinstance(expr, LiteralExpr):
            try:
                v = expr.value
                if isinstance(v, (int, float)):
                    return int(v)
                if isinstance(v, str) and v.lstrip("-").isdigit():
                    return int(v)
            except (ValueError, TypeError):
                pass
            return None
        if isinstance(expr, VarExpr):
            if expr.name == "pi":
                return int(math.pi)
            return None
        if isinstance(expr, GroupExpr):
            return self._eval_to_int(expr.expr)
        if isinstance(expr, UnaryExpr) and expr.op == "-":
            inner = self._eval_to_int(expr.right)
            return -inner if inner is not None else None
        if isinstance(expr, BinaryExpr):
            left = self._eval_to_int(expr.left)
            right = self._eval_to_int(expr.right)
            if left is None or right is None:
                return None
            if expr.op == "+":
                return left + right
            if expr.op == "-":
                return left - right
            if expr.op == "*":
                return left * right
            if expr.op == "/":
                return left // right if right != 0 else None
        return None

    def _get_register_wise_info(self, args: List[Expr]) -> Optional[Tuple[int, List[str]]]:
        if not args:
            return None
        names: List[str] = []
        size: Optional[int] = None
        for arg in args:
            if not isinstance(arg, VarExpr) or arg.name not in self.registers:
                return None
            kind, n = self.registers[arg.name]
            if kind not in ("qbit", "qint", "qdec", "qfloat"):
                return None
            if size is None:
                size = n
            elif size != n:
                return None
            names.append(arg.name)
        return (size, names) if size is not None else None

    def _handle_high_level_gate(self, gate_name: str, args: List[Expr],
                                 modifiers: List[str], ctrl_count: Optional[int]):
        if gate_name == "Bell":
            if len(args) == 2:
                self._generate_bell_gate(args)
        elif gate_name == "GHZ":
            if len(args) >= 2:
                self._generate_ghz_gate(args)
        elif gate_name == "WState":
            if len(args) == 3:
                self._generate_wstate_gate(args)
        elif gate_name == "SwapGate":
            if len(args) == 2:
                self._generate_swap_gate(args)
        elif gate_name == "QFT":
            if len(args) >= 1:
                self._generate_qft_gate(args)
        elif gate_name == "InverseQFT":
            if len(args) >= 1:
                self._generate_inverse_qft_gate(args)

    def _generate_bell_gate(self, args: List[Expr]):
        q0 = self._resolve_qubit(args[0])
        q1 = self._resolve_qubit(args[1])
        if q0 is None or q1 is None:
            return
        self.circuit.add_gate(QGate("h", (q0,), comment="Bell: H"))
        self.circuit.add_gate(QGate("cx", (q0, q1), comment="Bell: CNOT"))

    def _generate_ghz_gate(self, args: List[Expr]):
        qubits = [self._resolve_qubit(a) for a in args]
        if any(q is None for q in qubits):
            return
        self.circuit.add_gate(QGate("h", (qubits[0],), comment="GHZ: H"))
        for i in range(len(qubits) - 1):
            self.circuit.add_gate(QGate("cx", (qubits[i], qubits[i + 1]),
                                         comment=f"GHZ: CNOT {i}"))

    def _generate_wstate_gate(self, args: List[Expr]):
        import math
        q0 = self._resolve_qubit(args[0])
        q1 = self._resolve_qubit(args[1])
        q2 = self._resolve_qubit(args[2])
        if q0 is None or q1 is None or q2 is None:
            return
        theta = 2 * math.acos(1 / math.sqrt(3))
        self.circuit.add_gate(QGate("ry", (q0,), (theta,), comment="WState: RY"))
        self.circuit.add_gate(QGate("cx", (q0, q1), comment="WState: CNOT q0,q1"))
        self.circuit.add_gate(QGate("cx", (q0, q2), comment="WState: CNOT q0,q2"))

    def _generate_swap_gate(self, args: List[Expr]):
        a = self._resolve_qubit(args[0])
        b = self._resolve_qubit(args[1])
        if a is None or b is None:
            return
        self.circuit.add_gate(QGate("cx", (a, b), comment="SwapGate: CX a,b"))
        self.circuit.add_gate(QGate("cx", (b, a), comment="SwapGate: CX b,a"))
        self.circuit.add_gate(QGate("cx", (a, b), comment="SwapGate: CX a,b"))

    def _generate_qft_gate(self, args: List[Expr]):
        qubits = [self._resolve_qubit(a) for a in args]
        if any(q is None for q in qubits):
            return
        n = len(qubits)
        for i in range(n):
            self.circuit.add_gate(QGate("h", (qubits[i],), comment=f"QFT: H[{i}]"))
            for j in range(i + 1, n):
                phase = 3.141592653589793 / (2 ** (j - i))
                self.circuit.add_gate(QGate("crz", (qubits[j], qubits[i]), (phase,),
                                            comment=f"QFT: CRZ({j},{i})"))
        for i in range(n // 2):
            self.circuit.add_gate(QGate("swap", (qubits[i], qubits[n - 1 - i]),
                                        comment=f"QFT: SWAP({i},{n-1-i})"))

    def _generate_inverse_qft_gate(self, args: List[Expr]):
        qubits = [self._resolve_qubit(a) for a in args]
        if any(q is None for q in qubits):
            return
        n = len(qubits)
        for i in range(n // 2):
            self.circuit.add_gate(QGate("swap", (qubits[i], qubits[n - 1 - i]),
                                        comment=f"InvQFT: SWAP({i},{n-1-i})"))
        for i in range(n - 1, -1, -1):
            for j in range(n - 1, i, -1):
                phase = -3.141592653589793 / (2 ** (j - i))
                self.circuit.add_gate(QGate("crz", (qubits[j], qubits[i]), (phase,),
                                            comment=f"InvQFT: CRZ({j},{i})"))
            self.circuit.add_gate(QGate("h", (qubits[i],), comment=f"InvQFT: H[{i}]"))

    def _generate_bell_register_wise(self, args: List[Expr], size: int, names: List[str]):
        a, b = names[0], names[1]
        for i in range(size):
            q0 = self.circuit.resolve_qubit(a, i)
            q1 = self.circuit.resolve_qubit(b, i)
            self.circuit.add_gate(QGate("h", (q0,), comment=f"Bell[{i}]: H"))
            self.circuit.add_gate(QGate("cx", (q0, q1), comment=f"Bell[{i}]: CNOT"))

    def _generate_ghz_register_wise(self, args: List[Expr], size: int, names: List[str]):
        r0 = names[0]
        for i in range(size):
            q0 = self.circuit.resolve_qubit(r0, i)
            self.circuit.add_gate(QGate("h", (q0,), comment=f"GHZ[{i}]: H"))
            for j in range(1, len(names)):
                qj = self.circuit.resolve_qubit(names[j], i)
                self.circuit.add_gate(QGate("cx", (q0, qj),
                                             comment=f"GHZ[{i}]: CNOT r0,r{j}"))

    def _handle_quantum_arithmetic(self, op_name: str, args: List[Expr]):
        arg_names = [self._expr_name(a) for a in args]
        comment = f"{op_name}({', '.join(arg_names)})"

        all_qubits: Set[int] = set()
        for arg in args:
            for q in self._resolve_qubits(arg):
                all_qubits.add(q)

        anc = self.qadd_ancilla
        if anc in self.circuit.qubit_map:
            all_qubits.add(self.circuit.qubit_map[anc][0])

        if all_qubits:
            self.circuit.add_gate(QGate(
                op_name.lower(), tuple(sorted(all_qubits)), (),
                comment=comment + " [expanded]",
            ))
