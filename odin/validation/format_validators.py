"""Format validators for ODIN Schema validation.

Provides validation functions for common formats (email, URL, UUID, IPv4, IPv6,
date, time, timestamp, hostname, regex, phone, zip, VIN, FEIN, NAIC, SSN,
credit card, currency code, country codes, US states).

Each validator is a pure function: str -> bool.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

CURRENCY_CODES = frozenset([
    "AED", "AFN", "ALL", "AMD", "ANG", "AOA", "ARS", "AUD", "AWG", "AZN",
    "BAM", "BBD", "BDT", "BGN", "BHD", "BIF", "BMD", "BND", "BOB", "BRL",
    "BSD", "BTN", "BWP", "BYN", "BZD", "CAD", "CDF", "CHF", "CLP", "CNY",
    "COP", "CRC", "CUP", "CVE", "CZK", "DJF", "DKK", "DOP", "DZD", "EGP",
    "ERN", "ETB", "EUR", "FJD", "FKP", "GBP", "GEL", "GHS", "GIP", "GMD",
    "GNF", "GTQ", "GYD", "HKD", "HNL", "HRK", "HTG", "HUF", "IDR", "ILS",
    "INR", "IQD", "IRR", "ISK", "JMD", "JOD", "JPY", "KES", "KGS", "KHR",
    "KMF", "KPW", "KRW", "KWD", "KYD", "KZT", "LAK", "LBP", "LKR", "LRD",
    "LSL", "LYD", "MAD", "MDL", "MGA", "MKD", "MMK", "MNT", "MOP", "MRU",
    "MUR", "MVR", "MWK", "MXN", "MYR", "MZN", "NAD", "NGN", "NIO", "NOK",
    "NPR", "NZD", "OMR", "PAB", "PEN", "PGK", "PHP", "PKR", "PLN", "PYG",
    "QAR", "RON", "RSD", "RUB", "RWF", "SAR", "SBD", "SCR", "SDG", "SEK",
    "SGD", "SHP", "SLE", "SOS", "SRD", "SSP", "STN", "SVC", "SYP", "SZL",
    "THB", "TJS", "TMT", "TND", "TOP", "TRY", "TTD", "TWD", "TZS", "UAH",
    "UGX", "USD", "UYU", "UZS", "VES", "VND", "VUV", "WST", "XAF", "XCD",
    "XOF", "XPF", "YER", "ZAR", "ZMW", "ZWL",
])

ISO_ALPHA2 = frozenset([
    "AE", "AR", "AT", "AU", "BD", "BE", "BG", "BH", "BR", "CA",
    "CH", "CL", "CN", "CO", "CY", "CZ", "DE", "DK", "EG", "ES",
    "FI", "FR", "GB", "GH", "GR", "HK", "HR", "HU", "ID", "IE",
    "IL", "IN", "IS", "IT", "JO", "JP", "KE", "KR", "KW", "LB",
    "MA", "MX", "MY", "NG", "NL", "NO", "NZ", "OM", "PE", "PH",
    "PK", "PL", "PT", "QA", "RO", "RU", "SA", "SE", "SG", "TH",
    "TR", "TW", "TZ", "UA", "UG", "US", "VN", "ZA",
])

ISO_ALPHA3 = frozenset([
    "ARE", "ARG", "AUS", "AUT", "BEL", "BGD", "BGR", "BHR", "BRA", "CAN",
    "CHE", "CHL", "CHN", "COL", "CYP", "CZE", "DEU", "DNK", "EGY", "ESP",
    "FIN", "FRA", "GBR", "GHA", "GRC", "HKG", "HRV", "HUN", "IDN", "IND",
    "IRL", "ISL", "ISR", "ITA", "JOR", "JPN", "KEN", "KOR", "KWT", "LBN",
    "MAR", "MEX", "MYS", "NGA", "NLD", "NOR", "NZL", "OMN", "PAK", "PER",
    "PHL", "POL", "PRT", "QAT", "ROU", "RUS", "SAU", "SGP", "SWE", "THA",
    "TUR", "TWN", "TZA", "UGA", "UKR", "USA", "VNM", "ZAF",
])

US_STATES = frozenset([
    "AK", "AL", "AR", "AS", "AZ", "CA", "CO", "CT", "DC", "DE",
    "FL", "GA", "GU", "HI", "IA", "ID", "IL", "IN", "KS", "KY",
    "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MP", "MS", "MT",
    "NC", "ND", "NE", "NH", "NJ", "NM", "NV", "NY", "OH", "OK",
    "OR", "PA", "PR", "RI", "SC", "SD", "TN", "TX", "UT", "VA",
    "VI", "VT", "WA", "WI", "WV", "WY",
])

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_HEX = frozenset("0123456789abcdefABCDEF")


def _is_hex(ch: str) -> bool:
    return ch in _HEX


def _all_digits(s: str) -> bool:
    return s.isdigit()


# ---------------------------------------------------------------------------
# Individual validators
# ---------------------------------------------------------------------------

def validate_email(value: str) -> bool:
    """Simplified RFC 5322 email validation."""
    at_idx = value.find("@")
    if at_idx <= 0 or at_idx == len(value) - 1:
        return False
    if value.find("@", at_idx + 1) >= 0:
        return False
    local = value[:at_idx]
    domain = value[at_idx + 1:]
    if not local or not domain:
        return False
    return domain.find(".") > 0


def validate_url(value: str) -> bool:
    """Validate URL starts with http:// or https://."""
    return value.startswith("http://") or value.startswith("https://")


