# Prompt Opinion Marketplace Listings - Paste Sheet

Six listings to create. Open Marketplace Studio in the left sidebar of the Prompt Opinion workspace. For each listing, copy the values below into the corresponding fields. The base region for every URL is `europe-west4` Cloud Run, project `maternasquad`.

Common fields for every listing:

- **Publisher**: MaternaSquad
- **Version**: 0.1.0
- **License**: MIT
- **Repository**: https://github.com/arkhangio10/MaternaSquad
- **Contact**: arkhangio@gmail.com
- **Category**: Healthcare / Clinical Decision Support / Maternal Care
- **Tags (apply to all)**: maternal-health, FHIR, ACOG, USPSTF, CDC, multi-agent, A2A, MCP, Synthea, Claude

The clinical safety boilerplate paragraph for every listing:

> This is decision support and patient communication, not diagnosis or treatment. The system satisfies the four 21st Century Cures Act non-device CDS criteria. Every clinical claim is grounded in FHIR R4 resources with inline `[ResourceType/id]` citations to ACOG, USPSTF, ADA, or CDC published guidelines. Demo data is Synthea synthetic, never real PHI.

---

## 1. MaternaSquad MCP Server (the shared toolbox)

- **Listing type**: MCP Server
- **Name**: MaternaSquad MCP - Maternal Clinical Toolbox
- **Endpoint URL**: `https://maternasquad-mcp-mdf575wm2q-ez.a.run.app/mcp`
- **Transport**: streamable-http
- **Tagline**: Eight FHIR-grounded maternal care tools sharing one audited backend.

### Short description (paste into "Summary" / "Subtitle" field)

The shared MCP server behind the MaternaSquad five-agent squad. Eight clinical tools for maternal care: FHIR pregnancy context aggregation, deterministic preeclampsia / gestational diabetes / preterm birth scorers grounded in ACOG and USPSTF, multilingual patient translation, postpartum CDC Hear Her triage, and Da Vinci PAS-shaped prior-auth packet drafting. Single audit trail, single FHIR connection pool, single SHARP context plumbing.

### Long description (paste into "Description" / "Details" field)

```markdown
**Eight tools registered**

1. `fhir_get_pregnancy_context` - aggregates Patient + relevant Conditions, Observations, MedicationRequests into one structured payload.
2. `acog_preeclampsia_risk` - rule-based risk scoring per USPSTF Aspirin 2021 and ACOG Practice Bulletin 222 (2020).
3. `acog_gdm_risk` - rule-based screening per ACOG Practice Bulletin 234 (2021) and ADA Standards 2024.
4. `acog_preterm_birth_risk` - rule-based screening per ACOG Practice Bulletin 232 (2021).
5. `patient_translate_message` - Claude-powered patient-facing message generation. Locale-aware, grade-5 reading level, FHIR-cited.
6. `patient_warning_signs_card` - generates the warning-signs card (Spanish / English) with explicit citations.
7. `postpartum_triage` - matches symptoms against the CDC Hear Her checklist, returns urgency tier and SBAR draft.
8. `pa_draft_evidence_packet` - drafts a prior-auth evidence packet shaped to the Da Vinci PAS implementation guide.

Plus `healthcheck`.

**Why share an MCP**

Centralizes the FHIR aggregation, the risk scorers, the translation prompts, and the audit writer. One place writes audit entries, one connection pool stays warm, one SHARP context flows. Five A2A agents call into this single backend.

**Stack**

FastMCP 2.x streamable-http. FHIR R4 only. Pydantic v2 throughout. Claude Sonnet 4.6 via Anthropic API for narrative reasoning. structlog JSON output. Hosted on Google Cloud Run, project maternasquad, region europe-west4.

**Safety envelope**

Every clinical claim cites a FHIR resource. Risk scorers are deterministic; Claude provides narrative interpretation only. PHI is never logged.
```

---

## 2. Orchestrator Agent (the squad's front door)

- **Listing type**: A2A Agent
- **Name**: MaternaSquad Orchestrator - Plan, Route, Hand Off
- **Endpoint URL**: `https://maternasquad-orchestrator-mdf575wm2q-ez.a.run.app/invoke`
- **Healthcheck**: `https://maternasquad-orchestrator-mdf575wm2q-ez.a.run.app/healthcheck`
- **Tagline**: One door for the clinician. Five specialists behind it.

### Short description

The clinician-facing entry point of the MaternaSquad five-agent squad. Plans which specialists to call (risk, coverage, education, postpartum watch), invokes them in parallel, merges their structured outputs, and produces a 4 to 6 sentence cited clinician handoff. Locale-aware: matches the clinician's language. Trace-id propagated across every hop.

### Long description

