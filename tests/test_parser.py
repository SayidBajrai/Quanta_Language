"""
Tests for parser
"""

import pytest
from quanta.api import get_prints
from quanta.ast.nodes import LiteralExpr
from quanta.errors import QuantaSemanticError
from quanta.lexer.lexer import Lexer, TokenType
from quanta.parser.parser import Parser


def test_lexer_tensor_product_operators():
    tokens = Lexer().tokenize("A ⊙ B\nC ⊗ D\n")
    types = [t.type for t in tokens if t.type not in (TokenType.NEWLINE, TokenType.EOF)]
    assert types == [TokenType.IDENT, TokenType.HADAMARD, TokenType.IDENT, TokenType.IDENT, TokenType.KRON, TokenType.IDENT]


def test_parse_simple_program():
    """Test parsing a simple program"""
    source = """
qbit[2] q;
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


def test_parse_function_typed_classical_params():
    """func may use typed classical parameters."""
    source = """
func float add(float a, float b) {
    return a + b;
}
"""
    func = Parser().parse(Lexer().tokenize(source)).statements[0]
    assert func.return_type == "float"
    assert [(ps.kind, ps.name) for ps in func.param_specs] == [
        ("float", "a"),
        ("float", "b"),
    ]


def test_parse_function_unspecified_classical_params():
    """Classical func with var return uses cvar for unspecified params."""
    source = """
func var add(a, b) {
    return a + b;
}
"""
    func = Parser().parse(Lexer().tokenize(source)).statements[0]
    assert func.return_type == "var"
    assert [(ps.kind, ps.name) for ps in func.param_specs] == [
        ("cvar", "a"),
        ("cvar", "b"),
    ]


def test_parse_function_mixed_specified_return_unspecified_params():
    source = """
func int add(a, b) {
    return a + b;
}
"""
    func = Parser().parse(Lexer().tokenize(source)).statements[0]
    assert func.return_type == "int"
    assert [(ps.kind, ps.name) for ps in func.param_specs] == [
        ("cvar", "a"),
        ("cvar", "b"),
    ]


def test_parse_function_unspecified_quantum_params():
    source = """
func bell(a, b) {
    H(a);
    CNot(a, b);
}
"""
    func = Parser().parse(Lexer().tokenize(source)).statements[0]
    assert func.return_type is None
    assert [(ps.kind, ps.name) for ps in func.param_specs] == [
        ("qvar", "a"),
        ("qvar", "b"),
    ]


def test_parse_function_explicit_wildcard_params():
    source = """
func int pick(cvar x) { return x; }
func apply(var q) { H(q); }
func prep(qvar q) { H(q); }
"""
    funcs = Parser().parse(Lexer().tokenize(source)).statements
    assert [(ps.kind, ps.name) for ps in funcs[0].param_specs] == [("cvar", "x")]
    assert [(ps.kind, ps.name) for ps in funcs[1].param_specs] == [("var", "q")]
    assert [(ps.kind, ps.name) for ps in funcs[2].param_specs] == [("qvar", "q")]


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


def test_string_escape_sequences():
    """String literals decode common C-style escape sequences."""
    lexer = Lexer()
    tokens = lexer.tokenize(r'"a\nb\rc\td\\e\"f\x41\u0042\U00000043"')
    string_tokens = [t for t in tokens if t.type == TokenType.STRING]
    assert len(string_tokens) == 1
    assert string_tokens[0].value == "a\nb\rc\td\\e\"fABC"


def test_parse_string_escape_sequences():
    """Parser preserves decoded string literal values."""
    source = 'Print("line1\\nline2\\ttab");\n'
    ast = Parser().parse(Lexer().tokenize(source))
    expr_stmt = ast.statements[0]
    call = expr_stmt.expr
    literal = call.args[0]
    assert isinstance(literal, LiteralExpr)
    assert literal.value == "line1\nline2\ttab"


def test_print_string_escape_sequences():
    """Print output uses decoded escape sequences."""
    output = get_prints('Print("a\\nb\\tc\\\\d");\n')
    assert output == "a\nb\tc\\d"


def test_lowercase_print_rejected():
    with pytest.raises(QuantaSemanticError, match="Print\\(\\)"):
        get_prints("qbit q\nH(q)\nprint(q)\n")
