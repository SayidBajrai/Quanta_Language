"""
Structured OpenQASM 3 code generator.

Preserves ``def``/``gate`` structure and control flow instead of fully flattening
programs. Used when ``compile(..., keep_structure=True)``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from ..ast.nodes import (
    Program,
    Stmt,
    Expr,
    QuantumDecl,
    FuncDecl,
    GateDecl,
    ForStmt,
    WhileStmt,
    IfStmt,
    ReturnStmt,
    ExprStmt,
    CallExpr,
    VarExpr,
    LiteralExpr,
    BinaryExpr,
    UnaryExpr,
    GroupExpr,
    AssignExpr,
    ParamSpec,
)
from ..sema.overload import func_param_signature, mangled_def_name
from .qasm3 import QASM3Generator, GATE_MAP, QUANTUM_ARITHMETIC_OPS


class StructuredQASMGenerator(QASM3Generator):
    """Emit structured OpenQASM 3 with ``def``, ``gate``, and control flow."""

    def __init__(self):
        super().__init__()
        self.emitted_arithmetic_gates: Set[str] = set()
        self.in_def_body = False
        self.local_registers: Set[str] = set()

    def _func_def_name(self, func: FuncDecl) -> str:
        return mangled_def_name(func.name, func_param_signature(func))

    def _emit_user_func_call(self, expr: CallExpr) -> bool:
        if expr.resolved_func is None:
            return False
        qname = self._func_def_name(expr.resolved_func)
        args = ", ".join(self._expr_to_qasm(arg) for arg in expr.args)
        self._emit(f"{qname} {args};")
        return True

    def _format_user_func_call(self, expr: CallExpr) -> Optional[str]:
        if expr.resolved_func is None:
            return None
        qname = self._func_def_name(expr.resolved_func)
        args = ", ".join(self._expr_to_qasm(arg) for arg in expr.args)
        return f"{qname} {args}"

    def _emit(self, line: str) -> None:
        prefix = "    " * self.indent_level
        self.lines.append(f"{prefix}{line}" if line else "")

    def _qasm_quantum_kind(self, kind: str) -> str:
        if kind in ("qbit", "qint"):
            return "qubit"
        if kind in ("bit", "bint"):
            return "bit"
        return kind

    def _param_to_qasm_type(self, pspec: ParamSpec) -> str:
        qasm_kind = self._qasm_quantum_kind(pspec.kind)
        if pspec.size and pspec.size > 1:
            return f"{qasm_kind}[{pspec.size}]"
        return qasm_kind

    def _return_type_to_qasm(self, func: FuncDecl) -> str:
        if func.return_kind:
            qasm_kind = self._qasm_quantum_kind(func.return_kind)
            size = func.return_size or 1
            if size > 1:
                return f" -> {qasm_kind}[{size}]"
            return f" -> {qasm_kind}"
        if func.return_type == "int":
            return " -> int"
        if func.return_type == "float":
            return " -> float"
        if func.return_type == "bool":
            return " -> bool"
        return ""

    def generate(self, ast: Program) -> str:
        self.lines = []
        self.registers = {}
        self.gates = {}
        self.emitted_arithmetic_gates = set()
        self.in_def_body = False
        self.local_registers = set()
        self.indent_level = 0

        for stmt in ast.statements:
            if isinstance(stmt, GateDecl):
                self.gates[stmt.name] = stmt
            elif isinstance(stmt, QuantumDecl):
                self.registers[stmt.name] = (stmt.kind, stmt.size or 1)

        self._emit("OPENQASM 3;")
        self._emit('include "stdgates.inc";')
        self._emit("")

        for stmt in ast.statements:
            if isinstance(stmt, GateDecl):
                self.visit_gate_decl(stmt)

        for stmt in ast.statements:
            if isinstance(stmt, FuncDecl):
                self._emit_function_def(stmt)

        for stmt in ast.statements:
            if not isinstance(stmt, (GateDecl, FuncDecl)):
                self.visit(stmt)

        return "\n".join(self.lines)

    def _emit_function_def(self, node: FuncDecl) -> None:
        params = ", ".join(
            f"{self._param_to_qasm_type(pspec)} {pspec.name}" for pspec in node.param_specs
        )
        ret = self._return_type_to_qasm(node)
        qname = self._func_def_name(node)
        self._emit(f"def {qname} {params}{ret} {{")
        self.indent_level += 1
        self.in_def_body = True
        saved_locals = set(self.local_registers)
        for stmt in node.body:
            self.visit(stmt)
        self.local_registers = saved_locals
        self.in_def_body = False
        self.indent_level -= 1
        self._emit("}")
        self._emit("")

    def visit_quantum_decl(self, node: QuantumDecl) -> None:
        size = node.size or 1
        if not self.in_def_body:
            self.registers[node.name] = (node.kind, size)
        else:
            self.local_registers.add(node.name)

        qasm_kind = self._qasm_quantum_kind(node.kind)
        if size > 1:
            self._emit(f"{qasm_kind}[{size}] {node.name};")
        else:
            self._emit(f"{qasm_kind} {node.name};")

        if node.value and isinstance(node.value, LiteralExpr):
            try:
                init_value = int(node.value.value)
                for i in range(size):
                    if (init_value >> i) & 1:
                        self._emit(f"x {node.name}[{i}];")
            except (ValueError, TypeError):
                pass

    def visit_func_decl(self, node: FuncDecl) -> None:
        """Function declarations are emitted separately as OpenQASM ``def``."""
        pass

    def visit_while_stmt(self, node: WhileStmt) -> None:
        cond = self._expr_to_qasm(node.condition)
        self._emit(f"while ({cond}) {{")
        self.indent_level += 1
        for stmt in node.body:
            self.visit(stmt)
        self.indent_level -= 1
        self._emit("}")

    def visit_return_stmt(self, node: ReturnStmt) -> None:
        if node.value is None:
            self._emit("return;")
            return
        value = self._expr_to_qasm(node.value)
        self._emit(f"return {value};")

    def visit_expr_stmt(self, node: ExprStmt) -> None:
        expr = node.expr
        if isinstance(expr, AssignExpr):
            self._emit(f"{self._format_assignment(expr)};")
            return
        if isinstance(expr, CallExpr) and isinstance(expr.callee, VarExpr):
            if expr.callee.name == "Print":
                return
            if self._emit_user_func_call(expr):
                return
        super().visit_expr_stmt(node)

    def visit_assign_expr(self, node: AssignExpr) -> str:
        return self._format_assignment(node)

    def _format_assignment(self, node: AssignExpr) -> str:
        rhs = self._format_assign_rhs(node.value)
        return f"{node.name} = {rhs}"

    def _format_assign_rhs(self, expr: Expr) -> str:
        if isinstance(expr, CallExpr) and isinstance(expr.callee, VarExpr):
            call = self._format_user_func_call(expr)
            if call is not None:
                return call
            if name == "Measure" and len(expr.args) == 1:
                return f"measure {self._expr_to_qasm(expr.args[0])}"
        return self._expr_to_qasm(expr)

    def _expr_to_qasm(self, expr: Expr) -> str:
        if isinstance(expr, CallExpr) and isinstance(expr.callee, VarExpr):
            name = expr.callee.name
            if name == "int" and len(expr.args) == 1:
                return f"int({self._expr_to_qasm(expr.args[0])})"
            if name in ("arccos", "acos", "sin", "cos", "pi"):
                if name == "pi" and not expr.args:
                    return "pi"
                args = ", ".join(self._expr_to_qasm(arg) for arg in expr.args)
                fn = "arccos" if name == "acos" else name
                return f"{fn}({args})" if args else fn
        if isinstance(expr, BinaryExpr):
            left = self._expr_to_qasm(expr.left)
            right = self._expr_to_qasm(expr.right)
            return f"({left} {expr.op} {right})"
        if isinstance(expr, UnaryExpr):
            right = self._expr_to_qasm(expr.right)
            return f"{expr.op}{right}"
        if isinstance(expr, GroupExpr):
            return f"({self._expr_to_qasm(expr.expr)})"
        return super()._expr_to_qasm(expr)

    def _register_size_for_arg(self, arg: Expr) -> int:
        reg_str = QASM3Generator._expr_to_qasm(self, arg)
        reg_name = reg_str.split("[")[0]
        return self.registers.get(reg_name, (None, 1))[1]

    def _arithmetic_signature(self, op_name: str, args: List[Expr]) -> str:
        if op_name == "Grover" and len(args) >= 2:
            reg_size = str(self._register_size_for_arg(args[0]))
            target = QASM3Generator._eval_to_int(self, args[1])
            if target is not None:
                return f"Grover_{reg_size}_{target}"
        sizes = [str(self._register_size_for_arg(arg)) for arg in args]
        return f"{op_name}_{'_'.join(sizes)}"

    def _emit_arithmetic_gate_def(self, op_name: str, args: List[Expr], gate_name: str) -> None:
        if op_name == "Grover" and len(args) >= 2:
            pname = "__p0"
            reg_str = QASM3Generator._expr_to_qasm(self, args[0])
            reg_name = reg_str.split("[")[0]
            kind, size = self.registers.get(reg_name, ("qint", 1))
            temp_registers = dict(self.registers)
            temp_registers[pname] = (kind, size)
            saved_registers = self.registers
            saved_lines = self.lines
            body_lines: List[str] = []
            self.registers = temp_registers
            self.lines = body_lines
            try:
                QASM3Generator._generate_grover_circuit(
                    self, [VarExpr(pname), args[1]]
                )
            finally:
                self.registers = saved_registers
                self.lines = saved_lines

            self._emit(f"gate {gate_name} {pname} {{")
            self.indent_level += 1
            for line in body_lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("//"):
                    self._emit(stripped)
            self.indent_level -= 1
            self._emit("}")
            self._emit("")
            return

        param_names: List[str] = []
        temp_registers: Dict[str, Tuple[str, int]] = dict(self.registers)
        param_exprs: List[Expr] = []

        for i, arg in enumerate(args):
            pname = f"__p{i}"
            reg_str = QASM3Generator._expr_to_qasm(self, arg)
            reg_name = reg_str.split("[")[0]
            kind, size = self.registers.get(reg_name, ("qint", 1))
            temp_registers[pname] = (kind, size)
            param_names.append(pname)
            param_exprs.append(VarExpr(pname))

        saved_registers = self.registers
        saved_lines = self.lines
        body_lines: List[str] = []
        self.registers = temp_registers
        self.lines = body_lines
        try:
            super()._handle_quantum_arithmetic(op_name, param_exprs)
        finally:
            self.registers = saved_registers
            self.lines = saved_lines

        self._emit(f"gate {gate_name} {', '.join(param_names)} {{")
        self.indent_level += 1
        for line in body_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("//"):
                self._emit(stripped)
        self.indent_level -= 1
        self._emit("}")
        self._emit("")

    def _handle_quantum_arithmetic(self, op_name: str, args: List[Expr]) -> None:
        if len(args) < 2:
            return
        gate_name = f"__{self._arithmetic_signature(op_name, args)}"
        if gate_name not in self.emitted_arithmetic_gates:
            self._emit_arithmetic_gate_def(op_name, args, gate_name)
            self.emitted_arithmetic_gates.add(gate_name)
        if op_name == "Grover":
            operands = QASM3Generator._expr_to_qasm(self, args[0])
            self._emit(f"{gate_name} {operands};")
            return
        operands = ", ".join(QASM3Generator._expr_to_qasm(self, arg) for arg in args)
        self._emit(f"{gate_name} {operands};")

    def _generate_gate_call(
        self,
        name: str,
        args: List[Expr],
        modifiers: List[str],
        ctrl_count: Optional[int],
    ) -> None:
        """Emit a user-defined gate call with structured indentation."""
        operands = [self._expr_to_qasm(arg) for arg in args]
        qubits = ", ".join(operands)
        modifier_prefix = ""
        if modifiers:
            mods = []
            if "inv" in modifiers:
                mods.append("inv")
            if "ctrl" in modifiers:
                if ctrl_count:
                    mods.append(f"ctrl[{ctrl_count}]")
                else:
                    mods.append("ctrl")
            if mods:
                modifier_prefix = " @ ".join(mods) + " @ "
        if modifier_prefix:
            self._emit(f"{modifier_prefix}{name} {qubits};")
        else:
            self._emit(f"{name} {qubits};")

    def visit_call_expr(self, node: CallExpr) -> None:
        if isinstance(node.callee, VarExpr):
            name = node.callee.name
            if name == "Print":
                return
            if self._emit_user_func_call(node):
                return
            if name in QUANTUM_ARITHMETIC_OPS:
                self._handle_quantum_arithmetic(name, node.args)
                return
            if name == "reset" and len(node.args) == 1:
                target = self._expr_to_qasm(node.args[0])
                self._emit(f"reset {target};")
                return
            if name in self.gates:
                self._generate_gate_call(name, node.args, node.modifiers, node.ctrl_count)
                return
            if name in GATE_MAP:
                self._emit_structured_builtin_gate(name, node)
                return
        super().visit_call_expr(node)

    def _emit_structured_builtin_gate(self, name: str, node: CallExpr) -> None:
        qasm_name = GATE_MAP[name]
        operands = [self._expr_to_qasm(arg) for arg in node.args]
        modifier_prefix = ""
        if node.modifiers:
            mods = []
            if "inv" in node.modifiers:
                mods.append("inv")
            if "ctrl" in node.modifiers:
                if node.ctrl_count:
                    mods.append(f"ctrl[{node.ctrl_count}]")
                else:
                    mods.append("ctrl")
            if mods:
                modifier_prefix = " @ ".join(mods) + " @ "

        if name == "Measure" and len(operands) == 2:
            self._emit(f"measure {operands[0]} -> {operands[1]};")
        elif name in ("RZ", "RY", "RX") and len(operands) >= 2:
            param = operands[0]
            qubits = ", ".join(operands[1:])
            if modifier_prefix:
                self._emit(f"{modifier_prefix}{qasm_name}({param}) {qubits};")
            else:
                self._emit(f"{modifier_prefix}{qasm_name}({param}) {qubits};")
        else:
            qubits = ", ".join(operands)
            if modifier_prefix:
                self._emit(f"{modifier_prefix}{qasm_name} {qubits};")
            else:
                self._emit(f"{qasm_name} {qubits};")

    def visit_for_stmt(self, node: ForStmt) -> None:
        if isinstance(node.iterable, LiteralExpr) and isinstance(node.iterable.value, str):
            # Range-like iterable from parser sugar; keep body as-is.
            for body_stmt in node.body:
                self.visit(body_stmt)
            return
        super().visit_for_stmt(node)

    def visit_if_stmt(self, node: IfStmt) -> None:
        cond = self._expr_to_qasm(node.condition)
        self._emit(f"if ({cond}) {{")
        self.indent_level += 1
        for stmt in node.then_body:
            self.visit(stmt)
        self.indent_level -= 1
        self._emit("}")
        if node.else_body:
            self._emit("else {")
            self.indent_level += 1
            for stmt in node.else_body:
                self.visit(stmt)
            self.indent_level -= 1
            self._emit("}")
