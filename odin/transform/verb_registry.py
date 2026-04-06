"""Verb registry for the ODIN transform engine."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from odin.transform.dyn_value import DynValue

# VerbFunction: (args: List[DynValue], ctx: Any) -> DynValue
VerbFunction = Callable[[List[DynValue], object], DynValue]


class VerbRegistry:
    """Registry of transform verbs."""

    def __init__(self) -> None:
        self._verbs: Dict[str, VerbFunction] = {}

    def register(self, name: str, fn: VerbFunction) -> None:
        """Register a verb function."""
        self._verbs[name] = fn

    def get(self, name: str) -> Optional[VerbFunction]:
        """Get a verb function by name."""
        return self._verbs.get(name)

    def has(self, name: str) -> bool:
        """Check if a verb is registered."""
        return name in self._verbs

    def names(self) -> List[str]:
        """List all registered verb names."""
        return list(self._verbs.keys())


def create_default_registry() -> VerbRegistry:
    """Create a registry with all built-in verbs."""
    from odin.transform.verbs import core_verbs, string_verbs, logic_verbs
    from odin.transform.verbs import coercion_verbs, encoding_verbs, generation_verbs
    from odin.transform.verbs import numeric_verbs, collection_verbs, datetime_verbs
    from odin.transform.verbs import financial_verbs, aggregation_verbs, object_verbs, geo_verbs

    registry = VerbRegistry()

    # Core verbs
    registry.register("concat", core_verbs.verb_concat)
    registry.register("upper", core_verbs.verb_upper)
    registry.register("lower", core_verbs.verb_lower)
    registry.register("trim", core_verbs.verb_trim)
    registry.register("trimLeft", core_verbs.verb_trim_left)
    registry.register("trimRight", core_verbs.verb_trim_right)
    registry.register("coalesce", core_verbs.verb_coalesce)
    registry.register("ifNull", core_verbs.verb_if_null)
    registry.register("ifEmpty", core_verbs.verb_if_empty)
    registry.register("ifElse", core_verbs.verb_if_else)
    registry.register("lookup", core_verbs.verb_lookup)
    registry.register("lookupDefault", core_verbs.verb_lookup_default)

    # String verbs
    registry.register("capitalize", string_verbs.verb_capitalize)
    registry.register("titleCase", string_verbs.verb_title_case)
    registry.register("contains", string_verbs.verb_contains)
    registry.register("startsWith", string_verbs.verb_starts_with)
    registry.register("endsWith", string_verbs.verb_ends_with)
    registry.register("replace", string_verbs.verb_replace)
    registry.register("replaceRegex", string_verbs.verb_replace_regex)
    registry.register("padLeft", string_verbs.verb_pad_left)
    registry.register("padRight", string_verbs.verb_pad_right)
    registry.register("pad", string_verbs.verb_pad)
    registry.register("truncate", string_verbs.verb_truncate)
    registry.register("split", string_verbs.verb_split)
    registry.register("join", string_verbs.verb_join)
    registry.register("mask", string_verbs.verb_mask)
    registry.register("reverseString", string_verbs.verb_reverse_string)
    registry.register("repeat", string_verbs.verb_repeat)
    registry.register("substring", string_verbs.verb_substring)
    registry.register("length", string_verbs.verb_length)
    registry.register("camelCase", string_verbs.verb_camel_case)
    registry.register("pascalCase", string_verbs.verb_pascal_case)
    registry.register("snakeCase", string_verbs.verb_snake_case)
    registry.register("kebabCase", string_verbs.verb_kebab_case)
    registry.register("slugify", string_verbs.verb_slugify)
    registry.register("formatPhone", string_verbs.verb_format_phone)
    registry.register("match", string_verbs.verb_match)
    registry.register("matches", string_verbs.verb_matches)
    registry.register("extract", string_verbs.verb_extract)
    registry.register("normalizeSpace", string_verbs.verb_normalize_space)
    registry.register("leftOf", string_verbs.verb_left_of)
    registry.register("rightOf", string_verbs.verb_right_of)
    registry.register("wrap", string_verbs.verb_wrap)
    registry.register("center", string_verbs.verb_center)
    registry.register("stripAccents", string_verbs.verb_strip_accents)
    registry.register("clean", string_verbs.verb_clean)
    registry.register("wordCount", string_verbs.verb_word_count)
    registry.register("tokenize", string_verbs.verb_tokenize)
    registry.register("levenshtein", string_verbs.verb_levenshtein)
    registry.register("soundex", string_verbs.verb_soundex)

    # Logic verbs
    registry.register("and", logic_verbs.verb_and)
    registry.register("or", logic_verbs.verb_or)
    registry.register("not", logic_verbs.verb_not)
    registry.register("xor", logic_verbs.verb_xor)
    registry.register("eq", logic_verbs.verb_eq)
    registry.register("ne", logic_verbs.verb_ne)
    registry.register("lt", logic_verbs.verb_lt)
    registry.register("lte", logic_verbs.verb_lte)
    registry.register("gt", logic_verbs.verb_gt)
    registry.register("gte", logic_verbs.verb_gte)
    registry.register("between", logic_verbs.verb_between)
    registry.register("isNull", logic_verbs.verb_is_null)
    registry.register("isString", logic_verbs.verb_is_string)
    registry.register("isNumber", logic_verbs.verb_is_number)
    registry.register("isBoolean", logic_verbs.verb_is_boolean)
    registry.register("isArray", logic_verbs.verb_is_array)
    registry.register("isObject", logic_verbs.verb_is_object)
    registry.register("isDate", logic_verbs.verb_is_date)
    registry.register("typeOf", logic_verbs.verb_type_of)
    registry.register("cond", logic_verbs.verb_cond)
    registry.register("assert", logic_verbs.verb_assert)
    registry.register("switch", logic_verbs.verb_switch)
    registry.register("isFinite", logic_verbs.verb_is_finite)
    registry.register("isNaN", logic_verbs.verb_is_nan)

    # Coercion verbs
    registry.register("coerceString", coercion_verbs.verb_coerce_string)
    registry.register("coerceNumber", coercion_verbs.verb_coerce_number)
    registry.register("coerceInteger", coercion_verbs.verb_coerce_integer)
    registry.register("coerceBoolean", coercion_verbs.verb_coerce_boolean)
    registry.register("coerceDate", coercion_verbs.verb_coerce_date)
    registry.register("coerceTimestamp", coercion_verbs.verb_coerce_timestamp)
    registry.register("tryCoerce", coercion_verbs.verb_try_coerce)
    registry.register("toArray", coercion_verbs.verb_to_array)
    registry.register("toObject", coercion_verbs.verb_to_object)

    # Encoding verbs
    registry.register("base64Encode", encoding_verbs.verb_base64_encode)
    registry.register("base64Decode", encoding_verbs.verb_base64_decode)
    registry.register("urlEncode", encoding_verbs.verb_url_encode)
    registry.register("urlDecode", encoding_verbs.verb_url_decode)
    registry.register("hexEncode", encoding_verbs.verb_hex_encode)
    registry.register("hexDecode", encoding_verbs.verb_hex_decode)
    registry.register("jsonEncode", encoding_verbs.verb_json_encode)
    registry.register("jsonDecode", encoding_verbs.verb_json_decode)
    registry.register("sha256", encoding_verbs.verb_sha256)
    registry.register("sha1", encoding_verbs.verb_sha1)
    registry.register("sha512", encoding_verbs.verb_sha512)
    registry.register("md5", encoding_verbs.verb_md5)
    registry.register("crc32", encoding_verbs.verb_crc32)
    registry.register("jsonPath", encoding_verbs.verb_json_path)

    # Generation verbs
    registry.register("uuid", generation_verbs.verb_uuid)
    registry.register("sequence", generation_verbs.verb_sequence)
    registry.register("resetSequence", generation_verbs.verb_reset_sequence)
    registry.register("nanoid", generation_verbs.verb_nanoid)

    # Numeric verbs
    registry.register("formatNumber", numeric_verbs.verb_format_number)
    registry.register("formatInteger", numeric_verbs.verb_format_integer)
    registry.register("formatCurrency", numeric_verbs.verb_format_currency)
    registry.register("formatPercent", numeric_verbs.verb_format_percent)
    registry.register("add", numeric_verbs.verb_add)
    registry.register("subtract", numeric_verbs.verb_subtract)
    registry.register("multiply", numeric_verbs.verb_multiply)
    registry.register("divide", numeric_verbs.verb_divide)
    registry.register("mod", numeric_verbs.verb_mod)
    registry.register("abs", numeric_verbs.verb_abs)
    registry.register("floor", numeric_verbs.verb_floor)
    registry.register("ceil", numeric_verbs.verb_ceil)
    registry.register("round", numeric_verbs.verb_round)
    registry.register("negate", numeric_verbs.verb_negate)
    registry.register("sign", numeric_verbs.verb_sign)
    registry.register("trunc", numeric_verbs.verb_trunc)
    registry.register("random", numeric_verbs.verb_random)
    registry.register("minOf", numeric_verbs.verb_min_of)
    registry.register("maxOf", numeric_verbs.verb_max_of)
    registry.register("parseInt", numeric_verbs.verb_parse_int)
    registry.register("safeDivide", numeric_verbs.verb_safe_divide)
    registry.register("formatLocaleNumber", numeric_verbs.verb_format_locale_number)
    registry.register("log", numeric_verbs.verb_log)
    registry.register("ln", numeric_verbs.verb_ln)
    registry.register("log10", numeric_verbs.verb_log10)
    registry.register("exp", numeric_verbs.verb_exp)
    registry.register("pow", numeric_verbs.verb_pow)
    registry.register("sqrt", numeric_verbs.verb_sqrt)
    registry.register("clamp", numeric_verbs.verb_clamp)
    registry.register("pi", numeric_verbs.verb_pi)
    registry.register("e", numeric_verbs.verb_e)
    registry.register("convertUnit", numeric_verbs.verb_convert_unit)

    # Collection verbs
    registry.register("filter", collection_verbs.verb_filter)
    registry.register("flatten", collection_verbs.verb_flatten)
    registry.register("distinct", collection_verbs.verb_distinct)
    registry.register("unique", collection_verbs.verb_unique)
    registry.register("sort", collection_verbs.verb_sort)
    registry.register("sortDesc", collection_verbs.verb_sort_desc)
    registry.register("sortBy", collection_verbs.verb_sort_by)
    registry.register("map", collection_verbs.verb_map)
    registry.register("pluck", collection_verbs.verb_pluck)
    registry.register("indexOf", collection_verbs.verb_index_of)
    registry.register("at", collection_verbs.verb_at)
    registry.register("slice", collection_verbs.verb_slice)
    registry.register("reverse", collection_verbs.verb_reverse)
    registry.register("every", collection_verbs.verb_every)
    registry.register("some", collection_verbs.verb_some)
    registry.register("find", collection_verbs.verb_find)
    registry.register("findIndex", collection_verbs.verb_find_index)
    registry.register("includes", collection_verbs.verb_includes)
    registry.register("concatArrays", collection_verbs.verb_concat_arrays)
    registry.register("zip", collection_verbs.verb_zip)
    registry.register("groupBy", collection_verbs.verb_group_by)
    registry.register("partition", collection_verbs.verb_partition)
    registry.register("take", collection_verbs.verb_take)
    registry.register("drop", collection_verbs.verb_drop)
    registry.register("chunk", collection_verbs.verb_chunk)
    registry.register("range", collection_verbs.verb_range)
    registry.register("compact", collection_verbs.verb_compact)
    registry.register("rowNumber", collection_verbs.verb_row_number)
    registry.register("sample", collection_verbs.verb_sample)
    registry.register("limit", collection_verbs.verb_limit)
    registry.register("dedupe", collection_verbs.verb_dedupe)
    registry.register("cumsum", collection_verbs.verb_cumsum)
    registry.register("cumprod", collection_verbs.verb_cumprod)
    registry.register("diff", collection_verbs.verb_diff)
    registry.register("pctChange", collection_verbs.verb_pct_change)
    registry.register("shift", collection_verbs.verb_shift)
    registry.register("lag", collection_verbs.verb_lag)
    registry.register("lead", collection_verbs.verb_lead)
    registry.register("rank", collection_verbs.verb_rank)
    registry.register("fillMissing", collection_verbs.verb_fill_missing)
    registry.register("joinArray", collection_verbs.verb_join)
    registry.register("reduce", collection_verbs.verb_reduce)
    registry.register("pivot", collection_verbs.verb_pivot)
    registry.register("unpivot", collection_verbs.verb_unpivot)

    # DateTime verbs
    registry.register("today", datetime_verbs.verb_today)
    registry.register("now", datetime_verbs.verb_now)
    registry.register("formatDate", datetime_verbs.verb_format_date)
    registry.register("parseDate", datetime_verbs.verb_parse_date)
    registry.register("formatTime", datetime_verbs.verb_format_time)
    registry.register("formatTimestamp", datetime_verbs.verb_format_timestamp)
    registry.register("parseTimestamp", datetime_verbs.verb_parse_timestamp)
    registry.register("addDays", datetime_verbs.verb_add_days)
    registry.register("addMonths", datetime_verbs.verb_add_months)
    registry.register("addYears", datetime_verbs.verb_add_years)
    registry.register("dateDiff", datetime_verbs.verb_date_diff)
    registry.register("addHours", datetime_verbs.verb_add_hours)
    registry.register("addMinutes", datetime_verbs.verb_add_minutes)
    registry.register("addSeconds", datetime_verbs.verb_add_seconds)
    registry.register("startOfDay", datetime_verbs.verb_start_of_day)
    registry.register("endOfDay", datetime_verbs.verb_end_of_day)
    registry.register("startOfMonth", datetime_verbs.verb_start_of_month)
    registry.register("endOfMonth", datetime_verbs.verb_end_of_month)
    registry.register("startOfYear", datetime_verbs.verb_start_of_year)
    registry.register("endOfYear", datetime_verbs.verb_end_of_year)
    registry.register("dayOfWeek", datetime_verbs.verb_day_of_week)
    registry.register("dayOfMonth", datetime_verbs.verb_day_of_month)
    registry.register("dayOfYear", datetime_verbs.verb_day_of_year)
    registry.register("monthName", datetime_verbs.verb_month_name)
    registry.register("weekOfYear", datetime_verbs.verb_week_of_year)
    registry.register("quarter", datetime_verbs.verb_quarter)
    registry.register("isLeapYear", datetime_verbs.verb_is_leap_year)
    registry.register("isBefore", datetime_verbs.verb_is_before)
    registry.register("isAfter", datetime_verbs.verb_is_after)
    registry.register("isBetween", datetime_verbs.verb_is_between)
    registry.register("toUnix", datetime_verbs.verb_to_unix)
    registry.register("fromUnix", datetime_verbs.verb_from_unix)
    registry.register("daysBetweenDates", datetime_verbs.verb_days_between_dates)
    registry.register("ageFromDate", datetime_verbs.verb_age_from_date)
    registry.register("isValidDate", datetime_verbs.verb_is_valid_date)
    registry.register("formatLocaleDate", datetime_verbs.verb_format_locale_date)
    registry.register("businessDays", datetime_verbs.verb_business_days)
    registry.register("nextBusinessDay", datetime_verbs.verb_next_business_day)
    registry.register("formatDuration", datetime_verbs.verb_format_duration)

    # Financial verbs
    registry.register("compound", financial_verbs.verb_compound)
    registry.register("discount", financial_verbs.verb_discount)
    registry.register("pmt", financial_verbs.verb_pmt)
    registry.register("fv", financial_verbs.verb_fv)
    registry.register("pv", financial_verbs.verb_pv)
    registry.register("npv", financial_verbs.verb_npv)
    registry.register("irr", financial_verbs.verb_irr)
    registry.register("rate", financial_verbs.verb_rate)
    registry.register("nper", financial_verbs.verb_nper)
    registry.register("depreciation", financial_verbs.verb_depreciation)
    registry.register("variance", financial_verbs.verb_variance)
    registry.register("varianceSample", financial_verbs.verb_variance_sample)
    registry.register("std", financial_verbs.verb_std)
    registry.register("stdSample", financial_verbs.verb_std_sample)
    registry.register("median", financial_verbs.verb_median)
    registry.register("mode", financial_verbs.verb_mode)
    registry.register("percentile", financial_verbs.verb_percentile)
    registry.register("quantile", financial_verbs.verb_quantile)
    registry.register("covariance", financial_verbs.verb_covariance)
    registry.register("correlation", financial_verbs.verb_correlation)
    registry.register("zscore", financial_verbs.verb_zscore)
    registry.register("interpolate", financial_verbs.verb_interpolate)
    registry.register("weightedAvg", financial_verbs.verb_weighted_avg)
    registry.register("movingAvg", financial_verbs.verb_moving_avg)

    # Aggregation verbs
    registry.register("sum", aggregation_verbs.verb_sum)
    registry.register("count", aggregation_verbs.verb_count)
    registry.register("min", aggregation_verbs.verb_min)
    registry.register("max", aggregation_verbs.verb_max)
    registry.register("avg", aggregation_verbs.verb_avg)
    registry.register("first", aggregation_verbs.verb_first)
    registry.register("last", aggregation_verbs.verb_last)
    registry.register("accumulate", aggregation_verbs.verb_accumulate)
    registry.register("set", aggregation_verbs.verb_set)

    # Object verbs
    registry.register("keys", object_verbs.verb_keys)
    registry.register("values", object_verbs.verb_values)
    registry.register("entries", object_verbs.verb_entries)
    registry.register("has", object_verbs.verb_has)
    registry.register("get", object_verbs.verb_get)
    registry.register("merge", object_verbs.verb_merge)

    # Geo verbs
    registry.register("distance", geo_verbs.verb_distance)
    registry.register("inBoundingBox", geo_verbs.verb_in_bounding_box)
    registry.register("toRadians", geo_verbs.verb_to_radians)
    registry.register("toDegrees", geo_verbs.verb_to_degrees)
    registry.register("bearing", geo_verbs.verb_bearing)
    registry.register("midpoint", geo_verbs.verb_midpoint)

    return registry
