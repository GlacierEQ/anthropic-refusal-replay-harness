#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from refusal_harness import RefuseCase, RefusalReplayHarness

def main() -> int:
    h = RefusalReplayHarness([RefuseCase("1", "bash", {}, "RED_LINE")])
    ok = h.all_ok(lambda t, a: (False, "RED_LINE"))
    results = h.run(lambda t, a: (False, "RED_LINE"))
    out = {"all_ok": ok, "n": len(results), "first_reason": results[0].actual, "ok": ok and results[0].actual == "RED_LINE"}
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1
if __name__ == "__main__":
    raise SystemExit(main())