def validate_uuid(value: str) -> bool:
    """Validate UUID v1-v5 format (8-4-4-4-12 hex)."""
    if len(value) != 36:
        return False
    for i, ch in enumerate(value):
        if i in (8, 13, 18, 23):
            if ch != "-":
                return False
        else:
            if not _is_hex(ch):
                return False
    return True


def validate_ipv4(value: str) -> bool:
    """Validate IPv4 address (four dot-separated octets 0-255, no leading zeros)."""
    octets = value.split(".")
    if len(octets) != 4:
        return False
    for octet in octets:
        if not octet or len(octet) > 3:
            return False
        if len(octet) > 1 and octet[0] == "0":
            return False
        if not octet.isdigit():
            return False
        val = int(octet)
        if val < 0 or val > 255:
            return False
    return True


def _is_valid_ipv6_group(group: str) -> bool:
    if not group or len(group) > 4:
        return False
    return all(_is_hex(ch) for ch in group)


def validate_ipv6(value: str) -> bool:
    """Validate IPv6 address (8 colon-separated hex groups, with :: compression)."""
    compressed_count = value.count("::")
    if compressed_count > 1:
        return False

    if compressed_count == 1:
        parts = value.split("::", 1)
        left = parts[0].split(":") if parts[0] else []
        right = parts[1].split(":") if (len(parts) > 1 and parts[1]) else []
        total_groups = len(left) + len(right)
        if total_groups > 8:
            return False
        for group in left:
            if not _is_valid_ipv6_group(group):
                return False
        for group in right:
            if not _is_valid_ipv6_group(group):
                return False
        return True

    groups = value.split(":")
    if len(groups) != 8:
        return False
    return all(_is_valid_ipv6_group(g) for g in groups)


def validate_date(value: str) -> bool:
    """Validate ISO date YYYY-MM-DD."""
    if len(value) != 10:
        return False
    if value[4] != "-" or value[7] != "-":
        return False
    return value[:4].isdigit() and value[5:7].isdigit() and value[8:10].isdigit()


def validate_time(value: str) -> bool:
    """Validate time HH:MM:SS with optional fractional seconds."""
    # Strip timezone if present
    time_part = value
    if time_part.endswith("Z"):
        time_part = time_part[:-1]
    elif "+" in time_part[6:]:
        time_part = time_part[:time_part.index("+", 6)]
    elif time_part.count("-") > 0 and len(time_part) > 8:
        # offset like -05:00
        idx = time_part.rfind("-")
        if idx > 5:
            time_part = time_part[:idx]

    parts = time_part.split(":")
    if len(parts) < 2 or len(parts) > 3:
        return False
    if not parts[0].isdigit() or not parts[1].isdigit():
        return False
    hh = int(parts[0])
    mm = int(parts[1])
    if hh > 23 or mm > 59:
        return False
    if len(parts) == 3:
        sec_part = parts[2]
        if "." in sec_part:
            sec_str, _frac = sec_part.split(".", 1)
        else:
            sec_str = sec_part
        if not sec_str.isdigit():
            return False
        ss = int(sec_str)
        if ss > 59:
            return False
    return True


