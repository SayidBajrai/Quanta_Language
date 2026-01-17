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
        
        # Visit all statements (gates are expanded inline, not generated)
        for stmt in ast.statements:
            if not isinstance(stmt, GateDecl):  # Skip gate declarations
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
        self.lines.append(f"{node.kind}[{size}] {node.name};")
    
    def visit_func_decl(self, node: FuncDecl) -> None:
        """Function declarations are inlined, not generated"""
        pass
    
    def visit_gate_decl(self, node: GateDecl) -> None:
        """Gate declarations are expanded inline, not generated"""
        pass
    
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
            
            # Handle gate macros
            if name in self.gates:
                self._expand_gate_macro(name, node.args, node.modifiers, node.ctrl_count)
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
    
    def _expand_gate_macro(self, name: str, args: List[Expr], modifiers: List[str], ctrl_count: Optional[int]):
        """Expand a gate macro inline"""
        gate = self.gates[name]
        # Create parameter substitution map (param name -> argument Expr)
        param_map = {}
        for i, param in enumerate(gate.params):
            if i < len(args):
                param_map[param] = args[i]
        
        # Expand gate body with parameter substitution
        for stmt in gate.body:
            if isinstance(stmt, ExprStmt) and isinstance(stmt.expr, CallExpr):
                # Substitute parameters in the call expression
                substituted_expr = self._substitute_params(stmt.expr, param_map)
                # Apply modifiers to the call if present
                if modifiers:
                    substituted_expr.modifiers = modifiers
                    substituted_expr.ctrl_count = ctrl_count
                # Recursively handle calls in gate body
                self.visit_call_expr(substituted_expr)
    
    def _handle_measure_all(self, args: List[Expr]):
        """Handle MeasureAll(q, c) stdlib function"""
        if len(args) != 2:
            return
        q_reg = self._expr_to_qasm(args[0])
        c_reg = self._expr_to_qasm(args[1])
        # Extract register names (simplified - assumes q[0] format)
        q_name = q_reg.split("[")[0] if "[" in q_reg else q_reg
        c_name = c_reg.split("[")[0] if "[" in c_reg else c_reg
        # Get register sizes
        q_size = self.registers.get(q_name, (None, 1))[1] if q_name in self.registers else 1
        c_size = self.registers.get(c_name, (None, 1))[1] if c_name in self.registers else 1
        size = min(q_size, c_size)
        # Generate individual measure statements
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
