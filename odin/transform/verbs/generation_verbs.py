"""Generation verbs: uuid, sequence, resetSequence, nanoid."""

from __future__ import annotations

import uuid as uuid_lib
import hashlib
import random
import string
from typing import List

from odin.transform.dyn_value import DynValue, DynType
from odin.transform.verbs.helpers import coerce_str, coerce_num

NANOID_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_-"
NANOID_DEFAULT_SIZE = 21


def _js_signed_rshift(val: int, shift: int) -> int:
    """Emulate signed 32-bit right shift (>>)."""
    if val & 0x80000000:
        # Negative in signed 32-bit: sign-extend then shift
        val = val - 0x100000000
    return (val >> shift) & 0xFFFFFFFF


def _generate_seeded_uuid(seed: str) -> str:
    """Generate deterministic UUID using two DJB2 hashes."""
    hash1 = 5381
    hash2 = 52711
    for ch in seed:
        c = ord(ch)
        hash1 = (((hash1 << 5) + hash1) ^ c) & 0xFFFFFFFF
        hash2 = (((hash2 << 5) + hash2) ^ c) & 0xFFFFFFFF

    b = [0] * 16
    for i in range(8):
        b[i] = _js_signed_rshift(hash1, i * 4) & 0xFF
        b[i + 8] = _js_signed_rshift(hash2, i * 4) & 0xFF

    # Version 5 and variant bits
    b[6] = (b[6] & 0x0F) | 0x50
    b[8] = (b[8] & 0x3F) | 0x80

    h = ''.join(f'{x:02x}' for x in b)
    return f'{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}'


def verb_uuid(args: List[DynValue], ctx: object) -> DynValue:
    if args and not args[0].is_null():
        seed = coerce_str(args[0])
        return DynValue.of_string(_generate_seeded_uuid(seed))
    return DynValue.of_string(str(uuid_lib.uuid4()))


def verb_sequence(args: List[DynValue], ctx: object) -> DynValue:
    accumulators = getattr(ctx, "accumulators", {})
    name = "default"
    if args and not args[0].is_null():
        name = coerce_str(args[0])
    seq_key = f"__seq_{name}"

    start = 1
    if len(args) >= 2:
        sv = coerce_num(args[1])
        if sv is not None:
            start = int(sv)

    if seq_key not in accumulators:
        accumulators[seq_key] = DynValue.of_integer(start)

    current = accumulators[seq_key]
    val = current.as_int()
    accumulators[seq_key] = DynValue.of_integer(val + 1)
    return DynValue.of_integer(val)


def verb_reset_sequence(args: List[DynValue], ctx: object) -> DynValue:
    if not args:
        return DynValue.of_null()
    accumulators = getattr(ctx, "accumulators", {})
    name = coerce_str(args[0])
    seq_key = f"__seq_{name}"
    reset_to = 0
    if len(args) >= 2:
        rv = coerce_num(args[1])
        if rv is not None:
            reset_to = int(rv)
    accumulators[seq_key] = DynValue.of_integer(reset_to)
    return DynValue.of_integer(reset_to)


def verb_nanoid(args: List[DynValue], ctx: object) -> DynValue:
    size = NANOID_DEFAULT_SIZE
    if args and not args[0].is_null():
        sv = coerce_num(args[0])
        if sv is not None:
            size = max(1, int(sv))

    if len(args) >= 2 and not args[1].is_null():
        # Seeded: deterministic via Mulberry32
        seed_str = coerce_str(args[1])
        seed_val = _djb2_hash(seed_str)
        rng = _Mulberry32(seed_val)
        result = []
        for _ in range(size):
            idx = rng.next() & 0x3F
            result.append(NANOID_ALPHABET[idx % len(NANOID_ALPHABET)])
        return DynValue.of_string("".join(result))

    # Random
    result = []
    for _ in range(size):
        result.append(random.choice(NANOID_ALPHABET))
    return DynValue.of_string("".join(result))


def _hex_to_variant(ch: str) -> str:
    """Set variant bits for UUID (10xx)."""
    v = int(ch, 16)
    v = (v & 0x3) | 0x8
    return format(v, "x")


def _djb2_hash(s: str) -> int:
    h = 5381
    for ch in s:
        h = ((h << 5) + h + ord(ch)) & 0xFFFFFFFF
    return h


class _Mulberry32:
    """Seeded 32-bit PRNG."""

    def __init__(self, seed: int) -> None:
        self._state = seed & 0xFFFFFFFF

    def next(self) -> int:
        self._state = (self._state + 0x6D2B79F5) & 0xFFFFFFFF
        t = self._state
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t = (t ^ (t + ((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return (t ^ (t >> 14)) & 0xFFFFFFFF
