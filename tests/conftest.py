"""Shared test fixtures for ODIN tests."""
from __future__ import annotations

import pytest
from decimal import Decimal
from datetime import date, datetime

from odin.types.values import (
    OdinNull, OdinBoolean, OdinString, OdinNumber, OdinInteger,
    OdinCurrency, OdinPercent, OdinDate, OdinTimestamp, OdinTime,
    OdinDuration, OdinReference, OdinBinary, OdinVerbExpression,
    OdinArray, OdinObject, NULL, TRUE, FALSE,
)
from odin.types.document import OdinDocument, OdinDocumentBuilder, OdinModifiers


@pytest.fixture
def builder():
    """Fresh document builder."""
    return OdinDocumentBuilder()


@pytest.fixture
def simple_doc(builder):
    """Simple document with a few fields."""
    return (
        builder
        .set("name", OdinString("Alice"))
        .set("age", OdinInteger(30))
        .set("active", TRUE)
        .build()
    )
