"""Frontend simulation and desugaring tests for qint arithmetic."""

import pytest

from quanta import compile
from quanta.errors import QuantaSemanticError
from quanta.lexer.lexer import Lexer
from quanta.parser.parser import Parser
from quanta.runtime.frontend_sim import get_prints
from quanta.sema.transform import ASTTransformer


def _transformed_calls(source: str) -> list[str]:
    ast = Parser().parse(Lexer().tokenize(source))
    ast = ASTTransformer().transform(ast)
    calls = []
    for stmt in ast.statements:
        if hasattr(stmt, "expr") and hasattr(stmt.expr, "callee"):
            callee = stmt.expr.callee
            if hasattr(callee, "name"):
                calls.append(callee.name)
    return calls


def _ket_value(out: str) -> int:
    start = out.rfind("|")
    if start < 0:
        return -1
    bits = out[start + 1 :].split("⟩")[0]
    return int(bits, 2) if bits else 0


# --- QAdd simulation ---


def test_qadd_operator_form():
    source = """
quint(3) a = 1
quint(3) b = 3
quint(3) c = a + b
Print(f"{c}")
"""
    out = get_prints(source)
    assert "|100" in out


def test_qadd_statement_form():
    source = """
quint(3) a = 1
quint(3) b = 3
quint(3) c
QAdd(a, b, c)
Print(f"{c}")
"""
    assert "|100" in get_prints(source)


def test_qadd_inplace_two_arg():
    source = """
quint(3) a = 1
quint(3) b = 3
QAdd(a, b)
Print(f"{b}")
"""
    assert "|100" in get_prints(source)


# --- QSub simulation ---


@pytest.mark.parametrize(
    "a,b,expected",
    [(5, 3, 2), (3, 5, 6), (1, 3, 6), (7, 1, 6)],
)
def test_qsub_operator_form(a, b, expected):
    source = f"""
quint(3) a = {a}
quint(3) b = {b}
quint(3) c = a - b
Print(f"{{c}}")
"""
    out = get_prints(source)
    assert _ket_value(out) == expected


def test_qsub_statement_preserves_operands():
    source = """
quint(3) a = 5
quint(3) b = 3
quint(3) c
QSub(a, b, c)
Print(f"{a}|{b}|{c}")
"""
    out = get_prints(source)
    assert "|101" in out  # a=5
    assert "|011" in out  # b=3
    assert out.endswith("|010⟩") or "|010" in out.split("|")[-1]


# --- QMult simulation ---


@pytest.mark.parametrize(
    "a,b,expected",
    [(2, 3, 6), (3, 2, 6), (7, 3, 5), (3, 5, 7), (1, 1, 1)],
)
def test_qmult_operator_form(a, b, expected):
    source = f"""
quint(3) a = {a}
quint(3) b = {b}
quint(3) c = a * b
Print(f"{{c}}")
"""
    out = get_prints(source)
    assert _ket_value(out) == expected


def test_qmult_statement_form():
    source = """
quint(3) a = 2
quint(3) b = 3
quint(3) c
QMult(a, b, c)
Print(f"{c}")
"""
    assert "|110" in get_prints(source)


# --- QFTAdd simulation ---


def test_qftadd_statement_form():
    source = """
quint(3) a = 1
quint(3) b = 3
quint(3) c
QFTAdd(a, b, c)
Print(f"{c}")
"""
    assert "|100" in get_prints(source)


def test_qftadd_initializer_form():
    source = """
quint(3) a = 1
quint(3) b = 3
quint(3) c = QFTAdd(a, b)
Print(f"{c}")
"""
    assert "|100" in get_prints(source)


def test_qftadd_inplace_two_arg():
    source = """
quint(3) a = 1
quint(3) b = 3
QFTAdd(a, b)
Print(f"{b}")
"""
    assert "|100" in get_prints(source)


def test_qftadd_initializer_desugars():
    calls = _transformed_calls(
        "quint(3) a\nquint(3) b\nquint(3) c = QFTAdd(a, b)"
    )
    assert calls == ["QFTAdd"]


# --- QTreeAdd simulation ---


def test_qtreeadd_statement_form():
    source = """
quint(3) a = 1
quint(3) b = 3
quint(3) c
QTreeAdd(a, b, c)
Print(f"{c}")
"""
    assert "|100" in get_prints(source)


def test_qtreeadd_initializer_form():
    source = """
quint(3) a = 1
quint(3) b = 3
quint(3) c = QTreeAdd(a, b)
Print(f"{c}")
"""
    assert "|100" in get_prints(source)


# --- QExpEncMult / QTreeMult simulation ---


