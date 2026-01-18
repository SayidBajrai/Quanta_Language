"""
AST transformations for operator overloading and desugaring
"""

from typing import List, Optional, Union
from ..ast.nodes import (
    Program, Stmt, Expr,
    VarDecl, ConstDecl, LetDecl, QuantumDecl, FuncDecl, GateDecl, ClassDecl,
    ForStmt, IfStmt, ReturnStmt, ExprStmt,
    CallExpr, IndexExpr, BinaryExpr, UnaryExpr,
    VarExpr, LiteralExpr, ListExpr, GroupExpr, AssignExpr,
)
from ..ast.visitor import Visitor


class ASTTransformer(Visitor):
    """Transforms AST to desugar operator overloading and other syntactic sugar"""
    
    def __init__(self):
        self.symbols = {}  # Track symbol types
        self.temp_counter = 0
        self.new_statements = []
    
    def transform(self, ast: Program) -> Program:
        """Transform AST by desugaring operator overloading"""
        # First pass: collect symbol types
        for stmt in ast.statements:
            if isinstance(stmt, QuantumDecl):
                self.symbols[stmt.name] = f"{stmt.kind}[{stmt.size or 1}]"
            elif isinstance(stmt, VarDecl):
                if stmt.type_hint:
                    self.symbols[stmt.name] = stmt.type_hint
        
        # Second pass: transform statements
        transformed_statements = []
        for stmt in ast.statements:
            transformed = self._transform_statement(stmt)
            if isinstance(transformed, list):
                transformed_statements.extend(transformed)
            elif transformed:
                transformed_statements.append(transformed)
        
        return Program(transformed_statements)
    
    def _transform_statement(self, stmt: Stmt) -> Union[Stmt, List[Stmt]]:
        """Transform a statement"""
        if isinstance(stmt, VarDecl):
            # Transform assignment if it's a qint operation
            if stmt.value and isinstance(stmt.value, BinaryExpr):
                if stmt.value.op in ["+", "*", "-", "/", "%"]:
                    return self._transform_qint_assignment(stmt)
            return stmt
        elif isinstance(stmt, QuantumDecl):
            # Handle qint initialization with operator overloading
            if stmt.value and isinstance(stmt.value, BinaryExpr):
                if stmt.value.op in ["+", "*", "-", "/", "%"]:
                    return self._transform_qint_quantum_decl(stmt)
            # Handle other initialization values
            if stmt.value:
                transformed = self._transform_expression(stmt.value)
                if transformed != stmt.value:
                    stmt.value = transformed
            return stmt
        elif isinstance(stmt, ExprStmt):
            transformed = self._transform_expression(stmt.expr)
            if transformed != stmt.expr:
                stmt.expr = transformed
            return stmt
        elif isinstance(stmt, ForStmt):
            for body_stmt in stmt.body:
                transformed = self._transform_statement(body_stmt)
                if isinstance(transformed, list):
                    # Replace with multiple statements
                    idx = stmt.body.index(body_stmt)
                    stmt.body[idx:idx+1] = transformed
            return stmt
        elif isinstance(stmt, IfStmt):
            for then_stmt in stmt.then_body:
                transformed = self._transform_statement(then_stmt)
                if isinstance(transformed, list):
                    idx = stmt.then_body.index(then_stmt)
                    stmt.then_body[idx:idx+1] = transformed
            for else_stmt in stmt.else_body:
                transformed = self._transform_statement(else_stmt)
                if isinstance(transformed, list):
                    idx = stmt.else_body.index(else_stmt)
                    stmt.else_body[idx:idx+1] = transformed
            return stmt
        return stmt
    
    def _transform_expression(self, expr: Expr) -> Expr:
        """Transform an expression"""
        if isinstance(expr, BinaryExpr):
            return self._transform_binary_expr(expr)
        elif isinstance(expr, CallExpr):
            # Transform arguments recursively
            new_args = [self._transform_expression(arg) for arg in expr.args]
            if new_args != expr.args:
                expr.args = new_args
            return expr
        elif isinstance(expr, IndexExpr):
            expr.base = self._transform_expression(expr.base)
            expr.index = self._transform_expression(expr.index)
            return expr
        elif isinstance(expr, UnaryExpr):
            expr.right = self._transform_expression(expr.right)
            return expr
        elif isinstance(expr, GroupExpr):
            expr.expr = self._transform_expression(expr.expr)
            return expr
        return expr
    
    def _transform_binary_expr(self, expr: BinaryExpr) -> Expr:
        """Transform binary expression, handling operator overloading"""
        # Transform left and right recursively first
        left = self._transform_expression(expr.left)
        right = self._transform_expression(expr.right)
        
        # Check if this is a qint operation
        if expr.op in ["+", "*", "-", "/", "%"]:
            left_type = self._get_expression_type(left)
            right_type = self._get_expression_type(right)
            
            if left_type and left_type.startswith("qint") and right_type and right_type.startswith("qint"):
                # This is a qint operation - return a marker that will be handled by assignment
                # For now, return the binary expr but mark it for transformation
                return expr
        
        # For non-qint operations or other operators, return as-is
        expr.left = left
        expr.right = right
        return expr
    
    def _transform_qint_assignment(self, stmt: VarDecl) -> List[Stmt]:
        """Transform qint assignment like 'qint[3] z = x + y' into QAdd/QMult/QSub/QDiv/QMod calls"""
        if not isinstance(stmt.value, BinaryExpr):
            return [stmt]
        
        op = stmt.value.op
        if op not in ["+", "*", "-", "/", "%"]:
            return [stmt]
        
        # Get operands
        operands = self._collect_operands(stmt.value)
        
        # Determine operation name
        if op == "+":
            op_name = "QAdd"
        elif op == "*":
            op_name = "QMult"
        elif op == "-":
            op_name = "QSub"
        elif op == "/":
            # Division: QDiv(dividend, divisor, quotient, remainder)
            # For operator overloading, we only want the quotient
            # Create a temporary for remainder
            if len(operands) != 2:
                return [stmt]  # Only handle binary division for now
            
            temp_remainder = f"_remainder_{self.temp_counter}"
            self.temp_counter += 1
            
            # Get type hint for remainder (same as quotient)
            remainder_type = stmt.type_hint
            
            # Create QDiv call with temporary remainder
            dest = VarExpr(stmt.name)
            remainder_var = VarExpr(temp_remainder)
            args = operands + [dest, remainder_var]
            call = CallExpr(VarExpr("QDiv"), args)
            
            # Create declarations
            decl = VarDecl(stmt.name, stmt.type_hint, None)
            remainder_decl = VarDecl(temp_remainder, remainder_type, None)
            
            # Create expression statement with the call
            call_stmt = ExprStmt(call)
            
            return [decl, remainder_decl, call_stmt]
        elif op == "%":
            op_name = "QMod"
        else:
            return [stmt]
        
        # For +, *, -, %: standard variadic operations
        # Last argument is the destination (the variable being assigned)
        dest = VarExpr(stmt.name)
        args = operands + [dest]
        call = CallExpr(VarExpr(op_name), args)
        
        # Create declaration without initialization
        decl = VarDecl(stmt.name, stmt.type_hint, None)
        
        # Create expression statement with the call
        call_stmt = ExprStmt(call)
        
        return [decl, call_stmt]
    
    def _transform_qint_quantum_decl(self, stmt: QuantumDecl) -> List[Stmt]:
        """Transform qint declaration with binary expression like 'qint[3] c = a + b' into QAdd/QMult/QSub/QDiv/QMod calls"""
        if not isinstance(stmt.value, BinaryExpr):
            return [stmt]
        
        # Handle precedence: if we have (a + b) * c, we need to evaluate (a + b) first
        result = self._transform_with_precedence(stmt.value, stmt.name, stmt.kind, stmt.size)
        if result:
            return result
        
        op = stmt.value.op
        if op not in ["+", "*", "-", "/", "%"]:
            return [stmt]
        
        # Get operands
        operands = self._collect_operands(stmt.value)
        
        # Determine operation name
        if op == "+":
            op_name = "QAdd"
        elif op == "*":
            op_name = "QMult"
        elif op == "-":
            op_name = "QSub"
        elif op == "/":
            # Division: QDiv(dividend, divisor, quotient, remainder)
            # For operator overloading, we only want the quotient
            if len(operands) != 2:
                return [stmt]  # Only handle binary division for now
            
            temp_remainder = f"_remainder_{self.temp_counter}"
            self.temp_counter += 1
            
            # Create QDiv call with temporary remainder
            dest = VarExpr(stmt.name)
            remainder_var = VarExpr(temp_remainder)
            args = operands + [dest, remainder_var]
            call = CallExpr(VarExpr("QDiv"), args)
            
            # Create declarations
            decl = QuantumDecl(stmt.kind, stmt.size, stmt.name, None)
            remainder_decl = QuantumDecl(stmt.kind, stmt.size, temp_remainder, None)
            
            # Create expression statement with the call
            call_stmt = ExprStmt(call)
            
            return [decl, remainder_decl, call_stmt]
        elif op == "%":
            op_name = "QMod"
        else:
            return [stmt]
        
        # For +, *, -, %: standard variadic operations
        # Last argument is the destination (the variable being declared)
        dest = VarExpr(stmt.name)
        args = operands + [dest]
        call = CallExpr(VarExpr(op_name), args)
        
        # Create declaration without initialization
        decl = QuantumDecl(stmt.kind, stmt.size, stmt.name, None)
        
        # Create expression statement with the call
        call_stmt = ExprStmt(call)
        
        return [decl, call_stmt]
    
    def _transform_with_precedence(self, expr: BinaryExpr, dest_name: str, kind: str, size: Optional[int]) -> Optional[List[Stmt]]:
        """Handle precedence: if we have (a + b) * c, evaluate (a + b) first"""
        # Check if left side is a GroupExpr with a binary expression
        if isinstance(expr.left, GroupExpr) and isinstance(expr.left.expr, BinaryExpr):
            inner_expr = expr.left.expr
            if inner_expr.op in ["+", "*", "-", "/", "%"] and expr.op in ["+", "*", "-", "/", "%"] and inner_expr.op != expr.op:
                # We have (a + b) * c or (a * b) + c - need to handle precedence
                # Create temporary variable for inner expression
                temp_name = f"_temp_{self.temp_counter}"
                self.temp_counter += 1
                
                # Transform inner expression first
                if inner_expr.op == "+":
                    inner_op_name = "QAdd"
                elif inner_expr.op == "*":
                    inner_op_name = "QMult"
                elif inner_expr.op == "-":
                    inner_op_name = "QSub"
                elif inner_expr.op == "/":
                    inner_op_name = "QDiv"
                elif inner_expr.op == "%":
                    inner_op_name = "QMod"
                else:
                    return None
                
                inner_operands = self._collect_operands(inner_expr)
                inner_dest = VarExpr(temp_name)
                
                # Handle division specially (needs remainder)
                if inner_expr.op == "/" and len(inner_operands) == 2:
                    temp_remainder = f"_remainder_{self.temp_counter}"
                    self.temp_counter += 1
                    inner_remainder = VarExpr(temp_remainder)
                    inner_args = inner_operands + [inner_dest, inner_remainder]
                    inner_call = CallExpr(VarExpr(inner_op_name), inner_args)
                    temp_decl = QuantumDecl(kind, size, temp_name, None)
                    remainder_decl = QuantumDecl(kind, size, temp_remainder, None)
                    inner_call_stmt = ExprStmt(inner_call)
                else:
                    inner_args = inner_operands + [inner_dest]
                    inner_call = CallExpr(VarExpr(inner_op_name), inner_args)
                    temp_decl = QuantumDecl(kind, size, temp_name, None)
                    inner_call_stmt = ExprStmt(inner_call)
                    remainder_decl = None
                
                # Now transform outer expression with temp
                if expr.op == "+":
                    outer_op_name = "QAdd"
                elif expr.op == "*":
                    outer_op_name = "QMult"
                elif expr.op == "-":
                    outer_op_name = "QSub"
                elif expr.op == "/":
                    outer_op_name = "QDiv"
                elif expr.op == "%":
                    outer_op_name = "QMod"
                else:
                    return None
                
                # Handle division in outer expression
                if expr.op == "/":
                    temp_remainder2 = f"_remainder_{self.temp_counter}"
                    self.temp_counter += 1
                    outer_remainder = VarExpr(temp_remainder2)
                    outer_args = [VarExpr(temp_name), self._transform_expression(expr.right), VarExpr(dest_name), outer_remainder]
                    outer_call = CallExpr(VarExpr(outer_op_name), outer_args)
                    outer_call_stmt = ExprStmt(outer_call)
                    remainder_decl2 = QuantumDecl(kind, size, temp_remainder2, None)
                else:
                    outer_args = [VarExpr(temp_name), self._transform_expression(expr.right), VarExpr(dest_name)]
                    outer_call = CallExpr(VarExpr(outer_op_name), outer_args)
                    outer_call_stmt = ExprStmt(outer_call)
                    remainder_decl2 = None
                
                # Create final declaration
                final_decl = QuantumDecl(kind, size, dest_name, None)
                
                # Build result list
                result = [temp_decl]
                if remainder_decl:
                    result.append(remainder_decl)
                result.append(inner_call_stmt)
                result.append(final_decl)
                if remainder_decl2:
                    result.append(remainder_decl2)
                result.append(outer_call_stmt)
                
                return result
        
        return None
    
    def _collect_operands(self, expr: Expr) -> List[Expr]:
        """Collect all operands from a chained binary expression"""
        # Unwrap GroupExpr
        if isinstance(expr, GroupExpr):
            return self._collect_operands(expr.expr)
        
        if isinstance(expr, BinaryExpr) and expr.op in ["+", "*", "-", "/", "%"]:
            left_ops = self._collect_operands(expr.left)
            right_ops = self._collect_operands(expr.right)
            return left_ops + right_ops
        else:
            return [expr]
    
    def _get_expression_type(self, expr: Expr) -> Optional[str]:
        """Get the type of an expression"""
        if isinstance(expr, VarExpr):
            return self.symbols.get(expr.name)
        elif isinstance(expr, IndexExpr):
            if isinstance(expr.base, VarExpr):
                base_type = self.symbols.get(expr.base.name)
                if base_type and base_type.startswith("qint"):
                    return base_type
        return None
    
    # Visitor methods (required by Visitor interface but not used here)
    def visit_program(self, node: Program): pass
    def visit_var_decl(self, node: VarDecl): pass
    def visit_quantum_decl(self, node: QuantumDecl): pass
    def visit_func_decl(self, node: FuncDecl): pass
    def visit_gate_decl(self, node: GateDecl): pass
    def visit_class_decl(self, node: ClassDecl): pass
    def visit_for_stmt(self, node: ForStmt): pass
    def visit_if_stmt(self, node: IfStmt): pass
    def visit_return_stmt(self, node: ReturnStmt): pass
    def visit_expr_stmt(self, node: ExprStmt): pass
    def visit_call_expr(self, node: CallExpr): pass
    def visit_index_expr(self, node: IndexExpr): pass
    def visit_binary_expr(self, node: BinaryExpr): pass
    def visit_unary_expr(self, node: UnaryExpr): pass
    def visit_var_expr(self, node: VarExpr): pass
    def visit_literal_expr(self, node: LiteralExpr): pass
    def visit_list_expr(self, node: ListExpr): pass
    def visit_group_expr(self, node: GroupExpr): pass
    def visit_assign_expr(self, node: AssignExpr): pass
