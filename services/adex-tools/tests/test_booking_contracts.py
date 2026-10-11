from datetime import datetime, timezone
from uuid import uuid4
import pytest
from pydantic import ValidationError
from adex_tools.booking.contracts import BookingQuote, capabilities


def test_search_does_not_enable_transactions():
    assert capabilities()["status"] == "BLOCKED_EXTERNAL"
    assert not capabilities()["hotel_order"]
    assert not capabilities()["attraction_reservation"]


def test_quote_requires_verified_inventory_and_timezone():
    data = dict(
        owner_id=uuid4(),
        provider="fixture",
        quote_id="q1",
        product_id="hotel1",
        kind="hotel",
        total="120.00",
        currency="CNY",
        expires_at=datetime.now(timezone.utc),
        terms_hash="a" * 64,
        inventory_verified=True,
    )
    assert str(BookingQuote(**data).total) == "120.00"
    with pytest.raises(ValidationError):
        BookingQuote(**{**data, "inventory_verified": False})
    with pytest.raises(ValidationError):
        BookingQuote(**{**data, "expires_at": datetime.now()})
