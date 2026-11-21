# WhyTrace — Show Your Work

**ContextCon (HackerEarth × YugabyteDB) · Theme 07: Best Auditability**
*Anyone should be able to answer "why did the agent do that?" in 2 minutes.*

## The problem (from the official brief)

Multi-agent systems make real decisions — approving refunds, escalating cases,
rejecting applications — but the reasoning is scattered across each agent's raw
logs. When a decision is challenged, nobody can quickly say **who** decided
**what**, **why**, based on **which evidence**, and **when** — let alone replay
the decision to check it, or resume the work from that point.

## The solution

Every agent action writes a **structured decision trace** into one shared Meko
datapack: agent, action, decision, reason, the memory/evidence IDs it cited,
and token usage. WhyTrace's auditor then provides:

1. **Explain in 1 query** — a human-readable WHY report answering all five
   questions (who / what / why / evidence / when) plus the agent chain, stored
   back into the datapack as an artifact.
2. **Root-cause** — when a decision is wrong, the report names the exact
   culprit: in the demo, a billing agent approved a $900 refund at day 45 using
   a *stale, expired* promo memory; WhyTrace points at that memory ID and its
   source.
3. **Replay** — re-run the decision from the exact context slice the agent saw;
   the outcome must match the original, proving the trace is faithful.
4. **Resume** — restore the context slice from any checkpoint trace and
   continue the pipeline from there.

## Measured results (deterministic demo, `data/demo-output.json`)

| Metric | Raw-log baseline | WhyTrace |
|---|---|---|
| Events to dig through | 46 raw events | **1 query** |
| Why-questions answered | partial, manual | **5/5** (who, what, why, evidence, when) |
| Replay fidelity | not possible | **2/2 decisions reproduced exactly** |
| Root cause of the bad decision | unknown | **memory `POL-PROMO-LEGACY`, source "promo-team (expired)"** |

## Run it

```bash
python3 whytrace.py --selftest   # 10/10 checks
python3 whytrace.py --demo       # refund-ops incident story as JSON
python3 live_test.py             # live Meko cycle (needs .env MEKO_API_KEY)
```

No dependencies (Python stdlib). Agents are deterministic so every audit
number is verifiable.

## Live Meko mode — VERIFIED 21 Nov 2026

Against the production Meko account, `live_test.py` passed **6/6**:
`conversation_create` → `conversation_add_message` (decision trace with
reasoning + cited memories) → `artifact_put` (the WHY report) →
`conversation_get` → `artifact_get` → `selflearning_query_log`. The audit
trail lives in the same datapack the agents use — one audit surface, exactly
as the brief asks. Without an API key the client refuses and the local trace
store (identical semantics) is used, so the project demos fully offline.

## Layout

- `whytrace.py` — trace store (local + Meko MCP client), refund-ops pipeline, auditor (explain / root-cause / replay / resume), selftest
- `live_test.py` — live Meko verification cycle
- `ARCHITECTURE.md` — design, Meko feature mapping, judging-criteria mapping
- `SUBMISSION.md` — submission checklist + demo video script (<5 min)
- `data/` — recorded demo output, live-test results, MCP tool schemas
