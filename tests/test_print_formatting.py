"""
Tests for Python-style Print() and f-string object formatting.
"""

import pytest
from quanta.runtime.frontend_sim import get_prints
from quanta.lexer.lexer import Lexer
from quanta.parser.parser import Parser
from quanta.ast.nodes import FStringExpr, FStringPart, LiteralExpr, VarExpr


def _parse_expr(source: str):
    lexer = Lexer()
    parser = Parser()
    ast = parser.parse(lexer.tokenize(source + "\nPrint(0);"))
    call = ast.statements[0].expr
    return call.args[0]


def test_parse_fstring_simple():
    expr = _parse_expr('Print(f"{q}")')
    assert isinstance(expr, FStringExpr)
    assert len(expr.parts) == 1
    assert isinstance(expr.parts[0].expr, VarExpr)
    assert expr.parts[0].expr.name == "q"


def test_parse_fstring_with_literal():
    expr = _parse_expr('Print(f"State = {q}")')
    assert isinstance(expr, FStringExpr)
    assert expr.parts[0].literal == "State = "
    assert expr.parts[1].expr.name == "q"


def test_parse_fstring_with_specifier():
    expr = _parse_expr('Print(f"{q:symbolic}")')
    assert expr.parts[0].specifier == "symbolic"


def test_print_qbit_register():
    source = """
qbit[2] q
H(q[0])
CNot(q[0], q[1])
Print(q)
"""
    out = get_prints(source)
    assert "√2" in out
    assert "|00⟩" in out
    assert "|11⟩" in out
    assert "(" in out and ")" in out


def test_fstring_qbit_matches_print():
    source = """
qbit[2] q
H(q[0])
CNot(q[0], q[1])
Print(f"{q}")
"""
    direct = get_prints(
        """
qbit[2] q
H(q[0])
CNot(q[0], q[1])
Print(q)
"""
    )
    assert get_prints(source) == direct


def test_fstring_with_prefix_matches_print():
    source = """
qbit[2] q
H(q[0])
CNot(q[0], q[1])
Print(f"State = {q}")
"""
    state = get_prints(
        """
qbit[2] q
H(q[0])
CNot(q[0], q[1])
Print(q)
"""
    )
    assert get_prints(source) == f"State = {state}"


def test_qint_print_and_fstring_match():
    source_direct = """
qint[3] a = 5
Print(a)
"""
    source_f = """
qint[3] a = 5
Print(f"{a}")
"""
    assert get_prints(source_direct) == get_prints(source_f)
    assert "|" in get_prints(source_direct)


def test_bint_print_and_fstring_match():
    source_direct = """
bint[8] b = 12
Print(b)
"""
    source_f = """
bint[8] b = 12
Print(f"{b}")
"""
    assert get_prints(source_direct) == get_prints(source_f)
    assert get_prints(source_direct) == "12"


def test_fstring_value_prefix_bint():
    source = """
bint[8] b = 12
Print(f"Value = {b}")
"""
    assert get_prints(source) == "Value = 12"


def test_fstring_value_prefix_qint():
    source = """
qint[3] a = 5
Print(f"Value = {a}")
"""
    inner = get_prints("qint[3] a = 5\nPrint(a)")
    assert get_prints(source) == f"Value = {inner}"


def _bell_source(suffix: str) -> str:
    return f"""
qbit[2] q
H(q[0])
CNot(q[0], q[1])
{suffix}
"""


def test_fstring_symbolic_specifier():
    symbolic = get_prints(_bell_source('Print(f"{q:symbolic}")'))
    default = get_prints(_bell_source("Print(q)"))
    assert symbolic == default
    assert "\u221a2" in symbolic or "sqrt" in symbolic.lower()


def test_fstring_probabilities_specifier():
    out = get_prints(_bell_source('Print(f"{q:probabilities}")'))
    assert "50%" in out
    assert "|00" in out
    assert "|11" in out
    assert "\n" not in out or out.count("\n") >= 1


def test_fstring_density_specifier():
    out = get_prints(_bell_source('Print(f"{q:density}")'))
    assert "0.5" in out
    assert "[" in out and "]" in out
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    assert len(lines) >= 4


def test_symbolic_and_probabilities_differ():
    sym = get_prints(_bell_source('Print(f"{q:symbolic}")'))
    prob = get_prints(_bell_source('Print(f"{q:probabilities}")'))
    assert sym != prob


def test_specifier_aliases():
    prob = get_prints(_bell_source('Print(f"{q:probabilities}")'))
    density = get_prints(_bell_source('Print(f"{q:density}")'))
    assert get_prints(_bell_source('Print(f"{q:prob}")')) == prob
    assert get_prints(_bell_source('Print(f"{q:rho}")')) == density
    assert get_prints(_bell_source('Print(f"{q:sym}")')) == get_prints(_bell_source("Print(q)"))


def test_mixed_fstring_specifiers():
    out = get_prints(_bell_source('Print(f"sym={q:symbolic} | prob={q:prob}")'))
    assert "sym=" in out
    assert "prob=" in out
    assert "50%" in out