def validate_timestamp(value: str) -> bool:
    """Validate ISO 8601 timestamp (date + T + time, optional timezone)."""
    if "T" not in value:
        return False
    date_part, time_part = value.split("T", 1)
    return validate_date(date_part) and validate_time(time_part)


_HOSTNAME_RE = re.compile(
    r"^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(\.[a-zA-Z0-9-]{1,63})*$"
)


def validate_hostname(value: str) -> bool:
    """Validate hostname per RFC 952 / RFC 1123."""
    if not value or len(value) > 253:
        return False
    return _HOSTNAME_RE.match(value) is not None


def validate_regex(value: str) -> bool:
    """Validate that the string is a compilable regex pattern."""
    try:
        re.compile(value)
        return True
    except re.error:
        return False


def validate_phone(value: str) -> bool:
    """Validate phone number (at least 7 digits, allowed: +-(). )."""
    digit_count = 0
    for ch in value:
        if ch.isdigit():
            digit_count += 1
        elif ch not in "+-() .":
            return False
    return digit_count >= 7


def validate_zip(value: str) -> bool:
    """Validate US ZIP code (5 digits or 5+4)."""
    if len(value) == 5:
        return _all_digits(value)
    if len(value) == 10 and value[5] == "-":
        return _all_digits(value[:5]) and _all_digits(value[6:])
    return False


def validate_naic(value: str) -> bool:
    """Validate NAIC code (5 digits)."""
    return len(value) == 5 and _all_digits(value)


def validate_fein(value: str) -> bool:
    """Validate FEIN (XX-XXXXXXX)."""
    if len(value) != 10 or value[2] != "-":
        return False
    return _all_digits(value[:2]) and _all_digits(value[3:])


def validate_vin(value: str) -> bool:
    """Validate VIN (17 alphanumeric chars, no I/O/Q)."""
    if len(value) != 17:
        return False
    for ch in value:
        c = ch.upper()
        if not c.isalnum():
            return False
        if c in ("I", "O", "Q"):
            return False
    return True


def validate_currency_code(value: str) -> bool:
    """Validate ISO 4217 currency code."""
    if len(value) != 3:
        return False
    if not all("A" <= ch <= "Z" for ch in value):
        return False
    return value in CURRENCY_CODES


def validate_country_alpha2(value: str) -> bool:
    """Validate ISO 3166-1 alpha-2 country code."""
    if len(value) != 2:
        return False
    if not all("A" <= ch <= "Z" for ch in value):
        return False
    return value in ISO_ALPHA2


def validate_country_alpha3(value: str) -> bool:
    """Validate ISO 3166-1 alpha-3 country code."""
    if len(value) != 3:
        return False
    if not all("A" <= ch <= "Z" for ch in value):
        return False
    return value in ISO_ALPHA3


def validate_state_us(value: str) -> bool:
    """Validate US state/territory code."""
    if len(value) != 2:
        return False
    if not all("A" <= ch <= "Z" for ch in value):
        return False
    return value in US_STATES


def validate_creditcard(value: str) -> bool:
    """Validate credit card number using Luhn algorithm."""
    digits: List[int] = []
    for ch in value:
        if ch.isdigit():
            digits.append(int(ch))
        elif ch not in (" ", "-"):
            return False
    if len(digits) < 13 or len(digits) > 19:
        return False

    total = 0
    double_it = False
    for d in reversed(digits):
        if double_it:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        double_it = not double_it
    return total % 10 == 0


def validate_uri(value: str) -> bool:
    """Validate URI with a scheme (scheme:rest, no whitespace)."""
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:\S*$", value))


def validate_datetime(value: str) -> bool:
    """Validate ISO 8601 datetime (date + T + time)."""
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value))


def validate_iban(value: str) -> bool:
    """Validate IBAN shape (2 letters, 2 digits, 4-30 alphanumeric)."""
    return bool(re.match(r"^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$", value, re.IGNORECASE))


def validate_bic(value: str) -> bool:
    """Validate BIC/SWIFT shape (8 or 11 characters)."""
    return bool(
        re.match(r"^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$", value, re.IGNORECASE)
    )


