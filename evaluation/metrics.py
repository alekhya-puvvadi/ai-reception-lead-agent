"""Small, dependency-free metric helpers for the evaluation harness."""

import re
from typing import Iterable, Optional

_DIGIT_WORDS = {
    "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}


def digits_only(text: Optional[str]) -> str:
    return re.sub(r"\D", "", text or "")


def spoken_digits_to_numbers(text: str) -> str:
    """Replace spoken digits ('nine eight seven') with numerals so they can be compared."""
    words = re.findall(r"[A-Za-z]+|\d+|\S", text or "")
    return " ".join(_DIGIT_WORDS.get(w.lower(), w) for w in words)


def _tokens(text: Optional[str]) -> list[str]:
    return re.findall(r"[\w']+", (text or "").lower())


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate: (substitutions + deletions + insertions) / reference words."""
    ref, hyp = _tokens(reference), _tokens(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    previous = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        current = [i]
        for j, h in enumerate(hyp, start=1):
            cost = 0 if r == h else 1
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost))
        previous = current
    return previous[-1] / len(ref)


def name_match(expected: Optional[str], predicted: Optional[str]) -> bool:
    """True if the first name matches. When no name is expected, none should be predicted."""
    if not expected:
        return not (predicted or "").strip()
    if not predicted:
        return False
    return expected.split()[0].lower() in predicted.lower()


def phone_match(expected: Optional[str], predicted: Optional[str]) -> bool:
    """True if the digits match exactly. When no number is expected, none should be predicted."""
    if not expected:
        return not digits_only(predicted)
    return digits_only(predicted) == digits_only(expected)


def transcript_has_phone(expected: Optional[str], transcript: str) -> bool:
    return bool(expected) and digits_only(expected) in digits_only(spoken_digits_to_numbers(transcript))


def transcript_has_name(expected: Optional[str], transcript: str) -> bool:
    return bool(expected) and expected.split()[0].lower() in (transcript or "").lower()


def rate(flags: Iterable[bool]) -> Optional[float]:
    flags = list(flags)
    return sum(flags) / len(flags) if flags else None
