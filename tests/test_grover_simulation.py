"""Frontend simulation and lowering tests for Grover."""

from quanta import compile
from quanta.runtime.frontend_sim import get_prints


def _dominant_ket(out: str) -> str:
    start = out.rfind("|")
    if start < 0:
        return ""
    return out[start + 1 :].split("⟩")[0]


def test_grover_amplifies_target():
    source = """
quint(3) reg
H(reg)
Grover(reg, 5)
Print(f"{reg}")
"""
    out = get_prints(source)
    assert "|101" in out
    assert "0.8839" in out or "0.884" in out


def test_grover_compiles_with_gates():
    qasm = compile(
        "quint(3) reg\nH(reg)\nGrover(reg, 5)"
    )
    assert "Grover iteration" in qasm
    assert "h " in qasm
    assert "ccx" in qasm


def test_grover_structured_lowering():
    from quanta.compiler import Compiler

    qasm = Compiler().compile(
        "quint(2) a\nGrover(a, 3)", keep_structure=True
    )
    assert "__Grover_2_3" in qasm
    assert "h " in qasm
    assert "cx " in qasm
