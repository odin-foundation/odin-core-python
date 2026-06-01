"""Tests for odin.validation.format_validators.

Mirrors the Java FormatValidatorsTest.java test cases, plus additional
coverage for date, time, timestamp, hostname, and regex validators.
"""

import pytest

from odin.validation.format_validators import (
    get_format_validator,
    validate,
    validate_email,
    validate_url,
    validate_uuid,
    validate_ipv4,
    validate_ipv6,
    validate_date,
    validate_time,
    validate_timestamp,
    validate_hostname,
    validate_regex,
    validate_phone,
    validate_zip,
    validate_naic,
    validate_fein,
    validate_vin,
    validate_currency_code,
    validate_country_alpha2,
    validate_country_alpha3,
    validate_state_us,
    validate_creditcard,
    validate_ssn,
    validate_uri,
    validate_datetime,
    validate_iban,
    validate_bic,
    validate_routing,
    validate_cusip,
    validate_isin,
    validate_lei,
    validate_npi,
    validate_dea,
    validate_imei,
    validate_iccid,
)


# ── Email ──────────────────────────────────────────────────────────────────


class TestEmail:
    def test_valid_email(self):
        assert validate("user@example.com", "email")

    def test_valid_email_with_dots(self):
        assert validate("first.last@example.com", "email")

    def test_valid_email_with_plus(self):
        assert validate("user+tag@example.com", "email")

    def test_valid_email_subdomain(self):
        assert validate("user@sub.domain.com", "email")

    def test_invalid_email_no_at(self):
        assert not validate("userexample.com", "email")

    def test_invalid_email_no_domain(self):
        assert not validate("user@", "email")

    def test_invalid_email_no_local(self):
        assert not validate("@example.com", "email")

    def test_empty_email_fails_validation(self):
        assert not validate("", "email")

    def test_invalid_email_double_at(self):
        assert not validate_email("user@@example.com")

    def test_invalid_email_no_dot_in_domain(self):
        assert not validate_email("user@localhost")


# ── URL ────────────────────────────────────────────────────────────────────


class TestUrl:
    def test_valid_http_url(self):
        assert validate("http://example.com", "url")

    def test_valid_https_url(self):
        assert validate("https://example.com", "url")

    def test_valid_url_with_path(self):
        assert validate("https://example.com/path/to/resource", "url")

    def test_valid_url_with_query(self):
        assert validate("https://example.com?q=test", "url")

    def test_valid_url_with_port(self):
        assert validate("https://example.com:8080", "url")

    def test_invalid_url_no_scheme(self):
        assert not validate("example.com", "url")

    def test_empty_url_fails_validation(self):
        assert not validate("", "url")

    def test_invalid_ftp_url(self):
        assert not validate_url("ftp://files.example.com")


# ── UUID ───────────────────────────────────────────────────────────────────


class TestUuid:
    def test_valid_uuid(self):
        assert validate("550e8400-e29b-41d4-a716-446655440000", "uuid")

    def test_valid_uuid_uppercase(self):
        assert validate("550E8400-E29B-41D4-A716-446655440000", "uuid")

    def test_invalid_uuid_too_short(self):
        assert not validate("550e8400-e29b-41d4-a716", "uuid")

    def test_invalid_uuid_no_dashes(self):
        assert not validate("550e8400e29b41d4a716446655440000", "uuid")

    def test_empty_uuid_fails_validation(self):
        assert not validate("", "uuid")

    def test_invalid_uuid_bad_chars(self):
        assert not validate("550g8400-e29b-41d4-a716-446655440000", "uuid")

    def test_invalid_uuid_too_long(self):
        assert not validate_uuid("550e8400-e29b-41d4-a716-4466554400001")


# ── IPv4 ───────────────────────────────────────────────────────────────────


