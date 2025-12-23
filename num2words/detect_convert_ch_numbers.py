import re
from dataclasses import dataclass
from typing import List, Literal, Optional, Dict
import pandas as pd
import spacy
from num2words.num2words_CH import num2words
from py_heideltime.py_heideltime import heideltime


NumberKind = Literal[
    "YEAR", "ZIP", "PHONE", "CAR_PLATE", "ORDINAL",
    "MONEY", "MODEL", "NUMBER", "TIME"
]
convert_numbers_to_int = lambda number: int(number) if number.isdigit() else None

@dataclass
class NumberSpan:
    kind: NumberKind
    text: str
    start: int
    end: int
    value: Optional[str] = None


DATE_PATTERN = re.compile(
    r"""
    (?P<YEAR>\d{4}|XXXX)      # year
    -
    (?P<MONTH>\d{0,2}|XX)       # month
    -
    (?P<DAY>\d{0,2}|XX)       # day (can be missing or cut off)
    """,
    re.VERBOSE
)

def extract_date_parts(value: str) -> Dict[str, Optional[int]]:
    if len(value) == 4:
        value += "-XX-XX"
    if len(value) == 7:
        value += "-XX"
    match = DATE_PATTERN.search(value)
    if not match:
        return {"YEAR": None, "MONTH": None, "DAY": None}

    def parse(part):
        if part in (None, "", "XX", "XXXX"):
            return None
        return int(part)

    return {
        "YEAR": parse(match.group("YEAR")),
        "MONTH": parse(match.group("MONTH")),
        "DAY": parse(match.group("DAY")),
    }

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
TIME_RE = re.compile(r"\b([0-1]?[0-9]|2[0-3])[:.]([0-5][0-9])(?:[:.]([0-5][0-9]))?\b")
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
PLAIN_NUMBER_RE = re.compile(r"\d+(?:[’']\d{3})*(?:[.,]\d+)?")

SWISS_PLZ_PLACES = list(pd.read_csv("./helper_data/PLZ_Ortschaften.csv",sep=";",decimal=",")["Ortschaftsname"].drop_duplicates().str.lower())

ZIP_RE_RAW = re.compile(r"\b[1-9]\d{3}\b")
ZIP_CONTEXT_LEFT_RE = re.compile(r"(plz|PLZ|Postleitzahl|CH-?|CH\s*)\s*$", re.IGNORECASE)
ZIP_CONTEXT_RIGHT_RE = re.compile(r"^\s*(CH|Schweiz)\b", re.IGNORECASE)

# Load Spacy model for ordinal verification
try:
    nlp = spacy.load("de_core_news_sm")
except:
    raise OSError("Spacy model 'de_core_news_sm' not found. Download the modell first.")


def _is_ordinal_context(text: str, start: int, end: int):
    """
    Use Spacy NLP to verify if a number with period is used as an ordinal in German.
    German ordinals are typically preceded by a determiner/article (e.g., "der 2.", "die 1.")
    or followed by a noun. Returns False if it's just a number at end of sentence.
    """    
    # Extract the number without the period
    number_match = re.match(r"(\d+)", text[start:end])
    if not number_match:
        return False
    
    number_str = number_match.group(1)
    
    # Look at context before and after the number
    context_start = max(0, start - 30)
    context_end = min(len(text), end + 30)
    context = text[context_start:context_end]
    
    # Process with Spacy
    doc = nlp(context)
    
    # Find the token corresponding to our number in the doc
    offset = start - context_start
    ordinal_token = None
    for token in doc:
        if token.idx >= offset and token.idx < offset + len(number_str):
            ordinal_token = token
            break
    
    if ordinal_token is None:
        return False,None
    
    prev_token = ordinal_token.nbor(-1) if ordinal_token.i > 0 else None
    if prev_token and prev_token.pos_ in ["DET", "ADP"]:
        try:
            declension_type = get_declension_type(ordinal_token)
            gender = ordinal_token.morph.get("Gender")[0]
            case = ordinal_token.morph.get("Case")[0]

            if ordinal_token.morph.get("Number") == ["Plur"]:
                gender = "Plur"
            return True,{"declension":declension_type.lower(),"gender":gender.lower(),"case":case.lower()}

        except:
            return False,None
            
    
    return False,None


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
    """
    Add regex matches as NumberSpans.
    For ORDINAL kind, verify with Spacy that it's actually used as an ordinal.
    """
    for m in regex.finditer(text):
        # Special handling for ordinals: verify with Spacy
        if kind == "ORDINAL":
            is_ordinal, type_of_ordinal = _is_ordinal_context(text, m.start(), m.end())
            if not is_ordinal:
                continue  # Skip this match if it's not a true ordinal
            else:
                out.append(NumberSpan(
                    kind=kind,
                    text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    value=type_of_ordinal
                ))
        
        out.append(NumberSpan(
            kind=kind,
            text=m.group(0),
            start=m.start(),
            end=m.end(),
        ))


