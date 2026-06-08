"""
Tests for tensor algebra: DotProduct, CrossProduct, ElementwiseProduct, TensorProduct.
"""

import pytest

from quanta.errors import QuantaSemanticError
from quanta.runtime.frontend_sim import get_prints
from quanta.runtime.tensor_algebra import (
    cross_product,
    dot_product,
    elementwise_product,
    tensor_product,
    tensor_shape,
    tensor_elementwise_binop,
)


def test_dot_product_unit():
    assert dot_product([1.0, 2.0, 3.0], [4.0, 5.0, 6.0]) == 32.0


def test_dot_product_operator():
    source = """
float[3] a = [1.0, 2.0, 3.0]
float[3] b = [4.0, 5.0, 6.0]
float dot_ab = a . b
Print(dot_ab)
"""
    assert get_prints(source) == "32.0"


def test_cross_product_unit():
    result = cross_product([1.0, 2.0, 3.0], [4.0, 5.0, 6.0])
    assert result == [-3.0, 6.0, -3.0]


def test_cross_product_requires_3d():
    with pytest.raises(QuantaSemanticError, match="3D"):
        cross_product([1.0, 2.0], [3.0, 4.0])


def test_elementwise_product_matrix():
    a = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    b = [[9, 8, 7], [6, 5, 4], [3, 2, 1]]
    result = elementwise_product(a, b)
    assert result[0][0] == 9
    assert result[2][2] == 9


def test_elementwise_shape_mismatch():
    with pytest.raises(QuantaSemanticError, match="Shape mismatch"):
        elementwise_product([1, 2, 3], [1, 2])


def test_tensor_product_matrices():
    a = [[1, 2], [3, 4]]
    b = [[0, 5], [6, 7]]
    result = tensor_product(a, b)
    assert tensor_shape(result) == (4, 4)
    assert result[0][0] == 0
    assert result[0][1] == 5
    assert result[0][2] == 0
    assert result[0][3] == 10


def test_tensor_product_vectors():
    result = tensor_product([1, 2], [3, 4])
    assert result == [3, 4, 6, 8]


def test_tensor_product_scalar():
    assert tensor_product(2, [1, 3]) == [2, 6]
    assert tensor_product([1, 3], 2) == [2, 6]


def test_shape_builtin():
    source = """
float[3][3] A = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
float[3][3] B = [[9, 8, 7], [6, 5, 4], [3, 2, 1]]
float[9][9] kron = TensorProduct(A, B)
Print(Shape(kron))
"""
    assert get_prints(source) == "(9, 9)"


def test_bool_elementwise_multiply():
    assert tensor_elementwise_binop(False, False, "*") is False
    assert tensor_elementwise_binop(True, True, "*") is True
    assert tensor_elementwise_binop(True, False, "*") is False
    assert tensor_elementwise_binop([True, False], [False, True], "*") == [False, False]


def test_neural_layer_dot_products():
    source = """
float[3][3] W = [[0.2, 0.4, 0.6], [0.1, 0.3, 0.5], [0.7, 0.8, 0.9]]
float[3] x = [1, 0, 1]
float y0 = DotProduct(W[0,:], x)
float y1 = DotProduct(W[1,:], x)
float y2 = DotProduct(W[2,:], x)
Print(y0)
Print(y1)
Print(y2)
"""
    assert get_prints(source) == "0.8\n0.6\n1.6"


def test_cross_product_operator():
    source = """
float[3] a = [1.0, 2.0, 3.0]
float[3] b = [4.0, 5.0, 6.0]
float[3] c = a * b
Print(c)
"""
    assert get_prints(source) == "[-3.0, 6.0, -3.0]"


def test_hadamard_operator():
    source = """
float[2][2] A = [[1, 2], [3, 4]]
float[2][2] B = [[5, 6], [7, 8]]
float[2][2] C = A ⊙ B
Print(C)
"""
    assert get_prints(source) == "[[5, 12], [21, 32]]"


def test_kron_operator():
    source = """
float[2] a = [1, 2]
float[2] b = [3, 4]
Print(a ⊗ b)
"""
    assert get_prints(source) == "[3, 4, 6, 8]"


def test_star_on_matrices_requires_hadamard():
    source = """
float[2][2] A = [[1, 2], [3, 4]]
float[2][2] B = [[0, 5], [6, 7]]
var C = A * B
Print(C)
"""
    with pytest.raises(QuantaSemanticError, match="⊙"):
        get_prints(source)


def test_dot_product_rank_error():
    with pytest.raises(QuantaSemanticError, match="DotProduct"):
        dot_product([[1, 2]], [1, 2])
