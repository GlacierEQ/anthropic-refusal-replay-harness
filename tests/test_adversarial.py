from __future__ import annotations
import unittest
from src.refusal_harness import RefuseCase, RefusalReplayHarness

class Adv(unittest.TestCase):
    def test_reason_drift_fails(self):
        h = RefusalReplayHarness([RefuseCase("1", "bash", {}, "RED_LINE")])
        def decide(tool, args):
            return False, "OTHER"
        self.assertFalse(h.all_ok(decide))
    def test_allow_when_should_refuse_fails(self):
        h = RefusalReplayHarness([RefuseCase("1", "bash", {}, "RED_LINE")])
        self.assertFalse(h.all_ok(lambda t, a: (True, "OK")))
    def test_exact_reason_pass(self):
        h = RefusalReplayHarness([RefuseCase("1", "bash", {}, "RED_LINE")])
        self.assertTrue(h.all_ok(lambda t, a: (False, "RED_LINE")))