class TestIpv4:
    def test_valid_ipv4(self):
        assert validate("192.168.1.1", "ipv4")

    def test_valid_ipv4_localhost(self):
        assert validate("127.0.0.1", "ipv4")

    def test_valid_ipv4_all_zeros(self):
        assert validate("0.0.0.0", "ipv4")

    def test_valid_ipv4_max(self):
        assert validate("255.255.255.255", "ipv4")

    def test_invalid_ipv4_too_high(self):
        assert not validate("256.1.1.1", "ipv4")

    def test_invalid_ipv4_too_few_octets(self):
        assert not validate("192.168.1", "ipv4")

    def test_invalid_ipv4_letters(self):
        assert not validate("192.168.a.1", "ipv4")

    def test_empty_ipv4_fails_validation(self):
        assert not validate("", "ipv4")

    def test_invalid_ipv4_leading_zeros(self):
        assert not validate_ipv4("192.168.01.1")

    def test_invalid_ipv4_five_octets(self):
        assert not validate_ipv4("1.2.3.4.5")

    def test_invalid_ipv4_empty_octet(self):
        assert not validate_ipv4("1..2.3")


# ── IPv6 ───────────────────────────────────────────────────────────────────


class TestIpv6:
    def test_valid_ipv6_full(self):
        assert validate("2001:0db8:85a3:0000:0000:8a2e:0370:7334", "ipv6")

    def test_valid_ipv6_compressed(self):
        assert validate("2001:db8::1", "ipv6")

    def test_valid_ipv6_loopback(self):
        assert validate("::1", "ipv6")

    def test_empty_ipv6_fails_validation(self):
        assert not validate("", "ipv6")

    def test_invalid_ipv6_double_compression(self):
        assert not validate_ipv6("2001::db8::1")

    def test_valid_ipv6_all_zeros(self):
        assert validate_ipv6("::")

    def test_invalid_ipv6_too_many_groups(self):
        assert not validate_ipv6("1:2:3:4:5:6:7:8:9")

    def test_invalid_ipv6_bad_hex(self):
        assert not validate_ipv6("2001:0db8:85a3:0000:0000:8a2e:0370:ZZZZ")


# ── Date ───────────────────────────────────────────────────────────────────


class TestDate:
    def test_valid_date(self):
        assert validate_date("2024-06-15")

    def test_valid_date_jan_1(self):
        assert validate_date("2024-01-01")

    def test_valid_date_dec_31(self):
        assert validate_date("2024-12-31")

    def test_invalid_date_wrong_separator(self):
        assert not validate_date("2024/06/15")

    def test_invalid_date_too_short(self):
        assert not validate_date("2024-6-1")

    def test_invalid_date_letters(self):
        assert not validate_date("abcd-ef-gh")

    def test_invalid_date_no_dash(self):
        assert not validate_date("20240615xx")


# ── Time ───────────────────────────────────────────────────────────────────


class TestTime:
    def test_valid_time(self):
        assert validate_time("13:45:30")

    def test_valid_time_with_fraction(self):
        assert validate_time("13:45:30.123")

    def test_valid_time_with_z(self):
        assert validate_time("13:45:30Z")

    def test_valid_time_no_seconds(self):
        assert validate_time("13:45")

    def test_invalid_time_hour_too_high(self):
        assert not validate_time("25:00:00")

    def test_invalid_time_minute_too_high(self):
        assert not validate_time("12:61:00")

    def test_invalid_time_single_part(self):
        assert not validate_time("12")


# ── Timestamp ──────────────────────────────────────────────────────────────


class TestTimestamp:
    def test_valid_timestamp(self):
        assert validate_timestamp("2024-06-15T13:45:30")

    def test_valid_timestamp_with_z(self):
        assert validate_timestamp("2024-06-15T13:45:30Z")

    def test_valid_timestamp_with_fraction(self):
        assert validate_timestamp("2024-06-15T13:45:30.123Z")

    def test_invalid_timestamp_no_t(self):
        assert not validate_timestamp("2024-06-15 13:45:30")

    def test_invalid_timestamp_bad_date(self):
        assert not validate_timestamp("abcd-ef-ghT13:45:30")


# ── Hostname ───────────────────────────────────────────────────────────────


