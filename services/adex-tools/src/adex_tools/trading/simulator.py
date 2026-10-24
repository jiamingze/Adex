"""Pure, process-local test simulator. Never represents a terminal or durable ledger."""

from datetime import datetime, timezone
from hashlib import sha256
from hmac import compare_digest
from copy import deepcopy
from .contracts import Proposal, Snapshot, validate_proposal


def proposal_hash(proposal: Proposal) -> str:
    return sha256(proposal.model_dump_json().encode()).hexdigest()


class Simulator:
    def __init__(self):
        self.receipts: dict[str, dict] = {}

    def execute(self, snapshot: Snapshot, proposal: Proposal, approved_hash: str) -> dict:
        # Revalidate even model_copy-created instances; no test-only bypass of lot limits.
        proposal = Proposal.model_validate(proposal.model_dump())
        snapshot = Snapshot.model_validate(snapshot.model_dump())
        key = proposal_hash(proposal)
        if not compare_digest(key, approved_hash):
            raise ValueError("TRADING_APPROVAL_MISMATCH")
        validate_proposal(snapshot, proposal, datetime.now(timezone.utc))
        if key not in self.receipts:
            self.receipts[key] = {
                "mode": "SIMULATION",
                "broker_executed": False,
                "proposal_hash": key,
                "cancelled": proposal.cancel_tickets,
                "created": [
                    {"simulation_id": f"sim:{key[:16]}:{i}", **o.model_dump(mode="json")}
                    for i, o in enumerate(proposal.new_orders)
                ],
            }
        return deepcopy(self.receipts[key])
