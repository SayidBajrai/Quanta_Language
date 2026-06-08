"""
OpenQASM 3 code generator
"""

from typing import List, Dict, Optional, Tuple
from ..ast.nodes import (
    Program, Stmt, Expr,
    VarDecl, ConstDecl, LetDecl, ClassicalNumericDecl, QuantumDecl, FuncDecl, GateDecl, ClassDecl,
    ForStmt, WhileStmt, IfStmt, ReturnStmt, ExprStmt,
    CallExpr, IndexExpr, SingleIndex, SliceIndex, BinaryExpr, UnaryExpr,
    VarExpr, LiteralExpr, ListExpr, GroupExpr, AssignExpr,
    Node
)
from ..ast.visitor import Visitor
from ..runtime.quantum_arithmetic import (
    emit_qadd_lines,
    emit_qdiv_lines,
    emit_qexpencmult_lines,
    emit_qftadd_lines,
    emit_grover_lines,
    emit_qmod_lines,
    emit_qmult_lines,
    emit_qsub_lines,
    emit_qtreeadd_lines,
    emit_qtreemult_lines,
)


# Gate mapping: Quanta name -> QASM name
GATE_MAP: Dict[str, str] = {
    "H": "h",
    "X": "x",
    "Y": "y",
    "Z": "z",
    "CNot": "cx",
    "CNOT": "cx",
    "CZ": "cz",
    "Swap": "swap",
    "SWAP": "swap",
    "RZ": "rz",
    "RY": "ry",
    "RX": "rx",
    "Measure": "measure",
    "S": "s",
    "CCX": "ccx",
    "CCNot": "ccx",
}

# Quantum arithmetic operations (will be lowered to QASM circuits)
QUANTUM_ARITHMETIC_OPS = {
    "QAdd", "QMult", "Compare", "Grover",
    "QFTAdd", "QTreeAdd", "QExpEncMult", "QTreeMult",
    "QSub", "QDiv", "QMod"
}

# High-level quantum gates (will be lowered to QASM circuits)
HIGH_LEVEL_GATES = {
    "Bell", "GHZ", "WState", "SwapGate", "QFT", "InverseQFT"
}