class TestHostname:
    def test_valid_hostname(self):
        assert validate_hostname("example.com")

    def test_valid_hostname_subdomain(self):
        assert validate_hostname("sub.example.com")

    def test_valid_hostname_single_label(self):
        assert validate_hostname("localhost")

    def test_invalid_hostname_starts_with_dash(self):
        assert not validate_hostname("-example.com")

    def test_invalid_hostname_empty(self):
        assert not validate_hostname("")

    def test_invalid_hostname_too_long_label(self):
        assert not validate_hostname("a" * 64 + ".com")

    def test_valid_hostname_max_label(self):
        assert validate_hostname("a" * 63 + ".com")


# ── Regex ──────────────────────────────────────────────────────────────────


class TestRegex:
    def test_valid_regex(self):
        assert validate_regex(r"^[a-z]+$")

    def test_valid_regex_complex(self):
        assert validate_regex(r"\d{3}-\d{2}-\d{4}")

    def test_invalid_regex_unbalanced(self):
        assert not validate_regex("[unclosed")

    def test_invalid_regex_bad_quantifier(self):
        assert not validate_regex("*abc")

    def test_valid_regex_empty(self):
        assert validate_regex("")


# ── Phone ──────────────────────────────────────────────────────────────────


class TestPhone:
    def test_valid_phone(self):
        assert validate("555-123-4567", "phone")

    def test_valid_phone_intl(self):
        assert validate("+1-555-123-4567", "phone")

    def test_valid_phone_parens(self):
        assert validate("(555) 123-4567", "phone")

    def test_valid_phone_dots(self):
        assert validate("555.123.4567", "phone")

    def test_invalid_phone_too_short(self):
        assert not validate("123", "phone")

    def test_empty_phone_fails_validation(self):
        assert not validate("", "phone")

    def test_invalid_phone_letters(self):
        assert not validate("abc-def-ghij", "phone")


# ── ZIP ────────────────────────────────────────────────────────────────────


class TestZip:
    def test_valid_zip5(self):
        assert validate("12345", "zip")

    def test_valid_zip_plus4(self):
        assert validate("12345-6789", "zip")

    def test_invalid_zip_too_short(self):
        assert not validate("1234", "zip")

    def test_invalid_zip_letters(self):
        assert not validate("abcde", "zip")

    def test_empty_zip_fails_validation(self):
        assert not validate("", "zip")


# ── Date ISO (YYYY-MM-DD) ─────────────────────────────────────────────────


class TestDateIso:
    def test_valid_date(self):
        assert validate("2024-06-15", "date-iso")

    def test_valid_date_jan_1(self):
        assert validate("2024-01-01", "date-iso")

    def test_invalid_date_iso_random_string(self):
        assert not validate("anything", "date-iso")

    def test_invalid_date_iso_partial(self):
        assert not validate("2024-06", "date-iso")

    def test_invalid_date_iso_extra_chars(self):
        assert not validate("2024-06-15T00:00:00", "date-iso")


# ── VIN ────────────────────────────────────────────────────────────────────


class TestVin:
    def test_valid_vin(self):
        assert validate("1HGBH41JXMN109186", "vin")

    def test_invalid_vin_too_short(self):
        assert not validate("1HGBH41JXM", "vin")

    def test_invalid_vin_bad_chars(self):
        assert not validate("1HGBH41IXMN109186", "vin")

    def test_empty_vin_fails_validation(self):
        assert not validate("", "vin")


# ── Currency code ──────────────────────────────────────────────────────────


class TestCurrencyCode:
    def test_valid_usd(self):
        assert validate("USD", "currency-code")

    def test_valid_eur(self):
        assert validate("EUR", "currency-code")

    def test_valid_gbp(self):
        assert validate("GBP", "currency-code")

    def test_valid_jpy(self):
        assert validate("JPY", "currency-code")

    def test_invalid_currency_code(self):
        assert not validate("XYZ", "currency-code")

    def test_invalid_currency_code_lower(self):
        assert not validate("usd", "currency-code")

    def test_empty_currency_fails_validation(self):
        assert not validate("", "currency-code")


# ── Country codes ──────────────────────────────────────────────────────────


class TestCountryCodes:
    def test_valid_alpha2_us(self):
        assert validate("US", "country-alpha2")

    def test_valid_alpha2_gb(self):
        assert validate("GB", "country-alpha2")

    def test_invalid_alpha2(self):
        assert not validate("XX", "country-alpha2")

    def test_valid_alpha3_usa(self):
        assert validate("USA", "country-alpha3")

    def test_valid_alpha3_gbr(self):
        assert validate("GBR", "country-alpha3")

    def test_invalid_alpha3(self):
        assert not validate("XXX", "country-alpha3")


