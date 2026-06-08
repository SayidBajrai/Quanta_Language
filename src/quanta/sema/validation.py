"""
Semantic analyzer for Quanta
"""

from typing import Dict, Optional, List, Any
from ..ast.nodes import (
    Program, Stmt, Expr,
    VarDecl, ConstDecl, LetDecl, ClassicalNumericDecl, QuantumDecl, FuncDecl, GateDecl, ClassDecl,
    ForStmt, WhileStmt, IfStmt, ReturnStmt, ExprStmt,
    CallExpr, IndexExpr, SingleIndex, SliceIndex, SliceFull, BinaryExpr, UnaryExpr,
    VarExpr, LiteralExpr, FStringExpr, ListExpr, GroupExpr, AssignExpr,
)
from ..errors import QuantaSemanticError, QuantaTypeError
from ..types.tensor import TensorType, infer_shape, validate_shape
from .indexing import (
    expand_index_items,
    needs_index_expansion,
    get_register_size,
    get_register_shape,
    eval_const_int,
    effective_arg_count,
)
from .overload import FuncOverloadTable, infer_expr_type, resolve_func_overload
from .reserved_names import validate_qasm_identifier
from .typecheck import tensor_type_from_decl, tensor_type_from_quantum, eval_literal_list
from ..types.kinds import param_symbol_type, type_base


class Symbol:
    """Represents a symbol in the symbol table"""
    
    def __init__(self, name: str, symbol_type: str, value: Any = None):
        self.name = name
        self.type = symbol_type
        self.value = value