def test_qexpencmult_statement_form():
    source = """
quint(3) a = 2
quint(3) b = 3
quint(3) c
QExpEncMult(a, b, c)
Print(f"{c}")
"""
    assert "|110" in get_prints(source)


def test_qtreemult_statement_form():
    source = """
quint(3) a = 2
quint(3) b = 3
quint(3) c
QTreeMult(a, b, c)
Print(f"{c}")
"""
    assert "|110" in get_prints(source)


def test_qexpencmult_initializer_desugars():
    calls = _transformed_calls(
        "quint(3) a\nquint(3) b\nquint(3) c = QExpEncMult(a, b)"
    )
    assert calls == ["QExpEncMult"]


# --- QDiv / QMod simulation ---


def test_qdiv_statement_form():
    source = """
quint(3) dividend = 7
quint(3) divisor = 3
quint(3) quotient
quint(3) remainder
QDiv(dividend, divisor, quotient, remainder)
Print(f"{quotient}|{remainder}")
"""
    out = get_prints(source)
    assert "|010" in out  # quotient 2
    assert "|001" in out  # remainder 1


def test_qmod_statement_form():
    source = """
quint(3) a = 7
quint(3) b = 3
quint(3) c
QMod(a, b, c)
Print(f"{c}")
"""
    assert "|001" in get_prints(source)


def test_qmod_operator_form():
    source = """
quint(3) a = 7
quint(3) b = 3
quint(3) c = a % b
Print(f"{c}")
"""
    assert "|001" in get_prints(source)


# --- Desugaring ---


def test_subtraction_desugars_to_qsub():
    assert _transformed_calls("quint(3) a\nquint(3) b\nquint(3) c = a - b") == ["QSub"]


def test_multiplication_desugars_to_qmult():
    assert _transformed_calls("quint(3) a\nquint(3) b\nquint(3) c = a * b") == ["QMult"]


def test_division_desugars_to_qdiv():
    calls = _transformed_calls("quint(3) a\nquint(3) b\nquint(3) c = a / b")
    assert calls == ["QDiv"]


def test_modulo_desugars_to_qmod():
    calls = _transformed_calls("quint(3) a\nquint(3) b\nquint(3) c = a % b")
    assert calls == ["QMod"]


def test_chained_subtraction_desugar():
    source = """
quint(3) a
quint(3) b
quint(3) d
quint(3) r = a - b - d
"""
    assert _transformed_calls(source) == ["QSub"]


def test_precedence_multiply_before_subtract():
    source = """
quint(3) x
quint(3) y
quint(3) z
quint(3) r = x - y * z
"""
    assert _transformed_calls(source) == ["QMult", "QSub"]


# --- Compile lowering ---


def test_qsub_compiles_with_cdkm():
    qasm = compile("quint(3) a\nquint(3) b\nquint(3) c\nQSub(a, b, c)")
    assert "CDKM QSub" in qasm
    assert "ccx" in qasm


def test_qmult_compiles_with_shift_add():
    qasm = compile("quint(3) a\nquint(3) b\nquint(3) c\nQMult(a, b, c)")
    assert "QMult shift-and-add" in qasm
    assert "mcx" in qasm


def test_qftadd_compiles_with_draper():
    qasm = compile("quint(3) a\nquint(3) b\nquint(3) c\nQFTAdd(a, b, c)")
    assert "Draper QFT adder" in qasm
    assert "h " in qasm
    assert "cx " in qasm


def test_qtreeadd_compiles_with_vbe():
    qasm = compile("quint(3) a\nquint(3) b\nquint(3) c\nQTreeAdd(a, b, c)")
    assert "VBE tree adder" in qasm
    assert "ccx" in qasm


def test_qexpencmult_compiles_with_rgqf():
    qasm = compile("quint(3) a\nquint(3) b\nquint(3) c\nQExpEncMult(a, b, c)")
    assert "RGQFT exponent-encoded multiplier" in qasm


def test_qtreemult_compiles_with_hrs():
    qasm = compile("quint(3) a\nquint(3) b\nquint(3) c\nQTreeMult(a, b, c)")
    assert "HRS tree multiplier" in qasm


def test_qdiv_emits_structure():
    qasm = compile(
        "quint(3) dividend = 7\nquint(3) divisor = 3\nquint(3) quotient\nquint(3) remainder\n"
        "QDiv(dividend, divisor, quotient, remainder)"
    )
    assert "QDiv repeated subtraction" in qasm
    assert "ccx" in qasm


def test_qmod_emits_structure():
    qasm = compile("quint(3) a = 7\nquint(3) b = 3\nquint(3) c\nQMod(a, b, c)")
    assert "QMod repeated subtraction" in qasm
