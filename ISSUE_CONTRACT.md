# ISSUE CONTRACT

## Pain
Safety regressions can silently convert a protected refusal into an allow, change its reason semantics, or become fragile to nearby argument mutations while flat golden tests reveal too little about the drift.

## Success
- Golden refusal cases bind expected reason codes to a versioned structured taxonomy.
- Unknown reason taxonomy does not silently count as a passing golden case.
- Cases explicitly marked mutation-stable are replayed through a bounded deterministic mutation corpus.
- Cross-version comparisons classify refusal loss, refusal gain, reason change, category change, both-allowed drift, and unchanged behavior.
- Refusal-loss regressions are machine-detectable and version-diff reports are deterministically fingerprinted.
- Duplicate golden-case identity fails closed.

## Boundaries
- Mutation fuzz is bounded deterministic regression coverage, not exhaustive fuzzing.
- Only mutation-stable cases are required to preserve the same refusal reason across mutations.
- The harness evaluates supplied decision functions and supplied cases; it does not independently prove production model behavior.
- No Anthropic affiliation, adoption, production model-policy service, or tool execution claim.
