"""
Tests for structured OpenQASM lowering (keep_structure=True).
"""

import pytest
from quanta.compiler import Compiler
from quanta.api import compile as api_compile


def compile_structured(source: str) -> str:
    return Compiler().compile(source, keep_structure=True)


def compile_flat(source: str) -> str:
    return Compiler().compile(source, keep_structure=False)


def test_flat_mode_unchanged_for_bell_gate():
  source = """
qbit[2] q
gate Bell(a, b) {
    H(a)
    CNot(a, b)
}
Bell(q[0], q[1])
"""
  qasm = compile_flat(source)
  assert "OPENQASM 3" in qasm
  assert "gate Bell" in qasm
  assert "bell q[0]" in qasm.lower()


def test_structured_emits_function_def():
  source = """
func bit[2] segment(qbit[2] anc, qbit psi) {
    bit[2] b
    reset(anc)
    H(anc[0])
    Measure(anc, b)
    return b
}

qbit input
qbit[2] ancilla
bit[2] flags

reset(input)
H(input)
"""
  qasm = compile_structured(source)
  assert "def segment__qbit2_qbit" in qasm
  assert "qubit[2] anc, qubit psi -> bit[2]" in qasm
  assert "bit[2] b;" in qasm
  assert "reset anc;" in qasm or "reset(anc)" in source
  assert "measure anc -> b;" in qasm
  assert "return b;" in qasm
  assert "qubit input;" in qasm


def test_structured_while_loop():
  source = """
func bit[1] step(qbit q) {
    bit[1] b
    H(q)
    Measure(q, b)
    return b
}

qbit q
bit[1] flags

while (int(flags) != 0) {
    flags = step(q)
}
"""
  qasm = compile_structured(source)
  assert "while (" in qasm and "int(flags) != 0" in qasm
  assert "flags = step__qbit q;" in qasm


def test_while_requires_structured_mode():
  source = """
qbit q
while (1) {
    H(q[0])
}
"""
  with pytest.raises(Exception):
    compile_flat(source)


def test_structured_preserves_qadd_as_gate():
  source = """
qint[2] a
qint[2] b
qint[2] c
QAdd(a, b, c)
"""
  qasm = compile_structured(source)
  assert "gate __QAdd_" in qasm
  assert "__QAdd_2_2_2 a, b, c;" in qasm
  assert qasm.count("__QAdd_2_2_2") == 2


@pytest.mark.parametrize(
    "op_name,source,expected_gate",
    [
        (
            "QAdd",
            "qint[2] a\nqint[2] b\nqint[2] c\nQAdd(a, b, c)",
            "__QAdd_2_2_2",
        ),
        (
            "QSub",
            "qint[2] a\nqint[2] b\nQSub(a, b)",
            "__QSub_2_2",
        ),
        (
            "QMult",
            "qint[2] a\nqint[2] b\nqint[4] out\nQMult(a, b, out)",
            "__QMult_2_2_4",
        ),
        (
            "Compare",
            "qint[2] a\nqint[2] b\nqbit flag\nCompare(a, b, flag)",
            "__Compare_2_2_1",
        ),
        (
            "QDiv",
            "qint[2] a\nqint[2] b\nqint[2] q\nqint[2] r\nQDiv(a, b, q, r)",
            "__QDiv_2_2_2_2",
        ),
        (
            "QMod",
            "qint[2] a\nqint[2] b\nqint[2] c\nQMod(a, b, c)",
            "__QMod_2_2_2",
        ),
        (
            "QFTAdd",
            "qint[2] a\nqint[2] b\nqint[2] c\nQFTAdd(a, b, c)",
            "__QFTAdd_2_2_2",
        ),
        (
            "QTreeAdd",
            "qint[2] a\nqint[2] b\nqint[2] c\nQTreeAdd(a, b, c)",
            "__QTreeAdd_2_2_2",
        ),
        (
            "QExpEncMult",
            "qint[2] a\nqint[2] b\nqint[4] out\nQExpEncMult(a, b, out)",
            "__QExpEncMult_2_2_4",
        ),
        (
            "QTreeMult",
            "qint[2] a\nqint[2] b\nqint[4] out\nQTreeMult(a, b, out)",
            "__QTreeMult_2_2_4",
        ),
        (
            "Grover",
            "qint[2] a\nGrover(a, 3)",
            "__Grover_2_3",
        ),
    ],
)
def test_structured_preserves_quantum_arithmetic_as_gate(op_name, source, expected_gate):
    qasm = compile_structured(source)
    assert f"gate {expected_gate}" in qasm
    assert f"{expected_gate}" in qasm
    assert qasm.count(expected_gate) == 2, f"{op_name} should emit one gate def and one call"


def test_structured_user_gate_called_from_func():
    source = """
gate Prep(a) {
    H(a)
}

func apply(qbit q) {
    Prep(q)
}

qbit q
apply(q)
"""
    qasm = compile_structured(source)
    assert "gate Prep a {" in qasm
    assert "def apply__qbit qubit q {" in qasm
    assert "    Prep q;" in qasm
    assert "apply__qbit q;" in qasm


def test_structured_user_func_calls_user_gate_in_main():
    source = """
gate Bell(a, b) {
    H(a)
    CNot(a, b)
}

func entangle(qbit a, qbit b) {
    Bell(a, b)
}

qbit[2] q
entangle(q[0], q[1])
"""
    qasm = compile_structured(source)
    assert "gate Bell a, b {" in qasm
    assert "def entangle__qbit_qbit qubit a, qubit b {" in qasm
    assert "    Bell a, b;" in qasm
    assert "entangle__qbit_qbit q[0], q[1];" in qasm


def test_api_compile_keep_structure_flag():
  source = """
gate Bell(a, b) {
    H(a)
    CNot(a, b)
}
qbit[2] q
Bell(q[0], q[1])
"""
  assert "gate Bell" in api_compile(source, keep_structure=True)


def test_function_assignment_rejected_in_flat_mode():
  source = """
func bit[1] f(qbit q) {
    bit[1] b
    Measure(q, b)
    return b
}
qbit q
bit[1] flags
flags = f(q)
"""
  with pytest.raises(Exception):
    compile_flat(source)