def test_fstring_entropy_bell():
    out = get_prints(_bell_source('Print(f"{q:entropy}")'))
    assert out == "1.0000"


def test_fstring_entropy_pure_single():
    out = get_prints("qbit[1] q\nPrint(f\"{q:entropy}\")")
    assert out == "0.0000"


def test_fstring_amplitudes_bell():
    out = get_prints(_bell_source('Print(f"{q:amplitudes}")'))
    assert "|00⟩" in out
    assert "|11⟩" in out
    assert "0.7071" in out
    assert "|01⟩" not in out and "|10⟩" not in out


def test_fstring_amplitudes_differs_from_symbolic():
    sym = get_prints(_bell_source('Print(f"{q:symbolic}")'))
    amp = get_prints(_bell_source('Print(f"{q:amplitudes}")'))
    assert sym != amp


def test_fstring_summary_bell_structure():
    out = get_prints(_bell_source('Print(f"{q:summary}")'))
    assert "QUBIT INFO" in out
    assert "ENTANGLEMENT" in out
    assert "STATE COMPLEXITY" in out
    assert "PREVIEW" in out
    assert "- size: 2" in out
    assert "- type: entangled" in out
    assert "- purity: pure" in out
    assert "- entropy: 1.0000" in out
    assert "entangled_groups:" in out
    assert "dominant_states:" in out
    assert "0.7071" in out
    assert "√2" in out or "0.7071" in out


def test_fstring_summary_large_register():
    source = """
qbit[3] q
H(q[0])
Print(f"{q:summary}")
"""
    out = get_prints(source)
    assert "- size: 3" in out
    assert "STATE COMPLEXITY" in out
    assert "PREVIEW" in out


def test_entropy_amplitudes_summary_distinct():
    ent = get_prints(_bell_source('Print(f"{q:entropy}")'))
    amp = get_prints(_bell_source('Print(f"{q:amplitudes}")'))
    summ = get_prints(_bell_source('Print(f"{q:summary}")'))
    assert ent != amp
    assert ent != summ
    assert amp != summ


def test_fstring_bloch_plus_state():
    source = """
qbit[1] q
H(q[0])
Print(f"{q[0]:bloch}")
"""
    out = get_prints(source)
    assert "BLOCH SPHERE" in out
    assert "θ" in out or "theta" in out.lower()
    assert "90°" in out
    assert "vector: (1.0000, 0.0000, 0.0000)" in out
    assert "STATE" in out


def test_fstring_bloch_zero_state():
    source = """
qbit[1] q
Print(f"{q[0]:bloch}")
"""
    out = get_prints(source)
    assert "BLOCH SPHERE" in out
    assert "0°" in out
    assert "vector: (0.0000, 0.0000, 1.0000)" in out
    assert "STATE" not in out


def test_fstring_bloch_multi_qubit_error():
    out = get_prints(_bell_source('Print(f"{q:bloch}")'))
    assert out == "Bloch representation requires single qubit or reduced subsystem"


def test_fstring_bloch_vector_plus():
    source = """
qbit[1] q
H(q[0])
Print(f"{q[0]:bloch_vector}")
"""
    out = get_prints(source)
    assert out == "(1.0000, 0.0000, 0.0000)"


def test_fstring_bloch_vector_zero():
    source = """
qbit[1] q
Print(f"{q[0]:bloch_vector}")
"""
    out = get_prints(source)
    assert out == "(0.0000, 0.0000, 1.0000)"


def test_fstring_circuit_flat_gates():
    source = """
qbit[2] q
H(q[0])
CNot(q[0], q[1])
Print(f"{q:circuit}")
"""
    out = get_prints(source)
    assert "CIRCUIT EXECUTION TRACE" in out
    assert "H(q[0])" in out
    assert "CNOT(q[0], q[1])" in out
    assert "TOTAL GATES: 2" in out
    assert "DEPTH: 2" in out
    assert "QUBITS: 2" in out


def test_fstring_circuit_user_gate():
    source = """
qbit[2] q

gate Bell(a, b) {
    H(a)
    CNot(a, b)
}

Bell(q[0], q[1])
Print(f"{q:circuit}")
"""
    out = get_prints(source)
    assert "CIRCUIT EXECUTION TRACE" in out
    assert "Bell(q[0], q[1])" in out
    assert "H(q[0])" in out
    assert "CNOT(q[0], q[1])" in out
    assert "TOTAL GATES: 2" in out
    assert "DEPTH: 2" in out
    assert "QUBITS: 2" in out


def test_bloch_circuit_distinct_layers():
    circuit = get_prints(_bell_source('Print(f"{q:circuit}")'))
    bloch = get_prints("qbit[1] q\nH(q[0])\nPrint(f\"{q[0]:bloch}\")")
    assert "CIRCUIT" in circuit
    assert "BLOCH" in bloch
    assert circuit != bloch