def detect_number_spans(text: str) -> List[NumberSpan]:
    spans: List[NumberSpan] = []

    try:
        timexs = heideltime(
            text,
            language='german',
            document_type='scientific',
            dct=None,
        )
        for timex in timexs:
            if "span" in timex and isinstance(timex["span"], (list, tuple)) and timex["type"] in ["DATE", "TIME"]:
                s, e = timex["span"]
                s -=1
                e -=1
                # Guard against invalid spans
                if 0 <= s < e <= len(text):
                    if timex["type"] in ["TIME"]:
                        value =timex.get("value").split("T")[1]
                        value_to_append= {"HOUR": convert_numbers_to_int(value[-5:-3]),
                                    "MINUTE": convert_numbers_to_int(value[-2:])}.copy()
                        
                    elif timex["type"] in ["DATE"]:
                        value = timex.get("value")
                        # Remove leading "Jahr " only if followed by a full year
                        m_start = re.match(r"^Jahr\s+(?=\d{4}\b)", timex["text"])
                        if m_start:
                            delta = m_start.end()
                            s += delta

                        # Remove trailing " Jahr" only if preceded by a full year
                        m_end = re.search(r"(?<=\b\d{4})\s+Jahr$", timex["text"])
                        if m_end:
                            delta = len(timex["text"]) - m_end.start()
                            e -= delta

                        value_to_append= extract_date_parts(value)
                    spans.append(NumberSpan(kind=timex["type"], text=timex.get("text"), start=s, end=e,value=value_to_append))
    except Exception:
        pass
    # Specific types first
    _add_matches(text, PHONE_RE, "PHONE", spans)
    #_add_matches(text, CAR_PLATE_RE, "CAR_PLATE", spans)
    #_add_matches(text, MONEY_RE, "MONEY", spans)
    #_add_matches(text, TIME_RE, "TIME", spans)
    _add_matches(text, ORDINAL_RE, "ORDINAL", spans)
    #_add_matches(text, YEAR_RE, "YEAR", spans)

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

    #_add_matches(text, MODEL_RE, "MODEL", spans)
    _add_matches(text, PLAIN_NUMBER_RE, "NUMBER", spans)

    # --- overlap resolution with priority ---
    # Priority order: DATE/TIME > PHONE > ZIP > ORDINAL > NUMBER
    KIND_PRIORITY = {
        "DATE": 0,
        "TIME": 0,
        "PHONE": 1,
        "ZIP": 2,
        "ORDINAL": 3,
        "YEAR": 4,
        "MONEY": 5,
        "CAR_PLATE": 6,
        "MODEL": 7,
        "NUMBER": 8,
    }
    
    # Sort by: priority first, then start position, then longest span
    spans.sort(key=lambda s: (KIND_PRIORITY.get(s.kind, 99), s.start, -(s.end - s.start)))

    filtered: List[NumberSpan] = []
    for span in spans:
        # if this span is fully inside an already kept span, skip it
        if any(span.start >= s.start and span.end <= s.end for s in filtered):
            continue

        # if overlapping partially with an earlier span, we keep the first one (higher priority)
        if any(not (span.end <= s.start or span.start >= s.end) for s in filtered):
            continue

        filtered.append(span)

    return filtered