def validate_routing(value: str) -> bool:
    """Validate ABA routing number (9 digits)."""
    return len(value) == 9 and _all_digits(value)


def validate_cusip(value: str) -> bool:
    """Validate CUSIP shape (9 alphanumeric characters)."""
    return bool(re.match(r"^[A-Z0-9]{9}$", value, re.IGNORECASE))


def validate_isin(value: str) -> bool:
    """Validate ISIN shape (2 letters, 9 alphanumeric, 1 digit)."""
    return bool(re.match(r"^[A-Z]{2}[A-Z0-9]{9}\d$", value, re.IGNORECASE))


def validate_lei(value: str) -> bool:
    """Validate LEI shape (20 alphanumeric characters)."""
    return bool(re.match(r"^[A-Z0-9]{20}$", value, re.IGNORECASE))


def validate_npi(value: str) -> bool:
    """Validate NPI shape (10 digits)."""
    return len(value) == 10 and _all_digits(value)


def validate_dea(value: str) -> bool:
    """Validate DEA number shape (2 letters, 7 digits)."""
    return bool(re.match(r"^[A-Z]{2}\d{7}$", value, re.IGNORECASE))


def validate_imei(value: str) -> bool:
    """Validate IMEI shape (15 digits)."""
    return len(value) == 15 and _all_digits(value)


def validate_iccid(value: str) -> bool:
    """Validate ICCID shape (19-20 digits)."""
    return len(value) in (19, 20) and _all_digits(value)


def validate_ssn(value: str) -> bool:
    """Validate US Social Security Number."""
    digit_chars: List[str] = [ch for ch in value if ch.isdigit()]
    if len(digit_chars) != 9:
        return False

    valid_format = (
        len(value) == 9
        or (len(value) == 11 and value[3] == "-" and value[6] == "-")
    )
    if not valid_format:
        return False

    if digit_chars[0] == "0" and digit_chars[1] == "0" and digit_chars[2] == "0":
        return False

    return True


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_FORMAT_VALIDATORS: Dict[str, Callable[[str], bool]] = {
    "email": validate_email,
    "url": validate_url,
    "uuid": validate_uuid,
    "ipv4": validate_ipv4,
    "ipv6": validate_ipv6,
    "date": validate_date,
    "time": validate_time,
    "timestamp": validate_timestamp,
    "hostname": validate_hostname,
    "regex": validate_regex,
    "phone": validate_phone,
    "zip": validate_zip,
    "naic": validate_naic,
    "fein": validate_fein,
    "vin": validate_vin,
    "currency-code": validate_currency_code,
    "country-alpha2": validate_country_alpha2,
    "country-alpha3": validate_country_alpha3,
    "state-us": validate_state_us,
    "creditcard": validate_creditcard,
    "credit-card": validate_creditcard,
    "uri": validate_uri,
    "datetime": validate_datetime,
    "date-time": validate_datetime,
    "iban": validate_iban,
    "bic": validate_bic,
    "swift": validate_bic,
    "routing": validate_routing,
    "cusip": validate_cusip,
    "isin": validate_isin,
    "lei": validate_lei,
    "npi": validate_npi,
    "dea": validate_dea,
    "imei": validate_imei,
    "iccid": validate_iccid,
    "ssn": validate_ssn,
}


def get_format_validator(name: str) -> Optional[Callable[[str], bool]]:
    """Look up a format validator by name.

    Returns the validator function, or ``None`` if the format is unknown.
    """
    return _FORMAT_VALIDATORS.get(name)


def validate(value: str, fmt: str) -> bool:
    """Validate *value* against the named *fmt*.

    Matches Java ``FormatValidators.validate`` semantics:
    - Empty/null values always pass.
    - Unknown format names always pass.
    - ``date-iso`` validates ISO 8601 date format (YYYY-MM-DD).
    """
    if value is None:
        return True
    if not fmt:
        return True

    # Validate ISO date format (YYYY-MM-DD) matching TypeScript pattern
    if fmt == "date-iso":
        return bool(re.match(r'^\d{4}-\d{2}-\d{2}$', value))

    validator = get_format_validator(fmt)
    if validator is None:
        return True  # unknown format -> pass
    return validator(value)
