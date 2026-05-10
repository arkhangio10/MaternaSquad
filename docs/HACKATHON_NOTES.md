# Hackathon Notes

## Submission tracker

- [ ] Register on Prompt Opinion and confirm the SHARP spec details. If header names differ, update `mcp_server/src/sharp/context.py`.
- [ ] Generate Synthea personas. Verify Aisha has the postpartum preeclampsia event in the timeline.
- [ ] Local end-to-end smoke test passes: `.\scripts\smoke_test.ps1 <patient-id>`.
- [ ] Each agent passes its individual healthcheck.
- [ ] Deploy to Cloud Run. All 6 services green.
- [ ] Publish to the Prompt Opinion Marketplace: 1 MCP server + 5 agents = 6 listings.
- [ ] Record demo video. Length under 3:00.
- [ ] Verify "SYNTHETIC DATA" watermark on every patient screen in the video.
- [ ] Submit before May 11, 2026 at 11:00 PM EDT.

## Judge alignment cheatsheet

| Judge | Strength | What this submission shows them |
|---|---|---|
| Alice Zheng MD MBA MPH | Women's health x AI VC (Evvy, Millie, Cofertility) | Maternal mortality, multilingual patient communication, postpartum surveillance. Bullseye. |
| Josh Mandel MD | FHIR architect, Microsoft Research | A2A multi-agent collaboration with proper SHARP context propagation across 5 hops. FHIR R4 grounded with citations. Banterop-style language-first interoperability in action. |
| Joshua Hickey | Mayo Clinic Principal Tech PM | Workflow that reduces visit burden, auto-drafts PA packets, surfaces missing data. Mayo has a heavy OB program. |
| Parth Tripathi | Vertex AI Gemini Staff Engineer | Gemini 2.5 Flash for personalized risk communication and structured output. Clean Vertex AI showcase. |
| Piyush Mathur MD | Cleveland Clinic intensivist, BrainX | Severe maternal morbidity is ICU-adjacent. Postpartum preeclampsia, hemorrhage. SBAR escalation handoffs. |
| Stephon Proctor PhD | CHOP ACHIO (CHIPPER) | Perinatal angle. Postpartum mother + newborn dyad. |

## Why this is on theme

The hackathon name is **Agents Assemble**. A submission with 1 agent is off theme. A submission with 5 agents that literally light up one by one as a squad is on theme.

## Risk register and mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Scope: 5 agents in the time available | High | Build Orchestrator, Risk, and Postpartum Watch first (the demo critical path). Coverage and Education can be lighter implementations if needed. |
| Emotional manipulation backlash | Medium | Make the technical depth real. Cite ACOG by Practice Bulletin number. Show the audit trail. Always label data SYNTHETIC. |
| FDA SaMD drift | Medium | Risk scorers stay rule-based. Gemini provides narrative only. Always satisfy the four 21st Century Cures Act non-device CDS criteria. |
| PHI in demo | Critical | Synthea only. Watermark every screen. Sanity-check the recording before submission. |
| SHARP spec drift | Medium | All header names live in `sharp/context.py`. Swap in one place if the official spec differs. |
| Cloud Run cold start during demo | Medium | Pre-warm via healthcheck pings. Keep min_instances=1 for the demo window. |
| Gemini rate limit during recording | Low | Pre-record JSON responses for the agents. The narrative does not change. |

## Prompt Opinion Marketplace listings

Prepare 6 distinct listings:

1. **maternasquad-mcp** — shared MCP server with 8 tools.
2. **maternasquad-orchestrator** — A2A agent, front door.
3. **maternasquad-risk-agent** — A2A agent, ACOG risk stratification.
4. **maternasquad-coverage-agent** — A2A agent, PA packet drafter.
5. **maternasquad-education-agent** — A2A agent, multilingual teach-back.
6. **maternasquad-postpartum-watch** — A2A agent, postpartum symptom triage.

Each listing should include:
- Short description, 1 to 2 sentences.
- Required SHARP context fields.
- Inputs and outputs schema.
- Example invocation.
- Safety note (synthetic data, decision support, clinician-confirmed).

## Citations to keep handy in case judges ask

- USPSTF Aspirin Use to Prevent Preeclampsia, 2021 final recommendation.
- ACOG Practice Bulletin No. 222, Gestational Hypertension and Preeclampsia, 2020.
- ACOG Practice Bulletin No. 234, Pregestational and Gestational Diabetes, 2021.
- ACOG Practice Bulletin No. 232, Preterm Labor, 2021.
- ACOG Practice Bulletin No. 736, Optimizing Postpartum Care, 2018.
- CDC Hear Her campaign warning signs.
- CDC Pregnancy Mortality Surveillance System data, 2017 to 2019 figures.
- ADA Standards of Care 2024.
- HL7 Da Vinci PAS IG v2.1.0.
- 21st Century Cures Act Section 3060 (CDS device exemption criteria).
- FDA Clinical Decision Support Software final guidance (Sept 2022, updated Jan 2026).

## What we explicitly did NOT build (and why)

- A custom UI. The platform requires demos to run inside Prompt Opinion.
- A predictive risk model. Stays inside FDA SaMD non-device territory.
- A rules engine for payer-specific PA policies. Out of scope for the demo; we use generic CMS framing.
- Auto-submission of PA packets. Clinicians review and click Submit.
- Real EHR integration via SMART on FHIR. Out of scope for hackathon; HAPI loaded with Synthea is the substitute.

## Submission checklist (final pass)

- [ ] All code committed to a public Git repo.
- [ ] README has a clear "How to run" section that works from a clean clone.
- [ ] Demo video is under 3:00.
- [ ] Marketplace listings live.
- [ ] Architecture diagram in `docs/ARCHITECTURE.md` matches what we built.
- [ ] At least one happy-path test per MCP tool.
- [ ] No `TODO` markers in code submitted as-is. Either remove them or convert to tracked issues.
- [ ] License file present.
- [ ] No real PHI anywhere. Run a final search across the repo for common PHI patterns.
