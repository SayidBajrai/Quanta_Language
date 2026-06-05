"""
Tests for N-dimensional tensor types, shape validation, and slicing.
"""

import pytest

from quanta.lexer.lexer import Lexer
from quanta.parser.parser import Parser
from quanta.sema.transform import ASTTransformer
from quanta.sema.validation import SemanticAnalyzer
from quanta.runtime.frontend_sim import get_prints
from quanta.compiler import Compiler
from quanta.errors import QuantaSemanticError
from quanta.ast.nodes import SliceFull, VarDecl
from quanta.types.tensor import TensorType


def _parse_decl(source: str):
    lexer = Lexer()
    parser = Parser()
    ast = parser.parse(lexer.tokenize(source))
    return ast.statements[0]


def test_parse_tensor_type_matrix():
    decl = _parse_decl("float[3][4] m;\n")
    assert isinstance(decl, VarDecl)
    assert decl.tensor_type == TensorType("float", (3, 4))
    assert decl.tensor_type.format() == "float[3][4]"


def test_parse_dynamic_tensor_type():
    decl = _parse_decl("int[][] m;\n")
    assert decl.tensor_type.dimensions == (None, None)


def test_parse_qbit_grid():
    decl = _parse_decl("qbit[2][2] q;\n")
    assert decl.shape == [2, 2]
    assert decl.size == 4


def test_parse_slice_full_token():
    lexer = Lexer()
    parser = Parser()
    ast = parser.parse(lexer.tokenize("float[2][3][4] A\nPrint(0);\n"))
    decl = ast.statements[0]
    assert decl.tensor_type.rank == 3


def test_tensor_default_allocation_and_element_access():
    source = """
float[2][2] m
print(m[0][0])
print(m[1][1])
"""
    assert get_prints(source) == "0\n0"


def test_tensor_literal_initialization():
    source = """
float[2][2] m = [[1.0, 2.0], [3.0, 4.0]]
print(m[0][1])
print(m[1][0])
"""
    assert get_prints(source) == "2.0\n3.0"


def test_tensor_elementwise_add():
    source = """
float[2][2] A = [[1.0, 2.0], [3.0, 4.0]]
float[2][2] B = [[5.0, 6.0], [7.0, 8.0]]
float[2][2] C = A + B
print(C[0][0])
print(C[1][1])
"""
    assert get_prints(source) == "6.0\n12.0"


def test_dynamic_tensor_shape_lock():
    source = """
float[][] m
m = [[1, 2, 3], [4, 5, 6]]
print(m[1][2])
"""
    assert get_prints(source) == "6"


def test_invalid_ragged_tensor_rejected():
    with pytest.raises(QuantaSemanticError, match="Inconsistent|ragged|Shape"):
        get_prints(
            """
float[2][3] m = [[1,2], [3,4,5]]
print(m)
"""
        )


def test_reshape_builtin():
    source = """
float[2][2] m = [[1.0, 2.0], [3.0, 4.0]]
float[4] v = Reshape(m, 4)
print(v[3])
"""
    assert get_prints(source) == "4.0"


def test_qbit_grid_column_gates():
    source = """
qbit[2][2] q
H(q[:,0])
Print(f"{q:probabilities}")
"""
    out = get_prints(source)
    assert "25%" in out
    assert out.count("25%") == 4


def test_qbit_grid_row_gate():
    source = """
qbit[2][2] q
X(q[1,:])
print(0)
"""
    assert get_prints(source) == "0"


def test_tensor_rank_three_allocation():
    source = """
float[2][3][4] A
print(A[0][0][0])
"""
    assert get_prints(source) == "0"


def test_tensor_compiles_to_qasm():
    qasm = Compiler().compile("qbit[2][2] q\nH(q[0,0])\n")
    assert "qubit[4]" in qasm
