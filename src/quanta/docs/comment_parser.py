"""
Three-tier parser for /// documentation comments.

Rule 1 (highest): line starts with ``return:`` → return value
Rule 2: ``[Type] [Identifier] - [Description]`` → input parameter
Rule 3 (fallback): summary / prose (optional leading ``-`` bullet)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from ..stdlib.builtins import FunctionParam

# e.g. int, qbit, qint[n], float[3][3], qdec[4, 2]
_PARAM_RE = re.compile(
    r"^(\w+(?:\[[^\]]*\])+|\w+)\s+(\w+)\s-\s*(.+)$"
)


@dataclass(frozen=True)
class ParsedDocComment:
    """Structured documentation parsed from consecutive /// lines."""

    summary_lines: Tuple[str, ...] = ()
    params: Tuple[FunctionParam, ...] = ()
    returns: Optional[str] = None

    @property
    def summary(self) -> str:
        return "\n".join(self.summary_lines)


def _strip_summary_bullet(line: str) -> str:
    if line.startswith("- "):
        return line[2:]
    if line.startswith("-"):
        return line[1:].lstrip()
    return line


def parse_doc_comment(lines: Sequence[str]) -> ParsedDocComment:
    """Parse doc-comment lines using the three-tier rule set."""
    summary_lines: List[str] = []
    params: List[FunctionParam] = []
    returns: Optional[str] = None

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        if line.startswith("return:"):
            returns = line[len("return:") :].strip()
            continue

        param_match = _PARAM_RE.match(line)
        if param_match:
            type_name, ident, description = param_match.groups()
            params.append(FunctionParam(ident, type_name, description.strip()))
            continue

        summary_lines.append(_strip_summary_bullet(line))

    return ParsedDocComment(
        summary_lines=tuple(summary_lines),
        params=tuple(params),
        returns=returns,
    )
