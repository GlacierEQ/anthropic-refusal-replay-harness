from __future__ import annotations
import unittest
from src.refusal_harness import RefuseCase, RefusalReplayHarness

def decide(tool, args):
    if tool == "bash":
        return False, "RED_LINE"
    return True, "OK"

class HarnessTests(unittest.TestCase):
    def test_pass(self):
        h = RefusalReplayHarness([RefuseCase("1", "bash", {}, "RED_LINE")])
        self.assertTrue(h.all_ok(decide))

    def test_fail_allow(self):
        h = RefusalReplayHarness([RefuseCase("1", "search", {}, "RED_LINE")])
        self.assertFalse(h.all_ok(decide))

if __name__ == "__main__":
    unittest.main()
