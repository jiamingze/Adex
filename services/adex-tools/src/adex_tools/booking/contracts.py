"""Future booking adapters must bind consent to a concrete, expiring quote.

This is a port, not an enabled checkout API. The durable approval/effect ledger
must own consumption and UNKNOWN reconciliation before any adapter can be enabled.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class BookingQuote(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    owner_id: UUID
    provider: str = Field(min_length=1, max_length=80)
    quote_id: str = Field(min_length=1, max_length=180)
    product_id: str = Field(min_length=1, max_length=180)
    kind: Literal["hotel", "attraction"]
    total: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    expires_at: datetime
    terms_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    inventory_verified: Literal[True]

    @model_validator(mode="after")
    def timezone_required(self):
        if self.expires_at.tzinfo is None:
            raise ValueError("QUOTE_TIMEZONE_REQUIRED")
        return self


class BookingProvider(Protocol):
    async def quote(self, *, owner: UUID, request: dict) -> BookingQuote: ...

    async def submit(self, *, quote: BookingQuote, effect_key: str) -> dict: ...

    async def reconcile(self, *, effect_key: str, provider_order_id: str | None) -> dict: ...


def capabilities() -> dict:
    """Never infer transaction capability from browser/search access."""
    return {
        "hotel_order": False,
        "attraction_reservation": False,
        "status": "BLOCKED_EXTERNAL",
        "reason": "NO_BOOKING_PROVIDER_CONFIGURED",
    }
