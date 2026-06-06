"""Tests for user-defined /// documentation comments."""

from quanta import get_function_docs, get_user_function_docs, get_prints
from quanta.ast.nodes import FuncDecl, GateDecl
from quanta.docs.comment_parser import parse_doc_comment
from quanta.lexer.lexer import Lexer, TokenType
from quanta.parser.parser import Parser

ADD_DOC_LINES = [
    "- addition function",
    "- this function adds two numbers",
    "int a - first variable",
    "int b - second variable",
    "return: int - the summation of a and b",
]

ADD_SOURCE = """
/// - addition function
/// - this function adds two numbers
/// int a - first variable
/// int b - second variable
/// return: int - the summation of a and b
func int add(a, b) {
    return a + b;
}
"""

BELL_GATE_SOURCE = """
/// - prepare Bell state on two qubits
/// qbit a - control qubit
/// qbit b - target qubit
gate bell(a, b) {
    H(a);
    CX(a, b);
}
"""


def test_parse_doc_comment_three_tier_rules():
    doc = parse_doc_comment(ADD_DOC_LINES)
    assert doc.summary == "addition function\nthis function adds two numbers"
    assert len(doc.params) == 2
    assert doc.params[0].name == "a"
    assert doc.params[0].type == "int"
    assert doc.params[0].description == "first variable"
    assert doc.params[1].name == "b"
    assert "summation" in doc.returns


def test_lexer_emits_doc_comment_tokens():
    tokens = Lexer().tokenize("/// hello\n/// world\nfunc f() {}\n")
    doc_tokens = [t for t in tokens if t.type == TokenType.DOC_COMMENT]
    assert len(doc_tokens) == 2
    assert doc_tokens[0].value == "hello"
    assert doc_tokens[1].value == "world"


def test_regular_line_comment_not_doc_comment():
    tokens = Lexer().tokenize("// regular comment\nfunc f() {}\n")
    assert not any(t.type == TokenType.DOC_COMMENT for t in tokens)


def test_parser_attaches_doc_to_func():
    ast = Parser().parse(Lexer().tokenize(ADD_SOURCE))
    func = ast.statements[0]
    assert isinstance(func, FuncDecl)
    assert func.doc is not None
    assert "addition function" in func.doc.summary
    assert len(func.doc.params) == 2


def test_parser_attaches_doc_to_gate():
    ast = Parser().parse(Lexer().tokenize(BELL_GATE_SOURCE))
    gate = ast.statements[0]
    assert isinstance(gate, GateDecl)
    assert gate.doc is not None
    assert "Bell state" in gate.doc.summary
    assert gate.doc.params[0].name == "a"


def test_get_user_function_docs_single():
    doc = get_user_function_docs(ADD_SOURCE, "add")
    assert doc is not None
    assert doc.name == "add"
    assert doc.signature == "int add(a, b)"
    assert "addition function" in doc.summary
    assert len(doc.params) == 2
    assert "summation" in doc.returns


def test_get_user_function_docs_hover():
    doc = get_user_function_docs(ADD_SOURCE, "add")
    hover = doc.format_hover()
    assert "int add(a, b)" in hover
    assert "first variable" in hover
    assert "summation" in hover


def test_get_user_function_docs_all_dict():
    all_docs = get_user_function_docs(ADD_SOURCE)
    assert isinstance(all_docs, dict)
    assert "add" in all_docs
    assert "hover" in all_docs["add"]


def test_get_user_function_docs_unknown():
    assert get_user_function_docs(ADD_SOURCE, "missing") is None


def test_get_function_docs_fallback_to_user_source():
    doc = get_function_docs("add", source=ADD_SOURCE)
    assert doc is not None
    assert doc.name == "add"
    assert doc.category == "user"


def test_user_add_function_end_to_end():
    """Documented classical func runs in frontend sim and Print shows result."""
    source = """
/// - addition
/// - adds two integers together
/// int a - first variable
/// int b - second variable
/// return: int - result of add
func int add(a, b) {
    return a + b;
}

int a = 1
int b = 4
int c = add(a, b)
Print(c)
"""
    doc = get_user_function_docs(source, "add")
    assert doc is not None
    assert "addition" in doc.summary

    output = get_prints(source)
    assert output == "5"


def test_orphan_doc_comment_does_not_break_parse():
    source = """
/// orphan summary line
qbit q;
"""
    ast = Parser().parse(Lexer().tokenize(source))
    assert len(ast.statements) == 1


SPECIFIED_ADD_SOURCE = """
/// - add function
/// - adds two floats together
/// float a - first variable
/// float b - second variable
/// return: float - result of add
func float add(float a, float b) {
    return a + b;
}
"""

UNSPECIFIED_ADD_SOURCE = """
/// - add function
/// - adds two variables together
/// var a - first variable
/// var b - second variable
/// return: var - result of add
func var add(a, b) {
    return a + b;
}
"""


def test_doc_comments_specified_param_and_return_types():
    doc = get_user_function_docs(SPECIFIED_ADD_SOURCE, "add")
    assert doc is not None
    assert doc.signature == "float add(float a, float b)"
    assert doc.params[0].type == "float"
    assert "result of add" in doc.returns


def test_doc_comments_unspecified_param_and_return_types():
    doc = get_user_function_docs(UNSPECIFIED_ADD_SOURCE, "add")
    assert doc is not None
    assert doc.signature == "var add(a, b)"
    assert doc.params[0].type == "var"
    assert "result of add" in doc.returns


def test_specified_add_function_end_to_end():
    source = """
/// - add function
/// float a - first variable
/// float b - second variable
/// return: float - result of add
func float add(float a, float b) {
    return a + b;
}

float a = 1.5
float b = 2.5
float c = add(a, b)
Print(c)
"""
    assert get_prints(source) == "4.0"


def test_unspecified_add_function_end_to_end():
    source = """
func var add(a, b) {
    return a + b;
}

int a = 1
int b = 4
var c = add(a, b)
Print(c)
"""
    assert get_prints(source) == "5"
