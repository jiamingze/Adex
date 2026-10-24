"""Closed financial data contracts; a proposal never grants execution permission."""

from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from typing import Annotated, Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Positive = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Order(Strict):
    kind: Literal["BUY_LIMIT", "SELL_LIMIT", "BUY_STOP", "SELL_STOP"]
    volume: Annotated[Decimal, Field(gt=0, le=Decimal("0.01"), allow_inf_nan=False)]
    entry: Positive
    sl: Positive
    tp: Positive


class Snapshot(Strict):
    account_ref: str = Field(min_length=1, max_length=100)
    strategy_id: int = Field(gt=0)
    symbol: str = Field(pattern=r"^[A-Za-z0-9_.#-]{1,40}$")
    observed_at: AwareDatetime
    bid: Positive
    ask: Positive
    tick_size: Positive
    volume_min: Positive
    volume_step: Positive
    stops_distance: Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
    orders: dict[str, int] = Field(default_factory=dict, max_length=1000)

    def digest(self) -> str:
        return sha256(self.model_dump_json().encode()).hexdigest()


class Proposal(Strict):
    snapshot_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    expires_at: AwareDatetime
    analysis: Literal["SETUP", "NO_SETUP", "UNKNOWN"]
    cancel_tickets: list[str] = Field(default_factory=list, max_length=20)
    new_orders: list[Order] = Field(default_factory=list, max_length=1)


def validate_proposal(snapshot: Snapshot, proposal: Proposal, now: datetime) -> None:
    if proposal.snapshot_hash != snapshot.digest():
        raise ValueError("TRADING_SNAPSHOT_CHANGED")
    if proposal.expires_at <= now:
        raise ValueError("TRADING_APPROVAL_EXPIRED")
    age = (now - snapshot.observed_at).total_seconds()
    if not 0 <= age <= 60 or snapshot.ask < snapshot.bid:
        raise ValueError("TRADING_QUOTE_STALE_OR_INVALID")
    if proposal.analysis == "UNKNOWN" or (proposal.analysis == "NO_SETUP" and proposal.new_orders):
        raise ValueError("TRADING_ANALYSIS_NOT_ACTIONABLE")
    if len(set(proposal.cancel_tickets)) != len(proposal.cancel_tickets):
        raise ValueError("TRADING_DUPLICATE_TICKET")
    for ticket in proposal.cancel_tickets:
        if snapshot.orders.get(ticket) != snapshot.strategy_id:
            raise ValueError("TRADING_ORDER_OWNERSHIP")
    for order in proposal.new_orders:
        if order.volume < snapshot.volume_min or order.volume % snapshot.volume_step:
            raise ValueError("TRADING_VOLUME_NOT_SUPPORTED")
        if any(price % snapshot.tick_size for price in (order.entry, order.sl, order.tp)):
            raise ValueError("TRADING_PRICE_PRECISION")
        buy = order.kind.startswith("BUY")
        levels = order.sl < order.entry < order.tp if buy else order.tp < order.entry < order.sl
        relation = {
            "BUY_LIMIT": order.entry < snapshot.ask,
            "BUY_STOP": order.entry > snapshot.ask,
            "SELL_LIMIT": order.entry > snapshot.bid,
            "SELL_STOP": order.entry < snapshot.bid,
        }[order.kind]
        reference = snapshot.ask if buy else snapshot.bid
        if (
            not levels
            or not relation
            or min(abs(order.entry - order.sl), abs(order.tp - order.entry), abs(order.entry - reference))
            < snapshot.stops_distance
        ):
            raise ValueError("TRADING_INVALID_LEVELS")
