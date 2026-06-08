"""
Tests for QASM3 code generation
"""

import pytest
from quanta import compile


def test_bell_state():
    """Test Bell state compilation"""
    source = """
qbit[2] q;
bit[2] c;

H(q[0]);
CNot(q[0], q[1]);
Measure(q[0], c[0]);
"""
    qasm = compile(source)
    
    assert "OPENQASM 3" in qasm
    assert "qubit[2] q" in qasm
    assert "h q[0]" in qasm.lower()
    assert "cx" in qasm.lower() or "cnot" in qasm.lower()


def test_simple_gates():
    """Test simple gate compilation"""
    source = """
qbit[1] q;
H(q[0]);
X(q[0]);
"""
    qasm = compile(source)
    
    assert "h q[0]" in qasm.lower()
    assert "x q[0]" in qasm.lower()


def test_measure_registers():
    """Test Measure(q, c) with full registers"""
    source = """
qbit[2] q
bit[2] c
Measure(q, c)
"""
    qasm = compile(source)
    
    assert "measure q[0] -> c[0]" in qasm.lower()
    assert "measure q[1] -> c[1]" in qasm.lower()


def test_qdec_declaration():
    """Test qdec fixed-point register lowering"""
    source = """
qudec(4,4) fp;
"""
    qasm = compile(source)
    assert "qubit[8] fp" in qasm


def test_qfloat_declaration():
    """Test qfloat register lowering"""
    source = """
qfloat(5,10) qf;
"""
    qasm = compile(source)
    assert "qubit[16] qf" in qasm


def test_high_level_bell_gate():
    """Test Bell high-level gate lowering"""
    source = """
qbit[2] q0;
qbit[2] q1;
Bell(q0[0], q1[0]);
"""
    qasm = compile(source)
    qasm_lower = qasm.lower()
    assert "h q0[0]" in qasm_lower
    assert "cx q0[0], q1[0]" in qasm_lower
