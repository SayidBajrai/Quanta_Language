"""Tests for built-in function documentation registry."""

from quanta import get_function_docs, list_functions
from quanta.stdlib.builtins import FUNCTION_SUMMARIES


CORE_BUILTINS = {
    "QAdd",
    "QSub",
    "QMult",
    "QDiv",
    "QMod",
    "QFTAdd",
    "Compare",
    "Grover",
    "Bell",
    "GHZ",
    "QFT",
    "H",
    "CNot",
    "Measure",
    "Print",
    "len",
    "range",
    "reset",
    "Fidelity",
    "Shape",
    "DotProduct",
}


def test_all_core_builtins_documented():
    for name in CORE_BUILTINS:
        assert name in FUNCTION_SUMMARIES, f"missing summary for {name}"


def test_get_function_docs_single():
    doc = get_function_docs("QAdd")
    assert doc is not None
    assert doc.name == "QAdd"
    assert "addition" in doc.summary.lower()
    assert len(doc.params) >= 1
    assert "QAdd" in doc.signature


def test_get_function_docs_unknown():
    assert get_function_docs("NotARealFunction") is None


def test_get_function_docs_all_dict():
    all_docs = get_function_docs()
    assert isinstance(all_docs, dict)
    assert "Print" in all_docs
    hover = all_docs["Print"]["hover"]
    assert "Print" in hover
    assert "summary" in all_docs["Print"]


def test_format_hover_includes_params():
    doc = get_function_docs("Compare")
    hover = doc.format_hover()
    assert "Compare(a, b, flag)" in hover
    assert "flag" in hover
    assert "a ≥ b" in hover


def test_list_functions_by_category():
    gates = list_functions("gate")
    names = {d.name for d in gates}
    assert "H" in names
    assert "QAdd" not in names

    arithmetic = list_functions("quantum_arithmetic")
    arith_names = {d.name for d in arithmetic}
    assert "QAdd" in arith_names
    assert "H" not in arith_names
