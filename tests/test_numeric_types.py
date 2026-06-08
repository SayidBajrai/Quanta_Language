"""Tests for refactored numeric types and () syntax."""

import math

import pytest

from quanta import compile, get_prints
from quanta.errors import QuantaSyntaxError, QuantaTypeError
from quanta.lexer.lexer import Lexer
from quanta.parser.parser import Parser
from quanta.types.numeric import (
    basis_index_to_signed_value,
    decode_qdec_value,
    init_bit_pattern,
    is_uniform_superposition,
    qint_signed_range,
    qdec_signed_range,
    qdec_step,
    qreal_num_states,
    qreal_value_at,
    twos_complement_decode,
    twos_complement_encode,
)
from quanta.types.tensor import TensorType


def test_bracket_syntax_rejected_for_qint():
    with pytest.raises(QuantaSyntaxError, match="parenthesis syntax"):
        Parser().parse(Lexer().tokenize("qint[4] x\n"))


def test_parse_qint_qdec_qreal_parenthesis():
    ast = Parser().parse(Lexer().tokenize("""
qint(4) a
qdec(4,4) b
quint(8) c
qreal(-1,1,8) x
uint(8) u
dec(16,16) d
"""))
    kinds = [s.kind for s in ast.statements]
    assert kinds == ["qint", "qdec", "quint", "qreal", "uint", "dec"]


def test_tensor_type_format_parenthesis():
    assert TensorType("qint", (4,)).format() == "qint(4)"
    assert TensorType("qdec", (4, 4)).format() == "qdec(4,4)"
    formatted = TensorType("qreal", (8,), real_min=-1.0, real_max=1.0).format()
    assert formatted.startswith("qreal(") and ",8)" in formatted


def test_parse_legacy_rejects_brackets_for_numeric():
    with pytest.raises(QuantaTypeError, match="parenthesis syntax"):
        TensorType.parse_legacy("qint[4]")


def test_qint_signed_range_and_twos_complement():
    lo, hi = qint_signed_range(4)
    assert lo == -8 and hi == 7
    assert twos_complement_encode(-8, 4) == 8
    assert twos_complement_encode(7, 4) == 7
    assert twos_complement_decode(8, 4) == -8
    assert twos_complement_decode(7, 4) == 7


def test_qint_no_duplicate_zero():
    bits = 4
    values = [basis_index_to_signed_value(i, bits) for i in range(1 << bits)]
    assert values.count(0) == 1
    assert min(values) == -8 and max(values) == 7


def test_qdec_uniform_spacing():
    lo, hi = qdec_signed_range(4, 4)
    step = qdec_step(4)
    assert step == pytest.approx(1 / 16)
    assert lo == pytest.approx(-8.0)
    assert hi == pytest.approx(7.9375)
    vals = sorted(decode_qdec_value(i, 4, 4, signed=True) for i in range(1 << 8))
    diffs = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
    assert all(abs(d - step) < 1e-12 for d in diffs)


def test_qreal_interval_mapping():
    assert qreal_num_states(8) == 256
    vals = [qreal_value_at(k, 8, -1.0, 1.0) for k in range(256)]
    assert vals[0] == pytest.approx(-1.0)
    assert vals[-1] == pytest.approx(1.0)
    mid = min(range(256), key=lambda k: abs(vals[k]))
    assert vals[mid] == pytest.approx(0.0, abs=2 / 255)


def test_h_qint_uniform_superposition_simulation():
    """H(qint(2)) yields uniform amplitudes over 4 signed basis states."""
    from quanta.runtime.frontend_sim import get_prints

    out = get_prints('qint(2) q\nH(q)\nPrint(f"{q:probabilities}")\n')
    assert "25%" in out
    assert is_uniform_superposition([0.25, 0.25, 0.25, 0.25])


def test_h_qreal_uniform_superposition():
    from quanta.runtime.frontend_sim import get_prints

    out = get_prints('qreal(-1,1,2) theta\nH(theta)\nPrint(f"{theta:probabilities}")\n')
    assert "25%" in out


def test_qint_init_signed_lowering():
    qasm = compile("qint(4) reg = -1\n")
    assert "qubit[4] reg" in qasm
    # -1 in 4-bit two's complement is 1111 -> x on all lines
    assert qasm.count("x reg[") == 4


def test_quint_init_unsigned_lowering():
    qasm = compile("quint(3) reg = 2\n")
    assert "x reg[1];" in qasm


def test_classical_uint_decl_parses():
    ast = Parser().parse(Lexer().tokenize("uint(8) counter = 42\n"))
    assert ast.statements[0].kind == "uint"
    assert ast.statements[0].size == 8


def test_qudec_lowering_flat_qubits():
    qasm = compile("qudec(4,4) fp\n")
    assert "qubit[8] fp" in qasm


def test_bare_numeric_types_default_to_canonical_widths():
    source = """
qint qx
qdec qy
quint qz
uint ca
dec cb
qreal qr
qreal(0,1) qr01
"""
    ast = Parser().parse(Lexer().tokenize(source))
    formats = [s.tensor_type.format() for s in ast.statements]
    assert formats[0] == "qint(32)"
    assert formats[1] == "qdec(16,16)"
    assert formats[2] == "quint(32)"
    assert formats[3] == "uint(32)"
    assert formats[4] == "dec(16,16)"
    assert formats[5] == "qreal(-1.0,1.0,32)"
    assert formats[6] == "qreal(0.0,1.0,32)"


def test_bare_qint_equals_explicit_32():
    bare = Parser().parse(Lexer().tokenize("qint qx\n")).statements[0]
    explicit = Parser().parse(Lexer().tokenize("qint(32) qx\n")).statements[0]
    assert bare.tensor_type.format() == explicit.tensor_type.format()
    assert bare.size == 32 == explicit.size


def test_quint_empty_parens_remain_dynamic():
    stmt = Parser().parse(Lexer().tokenize("quint() z\n")).statements[0]
    assert stmt.tensor_type.is_dynamic
    assert stmt.size == 1  # placeholder until inference


def test_bare_qreal_lowers_to_32_qubits():
    qasm = compile("qreal qr\n")
    assert "qubit[32] qr" in qasm


def test_qreal_two_arg_form_defaults_qbits():
    stmt = Parser().parse(Lexer().tokenize("qreal(0,1) theta\n")).statements[0]
    assert stmt.size == 32
    assert stmt.real_min == 0.0
    assert stmt.real_max == 1.0