```markdown
**What it does**

1. Reads SHARP context from the workspace (patient_id, FHIR URL, locale).
2. Plans which sub-agents are relevant for the clinician's question (keyword router, deliberately LLM-free for speed).
3. Calls all selected sub-agents in parallel via `_invoke` over HTTPS.
4. Merges their structured outputs.
5. Calls Claude Sonnet 4.6 with the merged results and the FHIR resource references the sub-agents cited.
6. Forces inline `[ResourceType/id]` citations in the resulting clinician handoff.
7. Returns plan, per-agent outputs, the citation-backed summary, the union of cited references, and the trace_id.

**Inputs (POST /invoke)**

- Body: `{"user_message": "...", "context": {...}}`
- SHARP headers: `X-SHARP-Patient-Id`, `X-SHARP-FHIR-Server-URL`, `X-SHARP-User-Role`, `X-SHARP-Trace-Id`, `X-SHARP-Locale`

**Output**

- `plan`: list of sub-agents called
- `subagent_outputs`: dict of structured per-agent output
- `clinician_summary`: markdown handoff with inline citations
- `cited_references`: union list of FHIR resource refs

**Demo prompts that work today**

- "Set up this patient for the third trimester. She has been complaining about headaches." (preeclampsia case)
- "Patient is 4 weeks postpartum and reports feeling very sad and disconnected from the baby." (postpartum mental health)
- "This patient has gestational diabetes. Generate the patient-facing education card and a third-trimester risk summary." (with es-US locale for Spanish output)
```

### Sample query (paste into "Example Prompts" if available)

> Set up this patient for the third trimester. She has been complaining about headaches.

---

## 3. Risk Agent

- **Listing type**: A2A Agent
- **Name**: MaternaSquad Risk Agent - Preeclampsia, GDM, Preterm
- **Endpoint URL**: `https://maternasquad-risk-agent-mdf575wm2q-ez.a.run.app/invoke`
- **Healthcheck**: `https://maternasquad-risk-agent-mdf575wm2q-ez.a.run.app/healthcheck`
- **Tagline**: Deterministic ACOG / USPSTF risk scoring with FHIR citations.

### Short description

Computes preeclampsia, gestational diabetes, and preterm birth risk for a pregnant patient using deterministic, rule-based scorers. Each factor cites a specific FHIR resource (Observation, Condition, MedicationRequest). Each rule cites the ACOG Practice Bulletin or USPSTF Recommendation Statement it comes from. No autonomous risk model; the model never invents a number.

### Long description

```markdown
**Why deterministic**

Risk numbers are clinical. We do not let the LLM invent them. The Risk Agent computes scores from rule-based scorers in the MCP server (`acog_preeclampsia_risk`, `acog_gdm_risk`, `acog_preterm_birth_risk`). Claude is only used for narrative interpretation when needed.

**Rules implemented**

- Preeclampsia: USPSTF Aspirin Use 2021 (high-risk markers, moderate-risk markers) + ACOG Practice Bulletin 222 (2020).
- GDM: ACOG Practice Bulletin 234 (2021) + ADA Standards of Care 2024.
- Preterm birth: ACOG Practice Bulletin 232 (2021).

**Output schema**

For each risk: label, level (low/moderate/high), score_text, factors (each with name, present, value, FHIR citation, source), recommendations, cited_references, guideline_source.

**Designed for the Mandel/Hickey lens**

Every claim points to a chart resource. Every recommendation points to a published guideline. Judges can audit any line back to its source.
```

---

## 4. Coverage Agent (Prior Authorization)

- **Listing type**: A2A Agent
- **Name**: MaternaSquad Coverage Agent - Da Vinci PAS Drafter
- **Endpoint URL**: `https://maternasquad-coverage-agent-mdf575wm2q-ez.a.run.app/invoke`
- **Healthcheck**: `https://maternasquad-coverage-agent-mdf575wm2q-ez.a.run.app/healthcheck`
- **Tagline**: Drafts prior-auth packets shaped to the Da Vinci PAS implementation guide.

### Short description

Drafts a prior authorization evidence packet for a maternal-care service request (home BP monitor, glucometer, MRI, etc.). Output is shaped to the HL7 Da Vinci Prior Authorization Support implementation guide. Includes a 4 sentence medical-necessity narrative with FHIR `[ResourceType/id]` citations and a predicted denial-risk tier.

### Long description

```markdown
**Inputs**

`context.service_request_id` is required: the FHIR ServiceRequest the agent should draft a packet for.

**Output**

- PAS-shaped Bundle preview (Patient + Coverage + ServiceRequest + DocumentReference for the narrative).
- Medical-necessity narrative (4 sentences) with inline `[Observation/...]`, `[Condition/...]`, `[MedicationRequest/...]` citations.
- Predicted denial risk: low / moderate / high, with the factors that drove the prediction.

**Demo angle**

Aisha needs a home BP monitor. The Coverage Agent drafts the packet, the predicted denial risk is low because the chart shows a documented BP elevation. The clinician confirms and the packet is sent. No autonomous submission; the human stays in the loop.

**Spec**

HL7 Da Vinci PAS: https://hl7.org/fhir/us/davinci-pas/
```

