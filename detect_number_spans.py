import re
from dataclasses import dataclass
from typing import List, Literal
import pandas as pd

NumberKind = Literal[
    "YEAR", "ZIP", "PHONE", "CAR_PLATE", "ORDINAL",
    "MONEY", "MODEL", "NUMBER"
]

@dataclass
class NumberSpan:
    kind: NumberKind
    text: str
    start: int
    end: int

# --- regexes as before (shortened here) ---

YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")
ZIP_RE_RAW = re.compile(r"\b[1-9]\d{3}\b")
PHONE_RE = PHONE_RE = re.compile(
    r"""
    (?:
        (?:\+|00)
        [1-9]\d{0,2}
        (?:[\s\-/.()]*\d){6,12}
    )
    |
    (?:
        0\d
        (?:[\s\-/.()]*\d){7,10} 
    )
    """,
    re.VERBOSE,
)

CANTON_CODES = (
    "AG|AI|AR|BE|BL|BS|FR|GE|GL|GR|JU|LU|NE|NW|OW|SG|SH|SO|SZ|TG|TI|UR|VD|VS|ZG|ZH"
)
CAR_PLATE_RE = re.compile(
    rf"\b(?:{CANTON_CODES})\s?\d{{1,6}}\b"
)

ORDINAL_RE = re.compile(r"\b\d+\.(?=\s|$)")
MONEY_RE = re.compile(
    r"""
    (?:
        (?:CHF|SFr\.?|Fr\.?)\s*
        \d{1,3}(?:[\'’\s]\d{3})*
        (?:[.,]\d{1,2})?[-–.]?
    )
    |
    (?:
        \d{1,3}(?:[\'’\s]\d{3})*
        (?:[.,]\d{1,2})?\s*
        (?:CHF|SFr\.?|Fr\.?)
    )
    """,
    re.VERBOSE,
)
MODEL_RE = re.compile(
    r"\b(?=[A-Za-z0-9_-]*[A-Za-z])(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{3,}\b"
)
PLAIN_NUMBER_RE = re.compile(r"\b\d+(?:[’']\d{3})*(?:[.,]\d+)?\b")

SWISS_PLZ_PLACES = list(pd.read_csv("./helper_data/PLZ_Ortschaften.csv",sep=";",decimal=",")["Ortschaftsname"].drop_duplicates().str.lower())

ZIP_RE_RAW = re.compile(r"\b[1-9]\d{3}\b")
ZIP_CONTEXT_LEFT_RE = re.compile(r"(plz|PLZ|Postleitzahl|CH-?|CH\s*)\s*$", re.IGNORECASE)
ZIP_CONTEXT_RIGHT_RE = re.compile(r"^\s*(CH|Schweiz)\b", re.IGNORECASE)


def _has_place_after(text: str, end: int) -> bool:
    """
    Check if a known place name follows directly after the number.
    Handles multi-word names, accents, hyphens, apostrophes.
    """
    # Look ahead up to ~25 characters
    right_ctx = text[end:end + 25]

    place_regex = re.compile(
    r"""
    \s*(
        # --- St.-like names: St. Gallen / St Gallen / St.Gallen / StGallen / St. Moritz ---
        (?:St\.?\s*[A-ZÀ-ÖØ][A-Za-zÀ-ÖØ-öø-ÿ]*
            (?:[-'’][A-Za-zÀ-ÖØ-öø-ÿ]+)*
            (?:\s+[A-ZÀ-ÖØ][A-Za-zÀ-ÖØ-öø-ÿ]*
                (?:[-'’][A-Za-zÀ-ÖØ-öø-ÿ]+)*
            )*
        )
        |
        # --- Generic multi-word place names: La Chaux-de-Fonds, Bad Ragaz, Neu-Sankt-Johann, ... ---
        (?:[A-ZÀ-ÖØ][A-Za-zÀ-ÖØ-öø-ÿ]*
            (?:[-'’][A-Za-zÀ-ÖØ-öø-ÿ]+)*
            (?:\s+[A-ZÀ-ÖØ][A-Za-zÀ-ÖØ-öø-ÿ]*
                (?:[-'’][A-Za-zÀ-ÖØ-öø-ÿ]+)*
            )*
        )
    )
    """,
    re.VERBOSE)
    m = place_regex.match(right_ctx)
    
    if not m:
        return False

    candidate = m.group(1).strip().lower()
    return candidate in SWISS_PLZ_PLACES



def _has_zip_context(text: str, start: int, end: int, zip_code: str) -> bool:
    """
    Heuristik:
    - Links: PLZ / Postleitzahl / CH-
    - Rechts: 'CH' / 'Schweiz'
    - Oder: bekannte Ortsnamen-Datenbank: '4410 Liestal'
    """
    left_ctx = text[max(0, start - 20):start]
    right_ctx = text[end:end + 20]

    if ZIP_CONTEXT_LEFT_RE.search(left_ctx):
        return True
    if ZIP_CONTEXT_RIGHT_RE.search(right_ctx):
        return True
    if _has_place_after(text, end):
        return True
    return False


def _add_matches(text: str, regex, kind: NumberKind, out: List[NumberSpan]):
    for m in regex.finditer(text):
        out.append(NumberSpan(
            kind=kind,
            text=m.group(0),
            start=m.start(),
            end=m.end(),
        ))


def detect_number_spans(text: str) -> List[NumberSpan]:
    spans: List[NumberSpan] = []

    # Specific types first
    _add_matches(text, PHONE_RE, "PHONE", spans)
    _add_matches(text, CAR_PLATE_RE, "CAR_PLATE", spans)
    _add_matches(text, MONEY_RE, "MONEY", spans)
    _add_matches(text, ORDINAL_RE, "ORDINAL", spans)
    _add_matches(text, YEAR_RE, "YEAR", spans)

    # ZIP: only add if context suggests it's really a PLZ
    for m in ZIP_RE_RAW.finditer(text):
        zip_code = m.group(0)
        if _has_zip_context(text, m.start(), m.end(), zip_code):
            spans.append(NumberSpan(
                kind="ZIP",
                text=zip_code,
                start=m.start(),
                end=m.end(),
            ))

    _add_matches(text, MODEL_RE, "MODEL", spans)
    _add_matches(text, PLAIN_NUMBER_RE, "NUMBER", spans)

    # --- overlap resolution as before ---
    spans.sort(key=lambda s: (s.start, -(s.end - s.start)))

    filtered: List[NumberSpan] = []
    for span in spans:
        # if this span is fully inside an already kept span, skip it
        if any(span.start >= s.start and span.end <= s.end for s in filtered):
            continue

        # if overlapping partially with an earlier span, we keep the first one
        if any(not (span.end <= s.start or span.start >= s.end) for s in filtered):
            continue

        filtered.append(span)

    return filtered
