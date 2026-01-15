"""
Tests for parser
"""

import pytest
from quanta.lexer.lexer import Lexer
from quanta.parser.parser import Parser


def test_parse_simple_program():
    """Test parsing a simple program"""
    source = """
qubit[2] q;
bit[2] c;
H(q[0]);
"""
    lexer = Lexer()
    parser = Parser()
    
    tokens = lexer.tokenize(source)
    ast = parser.parse(tokens)
    
    assert ast is not None
    assert len(ast.statements) == 3


def test_parse_function():
    """Test parsing function declaration"""
    source = """
func bell(a, b) {
    H(a);
    CNot(a, b);
}
"""
    lexer = Lexer()
    parser = Parser()
    
    tokens = lexer.tokenize(source)
    ast = parser.parse(tokens)
    
    assert ast is not None
    assert len(ast.statements) == 1
    # Check that it's a function declaration
    from quanta.ast.nodes import FuncDecl
    assert isinstance(ast.statements[0], FuncDecl)


def test_parse_for_loop():
    """Test parsing for loop"""
    source = """
for (i in [0:3]) {
    H(q[i]);
}
"""
    lexer = Lexer()
    parser = Parser()
    
    tokens = lexer.tokenize(source)
    ast = parser.parse(tokens)
    
    assert ast is not None
    assert len(ast.statements) == 1
