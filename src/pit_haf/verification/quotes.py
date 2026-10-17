"""Resolve unique literal quotes to source offsets, allowing whitespace changes only."""

from dataclasses import asdict, dataclass


def normalized_space(text: str) -> str:
    return " ".join(text.split())


def _normalized_with_offsets(text: str) -> tuple[str, list[tuple[int, int]]]:
    chars = []
    spans = []
    for index, char in enumerate(text):
        if char.isspace():
            if chars and chars[-1] == " ":
                spans[-1] = (spans[-1][0], index + 1)
            elif chars:
                chars.append(" ")
                spans.append((index, index + 1))
        else:
            chars.append(char)
            spans.append((index, index + 1))
    if chars and chars[-1] == " ":
        chars.pop()
        spans.pop()
    return "".join(chars), spans


def _positions(text: str, value: str) -> list[int]:
    positions = []
    start = 0
    while len(positions) < 2:
        index = text.find(value, start)
        if index < 0:
            break
        positions.append(index)
        start = index + 1
    return positions


@dataclass(frozen=True)
class QuoteResolution:
    mode: str
    start: int | None = None
    end: int | None = None
    source_quote: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def resolve_quote(context: str, quote: str) -> QuoteResolution:
    """Never normalize numbers, signs, punctuation, case, spelling, or missing words.

    Offsets index the supplied context's Python characters, not PDF bytes/page text.
    Repeated matches are ambiguous. The caller retains the original model output.
    """
    if not quote.strip():
        return QuoteResolution("empty")
    exact = _positions(context, quote)
    if len(exact) > 1:
        return QuoteResolution("ambiguous")
    if exact:
        return QuoteResolution("exact", exact[0], exact[0] + len(quote), quote)
    normalized, spans = _normalized_with_offsets(context)
    target = normalized_space(quote)
    matches = _positions(normalized, target)
    if len(matches) > 1:
        return QuoteResolution("ambiguous")
    if not matches:
        return QuoteResolution("not_found")
    start = spans[matches[0]][0]
    end = spans[matches[0] + len(target) - 1][1]
    return QuoteResolution("whitespace_mapped", start, end, context[start:end])
