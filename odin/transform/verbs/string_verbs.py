"""String verbs: capitalize, titleCase, contains, startsWith, endsWith, replace, pad, etc."""

from __future__ import annotations

import math
import re
import unicodedata
from typing import List

from odin.transform.dyn_value import DynValue, DynType
from odin.transform.verbs.helpers import coerce_str, coerce_num, split_words, numeric_result

MAX_STRING_REPEAT = 10000
MAX_LEVENSHTEIN_LENGTH = 1000


def verb_capitalize(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    if not s:
        return DynValue.of_string("")
    return DynValue.of_string(s[0].upper() + s[1:].lower())


def verb_title_case(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    if not s:
        return DynValue.of_string("")
    words = re.split(r"\s+", s)
    result = " ".join(w[0].upper() + w[1:].lower() if w else "" for w in words)
    return DynValue.of_string(result)


def verb_contains(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_bool(False)
    s = coerce_str(args[0])
    sub = coerce_str(args[1])
    return DynValue.of_bool(sub in s)


def verb_starts_with(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_bool(False)
    s = coerce_str(args[0])
    prefix = coerce_str(args[1])
    return DynValue.of_bool(s.startswith(prefix))


def verb_ends_with(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_bool(False)
    s = coerce_str(args[0])
    suffix = coerce_str(args[1])
    return DynValue.of_bool(s.endswith(suffix))


def verb_replace(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 3 or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    old = coerce_str(args[1])
    new = coerce_str(args[2])
    return DynValue.of_string(s.replace(old, new))


def verb_replace_regex(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 3 or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    pattern = coerce_str(args[1])
    replacement = coerce_str(args[2])
    try:
        if len(pattern) > 256 or len(s) > 100000:
            return DynValue.of_null()
        result = re.sub(pattern, replacement, s)
        return DynValue.of_string(result)
    except re.error:
        return DynValue.of_null()


def verb_pad_left(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2 or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    width_val = coerce_num(args[1])
    if width_val is None:
        return DynValue.of_null()
    width = int(width_val)
    pad_char = _get_pad_char(args, 2)
    return DynValue.of_string(s.rjust(width, pad_char))


def verb_pad_right(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2 or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    width_val = coerce_num(args[1])
    if width_val is None:
        return DynValue.of_null()
    width = int(width_val)
    pad_char = _get_pad_char(args, 2)
    return DynValue.of_string(s.ljust(width, pad_char))


def verb_pad(args: List[DynValue], ctx: object) -> DynValue:
    """Pad on the right (alias for padRight)."""
    if len(args) < 3:
        return DynValue.of_null()
    s = coerce_str(args[0])
    width_val = coerce_num(args[1])
    if width_val is None:
        return DynValue.of_null()
    width = int(width_val)
    pad_char = _get_pad_char(args, 2)
    if len(s) >= width:
        return DynValue.of_string(s)
    return DynValue.of_string(s + pad_char * (width - len(s)))


def verb_truncate(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2 or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    max_len_val = coerce_num(args[1])
    if max_len_val is None:
        return DynValue.of_null()
    max_len = int(max_len_val)
    ellipsis = ""
    if len(args) >= 3:
        ellipsis = coerce_str(args[2])
    if len(s) <= max_len:
        return DynValue.of_string(s)
    if ellipsis and max_len > len(ellipsis):
        return DynValue.of_string(s[:max_len - len(ellipsis)] + ellipsis)
    return DynValue.of_string(s[:max_len])


def verb_split(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2 or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    delim = coerce_str(args[1])
    parts = s.split(delim) if delim else [s]

    if len(args) >= 3:
        idx_val = coerce_num(args[2])
        if idx_val is None:
            return DynValue.of_null()
        idx = int(idx_val)
        # Handle negative indices
        if idx < 0:
            idx = len(parts) + idx
        if 0 <= idx < len(parts):
            return DynValue.of_string(parts[idx])
        return DynValue.of_null()

    return DynValue.of_array([DynValue.of_string(p) for p in parts])


def verb_join(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2 or args[0].is_null():
        return DynValue.of_null()
    arr = args[0]
    delim = coerce_str(args[1])

    if arr.is_array():
        items = arr.as_array()
        parts = [coerce_str(item) for item in items]
        return DynValue.of_string(delim.join(parts))
    # If it's a string, just return it
    if arr.is_string():
        return arr
    return DynValue.of_null()


def verb_mask(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2 or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    pattern = coerce_str(args[1])
    result = []
    si = 0
    for ch in pattern:
        if si >= len(s):
            break
        if ch == "#" or ch == "A" or ch == "*":
            result.append(s[si])
            si += 1
        else:
            result.append(ch)
    return DynValue.of_string("".join(result))


def verb_reverse_string(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    return DynValue.of_string(s[::-1])


def verb_repeat(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2 or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    count_val = coerce_num(args[1])
    if count_val is None:
        return DynValue.of_null()
    count = int(count_val)
    if count < 0:
        return DynValue.of_null()
    if count > MAX_STRING_REPEAT:
        count = MAX_STRING_REPEAT
    return DynValue.of_string(s * count)


def verb_substring(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    start = 0
    if len(args) >= 2:
        sv = coerce_num(args[1])
        if sv is not None:
            start = int(sv)
    length = None
    if len(args) >= 3:
        lv = coerce_num(args[2])
        if lv is not None:
            length = int(lv)
    if start < 0:
        start = 0
    if start >= len(s):
        return DynValue.of_string("")
    if length is not None:
        end = start + length
        return DynValue.of_string(s[start:end])
    return DynValue.of_string(s[start:])


def verb_length(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_integer(0)
    v = args[0]
    if v.is_null():
        return DynValue.of_integer(0)
    if v.is_string():
        return DynValue.of_integer(len(v.as_string()))
    if v.is_array():
        return DynValue.of_integer(len(v.as_array()))
    if v.is_object():
        return DynValue.of_integer(len(v.as_object()))
    return DynValue.of_integer(len(coerce_str(v)))


def verb_camel_case(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    if not s:
        return DynValue.of_string("")
    words = split_words(s)
    if not words:
        return DynValue.of_string("")
    result = words[0].lower()
    for w in words[1:]:
        if w:
            result += w[0].upper() + w[1:].lower()
    return DynValue.of_string(result)


def verb_pascal_case(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    if not s:
        return DynValue.of_string("")
    words = split_words(s)
    if not words:
        return DynValue.of_string("")
    result = "".join(w[0].upper() + w[1:].lower() for w in words if w)
    return DynValue.of_string(result)


def verb_snake_case(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    if not s:
        return DynValue.of_string("")
    words = split_words(s)
    return DynValue.of_string("_".join(w.lower() for w in words if w))


def verb_kebab_case(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    if not s:
        return DynValue.of_string("")
    words = split_words(s)
    return DynValue.of_string("-".join(w.lower() for w in words if w))


def verb_slugify(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    if not s:
        return DynValue.of_string("")
    s = s.lower()
    # Drop everything that is not ASCII word char, whitespace, or hyphen
    s = re.sub(r"[^A-Za-z0-9_\s-]", "", s)
    # Whitespace and underscores become hyphens
    s = re.sub(r"[\s_]+", "-", s)
    # Collapse repeated hyphens
    s = re.sub(r"-+", "-", s)
    # Trim leading/trailing hyphens
    s = s.strip("-")
    return DynValue.of_string(s)


def verb_match(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    s = coerce_str(args[0])
    pattern = coerce_str(args[1])
    try:
        if len(pattern) > 256 or len(s) > 100000:
            return DynValue.of_null()
        m = re.search(pattern, s)
        return DynValue.of_bool(m is not None)
    except re.error:
        return DynValue.of_null()


def verb_matches(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    s = coerce_str(args[0])
    pattern = coerce_str(args[1])
    try:
        if len(pattern) > 256 or len(s) > 100000:
            return DynValue.of_null()
        m = re.search(pattern, s)
        return DynValue.of_bool(m is not None)
    except re.error:
        return DynValue.of_null()


def verb_extract(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    s = coerce_str(args[0])
    pattern = coerce_str(args[1])
    group = 0
    if len(args) >= 3:
        gv = coerce_num(args[2])
        if gv is not None:
            group = int(gv)
    try:
        if len(pattern) > 256 or len(s) > 100000:
            return DynValue.of_null()
        m = re.search(pattern, s)
        if m is None:
            return DynValue.of_null()
        if group == 0:
            return DynValue.of_string(m.group(0))
        if group <= len(m.groups()):
            g = m.group(group)
            return DynValue.of_string(g) if g is not None else DynValue.of_null()
        return DynValue.of_null()
    except (re.error, IndexError):
        return DynValue.of_null()


def verb_normalize_space(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    return DynValue.of_string(re.sub(r"\s+", " ", s).strip())


def verb_left_of(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2 or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    delim = coerce_str(args[1])
    idx = s.find(delim)
    if idx < 0:
        return DynValue.of_string(s)
    return DynValue.of_string(s[:idx])


def verb_right_of(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2 or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    delim = coerce_str(args[1])
    idx = s.find(delim)
    if idx < 0:
        return DynValue.of_string("")
    return DynValue.of_string(s[idx + len(delim):])


def verb_wrap(args: List[DynValue], ctx: object) -> DynValue:
    """Word-wrap a string to a width, joining lines with newlines."""
    import re
    if len(args) < 2 or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    width_val = coerce_num(args[1])
    if width_val is None:
        return DynValue.of_null()
    width = int(width_val)
    if width <= 0:
        return DynValue.of_null()
    if len(s) <= width:
        return DynValue.of_string(s)
    lines: List[str] = []
    current_line = ""
    for word in re.split(r"\s+", s):
        if not current_line:
            current_line = word
        elif len(current_line) + 1 + len(word) <= width:
            current_line += " " + word
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return DynValue.of_string("\n".join(lines))


def verb_center(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2 or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    width_val = coerce_num(args[1])
    if width_val is None:
        return DynValue.of_null()
    width = int(math.floor(width_val))
    pad_char = " "
    if len(args) >= 3:
        pc = coerce_str(args[2])
        if pc:
            pad_char = pc[0]
    if width <= 0:
        return DynValue.of_null()
    if len(s) >= width:
        return DynValue.of_string(s)
    total = width - len(s)
    left = total // 2
    right = total - left
    return DynValue.of_string(pad_char * left + s + pad_char * right)


def verb_strip_accents(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    return DynValue.of_string(_remove_accents(s))


def verb_clean(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    # Remove ASCII control chars except \t \n \r
    result = []
    for ch in s:
        cp = ord(ch)
        if (0x00 <= cp <= 0x1F or cp == 0x7F) and ch not in ("\t", "\n", "\r"):
            continue
        # Replace non-breaking spaces (U+00A0) with regular spaces
        if cp == 0x00A0:
            result.append(" ")
        else:
            result.append(ch)
    cleaned = "".join(result)
    # Normalize whitespace: trim and collapse internal whitespace to single spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return DynValue.of_string(cleaned)


def verb_word_count(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_integer(0)
    s = coerce_str(args[0])
    words = s.split()
    return DynValue.of_integer(len(words))


def verb_tokenize(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_array([])
    s = coerce_str(args[0])
    if not s:
        return DynValue.of_array([])
    delim = coerce_str(args[1]) if len(args) >= 2 else ""
    if delim == "":
        tokens = [t for t in s.split() if t]
    else:
        tokens = [t.strip() for t in s.split(delim)]
        tokens = [t for t in tokens if t]
    return DynValue.of_array([DynValue.of_string(t) for t in tokens])


def verb_levenshtein(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2 or args[0].is_null() or args[1].is_null():
        return DynValue.of_null()
    a = coerce_str(args[0])
    b = coerce_str(args[1])
    if len(a) > MAX_LEVENSHTEIN_LENGTH or len(b) > MAX_LEVENSHTEIN_LENGTH:
        return DynValue.of_null()
    m, n = len(a), len(b)
    if m == 0:
        return DynValue.of_integer(n)
    if n == 0:
        return DynValue.of_integer(m)
    # Space-optimized DP
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        curr = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = curr
    return DynValue.of_integer(prev[n])


def verb_soundex(args: List[DynValue], ctx: object) -> DynValue:
    if not args or args[0].is_null():
        return DynValue.of_null()
    s = coerce_str(args[0])
    if not s:
        return DynValue.of_null()
    # Remove non-alpha
    s = "".join(ch for ch in s if ch.isalpha())
    if not s:
        return DynValue.of_null()
    s = s.upper()
    code_map = {
        "B": "1", "F": "1", "P": "1", "V": "1",
        "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
        "D": "3", "T": "3",
        "L": "4",
        "M": "5", "N": "5",
        "R": "6",
    }
    result = [s[0]]
    prev_code = code_map.get(s[0], "0")
    for ch in s[1:]:
        code = code_map.get(ch, "0")
        if ch in ("H", "W"):
            # H and W don't update prev_code - they are transparent
            continue
        if code != "0" and code != prev_code:
            result.append(code)
            if len(result) == 4:
                break
        # Vowels (A,E,I,O,U,Y) reset the prev_code so same-coded letters
        # separated by a vowel get coded separately
        if code == "0":
            prev_code = "0"
        else:
            prev_code = code
    while len(result) < 4:
        result.append("0")
    return DynValue.of_string("".join(result))


# ── Helpers ────────────────────────────────────────────────────────────────────


def _get_pad_char(args: List[DynValue], idx: int) -> str:
    if idx < len(args) and not args[idx].is_null():
        s = coerce_str(args[idx])
        if s:
            return s[0]
    return " "


def _remove_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in nfkd if unicodedata.category(ch) != "Mn")


# ── formatPhone ───────────────────────────────────────────────────────────────

import re as _re


def verb_format_phone(args: List[DynValue], ctx: object) -> DynValue:
    """Format a phone number by country code."""
    if len(args) < 2:
        return DynValue.of_null()

    raw = coerce_str(args[0])
    country = coerce_str(args[1]).upper()

    # Strip non-digit characters
    digits = _re.sub(r"\D", "", raw)

    if country in ("US", "CA"):
        d = digits[1:] if len(digits) == 11 and digits[0] == "1" else digits
        if len(d) != 10:
            return DynValue.of_string(raw)
        return DynValue.of_string(f"({d[:3]}) {d[3:6]}-{d[6:]}")
    elif country == "GB":
        d = digits[2:] if digits.startswith("44") else digits
        if len(d) < 10 or len(d) > 11:
            return DynValue.of_string(raw)
        return DynValue.of_string(f"+44 {d[:4]} {d[4:]}")
    elif country == "DE":
        d = digits[2:] if digits.startswith("49") else digits
        if len(d) < 10 or len(d) > 11:
            return DynValue.of_string(raw)
        return DynValue.of_string(f"+49 {d[:4]} {d[4:]}")
    elif country == "FR":
        d = digits[2:] if digits.startswith("33") else digits
        if len(d) != 9:
            return DynValue.of_string(raw)
        return DynValue.of_string(f"+33 {d[0]} {d[1:3]} {d[3:5]} {d[5:7]} {d[7:]}")
    elif country == "AU":
        d = digits[2:] if digits.startswith("61") else digits
        if len(d) != 9:
            return DynValue.of_string(raw)
        return DynValue.of_string(f"+61 {d[0]} {d[1:5]} {d[5:]}")
    elif country == "JP":
        d = digits[2:] if digits.startswith("81") else digits
        if len(d) < 10 or len(d) > 11:
            return DynValue.of_string(raw)
        return DynValue.of_string(f"+81 {d[:2]}-{d[2:6]}-{d[6:]}")
    else:
        return DynValue.of_string(raw)


_HTML_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}


def verb_escape_html(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    s = coerce_str(args[0])
    return DynValue.of_string(re.sub(r"[&<>\"']", lambda m: _HTML_ESCAPES[m.group(0)], s))


def verb_unescape_html(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    s = coerce_str(args[0])
    named = {
        "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"',
        "&apos;": "'", "&#39;": "'",
    }
    s = re.sub(r"&(?:amp|lt|gt|quot|apos|#39);", lambda m: named[m.group(0)], s)
    s = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), s)
    s = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), s)
    return DynValue.of_string(s)


def verb_escape_xml(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    s = coerce_str(args[0])

    def repl(m: "re.Match") -> str:
        c = m.group(0)
        if c == "'":
            return "&apos;"
        return _HTML_ESCAPES[c]

    return DynValue.of_string(re.sub(r"[&<>\"']", repl, s))


def verb_strip_tags(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    s = coerce_str(args[0])
    return DynValue.of_string(re.sub(r"<[^>]*>", "", s))


def verb_template(args: List[DynValue], ctx: object) -> DynValue:
    if len(args) < 2:
        return DynValue.of_null()
    tpl = coerce_str(args[0])
    src = args[1]
    fields = src.as_object() if src.is_object() else {}

    def repl(m: "re.Match") -> str:
        key = m.group(1).strip()
        v = fields.get(key)
        if v is None or v.is_null():
            return ""
        return coerce_str(v)

    return DynValue.of_string(re.sub(r"\{([^{}]+)\}", repl, tpl))