### Sample query

> Draft the prior-auth packet for the home BP monitor request on this patient.

(Be sure to include `"context": {"service_request_id": "ServiceRequest/<id>"}` in the body.)

---

## 5. Education Agent

- **Listing type**: A2A Agent
- **Name**: MaternaSquad Education Agent - Multilingual, Grade-5, Cited
- **Endpoint URL**: `https://maternasquad-education-agent-mdf575wm2q-ez.a.run.app/invoke`
- **Healthcheck**: `https://maternasquad-education-agent-mdf575wm2q-ez.a.run.app/healthcheck`
- **Tagline**: Patient-facing messages at grade-5 reading level, in the patient's language.

### Short description

Generates patient-facing education and warning-signs material at grade-5 reading level in the patient's locale. Driven by `X-SHARP-Locale` (e.g. `en-US`, `es-US`). Always cites the FHIR conditions, observations, and medications the message references. Always returns the English back-translation underneath so the clinician can verify before sending.

### Long description

```markdown
**Designed for**

Pregnant and postpartum patients across language and literacy levels. The most preventable maternal deaths happen to patients who didn't get information in a form they could use.

**Locale-aware**

Reads `X-SHARP-Locale` and returns the message in that language. Confirmed working today: en-US, es-US.

**Reading level**

Grade-5 target. Short sentences. No medical jargon. Tone: warm, factual, never alarming unless the warning is real.

**Citations**

Every line that mentions a chart fact carries the FHIR reference: `[Patient/...]`, `[Condition/...]`, `[Observation/...]`, `[MedicationRequest/...]`. The clinician sees the citations; the patient sees a clean message.

**Back-translation**

Returns the English version alongside the localized version. The clinician verifies before sending. Mathur and Tripathi judges will recognize this is non-negotiable for cross-language safety.
```

### Sample query

> Generate the patient-facing warning signs card for this patient. Locale is es-US.

---

## 6. Postpartum Watch Agent

- **Listing type**: A2A Agent
- **Name**: MaternaSquad Postpartum Watch - CDC Hear Her Triage
- **Endpoint URL**: `https://maternasquad-postpartum-watch-mdf575wm2q-ez.a.run.app/invoke`
- **Healthcheck**: `https://maternasquad-postpartum-watch-mdf575wm2q-ez.a.run.app/healthcheck`
- **Tagline**: 12-week postpartum surveillance with SBAR drafts. The squad does not sleep.

### Short description

Triages postpartum patient messages against the CDC Hear Her urgent maternal warning signs checklist. Returns a structured urgency tier (`safe_routine`, `urgent_clinic_today`, `urgent_clinic_now`, `emergency_911`), the matched warning signs with FHIR citations, and an SBAR draft for the on-call clinician. Most preventable maternal deaths happen in the first 12 weeks postpartum; this is the window the squad watches.

### Long description

```markdown
**The why**

CDC data: 80 percent of maternal deaths are preventable. A large fraction occur in the postpartum window, often when the patient is at home, alone, often at night, often without language support. By the time they reach a clinician, hours have been lost. The Postpartum Watch Agent stays awake.

**Inputs**

- Body: `{"user_message": "<patient message or symptom description>", "context": {}}`
- SHARP headers including `X-SHARP-Patient-Id` and `X-SHARP-FHIR-Server-URL`.

**Output**

- `urgency`: one of `safe_routine`, `urgent_clinic_today`, `urgent_clinic_now`, `emergency_911`.
- `matched_warning_signs`: list of CDC Hear Her signs that matched, each with FHIR citation.
- `sbar_draft`: structured Situation-Background-Assessment-Recommendation for the on-call OB.
- `cited_references`: FHIR resources backing the assessment.

**Reference**

CDC Hear Her: https://www.cdc.gov/hearher/maternal-warning-signs/index.html

**Designed for the Proctor / Mathur lens**

Postpartum surveillance during the actual danger window, with structured handoff a covering clinician can act on in seconds.
```

### Sample query

> Patient message at 2 AM: "Me duele mucho la cabeza, no puedo ver bien." (Spanish: "I have a bad headache and I can't see well.")

---

## After you publish all six

Run a final smoke test: from your Prompt Opinion workspace, select Cordelia (or whichever Synthea persona is the demo star), open chat, and ask: *"Set up this patient for the third trimester. She has been complaining about headaches."* You should see the orchestrator route, the risk agent panel populate, and the citation tokens appear inline. That confirms the full chain is wired through the platform, not just the Cloud Run URLs.
