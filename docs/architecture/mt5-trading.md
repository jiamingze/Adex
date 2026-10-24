# M18 · Local MT5 research and order preparation

## Contract and boundaries

Routing contract: an explicit XAUUSD/MT5 terminal request defaults to local MT5,
before generic task or browser commerce routing. A correction such as “用MT5下单”
must not reuse an earlier assistant-selected brokerage website. This domain
selection grants no execution permission. Explicit website documentation/tutorial
requests can still use browser research; unrelated shopping remains unchanged.
MT5 progress labels must refer to terminal evidence, not travel or web search.
Gold trading language (黄金交易、现货黄金、伦敦金、做多/做空黄金) also selects
this domain without requiring the literal MT5/XAUUSD identifier. Physical gold
shopping, jewellery and explicitly different instruments (gold ETF/futures) must
not be silently normalized to XAUUSD. Receipt failures must not ask for an
unrelated todo title or schedule time.

The target is the owner's installed macOS MetaTrader 5 Wine prefix. This is a
Tools runner, not a fifth business service or scheduler. No credentials are
accepted by the model or runner: it uses the terminal's existing session.

`snapshot(symbol, bars)` returns terminal connectivity, masked account identity,
account mode, symbol specification, raw broker tick timestamps, M1/M5/H4 OHLCV,
and active pending orders. Missing data is an error, never an empty successful
portfolio. Broker timestamps are not silently relabelled as UTC.

`check(order)` calls the terminal's `order_check` only. A successful preflight is
not an order, fill, reservation, or guarantee of future broker acceptance.
The runner has no `order_send`, position-close or pending-order cancellation
command. Live final submission remains with the account owner.

The pure simulator accepts an immutable proposal, an exact SHA-256 approval,
and the same account/managed-order snapshot. Its output is explicitly
`SIMULATION`, never a broker receipt. Per-order volume is at most 0.01 lots;
broker minimum/step, quote age, entry/SL/TP relationships and strategy ownership
are checked. `UNKNOWN` analysis cannot cancel orders. `NO_SETUP` can propose
cancel-only actions on explicitly strategy-owned tickets. Changed snapshots
invalidate approval; replays must return the stored simulated receipt.

## Implementation plan / state ownership

1. Local read/preflight bridge, closed schemas, deterministic simulator and
   verification on this Mac (implemented).
2. Authenticated host-owner-scoped Tools read transport and built-in Agent
   Skill (implemented). Durable order preparation is pending: persist proposals
   using Tools approvals and effects, reuse Automation's
   lease/epoch/attempt/checkpoint/outbox. No second recovery loop.
3. Client proposal card with account mode, source time, chart provenance,
   exact old tickets/new parameters, risk and approval expiry.
4. Real terminal data + chart import via App File API and analysis integration.
   Browser ChatGPT interaction and order execution are not claimed by simulation.

No database migration is required for the pure read/preflight/simulator increment.
Before adding durable proposals, extend existing Tools approvals/effects rather
than introducing a separate trading approval table. Every leg must have a stable
effect key; external timeout becomes UNKNOWN and must reconcile before retry.

## Open-source review (2026-10-24)

