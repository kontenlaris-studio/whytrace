# Submission — ContextCon Theme 07 (WhyTrace)

Deadline: **18 Jan 2027, 00:30 WIB** · Pool $10,000 · Team "Ooblek's Team" (solo)
Second entry by the same team; a separate, substantially different project from
the Theme-01 entry (OneMemory). The Theme-01 submission must remain untouched.

## Checklist

- [x] Working code + selftest 10/10 + recorded demo (`data/demo-output.json`)
- [x] Live Meko verification 6/6 (`data/live-test.json`)
- [x] README + ARCHITECTURE
- [ ] Public GitHub repo
- [ ] Demo video < 5 min (script below), uploaded (unlisted)
- [ ] HackerEarth submission Published with Presentation PDF + Source Code ZIP
- [ ] Verify the Theme-01 OneMemory submission still shows Published afterwards

## Demo video script (< 5 min)

1. **0:00–0:40 — Problem.** Agents approve a $900 refund they shouldn't have.
   Logs are scattered; nobody can say why.
2. **0:40–1:30 — Traces by default.** The refund pipeline (triage, billing,
   support) writes a structured decision trace for every action into one Meko
   datapack.
3. **1:30–2:20 — Explain in 1 query.** The auditor answers who/what/why/
   evidence/when — 5/5 — and stores the report as an artifact.
4. **2:20–3:10 — Root cause.** The report names the culprit: stale memory
   POL-PROMO-LEGACY from an expired promo.
5. **3:10–4:10 — Replay & resume.** Re-running the decision from its recorded
   context slice reproduces it exactly; work resumes from the checkpoint.
6. **4:10–4:50 — Numbers.** 46 raw events → 1 query; replay 2/2; live Meko
   6/6. Close: "Show your work — every decision, explained."
