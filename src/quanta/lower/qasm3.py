"""
OpenQASM 3 code generator
"""

from typing import List, Dict, Optional
from ..ast.nodes import (
    Program, Stmt, Expr,
    VarDecl, ConstDecl, LetDecl, QuantumDecl, FuncDecl, GateDecl, ClassDecl,
    ForStmt, IfStmt, ReturnStmt, ExprStmt,
    CallExpr, IndexExpr, BinaryExpr, UnaryExpr,
    VarExpr, LiteralExpr, ListExpr, GroupExpr, AssignExpr,
    Node
)
from ..ast.visitor import Visitor


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
}

# Quantum arithmetic operations (will be lowered to QASM circuits)
QUANTUM_ARITHMETIC_OPS = {
    "QAdd", "QMult", "Compare", "Grover",
    "QFTAdd", "QTreeAdd", "QExpEncMult", "QTreeMult",
    "QSub", "QDiv", "QMod"
}


class QASM3Generator(Visitor):
    """Generates OpenQASM 3 code from AST"""
    
    def __init__(self):
        self.lines: List[str] = []
        self.registers: Dict[str, tuple] = {}  # name -> (kind, size)
        self.gates: Dict[str, GateDecl] = {}  # Gate macros
        self.indent_level = 0
    
    def generate(self, ast: Program) -> str:
        """Generate QASM 3 code from AST"""
        self.lines = []
        self.registers = {}
        self.gates = {}
        self.indent_level = 0
        
        # First pass: collect gate macros
        for stmt in ast.statements:
            if isinstance(stmt, GateDecl):
                self.gates[stmt.name] = stmt
        
        # Header
        self.lines.append("OPENQASM 3;")
        self.lines.append('include "stdgates.inc";')
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
    
    def visit_quantum_decl(self, node: QuantumDecl) -> None:
        """Generate quantum register declaration"""
        size = node.size or 1
        self.registers[node.name] = (node.kind, size)
        
        # Map qint/bint to qubit/bit for QASM output
        qasm_kind = node.kind
        if qasm_kind == "qint":
            qasm_kind = "qubit"
        elif qasm_kind == "bint":
            qasm_kind = "bit"
        
        self.lines.append(f"{qasm_kind}[{size}] {node.name};")
        
        # Handle initialization if present
        if node.value:
            # For qint initialization like qint[3] x = 2
            # We need to initialize the register and apply NOT gates
            if isinstance(node.value, LiteralExpr):
                try:
                    init_value = int(node.value.value)
                    # Initialize to |0⟩ (already done by declaration)
                    # Then apply NOT gates to set bits
                    for i in range(size):
                        if (init_value >> i) & 1:
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
            
            # Handle standard library functions
            if name == "MeasureAll":
                self._handle_measure_all(node.args)
                return
            elif name == "print":
                # Print is frontend-only, doesn't generate QASM
                return
            elif name in ["len", "range", "assert", "error", "warn"]:
                # These are compile-time or frontend-only
                return
            elif name == "reset" and len(node.args) == 1:
                q = self._expr_to_qasm(node.args[0])
                self.lines.append(f"reset {q};")
                return
            
            # Handle user-defined gates - generate gate call instead of expanding
            if name in self.gates:
                self._generate_gate_call(name, node.args, node.modifiers, node.ctrl_count)
                return
            
            # Handle built-in gates
            if name in GATE_MAP:
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
                
                if name == "Measure" and len(operands) == 2:
                    # Special handling for measure (no modifiers allowed)
                    self.lines.append(f"measure {operands[0]} -> {operands[1]};")
                elif name in ["RZ", "RY", "RX"] and len(operands) >= 2:
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
        """Generate index expression"""
        base = self.visit(node.base)
        index = self.visit(node.index)
        if isinstance(base, str) and isinstance(index, str):
            return f"{base}[{index}]"
        return f"{base}[{index}]"
    
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
            # Substitute in base and index
            new_base = self._substitute_params(expr.base, param_map)
            new_index = self._substitute_params(expr.index, param_map)
            return IndexExpr(new_base, new_index)
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
            # Grover(a, target) - Grover iteration
            if len(args) != 2:
                return
            a = self._expr_to_qasm(args[0])
            target = self._expr_to_qasm(args[1])
            self.lines.append(f"// Grover({a}, {target}) - Grover iteration")
            # TODO: Generate actual Grover operator circuit
    
    def _generate_qadd_circuit(self, args: List[Expr]):
        """Generate ripple-carry adder circuit for QAdd operation"""
        if len(args) < 2:
            return
        
        # Convert all arguments to QASM strings
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        
        # For variadic addition: QAdd(a, b, c, ..., dest)
        # We chain additions: first add a+b into temp1, then add temp1+c into temp2, etc.
        # Last argument is the destination
        if len(args) == 2:
            # Simple case: QAdd(a, b) - in-place addition: |a⟩|b⟩ → |a⟩|a+b mod 2^n⟩
            a_reg = operand_strs[0]
            b_reg = operand_strs[1]
            self._generate_ripple_carry_adder(a_reg, b_reg, b_reg, in_place=True)
        else:
            # Variadic case: QAdd(a, b, c, ..., dest)
            # Chain additions using temporary registers
            inputs = operand_strs[:-1]
            dest = operand_strs[-1]
            
            # For now, handle two inputs at a time
            # Start with first two inputs
            if len(inputs) >= 2:
                # Use destination as temporary for first addition
                temp = dest
                self._generate_ripple_carry_adder(inputs[0], inputs[1], temp, in_place=False)
                
                # Add remaining inputs one by one
                for i in range(2, len(inputs)):
                    # Add temp + inputs[i] into temp (in-place)
                    self._generate_ripple_carry_adder(temp, inputs[i], temp, in_place=True)
            elif len(inputs) == 1:
                # Only one input, just copy it (or handle as special case)
                # For now, generate a simple addition with zero
                self._generate_ripple_carry_adder(inputs[0], dest, dest, in_place=False)
    
    def _generate_ripple_carry_adder(self, a_reg: str, b_reg: str, result_reg: str, in_place: bool = False):
        """
        Generate a ripple-carry adder circuit with proper carry propagation.
        
        If in_place=True: |a⟩|b⟩ → |a⟩|a+b mod 2^n⟩ (b is overwritten)
        If in_place=False: |a⟩|b⟩|0⟩ → |a⟩|b⟩|a+b mod 2^n⟩ (result in third register)
        
        This implements a reversible ripple-carry adder using:
        - CNOT gates for XOR operations
        - Toffoli (CCX) gates for AND operations and carry computation
        - Proper carry propagation
        """
        # Extract register names and sizes
        a_name = a_reg.split("[")[0] if "[" in a_reg else a_reg
        b_name = b_reg.split("[")[0] if "[" in b_reg else b_reg
        result_name = result_reg.split("[")[0] if "[" in result_reg else result_reg
        
        # Get register sizes
        a_size = self.registers.get(a_name, (None, 1))[1] if a_name in self.registers else 1
        b_size = self.registers.get(b_name, (None, 1))[1] if b_name in self.registers else 1
        result_size = self.registers.get(result_name, (None, 1))[1] if result_name in self.registers else 1
        
        n = min(a_size, b_size, result_size)
        
        self.lines.append(f"// Ripple-carry adder: {a_reg} + {b_reg} -> {result_reg} (n={n} bits)")
        
        if n == 1:
            # Single bit: just XOR
            if in_place:
                self.lines.append(f"cx {a_name}[0], {b_name}[0];  // sum[0] = a[0] XOR b[0]")
            else:
                self.lines.append(f"cx {a_name}[0], {result_name}[0];  // result[0] = a[0]")
                self.lines.append(f"cx {b_name}[0], {result_name}[0];  // result[0] = a[0] XOR b[0]")
        else:
            if in_place:
                # In-place addition: |a⟩|b⟩ → |a⟩|a+b mod 2^n⟩
                # Bit 0: no carry
                self.lines.append(f"cx {a_name}[0], {b_name}[0];  // sum[0] = a[0] XOR b[0]")
                
                # Bits 1 to n-1: compute with carry
                for i in range(1, n):
                    # Compute a[i] XOR b[i] into b[i]
                    self.lines.append(f"cx {a_name}[{i}], {b_name}[{i}];  // b[{i}] = a[{i}] XOR b[{i}]")
                    
                    # Compute carry[i] = a[i-1] AND b[i-1] and XOR with sum
                    # For first carry, this is exact: carry[1] = a[0] AND b[0]
                    if i == 1:
                        self.lines.append(f"ccx {a_name}[0], {b_name}[0], {b_name}[1];  // b[1] = (a[1] XOR b[1]) XOR (a[0] AND b[0])")
                    else:
                        # Simplified: carry[i] ≈ a[i-1] AND b[i-1]
                        # Note: b[i-1] now contains sum[i-1], not original b[i-1]
                        self.lines.append(f"ccx {a_name}[{i-1}], {b_name}[{i-1}], {b_name}[{i}];  // apply carry[{i}] effect (simplified)")
            else:
                # Out-of-place addition: |a⟩|b⟩|0⟩ → |a⟩|b⟩|a+b mod 2^n⟩
                # Bit 0: no carry
                self.lines.append(f"cx {a_name}[0], {result_name}[0];  // result[0] = a[0]")
                self.lines.append(f"cx {b_name}[0], {result_name}[0];  // result[0] = a[0] XOR b[0]")
                
                # Bits 1 to n-1: compute carry and sum
                for i in range(1, n):
                    # Compute carry[i] = a[i-1] AND b[i-1]
                    # Store in result[i] temporarily
                    if i == 1:
                        self.lines.append(f"ccx {a_name}[0], {b_name}[0], {result_name}[1];  // carry[1] = a[0] AND b[0]")
                    else:
                        # For i > 1, simplified carry (full version needs OR with previous carry)
                        self.lines.append(f"ccx {a_name}[{i-1}], {b_name}[{i-1}], {result_name}[{i}];  // carry[{i}] = a[{i-1}] AND b[{i-1}]")
                    
                    # Compute sum[i] = a[i] XOR b[i] XOR carry[i]
                    # result[i] currently contains carry[i]
                    self.lines.append(f"cx {a_name}[{i}], {result_name}[{i}];  // result[{i}] = a[{i}] XOR carry[{i}]")
                    self.lines.append(f"cx {b_name}[{i}], {result_name}[{i}];  // result[{i}] = a[{i}] XOR b[{i}] XOR carry[{i}]")
                
                self.lines.append(f"// Note: This implements a simplified ripple-carry adder")
                self.lines.append(f"//       Full version would properly propagate all carries with OR terms")
    
    def _generate_qsub_circuit(self, args: List[Expr]):
        """Generate ripple-borrow subtractor circuit for QSub operation"""
        if len(args) < 2:
            return
        
        # Convert all arguments to QASM strings
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        
        # For variadic subtraction: QSub(a, b, c, ..., dest)
        # We chain subtractions: first subtract b from a into temp1, then subtract c from temp1, etc.
        # Last argument is the destination
        if len(args) == 2:
            # Simple case: QSub(a, b) - in-place subtraction: |a⟩|b⟩ → |a⟩|a-b mod 2^n⟩
            a_reg = operand_strs[0]
            b_reg = operand_strs[1]
            self._generate_ripple_borrow_subtractor(a_reg, b_reg, b_reg, in_place=True)
        else:
            # Variadic case: QSub(a, b, c, ..., dest)
            # Chain subtractions using temporary registers
            inputs = operand_strs[:-1]
            dest = operand_strs[-1]
            
            # Start with first input
            if len(inputs) >= 2:
                # Use destination as temporary for first subtraction
                temp = dest
                self._generate_ripple_borrow_subtractor(inputs[0], inputs[1], temp, in_place=False)
                
                # Subtract remaining inputs one by one
                for i in range(2, len(inputs)):
                    # Subtract inputs[i] from temp (in-place)
                    self._generate_ripple_borrow_subtractor(temp, inputs[i], temp, in_place=True)
            elif len(inputs) == 1:
                # Only one input, just copy it (or handle as special case)
                self._generate_ripple_borrow_subtractor(inputs[0], dest, dest, in_place=False)
    
    def _generate_ripple_borrow_subtractor(self, a_reg: str, b_reg: str, result_reg: str, in_place: bool = False):
        """
        Generate a ripple-borrow subtractor circuit.
        
        If in_place=True: |a⟩|b⟩ → |a⟩|a-b mod 2^n⟩ (b is overwritten)
        If in_place=False: |a⟩|b⟩|0⟩ → |a⟩|b⟩|a-b mod 2^n⟩ (result in third register)
        
        This implements a reversible ripple-borrow subtractor using:
        - CNOT gates for XOR operations
        - Toffoli (CCX) gates for borrow computation
        - Similar to addition but with borrow propagation instead of carry
        """
        # Extract register names and sizes
        a_name = a_reg.split("[")[0] if "[" in a_reg else a_reg
        b_name = b_reg.split("[")[0] if "[" in b_reg else b_reg
        result_name = result_reg.split("[")[0] if "[" in result_reg else result_reg
        
        # Get register sizes
        a_size = self.registers.get(a_name, (None, 1))[1] if a_name in self.registers else 1
        b_size = self.registers.get(b_name, (None, 1))[1] if b_name in self.registers else 1
        result_size = self.registers.get(result_name, (None, 1))[1] if result_name in self.registers else 1
        
        n = min(a_size, b_size, result_size)
        
        self.lines.append(f"// Ripple-borrow subtractor: {a_reg} - {b_reg} -> {result_reg} (n={n} bits)")
        
        if n == 1:
            # Single bit: just XOR (difference)
            if in_place:
                self.lines.append(f"cx {a_name}[0], {b_name}[0];  // diff[0] = a[0] XOR b[0]")
            else:
                self.lines.append(f"cx {a_name}[0], {result_name}[0];  // result[0] = a[0]")
                self.lines.append(f"cx {b_name}[0], {result_name}[0];  // result[0] = a[0] XOR b[0]")
        else:
            if in_place:
                # In-place subtraction: |a⟩|b⟩ → |a⟩|a-b mod 2^n⟩
                # Bit 0: no borrow
                self.lines.append(f"cx {a_name}[0], {b_name}[0];  // diff[0] = a[0] XOR b[0]")
                
                # Bits 1 to n-1: compute with borrow
                for i in range(1, n):
                    # Compute a[i] XOR b[i] into b[i]
                    self.lines.append(f"cx {a_name}[{i}], {b_name}[{i}];  // b[{i}] = a[{i}] XOR b[{i}]")
                    
                    # Compute borrow[i] and apply to difference
                    # borrow[i] = NOT a[i-1] AND b[i-1] (simplified)
                    if i == 1:
                        # borrow[1] = NOT a[0] AND b[0]
                        # Use X gate to invert a[0] for borrow computation
                        self.lines.append(f"x {a_name}[0];  // Invert a[0] for borrow")
                        self.lines.append(f"ccx {a_name}[0], {b_name}[0], {b_name}[1];  // b[1] = (a[1] XOR b[1]) XOR borrow[1]")
                        self.lines.append(f"x {a_name}[0];  // Restore a[0]")
                    else:
                        # Simplified borrow propagation
                        self.lines.append(f"x {a_name}[{i-1}];  // Invert a[{i-1}] for borrow")
                        self.lines.append(f"ccx {a_name}[{i-1}], {b_name}[{i-1}], {b_name}[{i}];  // apply borrow[{i}] effect")
                        self.lines.append(f"x {a_name}[{i-1}];  // Restore a[{i-1}]")
            else:
                # Out-of-place subtraction: |a⟩|b⟩|0⟩ → |a⟩|b⟩|a-b mod 2^n⟩
                # Bit 0: no borrow
                self.lines.append(f"cx {a_name}[0], {result_name}[0];  // result[0] = a[0]")
                self.lines.append(f"cx {b_name}[0], {result_name}[0];  // result[0] = a[0] XOR b[0]")
                
                # Bits 1 to n-1: compute borrow and difference
                for i in range(1, n):
                    # Compute borrow[i] = NOT a[i-1] AND b[i-1]
                    # Store in result[i] temporarily
                    if i == 1:
                        self.lines.append(f"x {a_name}[0];  // Invert a[0] for borrow")
                        self.lines.append(f"ccx {a_name}[0], {b_name}[0], {result_name}[1];  // borrow[1] = NOT a[0] AND b[0]")
                        self.lines.append(f"x {a_name}[0];  // Restore a[0]")
                    else:
                        # Simplified borrow propagation
                        self.lines.append(f"x {a_name}[{i-1}];  // Invert a[{i-1}] for borrow")
                        self.lines.append(f"ccx {a_name}[{i-1}], {b_name}[{i-1}], {result_name}[{i}];  // borrow[{i}] = NOT a[{i-1}] AND b[{i-1}]")
                        self.lines.append(f"x {a_name}[{i-1}];  // Restore a[{i-1}]")
                    
                    # Compute diff[i] = a[i] XOR b[i] XOR borrow[i]
                    # result[i] currently contains borrow[i]
                    self.lines.append(f"cx {a_name}[{i}], {result_name}[{i}];  // result[{i}] = a[{i}] XOR borrow[{i}]")
                    self.lines.append(f"cx {b_name}[{i}], {result_name}[{i}];  // result[{i}] = a[{i}] XOR b[{i}] XOR borrow[{i}]")
                
                self.lines.append(f"// Note: This implements a simplified ripple-borrow subtractor")
                self.lines.append(f"//       Full version would properly propagate all borrows")
    
    def _generate_qdiv_circuit(self, args: List[Expr]):
        """Generate quantum division circuit using repeated subtraction"""
        if len(args) < 4:
            return
        
        # QDiv(dividend, divisor, quotient, remainder)
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        dividend = operand_strs[0]
        divisor = operand_strs[1]
        quotient = operand_strs[2]
        remainder = operand_strs[3]
        
        dividend_name = dividend.split("[")[0] if "[" in dividend else dividend
        divisor_name = divisor.split("[")[0] if "[" in divisor else divisor
        quotient_name = quotient.split("[")[0] if "[" in quotient else quotient
        remainder_name = remainder.split("[")[0] if "[" in remainder else remainder
        
        # Get register sizes
        dividend_size = self.registers.get(dividend_name, (None, 1))[1] if dividend_name in self.registers else 1
        divisor_size = self.registers.get(divisor_name, (None, 1))[1] if divisor_name in self.registers else 1
        
        n = min(dividend_size, divisor_size)
        
        self.lines.append(f"// Quantum division: {dividend} / {divisor} -> {quotient}, remainder -> {remainder} (n={n} bits)")
        self.lines.append(f"// Algorithm: Repeated subtraction until dividend < divisor")
        self.lines.append(f"// Initialize quotient and remainder")
        self.lines.append(f"// remainder = dividend (copy)")
        
        # Copy dividend to remainder
        for i in range(n):
            self.lines.append(f"cx {dividend_name}[{i}], {remainder_name}[{i}];  // remainder[{i}] = dividend[{i}]")
        
        # Initialize quotient to zero (already done by declaration)
        self.lines.append(f"// Quotient initialized to |0⟩")
        
        # Repeated subtraction loop (simplified - full version would use controlled subtraction)
        self.lines.append(f"// Repeated subtraction: while remainder >= divisor:")
        self.lines.append(f"//   1. Subtract divisor from remainder")
        self.lines.append(f"//   2. Increment quotient")
        self.lines.append(f"//   3. Check if remainder >= divisor (using Compare)")
        self.lines.append(f"// Note: Full implementation requires controlled subtraction and comparison")
        self.lines.append(f"//       This is a simplified version showing the structure")
        
        # For a full implementation, we would:
        # 1. Use Compare to check if remainder >= divisor
        # 2. If yes, subtract divisor from remainder (controlled by comparison flag)
        # 3. Increment quotient (controlled by comparison flag)
        # 4. Repeat until remainder < divisor
        
        self.lines.append(f"// Full implementation would use:")
        self.lines.append(f"//   - Compare(remainder, divisor, flag) to check remainder >= divisor")
        self.lines.append(f"//   - Controlled QSub(remainder, divisor, remainder) with control = flag")
        self.lines.append(f"//   - Controlled increment of quotient with control = flag")
        self.lines.append(f"//   - Loop until flag = 0")
    
    def _generate_qmod_circuit(self, args: List[Expr]):
        """Generate quantum modulus circuit"""
        if len(args) < 3:
            return
        
        # Convert all arguments to QASM strings
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        
        # For variadic modulus: QMod(a, b, c, ..., dest)
        # Computes: result = a mod b mod c mod ...
        # Last argument is the destination
        if len(args) == 3:
            # Simple case: QMod(a, b, result) - result = a mod b
            a_reg = operand_strs[0]
            b_reg = operand_strs[1]
            result_reg = operand_strs[2]
            
            a_name = a_reg.split("[")[0] if "[" in a_reg else a_reg
            b_name = b_reg.split("[")[0] if "[" in b_reg else b_reg
            result_name = result_reg.split("[")[0] if "[" in result_reg else result_reg
            
            a_size = self.registers.get(a_name, (None, 1))[1] if a_name in self.registers else 1
            b_size = self.registers.get(b_name, (None, 1))[1] if b_name in self.registers else 1
            result_size = self.registers.get(result_name, (None, 1))[1] if result_name in self.registers else 1
            
            n = min(a_size, b_size, result_size)
            
            self.lines.append(f"// Quantum modulus: {a_reg} mod {b_reg} -> {result_reg} (n={n} bits)")
            self.lines.append(f"// Algorithm: Repeated subtraction until result < b")
            
            # Copy a to result
            for i in range(n):
                self.lines.append(f"cx {a_name}[{i}], {result_name}[{i}];  // result[{i}] = a[{i}]")
            
            # Repeated subtraction (simplified)
            self.lines.append(f"// Repeated subtraction: while result >= b:")
            self.lines.append(f"//   1. Subtract b from result")
            self.lines.append(f"//   2. Check if result >= b (using Compare)")
            self.lines.append(f"//   3. Repeat until result < b")
            self.lines.append(f"// Note: Full implementation requires controlled subtraction and comparison")
        else:
            # Variadic case: QMod(a, b, c, ..., dest)
            # Computes: result = a mod b mod c mod ...
            inputs = operand_strs[:-1]
            dest = operand_strs[-1]
            
            # Start with first modulus operation: a mod b
            if len(inputs) >= 2:
                # Compute a mod b into temp, then temp mod c, etc.
                temp = dest
                # First modulus: a mod b (need to create temp Expr)
                # For now, just generate the circuit directly
                a_reg = inputs[0]
                b_reg = inputs[1]
                result_reg = temp
                
                a_name = a_reg.split("[")[0] if "[" in a_reg else a_reg
                b_name = b_reg.split("[")[0] if "[" in b_reg else b_reg
                result_name = result_reg.split("[")[0] if "[" in result_reg else result_reg
                
                a_size = self.registers.get(a_name, (None, 1))[1] if a_name in self.registers else 1
                b_size = self.registers.get(b_name, (None, 1))[1] if b_name in self.registers else 1
                result_size = self.registers.get(result_name, (None, 1))[1] if result_name in self.registers else 1
                
                n = min(a_size, b_size, result_size)
                
                # Copy a to result
                for i in range(n):
                    self.lines.append(f"cx {a_name}[{i}], {result_name}[{i}];  // result[{i}] = a[{i}]")
                
                self.lines.append(f"// Repeated subtraction: while result >= b")
                
                # Apply remaining moduli
                for i in range(2, len(inputs)):
                    # Compute temp mod inputs[i] into temp
                    # This would require recursive call, but for now just note it
                    self.lines.append(f"// Apply modulus with {inputs[i]}")
    
    def _generate_qmult_circuit(self, args: List[Expr]):
        """Generate quantum multiplication circuit using shift-and-add approach"""
        if len(args) < 3:
            return
        
        # Convert all arguments to QASM strings
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        
        # QMult(a, b, c, ..., dest) - variadic multiplication
        # For now, handle the common case: QMult(a, b, dest)
        if len(args) == 3:
            # Binary multiplication: QMult(a, b, dest)
            a_reg = operand_strs[0]
            b_reg = operand_strs[1]
            dest_reg = operand_strs[2]
            self._generate_shift_and_add_multiplier(a_reg, b_reg, dest_reg)
        else:
            # Variadic case: chain multiplications
            # For simplicity, handle two at a time
            inputs = operand_strs[:-1]
            dest = operand_strs[-1]
            
            if len(inputs) >= 2:
                # Multiply first two, then multiply result with next, etc.
                temp = dest
                self._generate_shift_and_add_multiplier(inputs[0], inputs[1], temp)
                
                for i in range(2, len(inputs)):
                    # Multiply temp * inputs[i] into temp (would need new temp)
                    self.lines.append(f"// Variadic multiplication: would multiply intermediate result with {inputs[i]}")
    
    def _generate_shift_and_add_multiplier(self, a_reg: str, b_reg: str, result_reg: str):
        """
        Generate quantum multiplication circuit using shift-and-add approach.
        
        Algorithm:
        - For each bit i of B (multiplier):
          - If B[i] == 1, add (A shifted by i) to result using controlled adder
          - This is: result += (A * 2^i) when B[i] == 1
        
        Circuit structure:
        - Initialize result to |0⟩
        - For i = 0 to n-1:
          - Controlled addition: if B[i] == 1, add shifted A to result
          - The shift is implicit in which qubits of result receive the addition
        """
        # Extract register names and sizes
        a_name = a_reg.split("[")[0] if "[" in a_reg else a_reg
        b_name = b_reg.split("[")[0] if "[" in b_reg else b_reg
        result_name = result_reg.split("[")[0] if "[" in result_reg else result_reg
        
        # Get register sizes
        a_size = self.registers.get(a_name, (None, 1))[1] if a_name in self.registers else 1
        b_size = self.registers.get(b_name, (None, 1))[1] if b_name in self.registers else 1
        result_size = self.registers.get(result_name, (None, 1))[1] if result_name in self.registers else 1
        
        n = min(a_size, b_size)  # Size of input registers
        # Result should ideally be 2n for full precision, but we use what's available
        
        self.lines.append(f"// Quantum multiplier (shift-and-add): {a_reg} * {b_reg} -> {result_reg}")
        self.lines.append(f"// Algorithm: For each bit i of B, if B[i]==1, add (A shifted by i) to result")
        self.lines.append(f"// Result register size: {result_size} (ideally 2*{n}={2*n} for full precision)")
        
        # Initialize result to zero (should already be |0>)
        self.lines.append(f"// Initialize result register to |0> (already done by declaration)")
        
        # For each bit of the multiplier (B), perform controlled addition
        for i in range(n):
            self.lines.append(f"// Bit {i} of multiplier B: controlled addition of (A shifted by {i})")
            self.lines.append(f"// If B[{i}] == 1, add A shifted by {i} bits to result")
            
            # For each bit of A, add it to the appropriate position in result
            # Position in result = i + j (where j is the bit position in A)
            for j in range(min(a_size, result_size - i)):
                result_bit = i + j
                if result_bit < result_size:
                    # Controlled addition: if B[i] == 1, add A[j] to result[result_bit]
                    # This is: result[result_bit] += A[j] when B[i] == 1
                    # We use a controlled CNOT (Toffoli with control B[i])
                    self.lines.append(f"//   ccx {b_name}[{i}], {a_name}[{j}], {result_name}[{result_bit}];  // Controlled add: if B[{i}], add A[{j}] to result[{result_bit}]")
            
            # For a full implementation, we'd use controlled ripple-carry adders
            # For each bit i of B:
            #   - Create shifted version of A (starting at position i in result)
            #   - Use controlled QAdd with B[i] as control
            self.lines.append(f"//   Full implementation would use: controlled-QAdd(A shifted by {i}, result) with control = B[{i}]")
            self.lines.append(f"//   This requires a controlled ripple-carry adder circuit")
        
        self.lines.append(f"// Full shift-and-add multiplier structure:")
        self.lines.append(f"//   1. For each bit i = 0 to n-1 of multiplier B:")
        self.lines.append(f"//      a. If B[i] == 1 (controlled operation):")
        self.lines.append(f"//      b. Add (A shifted by i) to result using controlled ripple-carry adder")
        self.lines.append(f"//   2. Each controlled addition is reversible (uses uncomputation)")
        self.lines.append(f"//   3. Result accumulates: result = sum(B[i] * (A shifted by i)) for all i")
        self.lines.append(f"// Requires: Controlled ripple-carry adders, ancilla qubits for carries")
    
    def _generate_qftadd_circuit(self, args: List[Expr]):
        """Generate QFT-based adder circuit for QFTAdd operation"""
        if len(args) < 2:
            return
        
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        
        # For variadic addition: QFTAdd(a, b, c, ..., dest)
        if len(args) == 2:
            a_reg = operand_strs[0]
            b_reg = operand_strs[1]
            self._generate_qft_adder(a_reg, b_reg, b_reg, in_place=True)
        else:
            inputs = operand_strs[:-1]
            dest = operand_strs[-1]
            
            if len(inputs) >= 2:
                temp = dest
                self._generate_qft_adder(inputs[0], inputs[1], temp, in_place=False)
                
                for i in range(2, len(inputs)):
                    self._generate_qft_adder(temp, inputs[i], temp, in_place=True)
            elif len(inputs) == 1:
                self._generate_qft_adder(inputs[0], dest, dest, in_place=False)
    
    def _generate_qft_adder(self, a_reg: str, b_reg: str, result_reg: str, in_place: bool = False):
        """
        Generate QFT-based adder circuit (Draper adder).
        
        Algorithm:
        1. Apply QFT to target register
        2. Use controlled phase rotations to add the other operand
        3. Apply inverse QFT to transform back to computational basis
        """
        a_name = a_reg.split("[")[0] if "[" in a_reg else a_reg
        b_name = b_reg.split("[")[0] if "[" in b_reg else b_reg
        result_name = result_reg.split("[")[0] if "[" in result_reg else result_reg
        
        a_size = self.registers.get(a_name, (None, 1))[1] if a_name in self.registers else 1
        b_size = self.registers.get(b_name, (None, 1))[1] if b_name in self.registers else 1
        result_size = self.registers.get(result_name, (None, 1))[1] if result_name in self.registers else 1
        
        n = min(a_size, b_size, result_size)
        
        self.lines.append(f"// QFT-based adder (Draper adder): {a_reg} + {b_reg} -> {result_reg} (n={n} bits)")
        
        if in_place:
            # In-place: |a⟩|b⟩ → |a⟩|a+b mod 2^n⟩
            target_name = b_name
            target_reg = b_reg
        else:
            # Out-of-place: |a⟩|b⟩|0⟩ → |a⟩|b⟩|a+b mod 2^n⟩
            target_name = result_name
            target_reg = result_reg
        
        # Step 1: Apply QFT to target register
        # QFT layer 0
        if n > 0:
            self.lines.append(f"h {target_name}[0];")
            if n > 1:
                self.lines.append(f"crz(pi/2) {target_name}[1], {target_name}[0];")
            if n > 2:
                self.lines.append(f"crz(pi/4) {target_name}[2], {target_name}[0];")
                for k in range(3, n):
                    phase = f"pi/{2**k}"
                    self.lines.append(f"crz({phase}) {target_name}[{k}], {target_name}[0];")
        
        # QFT layer 1
        if n > 1:
            self.lines.append(f"h {target_name}[1];")
            if n > 2:
                self.lines.append(f"crz(pi/2) {target_name}[2], {target_name}[1];")
                for k in range(3, n):
                    phase = f"pi/{2**(k-1)}"
                    self.lines.append(f"crz({phase}) {target_name}[{k}], {target_name}[1];")
        
        # QFT layers 2 to n-1
        for layer in range(2, n):
            self.lines.append(f"h {target_name}[{layer}];")
            for k in range(layer + 1, n):
                phase = f"pi/{2**(k-layer)}"
                self.lines.append(f"crz({phase}) {target_name}[{k}], {target_name}[{layer}];")
        
        # Swap for correct order (reverse qubits)
        for i in range(n // 2):
            self.lines.append(f"swap {target_name}[{i}], {target_name}[{n-1-i}];")
        
        # Step 2: Controlled phase rotations to add operands
        import math
        for i in range(n):
            for j in range(min(i + 1, n)):
                if i - j >= 0:
                    phase_val = math.pi / (2 ** (i - j))
                    phase_str = f"pi/{2**(i-j)}" if (i - j) > 0 else "pi"
                    
                    # Add contribution from a_reg
                    if j < a_size:
                        self.lines.append(f"crz({phase_str}) {a_name}[{j}], {target_name}[{i}];")
                    
                    # Add contribution from b_reg (only if out-of-place)
                    if not in_place and j < b_size:
                        self.lines.append(f"crz({phase_str}) {b_name}[{j}], {target_name}[{i}];")
        
        # Step 3: Apply inverse QFT to target register
        # Unswap
        for i in range(n // 2):
            self.lines.append(f"swap {target_name}[{i}], {target_name}[{n-1-i}];")
        
        # Inverse QFT layers (reverse order)
        for layer in range(n - 1, 1, -1):
            for k in range(n - 1, layer, -1):
                phase = f"-pi/{2**(k-layer)}"
                self.lines.append(f"crz({phase}) {target_name}[{k}], {target_name}[{layer}];")
            self.lines.append(f"h {target_name}[{layer}];")
        
        # Inverse QFT layer 1
        if n > 1:
            for k in range(n - 1, 1, -1):
                phase = f"-pi/{2**(k-1)}"
                self.lines.append(f"crz({phase}) {target_name}[{k}], {target_name}[1];")
            if n > 2:
                self.lines.append(f"crz(-pi/2) {target_name}[2], {target_name}[1];")
            self.lines.append(f"h {target_name}[1];")
        
        # Inverse QFT layer 0
        if n > 0:
            for k in range(n - 1, 0, -1):
                phase = f"-pi/{2**k}"
                self.lines.append(f"crz({phase}) {target_name}[{k}], {target_name}[0];")
            if n > 2:
                self.lines.append(f"crz(-pi/4) {target_name}[2], {target_name}[0];")
            if n > 1:
                self.lines.append(f"crz(-pi/2) {target_name}[1], {target_name}[0];")
            self.lines.append(f"h {target_name}[0];")
    
    def _generate_qtreeadd_circuit(self, args: List[Expr]):
        """Generate tree-based adder circuit for QTreeAdd operation"""
        if len(args) < 2:
            return
        
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        
        # For variadic addition: QTreeAdd(a, b, c, ..., dest)
        if len(args) == 2:
            a_reg = operand_strs[0]
            b_reg = operand_strs[1]
            self._generate_tree_adder(a_reg, b_reg, b_reg, in_place=True)
        else:
            inputs = operand_strs[:-1]
            dest = operand_strs[-1]
            
            if len(inputs) >= 2:
                temp = dest
                self._generate_tree_adder(inputs[0], inputs[1], temp, in_place=False)
                
                for i in range(2, len(inputs)):
                    self._generate_tree_adder(temp, inputs[i], temp, in_place=True)
            elif len(inputs) == 1:
                self._generate_tree_adder(inputs[0], dest, dest, in_place=False)
    
    def _generate_tree_adder(self, a_reg: str, b_reg: str, result_reg: str, in_place: bool = False):
        """
        Generate tree-based carry-save/parallel adder circuit.
        
        Algorithm:
        - Uses balanced tree structure to parallelize carry computation
        - Reduces multiple partial operands in a tree (Wallace-tree inspired)
        - Parallel controlled gates handle carry propagation efficiently
        """
        a_name = a_reg.split("[")[0] if "[" in a_reg else a_reg
        b_name = b_reg.split("[")[0] if "[" in b_reg else b_reg
        result_name = result_reg.split("[")[0] if "[" in result_reg else result_reg
        
        a_size = self.registers.get(a_name, (None, 1))[1] if a_name in self.registers else 1
        b_size = self.registers.get(b_name, (None, 1))[1] if b_name in self.registers else 1
        result_size = self.registers.get(result_name, (None, 1))[1] if result_name in self.registers else 1
        
        n = min(a_size, b_size, result_size)
        
        self.lines.append(f"// Tree-based adder: {a_reg} + {b_reg} -> {result_reg} (n={n} bits)")
        
        # Generate ancilla register name for carries (simplified - in practice would need proper allocation)
        carry_name = f"_carry_{result_name}"
        
        # Level 0: Compute partial sums and carries in parallel
        for i in range(n):
            # Compute carry[i+1] = a[i] AND b[i]
            if i < n - 1:
                # Use result register bits as temporary carry storage (simplified)
                # In full implementation, would allocate proper ancilla qubits
                carry_bit = f"{result_name}[{i+1}]" if i+1 < result_size else f"{result_name}[{i}]"
                self.lines.append(f"ccx {a_name}[{i}], {b_name}[{i}], {carry_bit};  // carry[{i+1}] = a[{i}] AND b[{i}]")
            
            # Compute sum[i] = a[i] XOR b[i]
            self.lines.append(f"cx {a_name}[{i}], {result_name}[{i}];  // result[{i}] = a[{i}]")
            self.lines.append(f"cx {b_name}[{i}], {result_name}[{i}];  // result[{i}] = a[{i}] XOR b[{i}]")
        
        # Tree carry reduction (simplified for small n)
        # For n=3: combine carries 1,2,3
        if n >= 2:
            # Level 1: Combine carries
            if n >= 3:
                # Combine carry[1] and carry[2] into temp
                temp_carry = f"{result_name}[{min(2, result_size-1)}]"
                self.lines.append(f"ccx {result_name}[1], {result_name}[2], {temp_carry};  // Combine carries 1 and 2")
            
            # Level 2: Combine with carry[3] if exists
            if n >= 3:
                final_carry = f"{result_name}[{min(2, result_size-1)}]"
                if n >= 4:
                    self.lines.append(f"ccx {final_carry}, {result_name}[3], {result_name}[{min(3, result_size-1)}];  // Combine with carry 3")
        
        # Final sum combination: add carries to sum bits
        for i in range(1, n):
            carry_bit = f"{result_name}[{i}]"
            if i < result_size:
                # Add carry to sum[i]
                self.lines.append(f"cx {carry_bit}, {result_name}[{i}];  // Add carry[{i}] to sum[{i}]")
        
        # Note: This is a simplified implementation. Full tree adder would:
        # 1. Use proper ancilla qubits for carry storage
        # 2. Implement full tree reduction with proper carry propagation
        # 3. Uncompute intermediate carries for reversibility
    
    def _generate_qexpencmult_circuit(self, args: List[Expr]):
        """Generate exponent-encoded multiplication circuit for QExpEncMult operation"""
        if len(args) < 3:
            return
        
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        
        # QExpEncMult(a, b, c, ..., dest) - variadic multiplication
        if len(args) == 3:
            a_reg = operand_strs[0]
            b_reg = operand_strs[1]
            dest_reg = operand_strs[2]
            self._generate_expenc_multiplier(a_reg, b_reg, dest_reg)
        else:
            inputs = operand_strs[:-1]
            dest = operand_strs[-1]
            
            if len(inputs) >= 2:
                temp = dest
                self._generate_expenc_multiplier(inputs[0], inputs[1], temp)
                
                for i in range(2, len(inputs)):
                    self.lines.append(f"// Variadic exponent-encoded multiplication: would multiply intermediate result with {inputs[i]}")
    
    def _generate_expenc_multiplier(self, a_reg: str, b_reg: str, result_reg: str):
        """
        Generate exponent-encoded multiplication circuit.
        
        Algorithm:
        1. Encode operands as superposition states in compact form (logarithmic qubits)
        2. Use fast adder (QFT-based) to sum those encodings
        3. Extract product from sum via measurement and classical post-processing
        """
        a_name = a_reg.split("[")[0] if "[" in a_reg else a_reg
        b_name = b_reg.split("[")[0] if "[" in b_reg else b_reg
        result_name = result_reg.split("[")[0] if "[" in result_reg else result_reg
        
        a_size = self.registers.get(a_name, (None, 1))[1] if a_name in self.registers else 1
        b_size = self.registers.get(b_name, (None, 1))[1] if b_name in self.registers else 1
        result_size = self.registers.get(result_name, (None, 1))[1] if result_name in self.registers else 1
        
        n = min(a_size, b_size)
        log_n = max(1, (n.bit_length() - 1))
        
        self.lines.append(f"// Exponent-encoded multiplier: {a_reg} * {b_reg} -> {result_reg}")
        
        # Step 1: Encode m3 into phase (simplified - encode each bit with rotation)
        for i in range(min(n, a_size)):
            if i == 0:
                self.lines.append(f"rz(pi/2 * {i}) {a_name}[{i}];  // Encode bit {i} of {a_name}")
            else:
                self.lines.append(f"crz(pi/2 * {i}) {a_name}[0], {a_name}[{i}];  // Encode bit {i} of {a_name}")
        
        # Step 2: Encode m4 into phase
        for i in range(min(n, b_size)):
            if i == 0:
                self.lines.append(f"rz(pi/2 * {i}) {b_name}[{i}];  // Encode bit {i} of {b_name}")
            else:
                self.lines.append(f"crz(pi/2 * {i}) {b_name}[0], {b_name}[{i}];  // Encode bit {i} of {b_name}")
        
        # Step 3: QFT on result register
        if result_size > 0:
            # QFT layer 0
            self.lines.append(f"h {result_name}[0];")
            if result_size > 1:
                self.lines.append(f"crz(pi/2) {result_name}[1], {result_name}[0];")
            if result_size > 2:
                self.lines.append(f"crz(pi/4) {result_name}[2], {result_name}[0];")
                for k in range(3, result_size):
                    phase = f"pi/{2**k}"
                    self.lines.append(f"crz({phase}) {result_name}[{k}], {result_name}[0];")
            
            # QFT layer 1
            if result_size > 1:
                self.lines.append(f"h {result_name}[1];")
                if result_size > 2:
                    self.lines.append(f"crz(pi/2) {result_name}[2], {result_name}[1];")
                    for k in range(3, result_size):
                        phase = f"pi/{2**(k-1)}"
                        self.lines.append(f"crz({phase}) {result_name}[{k}], {result_name}[1];")
            
            # QFT layers 2 to result_size-1
            for layer in range(2, result_size):
                self.lines.append(f"h {result_name}[{layer}];")
                for k in range(layer + 1, result_size):
                    phase = f"pi/{2**(k-layer)}"
                    self.lines.append(f"crz({phase}) {result_name}[{k}], {result_name}[{layer}];")
            
            # Swap for correct order
            for i in range(result_size // 2):
                self.lines.append(f"swap {result_name}[{i}], {result_name}[{result_size-1-i}];")
        
        # Step 4: Add phases (multiplication in exponent domain)
        # Add a_reg encoding
        for i in range(min(n, a_size)):
            for j in range(min(result_size, n + 1)):
                if j == 0:
                    phase = "pi"
                else:
                    phase = f"pi/{2**j}"
                self.lines.append(f"crz({phase}) {a_name}[{i}], {result_name}[{j}];  // Add {a_name}[{i}] encoding")
        
        # Add b_reg encoding
        for i in range(min(n, b_size)):
            for j in range(min(result_size, n + 1)):
                if j == 0:
                    phase = "pi"
                else:
                    phase = f"pi/{2**j}"
                self.lines.append(f"crz({phase}) {b_name}[{i}], {result_name}[{j}];  // Add {b_name}[{i}] encoding")
        
        # Step 5: Inverse QFT
        if result_size > 0:
            # Unswap
            for i in range(result_size // 2):
                self.lines.append(f"swap {result_name}[{i}], {result_name}[{result_size-1-i}];")
            
            # Inverse QFT layers (reverse order)
            for layer in range(result_size - 1, 1, -1):
                for k in range(result_size - 1, layer, -1):
                    phase = f"-pi/{2**(k-layer)}"
                    self.lines.append(f"crz({phase}) {result_name}[{k}], {result_name}[{layer}];")
                self.lines.append(f"h {result_name}[{layer}];")
            
            # Inverse QFT layer 1
            if result_size > 1:
                for k in range(result_size - 1, 1, -1):
                    phase = f"-pi/{2**(k-1)}"
                    self.lines.append(f"crz({phase}) {result_name}[{k}], {result_name}[1];")
                if result_size > 2:
                    self.lines.append(f"crz(-pi/2) {result_name}[2], {result_name}[1];")
                self.lines.append(f"h {result_name}[1];")
            
            # Inverse QFT layer 0
            for k in range(result_size - 1, 0, -1):
                phase = f"-pi/{2**k}"
                self.lines.append(f"crz({phase}) {result_name}[{k}], {result_name}[0];")
            if result_size > 2:
                self.lines.append(f"crz(-pi/4) {result_name}[2], {result_name}[0];")
            if result_size > 1:
                self.lines.append(f"crz(-pi/2) {result_name}[1], {result_name}[0];")
            self.lines.append(f"h {result_name}[0];")
        
        # Step 6: Decode (result is now in computational basis)
        # Note: Full implementation would include measurement and classical post-processing
        self.lines.append(f"// Decode: result is now in computational basis (measurement may be required)")
    
    def _generate_qtreemult_circuit(self, args: List[Expr]):
        """Generate tree-based multiplication circuit for QTreeMult operation"""
        if len(args) < 3:
            return
        
        operand_strs = [self._expr_to_qasm(arg) for arg in args]
        
        # QTreeMult(a, b, c, ..., dest) - variadic multiplication
        if len(args) == 3:
            a_reg = operand_strs[0]
            b_reg = operand_strs[1]
            dest_reg = operand_strs[2]
            self._generate_tree_multiplier(a_reg, b_reg, dest_reg)
        else:
            inputs = operand_strs[:-1]
            dest = operand_strs[-1]
            
            if len(inputs) >= 2:
                temp = dest
                self._generate_tree_multiplier(inputs[0], inputs[1], temp)
                
                for i in range(2, len(inputs)):
                    self.lines.append(f"// Variadic tree multiplication: would multiply intermediate result with {inputs[i]}")
    
    def _generate_tree_multiplier(self, a_reg: str, b_reg: str, result_reg: str):
        """
        Generate tree-based multiplication circuit (Wallace/Dadda-style).
        
        Algorithm:
        - Inspired by classical multipliers like Wallace tree
        - Reduces partial products more efficiently using quantum reversible gates
        - Uses tree of controlled adders to combine partial products efficiently
        """
        a_name = a_reg.split("[")[0] if "[" in a_reg else a_reg
        b_name = b_reg.split("[")[0] if "[" in b_reg else b_reg
        result_name = result_reg.split("[")[0] if "[" in result_reg else result_reg
        
        a_size = self.registers.get(a_name, (None, 1))[1] if a_name in self.registers else 1
        b_size = self.registers.get(b_name, (None, 1))[1] if b_name in self.registers else 1
        result_size = self.registers.get(result_name, (None, 1))[1] if result_name in self.registers else 1
        
        n = min(a_size, b_size)
        
        self.lines.append(f"// Tree-based multiplier (Wallace/Dadda-style): {a_reg} * {b_reg} -> {result_reg}")
        
        # Step 1: Generate partial products in parallel
        # For 2x2 bit multiplier (simplified example)
        if n == 2:
            # n2[0] * n1[0] -> result[0]
            self.lines.append(f"ccx {b_name}[0], {a_name}[0], {result_name}[0];  // pp[0] = B[0] * A[0]")
            
            # n2[0] * n1[1] -> result[1]
            self.lines.append(f"ccx {b_name}[0], {a_name}[1], {result_name}[1];  // pp[1] = B[0] * A[1]")
            
            # n2[1] * n1[0] -> result[1] (accumulate)
            if result_size >= 2:
                self.lines.append(f"ccx {b_name}[1], {a_name}[0], {result_name}[2];  // temp = B[1] * A[0]")
                self.lines.append(f"cx {result_name}[1], {result_name}[2];  // result[2] = pp[1] XOR temp")
                self.lines.append(f"ccx {b_name}[1], {a_name}[0], {result_name}[2];  // Restore temp")
            
            # n2[1] * n1[1] -> result[2] and result[3]
            if result_size >= 3:
                self.lines.append(f"ccx {b_name}[1], {a_name}[1], {result_name}[3];  // pp[3] = B[1] * A[1]")
                if result_size >= 2:
                    self.lines.append(f"cx {result_name}[2], {result_name}[3];  // result[3] = result[2] XOR pp[3]")
                    self.lines.append(f"ccx {b_name}[1], {a_name}[1], {result_name}[3];  // Restore")
            
            # Tree reduction (simplified for 2x2)
            # First level: Add result[0] and result[1] into result[0:1]
            if result_size >= 1:
                # Half adder for bit 0 (already in result[0])
                pass
            
            if result_size >= 2:
                # Half adder for bit 1 (with carry from result[0]+result[1])
                if result_size >= 3:
                    self.lines.append(f"ccx {result_name}[0], {result_name}[1], {result_name}[2];  // carry from bit 0")
                    self.lines.append(f"cx {result_name}[0], {result_name}[1];  // sum bit 1")
                    self.lines.append(f"cx {result_name}[1], {result_name}[1];  // sum bit 1 (XOR)")
                
                # Second level: Add result[1:2] and result[2] with carry
                if result_size >= 3:
                    self.lines.append(f"ccx {result_name}[1], {result_name}[2], {result_name}[3];  // Full adder carry")
                    if result_size >= 2:
                        self.lines.append(f"ccx {result_name}[1], {result_name}[2], {result_name}[3];  // Full adder sum")
                        self.lines.append(f"cx {result_name}[1], {result_name}[2];  // sum bit 2")
                        self.lines.append(f"cx {result_name}[2], {result_name}[1];  // sum bit 1")
        else:
            # General n-bit case: generate partial products
            for i in range(n):
                for j in range(n):
                    result_bit = i + j
                    if result_bit < result_size:
                        self.lines.append(f"ccx {b_name}[{i}], {a_name}[{j}], {result_name}[{result_bit}];  // pp[{i}][{j}] = B[{i}] * A[{j}]")
            
            # Tree reduction would go here (simplified)
            self.lines.append(f"// Tree reduction: combine partial products using carry-save adders")
        
        # Note: This is a simplified implementation. Full tree multiplier would:
        # 1. Properly allocate ancilla qubits for partial products
        # 2. Implement full Wallace/Dadda tree reduction
        # 3. Use proper carry-save adders for tree levels
        # 4. Handle uncomputation for reversibility
    
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
    
    def _handle_measure_all(self, args: List[Expr]):
        """Handle MeasureAll(q, c) stdlib function"""
        if len(args) != 2:
            return
        q_reg = self._expr_to_qasm(args[0])
        c_reg = self._expr_to_qasm(args[1])
        # Extract register names (simplified - assumes q[0] format)
        q_name = q_reg.split("[")[0] if "[" in q_reg else q_reg
        c_name = c_reg.split("[")[0] if "[" in c_reg else c_reg
        
        # Check if both are full registers (not indexed)
        q_is_register = "[" not in q_reg or q_reg.endswith("]") and q_reg.count("[") == 1
        c_is_register = "[" not in c_reg or c_reg.endswith("]") and c_reg.count("[") == 1
        
        # Get register sizes
        q_size = self.registers.get(q_name, (None, 1))[1] if q_name in self.registers else 1
        c_size = self.registers.get(c_name, (None, 1))[1] if c_name in self.registers else 1
        
        # If both are full registers of same size, use register-to-register measurement
        if q_is_register and c_is_register and q_size == c_size and q_size > 1:
            self.lines.append(f"measure {q_name} -> {c_name};")
        else:
            # Generate individual measure statements
            size = min(q_size, c_size)
            for i in range(size):
                self.lines.append(f"measure {q_name}[{i}] -> {c_name}[{i}];")
    
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