# ── US State ───────────────────────────────────────────────────────────────


class TestStateUs:
    def test_valid_state_tx(self):
        assert validate("TX", "state-us")

    def test_valid_state_ca(self):
        assert validate("CA", "state-us")

    def test_valid_state_ny(self):
        assert validate("NY", "state-us")

    def test_invalid_state(self):
        assert not validate("XX", "state-us")

    def test_invalid_state_lower(self):
        assert not validate("tx", "state-us")


# ── Credit card ────────────────────────────────────────────────────────────


class TestCreditCard:
    def test_valid_visa(self):
        assert validate("4111111111111111", "creditcard")

    def test_valid_mastercard(self):
        assert validate("5500000000000004", "creditcard")

    def test_invalid_cc_bad_luhn(self):
        assert not validate("4111111111111112", "creditcard")

    def test_invalid_cc_too_short(self):
        assert not validate("411111111111", "creditcard")

    def test_empty_cc_fails_validation(self):
        assert not validate("", "creditcard")


# ── SSN ────────────────────────────────────────────────────────────────────


class TestSsn:
    def test_valid_ssn(self):
        assert validate("123-45-6789", "ssn")

    def test_valid_ssn_no_dashes(self):
        assert validate("123456789", "ssn")

    def test_empty_ssn_fails_validation(self):
        assert not validate("", "ssn")

    def test_invalid_ssn_starts_with_000(self):
        assert not validate_ssn("000-12-3456")


# ── FEIN ───────────────────────────────────────────────────────────────────


class TestFein:
    def test_valid_fein(self):
        assert validate("12-3456789", "fein")

    def test_invalid_fein_no_dash(self):
        assert not validate("123456789", "fein")

    def test_empty_fein_fails_validation(self):
        assert not validate("", "fein")


# ── Unknown format ─────────────────────────────────────────────────────────


class TestUnknownFormat:
    def test_unknown_format_returns_true(self):
        assert validate("anything", "nonexistent-format")


# ── Registry ───────────────────────────────────────────────────────────────


class TestRegistry:
    def test_get_known_validator(self):
        assert get_format_validator("email") is validate_email

    def test_get_unknown_validator(self):
        assert get_format_validator("nonexistent") is None

    def test_all_registered_validators(self):
        for name in [
            "email", "url", "uuid", "ipv4", "ipv6", "date", "time",
            "timestamp", "hostname", "regex", "phone", "zip", "naic",
            "fein", "vin", "currency-code", "country-alpha2",
            "country-alpha3", "state-us", "creditcard", "credit-card",
            "ssn", "uri", "datetime", "date-time", "iban", "bic", "swift",
            "routing", "cusip", "isin", "lei", "npi", "dea", "imei", "iccid",
        ]:
            assert get_format_validator(name) is not None, f"Missing validator: {name}"


# ── URI ────────────────────────────────────────────────────────────────────


class TestUri:
    def test_valid_urn(self):
        assert validate("urn:isbn:0451450523", "uri")

    def test_valid_mailto(self):
        assert validate("mailto:user@example.com", "uri")

    def test_valid_https(self):
        assert validate_uri("https://example.com/path")

    def test_invalid_no_scheme(self):
        assert not validate("/relative/path", "uri")

    def test_invalid_with_whitespace(self):
        assert not validate_uri("http://exa mple.com")


# ── Datetime ───────────────────────────────────────────────────────────────


class TestDatetime:
    def test_valid_datetime(self):
        assert validate("2024-06-15T10:30:00", "datetime")

    def test_valid_datetime_zulu(self):
        assert validate("2024-06-15T10:30:00Z", "datetime")

    def test_alias_date_time_zulu(self):
        assert validate("2024-06-15T10:30:00Z", "date-time")

    def test_invalid_space_separator(self):
        assert not validate("2024-06-15 10:30:00", "datetime")

    def test_invalid_date_only(self):
        assert not validate("2024-06-15", "datetime")

    def test_invalid_slashes(self):
        assert not validate("06/15/2024", "date-time")


