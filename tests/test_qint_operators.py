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

        if hasattr(stmt, "kind") and stmt.kind == "qint" and hasattr(stmt, "size"):

            sizes[stmt.name] = stmt.size

    return sizes





def test_chained_addition_desugar():

    source = """

qint[2] a

qint[2] b

qint[2] d

qint[2] total = a + b + d

"""

    assert _transformed_calls(source) == ["QAdd"]





def test_precedence_multiply_before_add():

    source = """

qint[2] x

qint[2] y

qint[2] z

qint[2] r = x + y * z

"""

    assert _transformed_calls(source) == ["QMult", "QAdd"]





def test_parenthesized_compound_expression():

    source = """

qint[2] a

qint[2] b

qint[2] c

qint[2] r = (a + b) * c

"""

    assert _transformed_calls(source) == ["QAdd", "QMult"]





def test_variadic_qmult_lowering():

    source = """

qint[2] a

qint[2] b

qint[2] c

qint[4] out

QMult(a, b, c, out)

"""

    qasm = compile(source)

    assert "Variadic multiplication: would multiply" not in qasm

    assert qasm.lower().count("quantum multiplier") >= 2





def test_simple_add_compiles():

    source = """

qint[2] a

qint[2] b

qint[2] c = a + b

"""

    qasm = compile(source)

    assert "ripple-carry adder" in qasm.lower() or "qadd" in qasm.lower()





def test_infer_size_from_operands():

    source = """

qint[3] a

qint[3] b

qint[] z = a + b

"""

    sizes = _transformed_sizes(source)

    assert sizes["z"] == 3





def test_infer_size_with_constant_operand():

    source = """

qint[4] x

qint[] y = x + 5

"""

    sizes = _transformed_sizes(source)

    assert sizes["y"] == 4





def test_constant_addition_desugar():

    source = """

qint[4] x

qint[4] y = x + 5

"""

    calls = _transformed_calls(source)

    assert calls == ["QAdd"]





def test_constant_multiplication_desugar():

    source = """

qint[3] x

qint[3] y

qint[3] z = x * y * 3

"""

    calls = _transformed_calls(source)

    assert calls == ["QMult"]





def test_add_zero_simplification():

    source = """

qint[4] a

qint[4] r = a + 0

"""

    calls = _transformed_calls(source)

    assert calls == ["QAdd"]

    assert len(calls) == 1





def test_multiply_zero_simplification():

    source = """

qint[4] a

qint[4] r = a * 0

"""

    calls = _transformed_calls(source)

    assert calls == []





def test_multiply_one_simplification():

    source = """

qint[4] a

qint[4] r = a * 1

"""

    calls = _transformed_calls(source)

    assert calls == ["QAdd"]





def test_width_mismatch_rejected():

    source = """

qint[2] a

qint[4] b

qint[4] c = a + b

"""

    with pytest.raises(QuantaSemanticError, match="same bit width"):

        compile(source)





def test_qint_empty_brackets_without_init_rejected():

    source = """

qint[] z;

"""

    with pytest.raises(QuantaSemanticError, match="qint\\[\\]"):

        compile(source)





def test_temp_reuse_across_statements():

    source = """

qint[2] a

qint[2] b

qint[2] c

qint[2] d

qint[2] r1 = a + b * c

qint[2] r2 = d + b * c

"""

    lexer = Lexer()

    parser = Parser()

    transformer = ASTTransformer()

    ast = parser.parse(lexer.tokenize(source))

    ast = transformer.transform(ast)

    temp_names = [

        stmt.name

        for stmt in ast.statements

        if hasattr(stmt, "kind") and stmt.kind == "qint" and stmt.name.startswith("_temp_")

    ]

    assert len(temp_names) == 1
    assert temp_names[0] == "_temp_0"


