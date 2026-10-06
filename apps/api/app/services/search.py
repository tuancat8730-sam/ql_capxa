"""Global search helpers (SPEC 4.16): diacritic-free matching and result snippets."""

import unicodedata

SNIPPET_WIDTH = 60
MIN_QUERY_LENGTH = 2


def escape_like(value: str) -> str:
    """Make `%`, `_` and `\\` literal inside an ILIKE pattern."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def fold(text: str) -> str:
    """Lower-case and strip Vietnamese marks, one output character per input character.

    Keeping the length equal lets a match position in the folded text point into the original,
    so a snippet can be cut from the real (accented) text.
    """
    out: list[str] = []
    for ch in text:
        if ch in "đĐ":
            out.append("d")
            continue
        base = unicodedata.normalize("NFD", ch)[:1] or ch
        out.append(base.lower() if len(base) == 1 else ch.lower())
    return "".join(out)


def snippet(text: str | None, query: str, width: int = SNIPPET_WIDTH) -> str | None:
    """A short excerpt around the first match of `query` (accent- and case-insensitive)."""
    if not text:
        return None
    flat = unicodedata.normalize("NFC", " ".join(text.split()))
    needle = fold(unicodedata.normalize("NFC", query.strip()))
    if not needle:
        return None
    at = fold(flat).find(needle)
    if at < 0:
        return None
    start = max(0, at - width)
    end = min(len(flat), at + len(needle) + width)
    cut = flat[start:end]
    return f"{'…' if start else ''}{cut}{'…' if end < len(flat) else ''}"


def first_snippet(query: str, *fields: str | None) -> str | None:
    """Excerpt from the first field that contains the query."""
    for value in fields:
        found = snippet(value, query)
        if found:
            return found
    return None
