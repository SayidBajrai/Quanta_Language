"""

Tests for qint operator overloading and variadic quantum arithmetic.

"""



import pytest



from quanta import compile

from quanta.compiler import Compiler

from quanta.errors import QuantaSemanticError

from quanta.lexer.lexer import Lexer

from quanta.parser.parser import Parser

from quanta.sema.transform import ASTTransformer





def _transformed_calls(source: str) -> list[str]:

    lexer = Lexer()

    parser = Parser()

    transformer = ASTTransformer()

    ast = parser.parse(lexer.tokenize(source))

    ast = transformer.transform(ast)

    calls = []

    for stmt in ast.statements:

        if hasattr(stmt, "expr") and hasattr(stmt.expr, "callee"):

            callee = stmt.expr.callee

            if hasattr(callee, "name"):

                calls.append(callee.name)

    return calls





def _transformed_sizes(source: str) -> dict[str, int]:

    lexer = Lexer()

    parser = Parser()

    transformer = ASTTransformer()

    ast = parser.parse(lexer.tokenize(source))

    ast = transformer.transform(ast)

    sizes = {}

    for stmt in ast.statements:

        if hasattr(stmt, "kind") and stmt.kind in ("qint", "quint") and hasattr(stmt, "size"):

            sizes[stmt.name] = stmt.size

    return sizes





def test_chained_addition_desugar():

    source = """

quint(2) a

quint(2) b

quint(2) d

quint(2) total = a + b + d

"""

    assert _transformed_calls(source) == ["QAdd"]





def test_precedence_multiply_before_add():

    source = """

quint(2) x

quint(2) y

quint(2) z

quint(2) r = x + y * z

"""

    assert _transformed_calls(source) == ["QMult", "QAdd"]





def test_parenthesized_compound_expression():

    source = """

quint(2) a

quint(2) b

quint(2) c

quint(2) r = (a + b) * c

"""

    assert _transformed_calls(source) == ["QAdd", "QMult"]





def test_variadic_qmult_lowering():

    source = """

quint(2) a

quint(2) b

quint(2) c

quint(4) out

QMult(a, b, c, out)

"""

    qasm = compile(source)

    assert "QMult shift-and-add" in qasm
    assert "mcx" in qasm





def test_simple_add_compiles():

    source = """

quint(2) a

quint(2) b

quint(2) c = a + b

"""

    qasm = compile(source)

    assert "ripple-carry adder" in qasm.lower() or "qadd" in qasm.lower()





def test_infer_size_from_operands():

    source = """

quint(3) a

quint(3) b

quint() z = a + b

"""

    sizes = _transformed_sizes(source)

    assert sizes["z"] == 3





def test_infer_size_with_constant_operand():

    source = """

quint(4) x

quint() y = x + 5

"""

    sizes = _transformed_sizes(source)

    assert sizes["y"] == 4





def test_constant_addition_desugar():

    source = """

quint(4) x

quint(4) y = x + 5

"""

    calls = _transformed_calls(source)

    assert calls == ["QAdd"]





def test_constant_multiplication_desugar():

    source = """

quint(3) x

quint(3) y

quint(3) z = x * y * 3

"""

    calls = _transformed_calls(source)

    assert calls == ["QMult"]





def test_add_zero_simplification():

    source = """

quint(4) a

quint(4) r = a + 0

"""

    calls = _transformed_calls(source)

    assert calls == ["QAdd"]

    assert len(calls) == 1





def test_multiply_zero_simplification():

    source = """

quint(4) a

quint(4) r = a * 0

"""

    calls = _transformed_calls(source)

    assert calls == []





def test_multiply_one_simplification():

    source = """

quint(4) a

quint(4) r = a * 1

"""

    calls = _transformed_calls(source)

    assert calls == ["QAdd"]





def test_width_mismatch_rejected():

    source = """

quint(2) a

quint(4) b

quint(4) c = a + b

"""

    with pytest.raises(QuantaSemanticError, match="same bit width"):

        compile(source)





def test_qint_empty_brackets_without_init_rejected():

    source = """

quint() n;

"""

    with pytest.raises(QuantaSemanticError, match="quint\\(\\)"):

        compile(source)





def test_temp_reuse_across_statements():

    source = """

quint(2) a

quint(2) b

quint(2) c

quint(2) d

quint(2) r1 = a + b * c

quint(2) r2 = d + b * c

"""

    lexer = Lexer()

    parser = Parser()

    transformer = ASTTransformer()

    ast = parser.parse(lexer.tokenize(source))

    ast = transformer.transform(ast)

    temp_names = [

        stmt.name

        for stmt in ast.statements

        if hasattr(stmt, "kind") and stmt.kind == "quint" and stmt.name.startswith("_temp_")

    ]

    assert len(temp_names) == 1
    assert temp_names[0] == "_temp_0"


