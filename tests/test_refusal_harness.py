from __future__ import annotations
import math
import unittest
from src.refusal_harness import (
    DiffKind,
    ReasonCategory,
    ReasonTaxonomy,
    RefuseCase,
    RefusalReplayHarness,
    deterministic_arg_mutations,
)


def decide(tool, args):
    if tool == "bash":
        return False, "RED_LINE"
    return True, "OK"


class HarnessTests(unittest.TestCase):
    def test_pass(self):
        harness = RefusalReplayHarness([
            RefuseCase("1", "bash", {}, "RED_LINE", ReasonCategory.POLICY_RED_LINE)
        ])
        self.assertTrue(harness.all_ok(decide))

    def test_fail_allow(self):
        harness = RefusalReplayHarness([
            RefuseCase("1", "search", {}, "RED_LINE", ReasonCategory.POLICY_RED_LINE)
        ])
        self.assertFalse(harness.all_ok(decide))

    def test_reason_taxonomy_is_structured_and_versioned(self):
        taxonomy = ReasonTaxonomy()
        self.assertEqual(taxonomy.classify("RED_LINE"), ReasonCategory.POLICY_RED_LINE)
        self.assertEqual(taxonomy.classify("NOT_IN_POLICY"), ReasonCategory.CAPABILITY_SCOPE)
        self.assertEqual(taxonomy.classify("UNREGISTERED_REASON"), ReasonCategory.UNKNOWN)
        self.assertEqual(len(taxonomy.fingerprint()), 64)

    def test_unknown_reason_taxonomy_does_not_pass_golden(self):
        harness = RefusalReplayHarness([RefuseCase("1", "bash", {}, "MYSTERY")])
        self.assertFalse(harness.all_ok(lambda tool, args: (False, "MYSTERY")))

    def test_mutation_fuzz_preserves_red_line(self):
        harness = RefusalReplayHarness([
            RefuseCase(
                "red",
                "bash",
                {"cmd": "rm", "recursive": True},
                "RED_LINE",
                ReasonCategory.POLICY_RED_LINE,
                mutation_stable=True,
            )
        ])
        results = harness.run_mutation_fuzz(decide)
        self.assertGreaterEqual(len(results), 4)
        self.assertTrue(all(result.ok for result in results))
        self.assertTrue(all(len(result.args_digest) == 64 for result in results))
        self.assertTrue(harness.mutation_fuzz_ok(decide))

    def test_mutation_generation_is_deterministic(self):
        args = {"b": "two", "a": "one"}
        a = deterministic_arg_mutations(args)
        b = deterministic_arg_mutations({"a": "one", "b": "two"})
        self.assertEqual(a, b)
        self.assertEqual(a[2][0], "drop-a")

    def test_cross_version_diff_detects_refusal_loss(self):
        harness = RefusalReplayHarness([
            RefuseCase("red", "bash", {}, "RED_LINE", ReasonCategory.POLICY_RED_LINE)
        ])
        report = harness.compare_versions(
            "v1",
            decide,
            "v2",
            lambda tool, args: (True, "OK"),
        )
        self.assertTrue(report.refusal_regression)
        self.assertFalse(report.equivalent)
        self.assertEqual(report.diffs[0].kind, DiffKind.REFUSAL_LOST)
        self.assertEqual(len(report.fingerprint), 64)

    def test_cross_version_diff_detects_category_change(self):
        harness = RefusalReplayHarness([
            RefuseCase("red", "bash", {}, "RED_LINE", ReasonCategory.POLICY_RED_LINE)
        ])
        report = harness.compare_versions(
            "v1",
            decide,
            "v2",
            lambda tool, args: (False, "NOT_IN_POLICY"),
        )
        self.assertEqual(report.diffs[0].kind, DiffKind.CATEGORY_CHANGED)

    def test_cross_version_equivalence_is_deterministic(self):
        harness = RefusalReplayHarness([
            RefuseCase("red", "bash", {"cmd": "rm"}, "RED_LINE", ReasonCategory.POLICY_RED_LINE)
        ])
        a = harness.compare_versions("v1", decide, "v1-copy", decide)
        b = harness.compare_versions("v1", decide, "v1-copy", decide)
        self.assertTrue(a.equivalent)
        self.assertFalse(a.refusal_regression)
        self.assertEqual(a.fingerprint, b.fingerprint)
        self.assertEqual(a.diffs[0].kind, DiffKind.UNCHANGED)

    def test_duplicate_case_ids_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_CASE_ID"):
            RefusalReplayHarness([
                RefuseCase("x", "bash", {}, "RED_LINE"),
                RefuseCase("x", "bash", {}, "RED_LINE"),
            ])

    def test_non_json_args_fail_closed(self):
        with self.assertRaises(ValueError):
            RefuseCase("x", "bash", {"score": math.nan}, "RED_LINE")
        with self.assertRaises(ValueError):
            RefuseCase("x", "bash", {"bad": {1, 2}}, "RED_LINE")


if __name__ == "__main__":
    unittest.main()
