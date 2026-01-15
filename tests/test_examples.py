"""
Integration tests with example programs
"""

import pytest
from quanta import compile


def test_quantum_register_declaration():
    """Test quantum register declarations"""
    source = """
qubit[2] q;
bit[2] c;
"""
    qasm = compile(source)
    
    assert "qubit[2] q" in qasm
    assert "bit[2] c" in qasm


def test_measurement():
    """Test measurement operations"""
    source = """
qubit[1] q;
bit[1] c;
Measure(q[0], c[0]);
"""
    qasm = compile(source)
    
    assert "measure" in qasm.lower()
