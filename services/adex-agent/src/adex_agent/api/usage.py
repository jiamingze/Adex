"""Usage HTTP adapter; scopes are checked before invoking capabilities."""

from uuid import UUID
from fastapi import APIRouter, Request
import os
from adex_agent.dependencies import core

router = APIRouter()


@router.get("/internal/usage")
async def usage(request: Request):
    claims = core.require(request, "app", "usage:read")
    owner = UUID(claims["owner"])
    counts = await core.query(
        "SELECT state,count(*) AS calls FROM invocations WHERE owner_id=%s AND created_at>=date_trunc('day',now()) GROUP BY state",
        (owner,),
    )
    tokens = await core.query(
        "SELECT COALESCE(sum(CASE WHEN result->'usage'->>'prompt_tokens' ~ '^[0-9]+$' THEN (result->'usage'->>'prompt_tokens')::bigint ELSE 0 END),0) AS input_tokens,COALESCE(sum(CASE WHEN result->'usage'->>'completion_tokens' ~ '^[0-9]+$' THEN (result->'usage'->>'completion_tokens')::bigint ELSE 0 END),0) AS output_tokens FROM invocations WHERE owner_id=%s AND created_at>=date_trunc('day',now())",
        (owner,),
        one=True,
    )
    estimated = None
    if os.getenv("ADEX_PRICE_INPUT_PER_MILLION") and os.getenv("ADEX_PRICE_OUTPUT_PER_MILLION"):
        from decimal import Decimal

        input_rate = Decimal(os.environ["ADEX_PRICE_INPUT_PER_MILLION"])
        output_rate = Decimal(os.environ["ADEX_PRICE_OUTPUT_PER_MILLION"])
        if input_rate.is_finite() and output_rate.is_finite() and input_rate >= 0 and output_rate >= 0:
            estimated = str(
                (
                    Decimal(tokens["input_tokens"]) * input_rate
                    + Decimal(tokens["output_tokens"]) * output_rate
                )
                / 1_000_000
            )
    return {
        "tokens": tokens,
        "estimated_cost": estimated,
        "currency": os.getenv("ADEX_PRICE_CURRENCY", "CNY"),
        "provider": os.getenv("ADEX_MODEL_PROVIDER", "minimax"),
        "daily_call_limit": int(os.getenv("ADEX_DAILY_MODEL_CALL_LIMIT", "50")),
        "states": counts,
        "pricing": "Provider billing is authoritative; local call counts do not imply currency cost",
    }