class SemanticAnalyzer:
    """Performs semantic analysis on AST"""
    
    def __init__(self):
        self.symbols: Dict[str, Symbol] = {}
        self.func_overloads = FuncOverloadTable()
        self.gates: Dict[str, GateDecl] = {}
        self.constants: Dict[str, ConstDecl] = {}
        self.tensor_shapes: Dict[str, tuple] = {}
        # Built-in constants
        import math
        self.builtin_constants = {
            "pi": math.pi,
            "e": math.e,
        }
        self.builtin_functions = {
            "reset",
            "int",
            "arccos",
            "acos",
            "sin",
            "cos",
            "len",
            "range",
            "assert",
            "error",
            "warn",
            "Print",
        }
    
    def analyze(self, ast: Program, keep_structure: bool = False):
        """Perform semantic analysis on program"""
        self.keep_structure = keep_structure
        # First pass: collect declarations
        for stmt in ast.statements:
            if isinstance(stmt, QuantumDecl):
                validate_qasm_identifier(stmt.name, "register name")
                tensor_type = tensor_type_from_quantum(stmt)
                self.symbols[stmt.name] = Symbol(stmt.name, tensor_type.format())
                if tensor_type.shape():
                    self.tensor_shapes[stmt.name] = tensor_type.shape()
            elif isinstance(stmt, FuncDecl):
                validate_qasm_identifier(stmt.name, "function name")
                for pspec in stmt.param_specs:
                    validate_qasm_identifier(pspec.name, "parameter name")
                self.func_overloads.register(stmt)
            elif isinstance(stmt, GateDecl):
                validate_qasm_identifier(stmt.name, "gate name")
                for param in stmt.params:
                    validate_qasm_identifier(param, "parameter name")
                self.gates[stmt.name] = stmt
            elif isinstance(stmt, ConstDecl):
                self.constants[stmt.name] = stmt
                self.symbols[stmt.name] = Symbol(stmt.name, "const", stmt.value)
            elif isinstance(stmt, LetDecl):
                self.symbols[stmt.name] = Symbol(stmt.name, "let", stmt.value)
            elif isinstance(stmt, ClassicalNumericDecl):
                if stmt.tensor_type:
                    self.symbols[stmt.name] = Symbol(stmt.name, stmt.tensor_type.format())
            elif isinstance(stmt, VarDecl):
                tensor_type = tensor_type_from_decl(stmt)
                self.symbols[stmt.name] = Symbol(stmt.name, tensor_type.format(), stmt.value)
                if tensor_type.shape():
                    self.tensor_shapes[stmt.name] = tensor_type.shape()
        
        # Second pass: validate statements
        for stmt in ast.statements:
            self._validate_statement(stmt)
    
    def _validate_statement(self, stmt: Stmt):
        """Validate a statement"""
        if isinstance(stmt, VarDecl):
            if stmt.value:
                self._validate_expression(stmt.value)
                self._validate_tensor_initializer(stmt)
        elif isinstance(stmt, ConstDecl):
            self._validate_expression(stmt.value)
        elif isinstance(stmt, LetDecl):
            self._validate_expression(stmt.value)
        elif isinstance(stmt, ClassicalNumericDecl):
            if stmt.value:
                self._validate_expression(stmt.value)
        elif isinstance(stmt, QuantumDecl):
            if stmt.kind in ("quint", "qint") and stmt.shape and any(d is None for d in stmt.shape):
                if stmt.value is None:
                    raise QuantaSemanticError(
                        f"{stmt.kind}() requires an initializer for size inference or an explicit bit width"
                    )
        elif isinstance(stmt, FuncDecl):
            self._validate_function(stmt)
        elif isinstance(stmt, GateDecl):
            self._validate_gate(stmt)
        elif isinstance(stmt, ForStmt):
            self._validate_for(stmt)
        elif isinstance(stmt, WhileStmt):
            self._validate_while(stmt)
        elif isinstance(stmt, IfStmt):
            self._validate_if(stmt)
        elif isinstance(stmt, ExprStmt):
            self._validate_expression(stmt.expr)
        elif isinstance(stmt, ReturnStmt):
            if stmt.value:
                self._validate_expression(stmt.value)
    
    def _validate_function(self, func: FuncDecl):
        """Validate function declaration"""
        saved_symbols = {}
        for pspec in func.param_specs:
            saved_symbols[pspec.name] = self.symbols.get(pspec.name)
            sym_type = param_symbol_type(pspec.kind)
            if pspec.shape and sym_type == "qbit" and pspec.kind == "qvar":
                if any(d is not None for d in pspec.shape):
                    dims = "".join(f"[{d}]" if d is not None else "[]" for d in pspec.shape)
                    sym_type = f"qbit{dims}"
            self.symbols[pspec.name] = Symbol(pspec.name, sym_type)

        has_return = any(isinstance(s, ReturnStmt) for s in func.body)
        if self.keep_structure and func.return_type and func.return_type != "var" and not has_return:
            raise QuantaSemanticError(
                f"Function '{func.name}' with return type '{func.return_type}' must contain a return statement"
            )

        for stmt in func.body:
            if isinstance(stmt, QuantumDecl):
                validate_qasm_identifier(stmt.name, "register name")
                self.symbols[stmt.name] = Symbol(stmt.name, stmt.kind)
            self._validate_statement(stmt)

        for stmt in func.body:
            if isinstance(stmt, QuantumDecl) and stmt.name not in saved_symbols:
                del self.symbols[stmt.name]

        for pspec in func.param_specs:
            if saved_symbols[pspec.name] is None:
                del self.symbols[pspec.name]
            else:
                self.symbols[pspec.name] = saved_symbols[pspec.name]
    
    def _validate_gate(self, gate: GateDecl):
        """Validate gate declaration"""
        # Add gate parameters to symbol table (as qbit parameters)
        saved_symbols = {}
        for param in gate.params:
            # Gate parameters are qbit/bit references
            saved_symbols[param] = self.symbols.get(param)
            self.symbols[param] = Symbol(param, "qbit")
        
        # Validate gate body with parameters in scope
        for stmt in gate.body:
            self._validate_statement(stmt)
        
        # Restore symbol table
        for param in gate.params:
            if saved_symbols[param] is None:
                del self.symbols[param]
            else:
                self.symbols[param] = saved_symbols[param]
    
    def _validate_for(self, stmt: ForStmt):
        """Validate for loop"""
        # Iterable must be compile-time evaluable
        self._validate_expression(stmt.iterable)
        
        # Add iterator variable to symbol table
        saved_iterator = self.symbols.get(stmt.iterator)
        self.symbols[stmt.iterator] = Symbol(stmt.iterator, "int")
        
        # Validate loop body with iterator in scope
        for body_stmt in stmt.body:
            self._validate_statement(body_stmt)
        
        # Restore symbol table
        if saved_iterator is None:
            del self.symbols[stmt.iterator]
        else:
            self.symbols[stmt.iterator] = saved_iterator
    
    def _validate_if(self, stmt: IfStmt):
        """Validate if statement"""
        self._validate_expression(stmt.condition)
        for then_stmt in stmt.then_body:
            self._validate_statement(then_stmt)
        for else_stmt in stmt.else_body:
            self._validate_statement(else_stmt)

    def _validate_while(self, stmt: WhileStmt):
        """Validate while loop"""
        if not self.keep_structure:
            raise QuantaSemanticError(
                "while loops require compile(..., keep_structure=True)"
            )
        self._validate_expression(stmt.condition)
        for body_stmt in stmt.body:
            self._validate_statement(body_stmt)
    
    def _validate_expression(self, expr: Expr):
        """Validate an expression"""
        if isinstance(expr, CallExpr):
            self._validate_call(expr)
        elif isinstance(expr, IndexExpr):
            self._validate_index(expr)
        elif isinstance(expr, BinaryExpr):
            self._validate_expression(expr.left)
            self._validate_expression(expr.right)
        elif isinstance(expr, UnaryExpr):
            self._validate_expression(expr.right)
        elif isinstance(expr, VarExpr):
            if (expr.name not in self.symbols and 
                not self.func_overloads.has(expr.name) and 
                expr.name not in self.gates and
                expr.name not in self.builtin_constants and
                expr.name not in self.builtin_functions):
                raise QuantaSemanticError(f"Undefined variable or function: {expr.name}")
        elif isinstance(expr, FStringExpr):
            for part in expr.parts:
                if part.expr is not None:
                    self._validate_expression(part.expr)
        elif isinstance(expr, ListExpr):
            for elem in expr.elements:
                self._validate_expression(elem)
        elif isinstance(expr, GroupExpr):
            self._validate_expression(expr.expr)
        elif isinstance(expr, AssignExpr):
            self._validate_expression(expr.value)
            if (
                isinstance(expr.value, CallExpr)
                and isinstance(expr.value.callee, VarExpr)
                and self.func_overloads.has(expr.value.callee.name)
                and not self.keep_structure
            ):
                raise QuantaSemanticError(
                    "Assignment from function calls requires compile(..., keep_structure=True)"
                )
    
    def _validate_call(self, expr: CallExpr):
        """Validate function/gate call"""
        # Validate modifiers
        if "ctrl" in expr.modifiers or "inv" in expr.modifiers:
            if isinstance(expr.callee, VarExpr):
                name = expr.callee.name
                if name == "Measure":
                    raise QuantaSemanticError("Modifiers (ctrl/inv) are not allowed on Measure")
        
        if isinstance(expr.callee, VarExpr):
            name = expr.callee.name
            
            # Validate quantum arithmetic operations
            if name == "QAdd":
                self._validate_qadd(expr)
                return
            elif name == "QFTAdd":
                self._validate_qftadd(expr)
                return
            elif name == "QTreeAdd":
                self._validate_qtreeadd(expr)
                return
            elif name == "QMult":
                self._validate_qmult(expr)
                return
            elif name == "QExpEncMult":
                self._validate_qexpencmult(expr)
                return
            elif name == "QTreeMult":
                self._validate_qtreemult(expr)
                return
            elif name == "QSub":
                self._validate_qsub(expr)
                return
            elif name == "QDiv":
                self._validate_qdiv(expr)
                return
            elif name == "QMod":
                self._validate_qmod(expr)
                return
            elif name == "Compare":
                self._validate_compare(expr)
                return
            elif name == "Grover":
                self._validate_grover(expr)
                return
            elif name == "Bell":
                self._validate_bell(expr)
                return
            elif name == "GHZ":
                self._validate_ghz(expr)
                return
            elif name == "WState":
                self._validate_wstate(expr)
                return
            elif name == "SwapGate":
                self._validate_swapgate(expr)
                return
            elif name == "QFT":
                self._validate_qft(expr)
                return
            elif name == "InverseQFT":
                self._validate_inverse_qft(expr)
                return
            
            if name in self.gates:
                # Gate call - validate arguments match (including fancy index expansion)
                gate = self.gates[name]
                registers = self._register_sizes()
                arg_count = sum(effective_arg_count(a, registers) for a in expr.args)
                if arg_count != len(gate.params):
                    raise QuantaSemanticError(
                        f"Gate '{name}' expects {len(gate.params)} arguments, "
                        f"got {arg_count}"
                    )
                for arg in expr.args:
                    self._validate_expression(arg)
            elif self.func_overloads.has(name):
                funcs = self.func_overloads.overloads(name)
                arg_types = [infer_expr_type(arg, self.symbols) for arg in expr.args]
                func = resolve_func_overload(name, funcs, arg_types)
                expr.resolved_func = func
                registers = self._register_sizes()
                arg_count = sum(effective_arg_count(a, registers) for a in expr.args)
                if arg_count != len(func.params):
                    raise QuantaSemanticError(
                        f"Function '{name}' expects {len(func.params)} arguments, "
                        f"got {arg_count}"
                    )
                for arg in expr.args:
                    self._validate_expression(arg)
            elif name == "reset" and len(expr.args) == 1:
                self._validate_expression(expr.args[0])
            elif name == "int" and len(expr.args) == 1:
                self._validate_expression(expr.args[0])
            elif name in ("arccos", "acos", "sin", "cos"):
                for arg in expr.args:
                    self._validate_expression(arg)
            elif name == "Measure" and len(expr.args) == 2:
                registers = self._register_sizes()
                q_count = effective_arg_count(expr.args[0], registers)
                c_count = effective_arg_count(expr.args[1], registers)
                if q_count != c_count:
                    raise QuantaSemanticError(
                        f"Measure index lists must have the same length "
                        f"(got {q_count} qbit indices and {c_count} classical indices)"
                    )
                for arg in expr.args:
                    self._validate_expression(arg)
            elif name == "Fidelity":
                self._validate_fidelity(expr)
            elif name == "Reshape":
                self._validate_reshape(expr)
            elif name in (
                "DotProduct",
                "CrossProduct",
                "ElementwiseProduct",
                "TensorProduct",
                "Shape",
            ):
                self._validate_tensor_algebra(name, expr)
            elif name == "print":
                raise QuantaSemanticError(
                    "Use 'Print()' (capital P); lowercase 'print()' is not valid Quanta syntax"
                )
            elif name == "Print":
                for arg in expr.args:
                    self._validate_expression(arg)
            else:
                # Assume it's a built-in gate or stdlib function - validate arguments
                for arg in expr.args:
                    self._validate_expression(arg)
        else:
            # Complex callee - validate recursively
            self._validate_expression(expr.callee)
            for arg in expr.args:
                self._validate_expression(arg)
    
    def _is_qbit_register_expr(self, expr: Expr) -> bool:
        if isinstance(expr, VarExpr):
            sym = self.symbols.get(expr.name)
            if sym and (
                type_base(sym.type) == "qvar"
                or sym.type.startswith(("qbit", "qint", "quint", "qdec", "qudec", "qfloat", "qreal"))
            ):
                return True
        if isinstance(expr, IndexExpr) and isinstance(expr.base, VarExpr):
            sym = self.symbols.get(expr.base.name)
            if sym and (
                type_base(sym.type) == "qvar"
                or sym.type.startswith(("qbit", "qint", "quint", "qdec", "qudec", "qfloat", "qreal"))
            ):
                return True
        return False

    def _qbit_register_size(self, expr: Expr, registers: Dict[str, tuple]) -> Optional[int]:
        if isinstance(expr, VarExpr) and expr.name in registers:
            return registers[expr.name][1]
        if isinstance(expr, IndexExpr) and isinstance(expr.base, VarExpr):
            if expr.base.name in registers:
                return 1
        return None

    def _validate_fidelity(self, expr: CallExpr):
        if len(expr.args) != 2:
            raise QuantaSemanticError("Fidelity requires exactly 2 arguments")
        registers = self._register_sizes()
        sizes = []
        for arg in expr.args:
            self._validate_expression(arg)
            if not self._is_qbit_register_expr(arg):
                raise QuantaSemanticError(
                    "Fidelity arguments must be qbit or qint registers"
                )
            sizes.append(self._qbit_register_size(arg, registers))
        if sizes[0] is not None and sizes[1] is not None and sizes[0] != sizes[1]:
            raise QuantaSemanticError(
                f"Fidelity requires registers of the same size "
                f"(got {sizes[0]} and {sizes[1]} qubits)"
            )

    def _validate_tensor_initializer(self, decl: VarDecl):
        tensor_type = tensor_type_from_decl(decl)
        if tensor_type.is_scalar or decl.value is None:
            return
        if not isinstance(decl.value, ListExpr):
            return
        try:
            literal = eval_literal_list(decl.value)
            if tensor_type.is_dynamic:
                shape = tuple(validate_shape(literal, tensor_type.dimensions, decl.name))
                self.tensor_shapes[decl.name] = shape
            else:
                validate_shape(literal, tensor_type.dimensions, decl.name)
        except QuantaSemanticError:
            raise
        except Exception:
            return

    def _validate_reshape(self, expr: CallExpr):
        if len(expr.args) < 2:
            raise QuantaSemanticError("Reshape requires a tensor and at least one dimension")
        for arg in expr.args:
            self._validate_expression(arg)

    def _validate_tensor_algebra(self, name: str, expr: CallExpr):
        arity = {
            "DotProduct": 2,
            "CrossProduct": 2,
            "ElementwiseProduct": 2,
            "TensorProduct": 2,
            "Shape": 1,
        }
        expected = arity[name]
        if len(expr.args) != expected:
            raise QuantaSemanticError(f"{name} requires exactly {expected} argument(s)")
        for arg in expr.args:
            self._validate_expression(arg)

    def _validate_index(self, expr: IndexExpr):
        """Validate index expression"""
        self._validate_expression(expr.base)
        if isinstance(expr.base, IndexExpr):
            for item in expr.items:
                if isinstance(item, SingleIndex):
                    self._validate_expression(item.expr)
            return
        for item in expr.items:
            if isinstance(item, SingleIndex):
                self._validate_expression(item.expr)
            elif isinstance(item, SliceIndex):
                if item.start:
                    self._validate_expression(item.start)
                if item.stop:
                    self._validate_expression(item.stop)
                if item.step:
                    self._validate_expression(item.step)
            elif isinstance(item, SliceFull):
                pass

        registers = self._register_sizes()
        reg_name, reg_size = get_register_size(expr, registers)
        shape = get_register_shape(expr, registers)

        if reg_name is None:
            base = expr.base
            while isinstance(base, IndexExpr):
                base = base.base
            if isinstance(base, VarExpr) and base.name in self.tensor_shapes:
                shape = list(self.tensor_shapes[base.name])
                depth = 0
                walker = expr
                while isinstance(walker.base, IndexExpr):
                    depth += 1
                    walker = walker.base
                remaining = shape[depth:]
                if isinstance(expr.base, IndexExpr):
                    if not expr.is_simple():
                        raise QuantaSemanticError(
                            f"Chained tensor indexing supports only scalar indices"
                        )
                else:
                    if len(expr.items) > len(remaining):
                        raise QuantaSemanticError(
                            f"Tensor index dimension mismatch for '{base.name}': "
                            f"expected at most {len(remaining)} indices, got {len(expr.items)}"
                        )
                    if len(expr.items) < len(remaining) and not all(
                        isinstance(i, SingleIndex) for i in expr.items
                    ):
                        raise QuantaSemanticError(
                            f"Partial tensor indexing for '{base.name}' must use scalar indices"
                        )

        if needs_index_expansion(expr, registers):
            expand_index_items(expr.items, reg_size, reg_name or "", shape=shape)
        elif expr.is_simple() and isinstance(expr.items[0], SingleIndex):
            idx_expr = expr.items[0].expr
            if reg_name and reg_size is not None:
                try:
                    idx = eval_const_int(idx_expr)
                    if idx < 0 or idx >= reg_size:
                        raise QuantaSemanticError(
                            f"Index {idx} out of range for {reg_name}"
                        )
                except QuantaTypeError:
                    pass  # dynamic index (e.g. for-loop variable) allowed for simple access
            elif isinstance(idx_expr, LiteralExpr):
                try:
                    int(idx_expr.value)
                except (ValueError, TypeError):
                    raise QuantaTypeError("Quantum register index must be a compile-time integer")

    def _register_sizes(self) -> Dict[str, tuple]:
        """Build register name -> (kind, flat_size, shape) from symbol table."""
        sizes: Dict[str, tuple] = {}
        for name, sym in self.symbols.items():
            if sym.type and ("qbit" in sym.type or "bit" in sym.type or "qint" in sym.type or "bint" in sym.type):
                tensor_type = TensorType.parse_legacy(sym.type)
                shape = [d if d is not None else 1 for d in tensor_type.dimensions] or [1]
                flat = tensor_type.total_size() or 1
                sizes[name] = (tensor_type.base, flat, shape)
        return sizes
    
    def _expr_qint_width(self, expr: Expr) -> Optional[int]:
        """Return bit width for a qint register expression, if known."""
        if isinstance(expr, VarExpr):
            sym = self.symbols.get(expr.name)
            if sym:
                tensor_type = TensorType.parse_legacy(sym.type)
                if tensor_type.base in ("qint", "quint"):
                    return tensor_type.total_size()
        elif isinstance(expr, IndexExpr) and isinstance(expr.base, VarExpr):
            return self._expr_qint_width(expr.base)
        return None

    def _collect_qint_widths(self, expr: CallExpr) -> List[int]:
        widths: List[int] = []
        for arg in expr.args:
            self._validate_expression(arg)
            width = self._expr_qint_width(arg)
            if width is not None:
                widths.append(width)
        return widths

    def _validate_qint_matching_widths(self, expr: CallExpr, op_name: str) -> None:
        widths = self._collect_qint_widths(expr)
        if len(widths) < 2:
            return
        dest_width = widths[-1]
        input_widths = widths[:-1]
        if input_widths and len(set(input_widths)) > 1:
            raise QuantaSemanticError(
                f"{op_name}: all input qint registers must have the same bit width"
            )
        if input_widths and dest_width != input_widths[0]:
            raise QuantaSemanticError(
                f"{op_name}: destination width ({dest_width}) must match input width ({input_widths[0]})"
            )

    def _validate_qadd(self, expr: CallExpr):
        """Validate QAdd operation"""
        if len(expr.args) < 2:
            raise QuantaSemanticError("QAdd requires at least 2 arguments (inputs and destination)")
        self._validate_qint_matching_widths(expr, "QAdd")

    def _validate_qmult(self, expr: CallExpr):
        """Validate QMult operation"""
        if len(expr.args) < 3:
            raise QuantaSemanticError("QMult requires at least 3 arguments (inputs and destination)")
        widths = self._collect_qint_widths(expr)
        if len(widths) < 2:
            return
        dest_width = widths[-1]
        input_widths = widths[:-1]
        if input_widths and len(set(input_widths)) > 1:
            raise QuantaSemanticError(
                "QMult: all input qint registers must have the same bit width"
            )
        if input_widths and dest_width < input_widths[0]:
            raise QuantaSemanticError(
                f"QMult: destination width ({dest_width}) must be at least input width ({input_widths[0]})"
            )
    
    def _validate_compare(self, expr: CallExpr):
        """Validate Compare operation"""
        if len(expr.args) != 3:
            raise QuantaSemanticError("Compare requires exactly 3 arguments: Compare(a, b, flag)")
        
        for arg in expr.args:
            self._validate_expression(arg)
        # TODO: Check that flag is qint[1] or qbit
    
    def _validate_qftadd(self, expr: CallExpr):
        """Validate QFTAdd operation"""
        if len(expr.args) < 2:
            raise QuantaSemanticError("QFTAdd requires at least 2 arguments (inputs and destination)")
        
        # All arguments should be qint types
        for arg in expr.args:
            self._validate_expression(arg)
            # TODO: Check that all args are qint types with matching widths
    
    def _validate_qtreeadd(self, expr: CallExpr):
        """Validate QTreeAdd operation"""
        if len(expr.args) < 2:
            raise QuantaSemanticError("QTreeAdd requires at least 2 arguments (inputs and destination)")
        
        # All arguments should be qint types
        for arg in expr.args:
            self._validate_expression(arg)
            # TODO: Check that all args are qint types with matching widths
    
    def _validate_qexpencmult(self, expr: CallExpr):
        """Validate QExpEncMult operation"""
        if len(expr.args) < 3:
            raise QuantaSemanticError("QExpEncMult requires at least 3 arguments (inputs and destination)")
        
        # All arguments should be qint types
        for arg in expr.args:
            self._validate_expression(arg)
            # TODO: Check that output width >= sum of input widths
    
    def _validate_qtreemult(self, expr: CallExpr):
        """Validate QTreeMult operation"""
        if len(expr.args) < 3:
            raise QuantaSemanticError("QTreeMult requires at least 3 arguments (inputs and destination)")
        
        # All arguments should be qint types
        for arg in expr.args:
            self._validate_expression(arg)
            # TODO: Check that output width >= sum of input widths
    
    def _validate_qsub(self, expr: CallExpr):
        """Validate QSub operation"""
        if len(expr.args) < 2:
            raise QuantaSemanticError("QSub requires at least 2 arguments (inputs and destination)")
        
        # All arguments should be qint types
        for arg in expr.args:
            self._validate_expression(arg)
            # TODO: Check that all args are qint types with matching widths
    
    def _validate_qdiv(self, expr: CallExpr):
        """Validate QDiv operation"""
        if len(expr.args) != 4:
            raise QuantaSemanticError("QDiv requires exactly 4 arguments: QDiv(dividend, divisor, quotient, remainder)")
        
        # All arguments should be qint types
        for arg in expr.args:
            self._validate_expression(arg)
        # TODO: Check that divisor is not zero (compile-time check if possible)
        # TODO: Check that quotient and remainder have same width as dividend
    
    def _validate_qmod(self, expr: CallExpr):
        """Validate QMod operation"""
        if len(expr.args) < 3:
            raise QuantaSemanticError("QMod requires at least 3 arguments: QMod(a, b, result)")
        
        # All arguments should be qint types
        for arg in expr.args:
            self._validate_expression(arg)
            # TODO: Check that all args are qint types with matching widths
    
    def _validate_grover(self, expr: CallExpr):
        """Validate Grover operation"""
        if len(expr.args) != 2:
            raise QuantaSemanticError("Grover requires exactly 2 arguments: Grover(a, target)")
        
        for arg in expr.args:
            self._validate_expression(arg)
        # TODO: Check that target is classical (int or bint)

    def _validate_bell(self, expr: CallExpr):
        """Validate Bell gate operation (2 qbits: explicit, or whole register/slice)"""
        if len(expr.args) < 1 or len(expr.args) > 2:
            raise QuantaSemanticError("Bell requires 1 or 2 arguments: Bell(q0, q1) or Bell(q[0:2])")
        for arg in expr.args:
            self._validate_expression(arg)

    def _validate_ghz(self, expr: CallExpr):
        """Validate GHZ gate operation (whole register, slice, or explicit qbits)"""
        if len(expr.args) < 1:
            raise QuantaSemanticError("GHZ requires at least 1 argument: GHZ(q) or GHZ(q[0], q[1], ...)")
        for arg in expr.args:
            self._validate_expression(arg)

    def _validate_wstate(self, expr: CallExpr):
        """Validate WState gate operation (3 qbits: explicit or slice)"""
        if len(expr.args) < 1 or len(expr.args) > 3:
            raise QuantaSemanticError("WState requires 1 or 3 arguments: WState(q[0:3]) or WState(q0, q1, q2)")
        for arg in expr.args:
            self._validate_expression(arg)

    def _validate_swapgate(self, expr: CallExpr):
        """Validate SwapGate operation"""
        if len(expr.args) != 2:
            raise QuantaSemanticError("SwapGate requires exactly 2 arguments: SwapGate(a, b)")
        for arg in expr.args:
            self._validate_expression(arg)

    def _validate_qft(self, expr: CallExpr):
        """Validate QFT gate operation (whole register, slice, or explicit qbits)"""
        if len(expr.args) < 1:
            raise QuantaSemanticError("QFT requires at least 1 argument: QFT(q) or QFT(q[0], q[1], ...)")
        for arg in expr.args:
            self._validate_expression(arg)

    def _validate_inverse_qft(self, expr: CallExpr):
        """Validate InverseQFT gate operation (whole register, slice, or explicit qbits)"""
        if len(expr.args) < 1:
            raise QuantaSemanticError("InverseQFT requires at least 1 argument: InverseQFT(q) or InverseQFT(q[0], ...)")
        for arg in expr.args:
            self._validate_expression(arg)