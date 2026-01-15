"""
Visitor pattern for AST traversal
"""

from abc import ABC, abstractmethod
from typing import Any
from .nodes import *


class Visitor(ABC):
    """Base visitor class"""
    
    @abstractmethod
    def visit_program(self, node: Program) -> Any:
        pass
    
    @abstractmethod
    def visit_var_decl(self, node: VarDecl) -> Any:
        pass
    
    @abstractmethod
    def visit_quantum_decl(self, node: QuantumDecl) -> Any:
        pass
    
    @abstractmethod
    def visit_func_decl(self, node: FuncDecl) -> Any:
        pass
    
    @abstractmethod
    def visit_class_decl(self, node: ClassDecl) -> Any:
        pass
    
    @abstractmethod
    def visit_for_stmt(self, node: ForStmt) -> Any:
        pass
    
    @abstractmethod
    def visit_if_stmt(self, node: IfStmt) -> Any:
        pass
    
    @abstractmethod
    def visit_return_stmt(self, node: ReturnStmt) -> Any:
        pass
    
    @abstractmethod
    def visit_expr_stmt(self, node: ExprStmt) -> Any:
        pass
    
    @abstractmethod
    def visit_call_expr(self, node: CallExpr) -> Any:
        pass
    
    @abstractmethod
    def visit_index_expr(self, node: IndexExpr) -> Any:
        pass
    
    @abstractmethod
    def visit_binary_expr(self, node: BinaryExpr) -> Any:
        pass
    
    @abstractmethod
    def visit_unary_expr(self, node: UnaryExpr) -> Any:
        pass
    
    @abstractmethod
    def visit_var_expr(self, node: VarExpr) -> Any:
        pass
    
    @abstractmethod
    def visit_literal_expr(self, node: LiteralExpr) -> Any:
        pass
    
    @abstractmethod
    def visit_list_expr(self, node: ListExpr) -> Any:
        pass
    
    @abstractmethod
    def visit_group_expr(self, node: GroupExpr) -> Any:
        pass
    
    @abstractmethod
    def visit_assign_expr(self, node: AssignExpr) -> Any:
        pass
