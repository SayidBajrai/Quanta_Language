"""User-defined documentation parsing and extraction."""

from .comment_parser import ParsedDocComment, parse_doc_comment
from .extract import (
    build_func_signature,
    build_gate_signature,
    extract_docs_from_ast,
    func_to_summary,
    gate_to_summary,
)

__all__ = [
    "ParsedDocComment",
    "parse_doc_comment",
    "build_func_signature",
    "build_gate_signature",
    "extract_docs_from_ast",
    "func_to_summary",
    "gate_to_summary",
]
