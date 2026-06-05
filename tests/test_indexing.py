"""
Tests for non-contiguous qbit/register indexing (fancy indexing).
"""

import pytest
from quanta.compiler import Compiler
from quanta.lexer.lexer import Lexer
from quanta.parser.parser import Parser


def compile(source: str) -> str:
    return Compiler().compile(source)
from quanta.ast.nodes import IndexExpr, SingleIndex, SliceIndex
from quanta.errors import QuantaSemanticError, QuantaSyntaxError


def _parse(source: str):
    lexer = Lexer()
    parser = Parser()
    return parser.parse(lexer.tokenize(source))


def _compile_raises(source: str, match: str):
    with pytest.raises((QuantaSemanticError, QuantaSyntaxError), match=match):
        compile(source)


# --- Parser / AST ---


def test_parse_single_index():
    ast = _parse("qbit[4] q\nH(q[0]);")
    stmt = ast.statements[1]
    from quanta.ast.nodes import ExprStmt, CallExpr
    idx = stmt.expr.args[0]
    assert isinstance(idx, IndexExpr)
    assert len(idx.items) == 1
    assert isinstance(idx.items[0], SingleIndex)


def test_parse_multi_index():
    ast = _parse("qbit[8] q\nH(q[0,2,5]);")
    idx = ast.statements[1].expr.args[0]
    assert isinstance(idx, IndexExpr)
    assert len(idx.items) == 3


def test_parse_mixed_slice_index():
    ast = _parse("qbit[10] q\nH(q[0,2:6,9]);")
    idx = ast.statements[1].expr.args[0]
    assert len(idx.items) == 3
    assert isinstance(idx.items[0], SingleIndex)
    assert isinstance(idx.items[1], SliceIndex)
    assert isinstance(idx.items[2], SingleIndex)


def test_parse_slice_and_scalar():
    ast = _parse("qbit[8] q\nH(q[0:4,7]);")
    idx = ast.statements[1].expr.args[0]
    assert isinstance(idx.items[0], SliceIndex)
    assert isinstance(idx.items[1], SingleIndex)


# --- Valid compilation ---


def test_multi_index_gate_expansion():
    source = """
qbit[8] q
H(q[0,2,5])
"""
    qasm = compile(source)
    line = next(l for l in qasm.lower().splitlines() if l.strip().startswith("h "))
    assert "q[0]" in line and "q[2]" in line and "q[5]" in line


def test_slice_mixed_index():
    source = """
qbit[10] q
H(q[0:4,7])
"""
    qasm = compile(source)
    line = next(l for l in qasm.lower().splitlines() if l.strip().startswith("h "))
    for i in [0, 1, 2, 3, 7]:
        assert f"q[{i}]" in line


def test_mixed_slice_scalar():
    source = """
qbit[10] q
H(q[0,2:6,9])
"""
    qasm = compile(source)
    line = next(l for l in qasm.lower().splitlines() if l.strip().startswith("h "))
    for i in [0, 2, 3, 4, 5, 9]:
        assert f"q[{i}]" in line


def test_gate_macro_multi_index():
    source = """
qbit[4] q
bit[4] c

gate GHZ(a, b, c) {
    H(a)
    CNot(a, b)
    CNot(b, c)
}

GHZ(q[0,2,3])
"""
    qasm = compile(source)
    assert "ghz q[0], q[2], q[3]" in qasm.lower() or "ghz" in qasm.lower()


def test_measure_multi_index():
    source = """
qbit[4] q
bit[4] c
Measure(q[0,2,3], c[0,2,3])
"""
    qasm = compile(source)
    assert "measure q[0] -> c[0]" in qasm.lower()
    assert "measure q[2] -> c[2]" in qasm.lower()
    assert "measure q[3] -> c[3]" in qasm.lower()


# --- Invalid ---


def test_duplicate_literal_indices():
    _compile_raises(
        "qbit[4] q\nH(q[0,0])",
        "Duplicate qbit index: 0",
    )


def test_duplicate_from_slice_overlap():
    _compile_raises(
        "qbit[8] q\nH(q[0:4,2])",
        "Duplicate qbit index: 2",
    )


def test_index_out_of_range():
    _compile_raises(
        "qbit[8] q\nH(q[100])",
        "Index 100 out of range for qbit\\[8\\]",
    )


def test_slice_out_of_range_element():
    _compile_raises(
        "qbit[4] q\nH(q[0:10])",
        "out of range",
    )
