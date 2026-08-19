"""Result table formatting (Phase 2, Task 2.1)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def format_value(v, fmt: str = ".3g") -> str:
    """Format a single cell, handling None/NaN and short strings."""
    if v is None:
        return "n/a"
    if isinstance(v, float):
        if v != v:  # NaN
            return "n/a"
        return f"{v:{fmt}}"
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v)


def build_table(rows: Sequence[Mapping], columns: Sequence[str]) -> str:
    """Render rows (mappings) as a fixed-width text table limited to `columns`.

    Args:
        rows: list of dicts, one per experiment row.
        columns: the columns to display, in order; keys into the row dicts.

    Returns:
        A padded, left-aligned text table string.
    """
    headers = [str(c) for c in columns]
    body = [[format_value(r.get(c)) for c in columns] for r in rows]
    widths = [
        max([len(headers[i])] + [len(row[i]) for row in body])
        for i in range(len(headers))
    ]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep = "  ".join("-" * w for w in widths)
    lines = [line, sep]
    for row in body:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)


def format_results(rows: Sequence[Mapping], columns: Sequence[str]) -> str:
    """Alias for build_table (keeps the experiment-facing name short)."""
    return build_table(rows, columns)