# ── Credit card (hyphenated alias) ─────────────────────────────────────────


class TestCreditCardAlias:
    def test_valid_visa(self):
        assert validate("4111111111111111", "credit-card")

    def test_invalid_checksum(self):
        assert not validate("4111111111111112", "credit-card")

    def test_invalid_too_short(self):
        assert not validate("411111111111", "credit-card")


# ── IBAN ───────────────────────────────────────────────────────────────────


class TestIban:
    def test_valid_gb(self):
        assert validate("GB82WEST12345698765432", "iban")

    def test_valid_de(self):
        assert validate("DE89370400440532013000", "iban")

    def test_invalid_no_country(self):
        assert not validate("1234WEST", "iban")

    def test_invalid_too_short(self):
        assert not validate_iban("GB82")


# ── BIC / SWIFT ────────────────────────────────────────────────────────────


class TestBic:
    def test_valid_8(self):
        assert validate("DEUTDEFF", "bic")

    def test_valid_11(self):
        assert validate("DEUTDEFF500", "bic")

    def test_invalid_9_chars(self):
        assert not validate("DEUTDEFF5", "bic")

    def test_swift_valid(self):
        assert validate("BOFAUS3N", "swift")

    def test_swift_invalid_too_short(self):
        assert not validate("BOFAUS3", "swift")


# ── Routing ────────────────────────────────────────────────────────────────


class TestRouting:
    def test_valid(self):
        assert validate("021000021", "routing")

    def test_invalid_8_digits(self):
        assert not validate("12345678", "routing")

    def test_invalid_letters(self):
        assert not validate_routing("02100002A")


# ── CUSIP ──────────────────────────────────────────────────────────────────


class TestCusip:
    def test_valid(self):
        assert validate("037833100", "cusip")

    def test_invalid_too_short(self):
        assert not validate("03783310", "cusip")

    def test_invalid_symbol(self):
        assert not validate("037833$00", "cusip")


# ── ISIN ───────────────────────────────────────────────────────────────────


class TestIsin:
    def test_valid(self):
        assert validate("US0378331005", "isin")

    def test_invalid_too_short(self):
        assert not validate("US037833100", "isin")

    def test_invalid_non_digit_check(self):
        assert not validate("US037833100X", "isin")


# ── LEI ────────────────────────────────────────────────────────────────────


class TestLei:
    def test_valid(self):
        assert validate("529900T8BM49AURSDO55", "lei")

    def test_invalid_too_short(self):
        assert not validate("529900T8BM49AURSDO5", "lei")

    def test_invalid_symbol(self):
        assert not validate("529900T8BM49AURSDO5$", "lei")


# ── NPI ────────────────────────────────────────────────────────────────────


class TestNpi:
    def test_valid(self):
        assert validate("1234567890", "npi")

    def test_invalid_too_short(self):
        assert not validate("123456789", "npi")

    def test_invalid_too_long(self):
        assert not validate("12345678901", "npi")


# ── DEA ────────────────────────────────────────────────────────────────────


class TestDea:
    def test_valid(self):
        assert validate("AB1234567", "dea")

    def test_invalid_one_letter(self):
        assert not validate("A1234567", "dea")

    def test_invalid_short_digits(self):
        assert not validate("AB123456", "dea")


# ── IMEI ───────────────────────────────────────────────────────────────────


class TestImei:
    def test_valid(self):
        assert validate("490154203237518", "imei")

    def test_invalid_too_short(self):
        assert not validate("49015420323751", "imei")

    def test_invalid_too_long(self):
        assert not validate("4901542032375189", "imei")


# ── ICCID ──────────────────────────────────────────────────────────────────


class TestIccid:
    def test_valid_19(self):
        assert validate("8901234567890123456", "iccid")

    def test_valid_20(self):
        assert validate("89012345678901234567", "iccid")

    def test_invalid_too_short(self):
        assert not validate("890123456789012345", "iccid")

    def test_invalid_letter(self):
        assert not validate("8901234567890123456X", "iccid")
