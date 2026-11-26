"""Simple, explainable matching for Philadelphia's signature foods."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


FOOD_ALIASES: dict[str, tuple[str, ...]] = {
    "Philly Cheesesteak": (
        "philly cheesesteak",
        "philadelphia cheesesteak",
        "cheesesteak",
        "cheese steak",
    ),
    "Roast Pork Sandwich": (
        "roast pork sandwich",
        "roasted pork sandwich",
        "roast pork",
        "pork sandwich",
    ),
    "Hoagie": (
        "hoagie",
        "hoagies",
        "hoagy",
        "hoagys",
    ),
    "Philadelphia Soft Pretzel": (
        "philadelphia soft pretzel",
        "philly soft pretzel",
        "soft pretzel",
        "soft pretzels",
        "pretzel",
        "pretzels",
    ),
    "Tomato Pie": (
        "tomato pie",
        "tomato pies",
    ),
    "Scrapple": ("scrapple",),
    "Water Ice": (
        "water ice",
        "wooder ice",
        "italian ice",
        "gelati",
    ),
}


def normalize_text(text: str) -> str:
    """Normalize capitalization, accents, punctuation, and whitespace."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    lowercase = ascii_text.casefold().replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", lowercase)).strip()


def _token_similar(left: str, right: str) -> bool:
    if left == right:
        return True
    if min(len(left), len(right)) <= 3:
        return False
    if left[0] != right[0] or abs(len(left) - len(right)) > 2:
        return False
    return SequenceMatcher(None, left, right).ratio() >= 0.84


def match_foods(text: str) -> list[str]:
    """Return canonical foods mentioned in review text.

    The matcher combines curated aliases with conservative token-level fuzzy
    matching. This handles capitalization, punctuation, plurals, and modest
    misspellings while keeping every match explainable.
    """
    normalized = normalize_text(text)
    tokens = normalized.split()
    if not tokens:
        return []
    padded = f" {normalized} "
    matches: set[str] = set()
    for food, aliases in NORMALIZED_ALIASES.items():
        if any(f" {' '.join(alias_tokens)} " in padded for alias_tokens in aliases):
            matches.add(food)

    # Fuzzy comparison is limited to distinctive food words and phrases. The
    # first-letter index avoids comparing every word with every alias.
    for index, token in enumerate(tokens):
        for target, food in FUZZY_SINGLE_BY_INITIAL.get(token[0], ()):
            if _token_similar(token, target):
                matches.add(food)
        for phrase, food in FUZZY_PHRASE_BY_INITIAL.get(token[0], ()):
            window = tokens[index : index + len(phrase)]
            if len(window) == len(phrase) and all(
                _token_similar(actual, expected)
                for actual, expected in zip(window, phrase)
            ):
                matches.add(food)
    return [food for food in FOOD_ALIASES if food in matches]


def extract_food_snippets(text: str) -> dict[str, str]:
    """Return only the review sentences that mention each supported food."""
    snippets: dict[str, list[str]] = {}
    sentences = re.split(r"(?<=[.!?])\s+|[\r\n]+", text)
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        for food in match_foods(sentence):
            snippets.setdefault(food, []).append(sentence)
    return {food: " ".join(parts) for food, parts in snippets.items()}


NORMALIZED_ALIASES: dict[str, tuple[tuple[str, ...], ...]] = {
    food: tuple(tuple(normalize_text(alias).split()) for alias in aliases)
    for food, aliases in FOOD_ALIASES.items()
}

FUZZY_SINGLE_BY_INITIAL: dict[str, tuple[tuple[str, str], ...]] = {
    "c": (("cheesesteak", "Philly Cheesesteak"),),
    "h": (("hoagie", "Hoagie"),),
    "p": (("pretzel", "Philadelphia Soft Pretzel"),),
    "s": (("scrapple", "Scrapple"),),
    "g": (("gelati", "Water Ice"),),
}

FUZZY_PHRASE_BY_INITIAL: dict[str, tuple[tuple[tuple[str, ...], str], ...]] = {
    "r": ((('roast', 'pork'), "Roast Pork Sandwich"),),
    "t": ((('tomato', 'pie'), "Tomato Pie"),),
    "w": ((('water', 'ice'), "Water Ice"), (('wooder', 'ice'), "Water Ice")),
    "i": ((('italian', 'ice'), "Water Ice"),),
}
