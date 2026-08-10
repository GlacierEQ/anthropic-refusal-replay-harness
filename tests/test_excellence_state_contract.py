import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = json.loads((ROOT / "machine" / "excellence-state.json").read_text(encoding="utf-8"))
TARGET = json.loads((ROOT / "machine" / "target-contract.json").read_text(encoding="utf-8"))

STAGES = [
    ("IDENTITY_RESOLVED", "IDENTITY_RESOLVED"),
    ("PROBLEM_VERIFIED", "PROBLEM_VERIFIED"),
    ("TARGET_CONTRACTED", "TARGET_CONTRACT_FROZEN"),
    ("SEEDED", "DONOR_PLAN_RESOLVED"),
    ("VERTICAL_SLICE", "VERTICAL_SLICE_ALIVE"),
    ("IMPLEMENTED", "CENTRAL_MECHANISM_PRESENT"),
    ("TESTED", "DETERMINISTIC_PROOF_GREEN"),
    ("ADVERSARIAL_VERIFIED", "ADVERSARIAL_SURVIVAL"),
    ("OPERABLE", "OPERABLE_AND_OBSERVABLE"),
    ("PROOF_REPRODUCED", "PROOF_RECEIPT_BOUND"),
    ("PROMOTED", "AUTHORITY_BOUND"),
]


class ExcellenceStateContractTests(unittest.TestCase):
    def test_promoted_state_has_every_prerequisite_gate(self):
        self.assertEqual(STATE["principal_state"], "PROMOTED")
        for _, gate in STAGES:
            self.assertEqual(STATE["gates"].get(gate, {}).get("status"), "PASS", gate)

    def test_target_contract_and_donor_plan_are_resolved(self):
        self.assertEqual(TARGET["identity"]["repository_id"], STATE["repository"])
        self.assertEqual(TARGET["current"]["principal_state"], STATE["principal_state"])
        self.assertEqual(TARGET["donor_plan"]["status"], "RESOLVED")
        self.assertEqual(TARGET["donor_plan"]["strategy"], "INDEPENDENT_MECHANISM_PRESERVED")

    def test_canonical_position_is_the_next_unresolved_gate(self):
        self.assertEqual(STATE["gates"]["CANONICAL_POSITION_RESOLVED"]["status"], "PENDING")
        self.assertIn("canonical_position", STATE["evolution_cursor"])

    def test_reconciliation_preserves_promotion_claim_ceiling(self):
        self.assertEqual(STATE["reconciliation"]["previous_state_claim"], "PROMOTED_WITH_PREREQUISITE_GAPS")
        self.assertFalse(TARGET["current"]["deployed"])


if __name__ == "__main__":
    unittest.main()