class QASM3Generator(Visitor):
    """Generates OpenQASM 3 code from AST"""
    
    def __init__(self):
        self.lines: List[str] = []
        self.registers: Dict[str, tuple] = {}  # name -> (kind, size)
        self.gates: Dict[str, GateDecl] = {}  # Gate macros
        self.indent_level = 0
        self.qadd_ancilla = "__qarith_anc"
        self.qarith_temp = "__qarith_temp"
        self.qarith_one = "__qarith_one"
        self.qarith_vbe_helper = "__qarith_vbe_helper"
        self.qarith_product = "__qarith_product"
        self.register_init: Dict[str, int] = {}
    
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
    
    def generate(self, ast: Program) -> str:
        """Generate QASM 3 code from AST"""
        self.lines = []
        self.registers = {}
        self.gates = {}
        self.register_init = {}
        self.indent_level = 0
        uses = self._collect_arithmetic_ops(ast)
        
        # First pass: collect gate macros and qint register sizes
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
        
        # Header
        self.lines.append("OPENQASM 3;")
        self.lines.append('include "stdgates.inc";')
        self.lines.append("")
        if uses_scratch:
            self.registers[self.qadd_ancilla] = ("qbit", 1)
            self.lines.append(f"qubit {self.qadd_ancilla};")
            if uses["QSub"] or uses["QMult"] or uses["QDiv"] or uses["QMod"]:
                self.registers[self.qarith_temp] = ("qbit", scratch_w)
                self.registers[self.qarith_one] = ("qbit", scratch_w)
                self.lines.append(f"qubit[{scratch_w}] {self.qarith_temp};")
                self.lines.append(f"qubit[{scratch_w}] {self.qarith_one};")
                self.lines.append(f"x {self.qarith_one}[0];")
            if uses["QTreeAdd"]:
                self.registers[self.qarith_vbe_helper] = ("qbit", 2)
                self.lines.append(f"qubit[2] {self.qarith_vbe_helper};")
            if uses["QExpEncMult"] or uses["QTreeMult"]:
                self.registers[self.qarith_product] = ("qbit", scratch_w * 2)
                self.lines.append(f"qubit[{scratch_w * 2}] {self.qarith_product};")
            self.lines.append("")
        
        # Second pass: generate gate definitions first
        for stmt in ast.statements:
            if isinstance(stmt, GateDecl):
                self.visit_gate_decl(stmt)
        
        # Third pass: generate other statements (registers, calls, etc.)
        for stmt in ast.statements:
            if not isinstance(stmt, GateDecl):
                self.visit(stmt)
        
        return "\n".join(self.lines)
    
    def visit_program(self, node: Program) -> None:
        """Visit program node"""
        for stmt in node.statements:
            self.visit(stmt)
    
    def visit_var_decl(self, node: VarDecl) -> None:
        """Variable declarations don't generate QASM"""
        pass

    def visit_classical_numeric_decl(self, node: ClassicalNumericDecl) -> None:
        """Classical numeric types are frontend-only."""
        pass
    
    def visit_quantum_decl(self, node: QuantumDecl) -> None:
        """Generate quantum register declaration"""
        from ..types.numeric import flat_qubit_count, init_bit_pattern, qreal_nearest_index

        size = flat_qubit_count(node.kind, node.size, node.size2)
        self.registers[node.name] = (node.kind, size)

        qasm_kind = node.kind
        if qasm_kind in ("qbit", "qint", "quint", "qdec", "qudec", "qfloat", "qreal"):
            qasm_kind = "qubit"
        elif qasm_kind == "bint":
            qasm_kind = "bit"

        self.lines.append(f"{qasm_kind}[{size}] {node.name};")

        from .init_value import compile_time_number

        raw_init = compile_time_number(node.value) if node.value else None
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
                        self.lines.append(f"x {node.name}[{i}];")
            except (ValueError, TypeError):
                pass
    
    def visit_func_decl(self, node: FuncDecl) -> None:
        """Function declarations are inlined, not generated"""
        pass
    
    def visit_gate_decl(self, node: GateDecl) -> None:
        """Generate gate definition in QASM format"""
        # Generate gate definition: gate name param1, param2, ... { body }
        # In QASM, parameters are comma-separated names
        if node.params:
            params_str = ", ".join(node.params)
            self.lines.append(f"gate {node.name} {params_str} {{")
        else:
            self.lines.append(f"gate {node.name} {{")
        
        # Generate gate body
        for stmt in node.body:
            if isinstance(stmt, ExprStmt) and isinstance(stmt.expr, CallExpr):
                # Generate gate call in body
                call_expr = stmt.expr
                if isinstance(call_expr.callee, VarExpr):
                    name = call_expr.callee.name
                    
                    # Handle built-in gates - convert to QASM names
                    if name in GATE_MAP:
                        qasm_name = GATE_MAP[name]
                        operands = []
                        for arg in call_expr.args:
                            # In gate body, arguments are parameter names or expressions
                            # Convert to QASM format
                            arg_str = self._expr_to_qasm(arg)
                            operands.append(arg_str)
                        
                        # Build gate call (no modifiers inside gate definitions in QASM)
                        if name in ["RZ", "RY", "RX"] and len(operands) >= 2:
                            param = operands[0]
                            qubits = ", ".join(operands[1:])
                            self.lines.append(f"    {qasm_name}({param}) {qubits};")
                        elif name == "Measure" and len(operands) == 2:
                            self.lines.append(f"    measure {operands[0]} -> {operands[1]};")
                        else:
                            qubits = ", ".join(operands)
                            self.lines.append(f"    {qasm_name} {qubits};")
                    # Handle user-defined gates (nested gates)
                    elif name in self.gates:
                        operands = []
                        for arg in call_expr.args:
                            operands.append(self._expr_to_qasm(arg))
                        qubits = ", ".join(operands)
                        self.lines.append(f"    {name} {qubits};")
        
        self.lines.append("}")
        self.lines.append("")  # Empty line after gate definition
    
    def visit_class_decl(self, node: ClassDecl) -> None:
        """Class declarations don't generate QASM"""
        pass

    def visit_while_stmt(self, node: WhileStmt) -> None:
        """While loops require structured compilation mode."""
        pass
    
    def visit_for_stmt(self, node: ForStmt) -> None:
        """For loops must be unrolled before codegen"""
        # This should have been expanded in semantic analysis
        # For now, we'll handle simple compile-time ranges
        if isinstance(node.iterable, ListExpr):
            for elem in node.iterable.elements:
                # Create a scope for the iterator
                # In a real implementation, we'd substitute the iterator variable
                for body_stmt in node.body:
                    self.visit(body_stmt)
        else:
            # Fallback: assume it's a range-like expression
            for body_stmt in node.body:
                self.visit(body_stmt)
    
    def visit_if_stmt(self, node: IfStmt) -> None:
        """If statements (classical only in v1)"""
        # In v1, if conditions must be compile-time
        # For now, we'll generate the then branch
        for stmt in node.then_body:
            self.visit(stmt)
        for stmt in node.else_body:
            self.visit(stmt)
    
    def visit_return_stmt(self, node: ReturnStmt) -> None:
        """Return statements don't generate QASM"""
        pass
    
    def visit_expr_stmt(self, node: ExprStmt) -> None:
        """Expression statement"""
        self.visit(node.expr)
    
    def visit_call_expr(self, node: CallExpr) -> None:
        """Generate gate/function call"""
        if isinstance(node.callee, VarExpr):
            name = node.callee.name
            
            # Handle quantum arithmetic operations
            if name in QUANTUM_ARITHMETIC_OPS:
                self._handle_quantum_arithmetic(name, node.args)
                return
            
            if name == "Print":
                return
            elif name == "Fidelity":
                return
            elif name == "Reshape":
                return
            elif name in (
                "DotProduct",
                "CrossProduct",
                "ElementwiseProduct",
                "TensorProduct",
                "Shape",
            ):
                return

            # User-defined gates take precedence over built-in high-level gates
            if name in self.gates:
                self._generate_gate_call(name, node.args, node.modifiers, node.ctrl_count)
                return

            # Handle high-level quantum gates (support whole register and slice)
            if name in HIGH_LEVEL_GATES:
                # Register-wise Bell/GHZ: all args same-size registers -> apply per index
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
            
            # Handle Measure(q, c): single qubit or full registers
            if name == "Measure" and len(node.args) == 2:
                if isinstance(node.args[0], VarExpr) and isinstance(node.args[1], VarExpr):
                    q_name = node.args[0].name
                    c_name = node.args[1].name
                    if q_name in self.registers and c_name in self.registers:
                        q_kind, q_size = self.registers[q_name]
                        c_kind, c_size = self.registers[c_name]
                        if q_kind in ("qbit", "qint", "quint", "qdec", "qudec", "qfloat", "qreal") and c_kind in ("bit", "bint"):
                            size = min(q_size, c_size)
                            for i in range(size):
                                self.lines.append(f"measure {q_name}[{i}] -> {c_name}[{i}];")
                            return
                # Single qubit/bit: Measure(q[i], c[i])
                q_str = self._expr_to_qasm(node.args[0])
                c_str = self._expr_to_qasm(node.args[1])
                self.lines.append(f"measure {q_str} -> {c_str};")
                return
            elif name in ["len", "range", "assert", "error", "warn"]:
                # These are compile-time or frontend-only
                return
            elif name == "reset" and len(node.args) == 1:
                q = self._expr_to_qasm(node.args[0])
                self.lines.append(f"reset {q};")
                return
            
            # Handle built-in gates
            if name in GATE_MAP:
                # Measure already handled above
                if name == "Measure":
                    pass  # handled in Measure branch
                else:
                    # Build modifier prefix
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
                    
                    qasm_name = GATE_MAP[name]
                    operands = []
                    for arg in node.args:
                        operands.append(self._expr_to_qasm(arg))
                    
                    if name in ["RZ", "RY", "RX"] and len(operands) >= 2:
                        # Parameterized gates
                        param = operands[0]
                        qubits = ", ".join(operands[1:])
                        if modifier_prefix:
                            self.lines.append(f"{modifier_prefix}{qasm_name}({param}) {qubits};")
                        else:
                            self.lines.append(f"{qasm_name}({param}) {qubits};")
                    else:
                        # Standard gates
                        qubits = ", ".join(operands)
                        if modifier_prefix:
                            self.lines.append(f"{modifier_prefix}{qasm_name} {qubits};")
                        else:
                            self.lines.append(f"{qasm_name} {qubits};")
            else:
                # Function call - should have been inlined
                pass
    
    def visit_index_expr(self, node: IndexExpr) -> str:
        """Generate index expression (single scalar index after desugaring)."""
        base = self.visit(node.base)
        if len(node.items) == 1 and isinstance(node.items[0], SingleIndex):
            index = self.visit(node.items[0].expr)
            return f"{base}[{index}]"
        raise NotImplementedError(
            "Multi-index register access must be desugared before code generation"
        )
    
    def visit_binary_expr(self, node: BinaryExpr) -> str:
        """Binary expressions (for compile-time evaluation)"""
        left = self.visit(node.left)
        right = self.visit(node.right)
        return f"({left} {node.op} {right})"
    
    def visit_unary_expr(self, node: UnaryExpr) -> str:
        """Unary expressions"""
        right = self.visit(node.right)
        return f"{node.op}{right}"
    
    def visit_var_expr(self, node: VarExpr) -> str:
        """Variable reference"""
        # Handle built-in constants
        import math
        builtin_constants = {
            "pi": str(math.pi),
            "e": str(math.e),
        }
        if node.name in builtin_constants:
            return builtin_constants[node.name]
        return node.name
    
    def visit_literal_expr(self, node: LiteralExpr) -> str:
        """Literal expression"""
        return str(node.value)
    
    def visit_list_expr(self, node: ListExpr) -> str:
        """List expression"""
        elements = [str(self.visit(elem)) for elem in node.elements]
        return f"[{', '.join(elements)}]"
    
    def visit_group_expr(self, node: GroupExpr) -> str:
        """Grouped expression"""
        return f"({self.visit(node.expr)})"
    
    def visit_assign_expr(self, node: AssignExpr) -> str:
        """Assignment expression"""
        value = self.visit(node.value)
        return f"{node.name} = {value}"
    
    def _expr_to_qasm(self, expr: Expr) -> str:
        """Convert expression to QASM string representation"""
        result = self.visit(expr)
        if isinstance(result, str):
            return result
        return str(result)
    
    def _substitute_params(self, expr: Expr, param_map: Dict[str, Expr]) -> Expr:
        """Recursively substitute parameter names with argument expressions"""
        if isinstance(expr, VarExpr):
            # If this is a parameter, substitute it
            if expr.name in param_map:
                return param_map[expr.name]
            return expr
        elif isinstance(expr, CallExpr):
            # Recursively substitute in call arguments
            new_args = [self._substitute_params(arg, param_map) for arg in expr.args]
            # Create new CallExpr with substituted args
            new_call = CallExpr(expr.callee, new_args)
            new_call.modifiers = expr.modifiers
            new_call.ctrl_count = expr.ctrl_count
            return new_call
        elif isinstance(expr, IndexExpr):
            new_base = self._substitute_params(expr.base, param_map)
            new_items = []
            for item in expr.items:
                if isinstance(item, SingleIndex):
                    new_items.append(SingleIndex(self._substitute_params(item.expr, param_map)))
                elif isinstance(item, SliceIndex):
                    new_items.append(SliceIndex(
                        self._substitute_params(item.start, param_map),
                        self._substitute_params(item.stop, param_map),
                        self._substitute_params(item.step, param_map) if item.step else None,
                    ))
                else:
                    new_items.append(item)
            return IndexExpr(new_base, new_items)
        elif isinstance(expr, BinaryExpr):
            new_left = self._substitute_params(expr.left, param_map)
            new_right = self._substitute_params(expr.right, param_map)
            return BinaryExpr(new_left, expr.op, new_right)
        elif isinstance(expr, UnaryExpr):
            new_right = self._substitute_params(expr.right, param_map)
            return UnaryExpr(expr.op, new_right)
        elif isinstance(expr, GroupExpr):
            new_expr = self._substitute_params(expr.expr, param_map)
            return GroupExpr(new_expr)
        else:
            # LiteralExpr, ListExpr, etc. - no substitution needed
            return expr
    
    def _generate_gate_call(self, name: str, args: List[Expr], modifiers: List[str], ctrl_count: Optional[int]):
        """Generate gate call in QASM format (preserves user-defined gates)"""
        # Convert arguments to QASM format
        operands = []
        for arg in args:
            operands.append(self._expr_to_qasm(arg))
        
        qubits = ", ".join(operands)
        
        # Build modifier prefix for gate calls
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
        
        # Generate gate call with modifiers
        if modifier_prefix:
            self.lines.append(f"{modifier_prefix}{name} {qubits};")
        else:
            self.lines.append(f"{name} {qubits};")
    
    def _handle_quantum_arithmetic(self, op_name: str, args: List[Expr]):
        """Handle quantum arithmetic operations (QAdd, QMult, Compare, Grover, QFTAdd, QTreeAdd, QExpEncMult, QTreeMult, QSub, QDiv, QMod)"""
        if op_name == "QAdd":
            # QAdd(a, b, c, ..., dest) - variadic addition
            if len(args) < 2:
                return
            self._generate_qadd_circuit(args)
        elif op_name == "QFTAdd":
            # QFTAdd(a, b, c, ..., dest) - QFT-based variadic addition
            if len(args) < 2:
                return
            self._generate_qftadd_circuit(args)
        elif op_name == "QTreeAdd":
            # QTreeAdd(a, b, c, ..., dest) - Tree-based variadic addition
            if len(args) < 2:
                return
            self._generate_qtreeadd_circuit(args)
        elif op_name == "QSub":
            # QSub(a, b, c, ..., dest) - variadic subtraction
            if len(args) < 2:
                return
            self._generate_qsub_circuit(args)
        elif op_name == "QMult":
            # QMult(a, b, c, ..., dest) - variadic multiplication
            if len(args) < 3:
                return
            self._generate_qmult_circuit(args)
        elif op_name == "QExpEncMult":
            # QExpEncMult(a, b, c, ..., dest) - Exponent-encoded variadic multiplication
            if len(args) < 3:
                return
            self._generate_qexpencmult_circuit(args)
        elif op_name == "QTreeMult":
            # QTreeMult(a, b, c, ..., dest) - Tree-based variadic multiplication
            if len(args) < 3:
                return
            self._generate_qtreemult_circuit(args)
        elif op_name == "QDiv":
            # QDiv(dividend, divisor, quotient, remainder) - division with remainder
            if len(args) < 4:
                return
            self._generate_qdiv_circuit(args)
        elif op_name == "QMod":
            # QMod(a, b, c, ..., dest) - variadic modulus
            if len(args) < 2:
                return
            self._generate_qmod_circuit(args)
        elif op_name == "Compare":
            # Compare(a, b, flag) - comparison operation
            if len(args) != 3:
                return
            self._generate_compare_circuit(args)
        elif op_name == "Grover":
            if len(args) != 2:
                return
            self._generate_grover_circuit(args)
    
    def _generate_grover_circuit(self, args: List[Expr]):
        """Generate Grover oracle + diffusion for one iteration."""
        if len(args) != 2:
            return
        reg_bits = self._register_bit_names(self._expr_to_qasm(args[0]))
        target = self._eval_to_int(args[1])
        n = len(reg_bits)
        self.lines.append(f"// Grover iteration ({n} bits, target={target})")
        if target is None:
            self.lines.append("// Grover requires compile-time integer target")
            return
        emit_grover_lines(reg_bits, target, self.lines.append)

    def _register_bit_names(self, reg_expr: str) -> List[str]:
        """Expand a register QASM reference into per-bit names."""
        if "[" in reg_expr:
            return [reg_expr]
        reg_name = reg_expr
        size = self.registers.get(reg_name, (None, 1))[1] if reg_name in self.registers else 1
        if size <= 1:
            return [reg_name]
        return [f"{reg_name}[{i}]" for i in range(size)]

    def _generate_qadd_circuit(self, args: List[Expr]):
        """Generate CDKM ripple-carry adder circuit for QAdd."""
        if len(args) < 2:
            return
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        register_bits = [self._register_bit_names(reg) for reg in operand_strs]
        n = len(register_bits[0]) if register_bits else 0
        self.lines.append(
            f"// CDKM ripple-carry adder ({n} bits, {len(args)} operands)"
        )
        emit_qadd_lines(register_bits, self.qadd_ancilla, self.lines.append)
    
    def _scratch_bit_names(self, reg_name: str, width: int) -> List[str]:
        if width <= 1:
            return [reg_name]
        return [f"{reg_name}[{i}]" for i in range(width)]

    def _generate_qsub_circuit(self, args: List[Expr]):
        """Generate CDKM-based subtractor circuit for QSub."""
        if len(args) < 2:
            return
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        register_bits = [self._register_bit_names(reg) for reg in operand_strs]
        n = len(register_bits[0]) if register_bits else 0
        temp_bits = self._scratch_bit_names(self.qarith_temp, n)
        one_bits = self._scratch_bit_names(self.qarith_one, n)
        self.lines.append(f"// CDKM QSub ({n} bits, {len(args)} operands)")
        emit_qsub_lines(register_bits, temp_bits, one_bits, self.qadd_ancilla, self.lines.append)
    
    def _reg_name(self, reg_expr: str) -> str:
        return reg_expr.split("[")[0] if "[" in reg_expr else reg_expr

    def _generate_qdiv_circuit(self, args: List[Expr]):
        """Generate QDiv via repeated subtraction."""
        if len(args) < 4:
            return
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        register_bits = [self._register_bit_names(reg) for reg in operand_strs]
        n = len(register_bits[0]) if register_bits else 0
        temp_bits = self._scratch_bit_names(self.qarith_temp, n)
        one_bits = self._scratch_bit_names(self.qarith_one, n)
        dividend_name = self._reg_name(operand_strs[0])
        divisor_name = self._reg_name(operand_strs[1])
        emit_qdiv_lines(
            register_bits[0],
            register_bits[1],
            register_bits[2],
            register_bits[3],
            temp_bits,
            one_bits,
            self.qadd_ancilla,
            self.lines.append,
            dividend_value=self.register_init.get(dividend_name),
            divisor_value=self.register_init.get(divisor_name),
        )

    def _generate_qmod_circuit(self, args: List[Expr]):
        """Generate QMod via repeated subtraction."""
        if len(args) < 3:
            return
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        register_bits = [self._register_bit_names(reg) for reg in operand_strs]
        n = len(register_bits[0]) if register_bits else 0
        temp_bits = self._scratch_bit_names(self.qarith_temp, n)
        one_bits = self._scratch_bit_names(self.qarith_one, n)
        emit_qmod_lines(
            register_bits,
            temp_bits,
            one_bits,
            self.qadd_ancilla,
            self.lines.append,
            init_values=self.register_init,
        )

    def _generate_qmult_circuit(self, args: List[Expr]):
        """Generate shift-and-add multiplier circuit for QMult."""
        if len(args) < 3:
            return
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        register_bits = [self._register_bit_names(reg) for reg in operand_strs]
        n = max(len(bits) for bits in register_bits) if register_bits else 0
        temp_bits = self._scratch_bit_names(self.qarith_temp, n)
        one_bits = self._scratch_bit_names(self.qarith_one, n)
        self.lines.append(f"// QMult shift-and-add ({n} bits, {len(args)} operands)")
        emit_qmult_lines(register_bits, temp_bits, one_bits, self.qadd_ancilla, self.lines.append)
        self.lines.append(f"// Requires: Controlled ripple-carry adders, ancilla qubits for carries")
    
    def _generate_qftadd_circuit(self, args: List[Expr]):
        """Generate Draper QFT adder circuit for QFTAdd."""
        if len(args) < 2:
            return
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        register_bits = [self._register_bit_names(reg) for reg in operand_strs]
        n = len(register_bits[0]) if register_bits else 0
        self.lines.append(
            f"// Draper QFT adder ({n} bits, {len(args)} operands)"
        )
        emit_qftadd_lines(register_bits, self.lines.append)

    def _generate_qtreeadd_circuit(self, args: List[Expr]):
        """Generate VBE tree adder circuit for QTreeAdd."""
        if len(args) < 2:
            return
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        register_bits = [self._register_bit_names(reg) for reg in operand_strs]
        n = len(register_bits[0]) if register_bits else 0
        helper_bits = self._scratch_bit_names(self.qarith_vbe_helper, 2)
        self.lines.append(f"// VBE tree adder ({n} bits, {len(args)} operands)")
        emit_qtreeadd_lines(register_bits, helper_bits, self.lines.append)

    def _generate_qexpencmult_circuit(self, args: List[Expr]):
        """Generate RGQFT exponent-encoded multiplier for QExpEncMult."""
        if len(args) < 3:
            return
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        register_bits = [self._register_bit_names(reg) for reg in operand_strs]
        n = len(register_bits[0]) if register_bits else 0
        product_bits = self._scratch_bit_names(self.qarith_product, n * 2)
        self.lines.append(f"// RGQFT exponent-encoded multiplier ({n} bits, {len(args)} operands)")
        emit_qexpencmult_lines(register_bits, product_bits, self.lines.append)

    def _generate_qtreemult_circuit(self, args: List[Expr]):
        """Generate HRS tree multiplier for QTreeMult."""
        if len(args) < 3:
            return
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        register_bits = [self._register_bit_names(reg) for reg in operand_strs]
        n = len(register_bits[0]) if register_bits else 0
        product_bits = self._scratch_bit_names(self.qarith_product, n * 2)
        self.lines.append(f"// HRS tree multiplier ({n} bits, {len(args)} operands)")
        emit_qtreemult_lines(
            register_bits, product_bits, self.qadd_ancilla, self.lines.append
        )

    def _generate_compare_circuit(self, args: List[Expr]):
        """Generate quantum comparison circuit for Compare operation"""
        if len(args) != 3:
            return
        
        a_reg = self._expr_to_qasm(args[0])
        b_reg = self._expr_to_qasm(args[1])
        flag_reg = self._expr_to_qasm(args[2])
        
        a_name = a_reg.split("[")[0] if "[" in a_reg else a_reg
        b_name = b_reg.split("[")[0] if "[" in b_reg else b_reg
        flag_name = flag_reg.split("[")[0] if "[" in flag_reg else flag_reg
        
        a_size = self.registers.get(a_name, (None, 1))[1] if a_name in self.registers else 1
        b_size = self.registers.get(b_name, (None, 1))[1] if b_name in self.registers else 1
        
        n = min(a_size, b_size)
        
        self.lines.append(f"// Compare({a_reg}, {b_reg}, {flag_reg}) - quantum comparison (a >= b)")
        
        # Generate borrow ancilla register name (simplified)
        borrow_name = f"_borrow_{a_name}_{b_name}"
        
        # 3-bit reversible subtractor (generalized to n-bit)
        # Bit 0 subtraction
        if n > 0:
            borrow_bit_0 = f"{b_name}[0]"  # Reuse b[0] temporarily for borrow[0]
            self.lines.append(f"ccx {a_name}[0], {b_name}[0], {borrow_bit_0};  // borrow[0] = a[0] AND NOT b[0]")
            self.lines.append(f"cx {a_name}[0], {b_name}[0];  // b[0] = a[0] XOR b[0]")
        
        # Bit 1 to n-1 subtraction (with borrow in)
        for i in range(1, n):
            borrow_prev = f"{b_name}[{i-1}]" if i == 1 else f"{b_name}[{i-1}]"
            borrow_curr = f"{b_name}[{i}]" if i < n - 1 else f"{b_name}[{i}]"
            
            # Compute borrow[i]
            self.lines.append(f"ccx {a_name}[{i}], {b_name}[{i}], {borrow_curr};  // borrow[{i}] = a[{i}] AND NOT b[{i}]")
            if i > 0:
                self.lines.append(f"ccx {a_name}[{i}], {borrow_prev}, {borrow_curr};  // borrow[{i}] OR= (a[{i}] AND borrow[{i-1}])")
            
            # Compute difference
            self.lines.append(f"cx {a_name}[{i}], {b_name}[{i}];  // b[{i}] = a[{i}] XOR b[{i}]")
            if i > 0:
                self.lines.append(f"cx {borrow_prev}, {b_name}[{i}];  // b[{i}] = a[{i}] XOR b[{i}] XOR borrow[{i-1}]")
        
        # Set flag if val1 >= val2 (i.e., final borrow is 0)
        # If borrow[n-1] == 0, then val1 >= val2
        final_borrow = f"{b_name}[{n-1}]"
        self.lines.append(f"x {final_borrow};  // Invert borrow to get >= flag")
        self.lines.append(f"cx {final_borrow}, {flag_reg};  // flag = (val1 >= val2)")
        self.lines.append(f"x {final_borrow};  // Restore borrow")
        
        # Uncompute subtraction (reverse order)
        for i in range(n - 1, 0, -1):
            borrow_prev = f"{b_name}[{i-1}]" if i == 1 else f"{b_name}[{i-1}]"
            borrow_curr = f"{b_name}[{i}]" if i < n - 1 else f"{b_name}[{i}]"
            
            # Uncompute difference
            if i > 0:
                self.lines.append(f"cx {borrow_prev}, {b_name}[{i}];  // Restore b[{i}]")
            self.lines.append(f"cx {a_name}[{i}], {b_name}[{i}];  // Restore b[{i}]")
            
            # Uncompute borrow[i]
            if i > 0:
                self.lines.append(f"ccx {a_name}[{i}], {borrow_prev}, {borrow_curr};  // Uncompute borrow[{i}]")
            self.lines.append(f"ccx {a_name}[{i}], {b_name}[{i}], {borrow_curr};  // Uncompute borrow[{i}]")
        
        # Uncompute bit 0
        if n > 0:
            borrow_bit_0 = f"{b_name}[0]"
            self.lines.append(f"cx {a_name}[0], {b_name}[0];  // Restore b[0]")
            self.lines.append(f"ccx {a_name}[0], {b_name}[0], {borrow_bit_0};  // Uncompute borrow[0]")
        
        # Note: This is a simplified implementation. Full comparator would:
        # 1. Use proper ancilla qubits for borrow storage
        # 2. Implement full reversible subtraction with proper uncomputation
        # 3. Handle edge cases more carefully
    
    def _expand_qubit_args(self, args: List[Expr]) -> Optional[List[Expr]]:
        """Expand register and slice arguments to a flat list of single-qubit IndexExprs.
        Returns None if any argument cannot be expanded (e.g. not a register/slice/index).
        """
        import math
        result: List[Expr] = []
        for arg in args:
            if isinstance(arg, VarExpr):
                # Whole register: q -> q[0], q[1], ... (only quantum registers)
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
        """Evaluate a compile-time expression to a Python int (for slice bounds)."""
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
        if isinstance(expr, UnaryExpr):
            if expr.op == "-":
                inner = self._eval_to_int(expr.right)
                return -inner if inner is not None else None
            return None
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
        """If all args are whole quantum registers of the same size, return (size, [reg_names]). Else None."""
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

    def _handle_high_level_gate(self, gate_name: str, args: List[Expr], modifiers: List[str], ctrl_count: Optional[int]):
        """Handle high-level quantum gates (Bell, GHZ, WState, SwapGate, QFT, InverseQFT).
        args must already be expanded to a flat list of single-qubit expressions."""
        if gate_name == "Bell":
            if len(args) != 2:
                return
            self._generate_bell_gate(args)
        elif gate_name == "GHZ":
            if len(args) < 2:
                return
            self._generate_ghz_gate(args)
        elif gate_name == "WState":
            if len(args) != 3:
                return
            self._generate_wstate_gate(args)
        elif gate_name == "SwapGate":
            if len(args) != 2:
                return
            self._generate_swap_gate(args)
        elif gate_name == "QFT":
            if len(args) < 1:
                return
            self._generate_qft_gate(args)
        elif gate_name == "InverseQFT":
            if len(args) < 1:
                return
            self._generate_inverse_qft_gate(args)
    
    def _generate_bell_register_wise(self, args: List[Expr], size: int, names: List[str]):
        """Register-wise Bell: for each index i, H(a[i]); CX(a[i], b[i])."""
        a, b = names[0], names[1]
        self.lines.append(f"// Bell({a}, {b}) register-wise")
        for i in range(size):
            self.lines.append(f"h {a}[{i}];")
            self.lines.append(f"cx {a}[{i}], {b}[{i}];")

    def _generate_bell_gate(self, args: List[Expr]):
        """Generate Bell state: H(q0), CNot(q0, q1)"""
        q0 = self._expr_to_qasm(args[0])
        q1 = self._expr_to_qasm(args[1])
        self.lines.append(f"// Bell({q0}, {q1})")
        self.lines.append(f"h {q0};")
        self.lines.append(f"cx {q0}, {q1};")

    def _generate_ghz_register_wise(self, args: List[Expr], size: int, names: List[str]):
        """Register-wise GHZ: for each index i, H(r0[i]); CX(r0[i], r1[i]); CX(r0[i], r2[i]); ..."""
        self.lines.append(f"// GHZ({', '.join(names)}) register-wise")
        r0 = names[0]
        for i in range(size):
            self.lines.append(f"h {r0}[{i}];")
            for j in range(1, len(names)):
                self.lines.append(f"cx {r0}[{i}], {names[j]}[{i}];")
    
    def _generate_ghz_gate(self, args: List[Expr]):
        """Generate GHZ state: H(q0), then chain CNOTs"""
        qubits = [self._expr_to_qasm(arg) for arg in args]
        self.lines.append(f"// GHZ({', '.join(qubits)})")
        if len(qubits) < 2:
            return
        
        # Apply Hadamard to first qubit
        self.lines.append(f"h {qubits[0]};")
        
        # Chain CNOTs: q0 -> q1, q1 -> q2, q2 -> q3, etc.
        for i in range(len(qubits) - 1):
            self.lines.append(f"cx {qubits[i]}, {qubits[i+1]};")
    
    def _generate_wstate_gate(self, args: List[Expr]):
        """Generate W state: (|100⟩ + |010⟩ + |001⟩) / √3"""
        q0 = self._expr_to_qasm(args[0])
        q1 = self._expr_to_qasm(args[1])
        q2 = self._expr_to_qasm(args[2])
        self.lines.append(f"// WState({q0}, {q1}, {q2})")
        
        # W state preparation: RY(2*acos(1/sqrt(3))) on q0, then CNOTs
        import math
        theta = 2 * math.acos(1 / math.sqrt(3))
        self.lines.append(f"ry({theta}) {q0};")
        self.lines.append(f"cx {q0}, {q1};")
        self.lines.append(f"cx {q0}, {q2};")
    
    def _generate_swap_gate(self, args: List[Expr]):
        """Generate swap gate: 3 CNOTs (Fredkin-like decomposition)"""
        a = self._expr_to_qasm(args[0])
        b = self._expr_to_qasm(args[1])
        self.lines.append(f"// SwapGate({a}, {b})")
        self.lines.append(f"cx {a}, {b};")
        self.lines.append(f"cx {b}, {a};")
        self.lines.append(f"cx {a}, {b};")
    
    def _generate_qft_gate(self, args: List[Expr]):
        """Generate Quantum Fourier Transform circuit"""
        qubits = [self._expr_to_qasm(arg) for arg in args]
        n = len(qubits)
        self.lines.append(f"// QFT({', '.join(qubits)})")
        
        if n == 0:
            return
        
        # Extract register names for indexing
        qubit_names = []
        qubit_indices = []
        for q in qubits:
            if "[" in q:
                name, idx = q.split("[")
                idx = idx.rstrip("]")
                qubit_names.append(name)
                qubit_indices.append(int(idx))
            else:
                qubit_names.append(q)
                qubit_indices.append(0)
        
        # QFT: Apply Hadamard and controlled rotations
        for i in range(n):
            # Hadamard on qubit i
            self.lines.append(f"h {qubits[i]};")
            
            # Controlled rotations from qubit i to qubits j > i
            for j in range(i + 1, n):
                phase = f"pi/{2**(j-i)}"
                self.lines.append(f"crz({phase}) {qubits[j]}, {qubits[i]};")
        
        # Bit-reversal (swap qubits)
        for i in range(n // 2):
            self.lines.append(f"swap {qubits[i]}, {qubits[n-1-i]};")
    
    def _generate_inverse_qft_gate(self, args: List[Expr]):
        """Generate Inverse Quantum Fourier Transform circuit"""
        qubits = [self._expr_to_qasm(arg) for arg in args]
        n = len(qubits)
        self.lines.append(f"// InverseQFT({', '.join(qubits)})")
        
        if n == 0:
            return
        
        # Inverse QFT: exact reverse of QFT
        
        # Step 1: Bit-reversal (same as QFT, but done first in inverse)
        for i in range(n // 2):
            self.lines.append(f"swap {qubits[i]}, {qubits[n-1-i]};")
        
        # Step 2: Apply controlled rotations in reverse order with negative phases
        # Reverse the order: from n-1 down to 0
        for i in range(n - 1, -1, -1):
            # Controlled rotations from qubit i to qubits j > i (in reverse order)
            for j in range(n - 1, i, -1):
                phase = f"-pi/{2**(j-i)}"
                self.lines.append(f"crz({phase}) {qubits[j]}, {qubits[i]};")
            
            # Hadamard on qubit i (last operation for each qubit in inverse QFT)
            self.lines.append(f"h {qubits[i]};")
    
    def visit(self, node: Node):
        """Generic visit method"""
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
        else:
            raise NotImplementedError(f"No visit method for {type(node).__name__}")
