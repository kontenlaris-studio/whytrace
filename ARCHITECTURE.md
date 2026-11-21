# Architecture — WhyTrace

## Flow

```
ACT     Triage / Billing / Support agents work a refund case
        every action ──record──▶ ┌────────────────────────────────┐
                                 │ MEKO DATAPACK (one audit       │
                                 │ surface): conversations hold   │
EXPLAIN Auditor ──1 query──▶ WHY report (who/what/why/evidence/    │
        when + agent chain), saved back as an ARTIFACT            │
DIAGNOSE Root-cause: cited memory IDs resolved to sources;        │
        stale/expired memory named as culprit                     │
REPLAY  Context slice from the trace re-runs the decision         │
        function ──▶ outcome must match the original              │
RESUME  Context slice restored from any checkpoint trace          │
                                 └────────────────────────────────┘
```

## Meko features used (brief mapping)

| Meko capability | Where WhyTrace uses it |
|---|---|
| Conversations (verbatim record) | Decision traces are conversation messages with `reasoning` and cited-memory metadata (live-verified) |
| Decision traces | The core data model: every action is a structured trace (agent, decision, why, cited IDs, tokens) |
| Artifacts (versioned outputs) | WHY reports stored via `artifact_put`, retrieved via `artifact_get` (live-verified) |
| Self-learning query log | `selflearning_query_log` exposes what the system searched and where recall fell short (live-verified) |
| Memory with provenance | Cited memories resolve to text + source, so "evidence" in a report is inspectable, not asserted |
| Single MCP endpoint | `MekoClient` → `https://mcp.mekodata.ai/mcp`, official tool names from `tools/list` |

## Design decisions

- **Traces are written by code, not by the model's narration.** The acting
  agent's cited memory IDs and the applied rule are recorded at decision time,
  so the audit trail is evidence, not a post-hoc story.
- **Replay is the honesty test.** An explanation that cannot reproduce the
  decision from its own recorded context slice is decoration; WhyTrace's
  replay must match 2/2 in the demo and is part of the selftest.
- **One query, five answers.** The brief's bar is "why in 2 minutes"; WhyTrace
  answers who/what/why/evidence/when from a single trace lookup, versus
  scanning 46 raw events in the demo baseline.
- **Distinct from our Theme-01 entry.** OneMemory governs *what agents may
  learn* (promotion gates for coding standards). WhyTrace explains *what
  agents already did* (audit, root-cause, replay) in a different domain
  (refund operations). Only the Meko client pattern is shared infrastructure.

## Judging criteria mapping (published weights)

- **Use of Meko (30%)** — conversations, decision traces, artifacts and the
  self-learning log in one datapack; live-verified 6/6.
- **Impact & Usefulness (25%)** — incident response and compliance for any
  team running agents that touch money or customers; root-cause in one query.
- **Technical Execution (20%)** — stdlib-only, selftest 10/10, replay-verified
  traces, recorded demo + live results in `data/`.
- **Innovation (15%)** — replay-as-proof auditing: explanations that must
  reproduce the decision they explain.
- **Presentation (10%)** — <5-minute video following the incident story
  (bad decision → why report → culprit memory → replay proof).
