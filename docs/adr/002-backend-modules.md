# ADR 002: Capability modules and explicit composition

Status: accepted. Date: 2026-10-11.

## Problem

Flat packages and large HTTP entry points combine unrelated capabilities, hide transaction boundaries and make changes difficult to review. Functional completeness does not establish engineering maturity.

## Decision

Keep the four approved service owners. Split Java controllers by capability and move shared conversation/account use cases behind application services. Separate Python composition, schemas, route modules, execution and provider adapters. Preserve contracts and database ownership; do not migrate user data for a package refactor. Add automated architecture/formatting checks and verify with the existing isolated PostgreSQL fault suite.

## Consequences

Internal import paths change and IDE configurations must still launch stable service entry points. Module APIs stay deliberately small. Remaining persistence-heavy HTTP endpoints are visible migration debt, to be extracted with tests rather than hidden behind pass-through interfaces. No production scale claim follows from this decision.
