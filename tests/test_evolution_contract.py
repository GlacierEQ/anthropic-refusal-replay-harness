import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = json.loads((ROOT / "machine" / "excellence-state.json").read_text(encoding="utf-8"))
POSITION = json.loads((ROOT / "machine" / "canonical-position.json").read_text(encoding="utf-8"))
TARGET = json.loads((ROOT / "machine" / "target-contract.json").read_text(encoding="utf-8"))
RECEIPT_PATH = ROOT / "machine" / "evolution-receipts" / "2026-08-11-taxonomy-mutation-version-diff.json"
RECEIPT = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


class EvolutionContractTests(unittest.TestCase):
    def test_machine_contract_is_conflict_free_json(self):
        raw = (ROOT / "machine" / "target-contract.json").read_text(encoding="utf-8")
        self.assertNotIn("<<<<<<<", raw)
        self.assertNotIn("=======", raw)
        self.assertNotIn(">>>>>>>", raw)
        self.assertEqual(TARGET["current"]["state"], "EVOLVING")

    def test_consumed_cursor_is_exact_proof_bound(self):
        self.assertEqual(RECEIPT["result"], "PASS")
        self.assertEqual(RECEIPT["candidate_source_sha"], "a5d3bdadf80da3ee85020318f8caf8e2b5674e5d")
        self.assertEqual(RECEIPT["workflow_run"], 31462715434)
        event = STATE["evolution_history"][-1]
        self.assertEqual(event["consumed_cursor"], RECEIPT["consumed_cursor"])
        self.assertEqual(event["receipt"], str(RECEIPT_PATH.relative_to(ROOT)))

    def test_next_cursor_is_consistent(self):
        expected = "next:corpus_lineage_minimized_counterexamples_and_signed_regression_baselines"
        self.assertEqual(STATE["evolution_cursor"], expected)
        self.assertEqual(TARGET["next_evolution"], expected)
        self.assertEqual(RECEIPT["next_cursor"], expected)
        self.assertIn("golden-case corpus lineage", POSITION["next_evolution"])
        self.assertIn("sign/version baseline manifests", POSITION["next_evolution"])

    def test_claim_ceiling_and_fuzz_boundary_do_not_inflate(self):
        self.assertEqual(STATE["claim_ceiling"], "PROMOTED")
        boundary = " ".join(TARGET["nonclaims"]).lower()
        self.assertIn("no anthropic affiliation", boundary)
        self.assertIn("mutation fuzz is bounded", boundary)
        self.assertIn("does not execute tools", boundary)


if __name__ == "__main__":
    unittest.main()