- [meta-trader-5-mcp](https://github.com/CodeWithBehnam/meta-trader-5-mcp):
  studied Wine bridge, serialized terminal access, guard/check/intent/send flow,
  and no write retries after IPC failure. Not installed as a trading server.
- [ClaudeTrading](https://github.com/MichelePolo/ClaudeTrading/tree/main/mt5-trading):
  studied Skill + structured strategy separation. Its Windows/manual-command
  workflow and broad cancel-all functions are not adopted.
- [mql5-skills](https://github.com/ZhijuCen/mql5-skills): studied broker precision,
  strategy magic isolation and result checking. Strategy heuristics are not
  treated as broker rules.
- [mt5-agent-toolkit](https://github.com/smizxe/mt5-agent-toolkit): studied fresh
  artifact/log validation and reproducible backtests. Backtest metrics do not
  certify future returns.

This is independently implemented code; no remote Skill executes on installation.
An unconnected terminal, missing login, market closure, unavailable broker data,
or unavailable analysis provider is reported as `BLOCKED_EXTERNAL`.

## Local setup and observed verification

```sh
# Uses only the existing MT5 prefix; installs no system Python or trading server.
uv run python scripts/setup_mt5_bridge.py
uv run --project services/adex-tools python scripts/mt5_diagnostics.py
uv run --project services/adex-tools pytest services/adex-tools/tests/test_trading.py -q
uv run --project services/adex-agent pytest services/adex-agent/tests/test_skills.py -q
make build test check-style
uv run python scripts/test_stack.py
```

Gold-language routing checks (isolated PostgreSQL, no order sender):

```sh
uv run python scripts/test_stack.py tests/integration/test_mt5_routing.py -q
# Real Qwen text generation; terminal reads disabled in the fixture by default.
ADEX_TEST_REAL_TRADING_LANGUAGE=1 uv run python scripts/test_stack.py tests/integration/test_mt5_routing.py -q -s
# Separately opt into actual owner-authorized MT5 read-only evidence.
ADEX_TEST_REAL_TRADING_LANGUAGE=1 ADEX_TEST_REAL_MT5_READ=1 uv run python scripts/test_stack.py tests/integration/test_mt5_routing.py -k gold_trade -q -s
```

The real model requires the configured DashScope key. Neither flag enables order
submission. The first development real-language check also read terminal data;
fixture terminal access is now independently gated so text tests do not silently
depend on a personal terminal session. Private responses stay in ignored local logs.

The diagnostic prints only connection/mode/count summaries. For an explicit
read-only broker check, pass `--preflight /private/path/order.json`, using the
closed Order fields `kind`, `volume`, `entry`, `sl`, `tp`. No diagnostic command
submits or cancels anything. Do not commit account snapshots or order JSON files.

Tools exposes `POST /internal/trading/context` with a closed body
`{"symbol":"XAUUSD"}`. It requires an Agent-signed `trading:read` token and the
configured `ADEX_COMPUTER_OWNER_ID` while `ADEX_COMPUTER_ENABLED=true`.
Other owners are rejected before terminal activation. This read endpoint does
not grant trading rights; it is not a public client API. Agent's MT5 research
Skill currently supplies XAUUSD data only, with at most 30 bars per timeframe
in model context. Terminal calls are bounded, serialized and never retried as
writes. Do not expose the Wine runtime as an unauthenticated network service.

Observed on this Mac on 2026-10-24:

- Existing terminal connected; non-demo account detected (no private identity
  committed). Read M1/M5/H4, 120 bars each, and pending-order metadata.
- Real `order_check` accepted a 0.01-lot hypothetical pending-order request:
  `retcode=0`. No order was sent, modified, filled or cancelled. This is not a
  market-open test or proof of broker execution.
- Agent-signed HTTP request → Tools → installed Wine MT5 returned
  `TERMINAL_READ_ONLY`, all three data series and `broker_executed=false`.
- Simulator tests use synthetic data and memory-only receipts. They verify
  approval/snapshot mismatch, expiry, lot limits/step, stale quotes, strategy
  ownership and UNKNOWN/NO_SETUP handling. They do not test broker execution,
  durable effects, restart recovery or client confirmation cards.
- Full isolated integration regression: **103 passed, 7 skipped in 380.61s**.
  Agent unit tests: **139 passed**; Tools unit tests: **159 passed**.

`BLOCKED_EXTERNAL` / not delivered: a connected **demo** trading account,
real trade execution/cancellation, native chart screenshot import, browser
ChatGPT upload/analysis, durable trading approvals and the client trading card.
Do not advertise this increment as an end-to-end autonomous trading feature.