def convert_numbers(text: str,dialect) -> str:
    spans = detect_number_spans(text)

    # Work from end to start so indices stay valid when we modify the string
    spans.sort(key=lambda s: s.start, reverse=True)
    out = text

    for span in spans:
        number = span.text

        if span.kind == "NUMBER":
            number_str = number
            leading_zeros = len(number_str) - len(number_str.lstrip('0'))
            
            if leading_zeros > 0:
                zero_part = " ".join([num2words("0", lang=dialect) for _ in range(leading_zeros)])
                if leading_zeros == len(number_str):
                    number = zero_part
                else:
                    number = zero_part + " " + num2words(number_str[leading_zeros:], lang=dialect)
            else:
                number = num2words(number, lang=dialect)
        elif span.kind == "ZIP":
            if len(number) == 4:
                if number[1] == "000":
                    number = num2words(number, lang=dialect)
                elif number[2] == "0":
                    number = num2words(number[:2], lang=dialect) + " " + num2words(0, lang=dialect) + " " + num2words(number[3], lang=dialect)
                else:
                    number = num2words(number[:2], lang=dialect) + " " + num2words(number[2:], lang=dialect)

        elif span.kind == "PHONE":
            cleaned_number = number.replace(" ","")
            number = ""
            if cleaned_number.startswith("+"):
                number = "plus"
            for digit in cleaned_number.lstrip("+"):
                number += " " + num2words(digit, lang=dialect) 

        elif span.kind == "ORDINAL":
            number = num2words(number[:-1], lang=dialect, ordinal=True,declension=span.value)

        elif span.kind == "TIME":
                hours = span.value.get("HOUR")
                minutes = span.value.get("MINUTE")
                seconds = span.value.get("SECOND")
                if (minutes == 25) or (minutes >= 30):
                    hours += 1
                if hours > 12:
                    hours -= 12
                number = num2words(hours, to="hours", lang=dialect)

                # Convert minutes
                if minutes > 0:
                    number = num2words(minutes, to="minutes", lang=dialect) + " " + number
        
                
                # Convert seconds if present
                if seconds is not None and seconds > 0:
                    number += " " + num2words(seconds, lang=dialect) + num2words("sek",to="lookup", dialect="ch_bs")
                
        elif span.kind == "DATE": # TODO: include declension
            value = span.value
            year = value.get("YEAR")
            month = value.get("MONTH")
            day = value.get("DAY")
            date_parts = []
            if day is not None:                
                date_parts.append(num2words(day, lang=dialect, ordinal=True,declension= {'declension': 'gemischt', 'gender': 'masc', 'case': 'nom'}))
            if month is not None:
                date_parts.append(num2words(month, lang=dialect,to="month_dates"))
            if year is not None:
                year = str(year)
                if (len(year) == 4) and (int(year) <= 1999):
                    date_parts.append(num2words(year[:2], lang=dialect) + " " + num2words(year[2:], lang=dialect))
                else:
                    date_parts.append(num2words(year, lang=dialect))
            number = " ".join(date_parts)

                    

        out = out[:span.start] + number + out[span.end:]

    return out


def get_declension_type(adj_token):
    """
    adj_token: spaCy-Token des Adjektivs/Ordinalwortes (z.B. 'zweite', 'dritte')
    Rückgabe: 'weak', 'mixed', 'strong'
    """
    # Artikel zum Adjektiv suchen (im selben Nominalausdruck)
    article = None
    for child in adj_token.head.children:
        if child.pos_ == "DET":
            article = child
            break

    if article:
        morph = article.morph
        # bestimmter Artikel: der, die, das, dieser, jener, solcher, welcher
        if "Definite=Def" in morph:
            return "schwach"
        # unbestimmter/possessiver Artikel: ein, kein, mein, dein, sein, ihr, unser, euer, Ihr
        if "Definite=Ind" in morph:
            return "gemischt"
        # falls spaCy etwas Spezielles taggt
        return "gemischt"
    else:
        # kein Artikel → starke Deklination
        return "stark"