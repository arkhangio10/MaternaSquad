# Demo Script

> Target: 3:00 max. Submission requires the demo to run inside the Prompt Opinion platform.

## Cast

- **Aisha Williams**, 32, Black, Detroit. BMI 31, prior preterm birth, current pregnancy with rising BP. Demo star.
- **Sofia Ramirez**, 28, Hispanic, Houston. GDM, prefers Spanish. Backup angle.
- **Jordan Bell**, 19, rural Kentucky. Postpartum mental health risk. Backup angle.

For the 3-minute video we focus on Aisha. Sofia and Jordan show in still frames during transitions to demonstrate that the system is multi-persona.

## Storyboard (timecodes are upper bounds)

### 0:00 to 0:15 — Cold open

Black screen. Single line of white text fades in:

> "In the United States, a woman dies in pregnancy or postpartum every 12 hours."
> "80 percent of these deaths are preventable."
> *Source: CDC, 2024.*

Cut to title card: **MaternaSquad. The Avengers of Maternal Care.**

### 0:15 to 0:35 — Meet Aisha

Voice-over (calm, factual):

> "This is Aisha Williams. 32 years old. 28 weeks pregnant. She lives 45 minutes from her OB clinic. Her last visit, her blood pressure was creeping up."

On screen: Synthea-derived patient view in Prompt Opinion. Patient banner shows "SYNTHETIC DATA" watermark. Show Conditions list (preeclampsia history flag, BMI 31), recent BP Observations trending up.

### 0:35 to 1:00 — Squad assembles

Clinician types in the Prompt Opinion chat:

> "Set up Aisha for the third trimester. She's been complaining about headaches."

Cut to the **Orchestrator** agent. On screen, 5 hexagonal icons light up one by one as the squad activates. Voice-over:

> "MaternaSquad. Five specialist agents. One mother."

Show the Orchestrator's plan card listing: Risk Agent, Postpartum Watch Agent (preeclampsia symptom flag), Education Agent.

### 1:00 to 1:30 — Risk Agent does its thing

Cut to **Risk Agent** output card. Voice-over reads the headline:

> "Severe preeclampsia risk. Per USPSTF 2021 and ACOG Practice Bulletin 222."

On screen, the structured output. Highlight the citations: `[Observation/bp-obs-id]`, `[Condition/preterm-history-id]`, `[Observation/bmi-obs-id]`. Highlight that the preventive plan (low-dose aspirin) was already started on a specific date, with the FHIR MedicationRequest reference.

Voice-over:

> "Every claim points to a chart resource. Every recommendation cites a published guideline."

### 1:30 to 2:00 — Coverage and Education in parallel

Split screen.

Left: **Coverage Agent** drafts a prior-auth packet for a home BP monitor. Show the medical-necessity narrative (4 sentences) with `[ResourceType/id]` tokens, and the PAS-shaped Bundle preview. Predicted denial risk: **low**.

Right: **Education Agent** generates a Spanish-language warning-signs card at grade-5 reading level. Show the card on a phone mockup. Show the English back-translation underneath for the clinician to verify before sending.

Voice-over:

> "Aisha gets a card she can read. Her clinician gets a packet that won't bounce."

### 2:00 to 2:30 — Time jump

Hard cut. On-screen text: **6 days postpartum. 2:14 AM.**

A patient-message bubble appears in Spanish:

> "Me duele mucho la cabeza, no puedo ver bien."

Cut to the **Postpartum Watch Agent**. The triage card snaps into focus:

- Urgency: **urgent_clinic_now**
- Matched warning signs: severe headache, vision changes (CDC Hear Her).
- SBAR draft for the on-call OB.

Voice-over:

> "Postpartum preeclampsia. Most maternal deaths happen here, in the first 12 weeks after delivery. The squad doesn't sleep."

### 2:30 to 2:50 — Outcome and audit

Cut to outcome card:

> "Aisha was diagnosed with postpartum preeclampsia and treated. She survived."

Then cut to the audit trail: a vertical list of timestamped JSON-line entries showing every agent and tool call, the trace_id propagating across all 5 agents, the FHIR resources cited.

Voice-over:

> "Every decision logged. Every claim cited. Every action approved by a human."

### 2:50 to 3:00 — Closing

White text on black:

> "5 agents. 1 mother. 0 deaths."
> "MaternaSquad."
> "Built on Prompt Opinion. Powered by Claude Sonnet 4.6 via Anthropic."

End.

## Recording checklist

- [ ] Synthea has been regenerated with the latest custom module.
- [ ] All 6 services healthchecked green on Cloud Run before recording.
- [ ] "SYNTHETIC DATA" watermark visible on every patient screen.
- [ ] No real names anywhere in the screen recording (check Recent Patients lists).
- [ ] Audio levels normalized.
- [ ] Final length under 2:55 (give yourself buffer).
- [ ] Captions in English, available toggle for Spanish.
- [ ] First frame: project name. Last frame: project name.

## Fallback for live demo failures

- If Gemini is rate-limited during recording, switch to a pre-recorded JSON response file. The narrative does not change.
- If HAPI is slow, use a pre-warmed bundle in `synthea/output/cached/`.
- If Cloud Run cold starts cause a delay, hit each service's `/healthcheck` 30 seconds before recording.

## What the judges should walk away remembering

1. Five distinct agents collaborating with a shared MCP server. (On theme.)
2. Every claim cited to a FHIR resource and a published guideline. (Mandel and Hickey.)
3. Multilingual patient-facing communication. (Tripathi and Zheng.)
4. Postpartum surveillance during the actual danger window. (Mathur and Proctor.)
5. The audit trail. (Everyone.)
