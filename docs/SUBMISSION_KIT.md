# MaternaSquad Submission Kit

Everything you need to copy-paste on submission day, in one place.

---

## 1. Po Care Coordinator - System Prompt

Open the **Configure Agent** modal for "MaternaSquad Care Coordinator" under `Agents → Orchestrator Agents`. Click the **System Prompt** tab. Paste the block below.

```
You are MaternaSquad Care Coordinator, a clinical decision-support assistant for pregnant and postpartum patients. You operate inside the Prompt Opinion workspace alongside a clinician.

ROLE
You coordinate maternal-care reasoning by calling tools on the MaternaSquad MCP server. You do not diagnose, prescribe, or auto-submit anything to a payer. You draft; the clinician decides.

HARD CONSTRAINTS
- Every clinical claim about THIS patient must include an inline FHIR citation in the format [ResourceType/id], for example [Observation/1371] or [Condition/1084]. If a tool returns no FHIR resources to cite, say so explicitly instead of inventing claims.
- Risk numbers come ONLY from the deterministic MCP tools (acog_preeclampsia_risk, acog_gdm_risk, acog_preterm_birth_risk). Never invent a risk score.
- Recommendations cite a published guideline by name and year (ACOG Practice Bulletin 222 (2020), USPSTF Aspirin 2021, ADA Standards 2024, CDC Hear Her).
- Match the patient's locale for any patient-facing content. The Prompt Opinion workspace's selected patient and language drive this.
- Synthetic data only. Never assume the patient is real.

WORKFLOW
1. Read the clinician's question and the selected patient context.
2. Call fhir_get_pregnancy_context to load the patient's chart, then choose the relevant tool(s):
   - For risk questions: acog_preeclampsia_risk, acog_gdm_risk, acog_preterm_birth_risk
   - For patient-facing materials: patient_translate_message or patient_warning_signs_card
   - For postpartum symptoms: postpartum_triage
   - For prior-auth drafts: pa_draft_evidence_packet (requires service_request_id from the clinician)
3. Synthesize a 4 to 6 sentence clinician handoff that cites the FHIR resources and guidelines you used. Use the patient's language.
4. Output structure:
   - Headline: one-sentence clinical takeaway with the most important [ResourceType/id] citation.
   - Recommendations: 2 to 4 bullets, each cited.
   - If postpartum symptoms triggered urgent_clinic_now or emergency_911, surface that FIRST and include the SBAR draft.

REFUSAL
If the clinician asks for a definitive diagnosis, a specific medication dose without a guideline reference, or anything that would auto-submit to a payer or EHR, refuse politely and explain that you draft for clinician review only.
```

After pasting, click **Save**. Then go back into the agent and click the **Tools** tab. Attach the **MaternaSquad MCP - Maternal Clinical Toolbox** server. Save again.

To test the chat: open a workspace, select **Patient/1076** (Cordelia), and ask:

```
Set up this patient for the third trimester. She has been complaining about headaches.
```

If it routes to MCP tools and returns a cited handoff, the demo flow is wired.

---

## 2. Devpost project copy

Project URL: https://agents-assemble.devpost.com/

### Project name

```
MaternaSquad
```

### Tagline (256 char max)

```
Five A2A agents collaborating around one mother to reduce preventable maternal morbidity. Cited to FHIR R4 and ACOG, USPSTF, ADA, CDC. Built on Prompt Opinion + Claude Sonnet 4.6 + FastMCP. Demo data is Synthea, never real PHI.
```

### Inspiration

```
Every 12 hours a woman dies in pregnancy or postpartum in the United States. Eighty percent of those deaths are preventable (CDC, 2024). Most preventable deaths occur in postpartum, when the patient is at home, sometimes alone, sometimes at night, sometimes without language support. By the time a clinician is reached, hours have been lost. We wanted to build a squad of agents that does not sleep during that danger window.
```

### What it does

```
MaternaSquad is five specialist A2A agents that share one MCP toolbox.

The Orchestrator routes the clinician's question. The Risk Agent stratifies preeclampsia, gestational diabetes, and preterm birth risk per ACOG and USPSTF, with every factor cited to a FHIR Observation or Condition. The Coverage Agent drafts prior-authorization packets shaped to the HL7 Da Vinci PAS implementation guide. The Education Agent generates patient-facing material at grade-5 reading level in the patient's language and returns the English back-translation for clinician verification. The Postpartum Watch Agent triages symptom messages against the CDC Hear Her warning signs and drafts an SBAR for the on-call clinician.

Every clinical claim cites a FHIR R4 resource. Every recommendation cites a published guideline. Demo data is Synthea synthetic; no real PHI ever.
```

### How we built it

```
Stack: Python 3.11, Claude Sonnet 4.6 via Anthropic API for narrative reasoning, FastMCP 3.x for the shared MCP server (streamable-http transport), FastAPI for the five A2A agents (each publishing an A2A v0.2 agent card at /.well-known/agent-card.json), HAPI FHIR R4 in Docker, Synthea with a custom maternal-care module, deployed on Google Cloud Run via a 9-step Cloud Build pipeline.

Risk numbers come from deterministic Python scorers that reproduce the published ACOG and USPSTF criteria; Claude only writes the narrative. Citation guards in the LLM wrapper reject any clinical narrative that lacks at least one [ResourceType/id] inline token. Every agent and tool call writes a JSON-line audit entry the clinician can read.

Listed on Prompt Opinion as 1 MCP server plus 5 External Agents.
```

### Challenges we ran into

```
Cloud Build substitution variables were silently splitting on PowerShell commas, producing tags like "europe-west4 _REPO=maternasquad" until we wrapped the substitutions argument in double quotes. Anthropic's API rejected our generate_structured calls because adaptive thinking is incompatible with forced tool_choice; we dropped thinking from the structured path. Secret Manager stored a trailing CRLF on our API key because PowerShell pipes auto-append newlines, which httpx then rejected as illegal header value. The A2A protocol agent card schema in Prompt Opinion is strict (camelCase, supportedInterfaces with protocolBinding and protocolVersion required). Cloud Run terminates TLS upstream so the agent self-reports an http URL unless you honor X-Forwarded-Proto.
```

### Accomplishments we are proud of

```
A clean separation between deterministic clinical reasoning (the rule-based scorers) and LLM narrative interpretation. A citation chain that the clinician can audit line by line. A multilingual patient-facing path with mandatory back-translation. A postpartum surveillance flow shaped to the CDC Hear Her checklist with structured SBAR output. End-to-end FHIR grounding from a Synthea persona all the way to a cited clinician handoff.
```

### What we learned

```
Healthcare-grade decision support is mostly about constraints, not about clever generation. The hard part is not getting the LLM to say something useful; it is making sure it cannot say something it cannot support. The citation guard, the deterministic scorers, the audit trail, and the SHARP context propagation are what make the output safe to read.
```

### What is next

```
Wire the orchestrator's keyword router into a planning loop that uses Claude tool calling for harder routing decisions. Add a longitudinal-memory tool that summarizes the patient's care plan deltas across visits. Add a doula-companion agent for non-clinical support, with a clear handoff to clinical agents. Connect to a real EHR via SMART on FHIR for a pilot study.
```

### Built With

```
Anthropic Claude Sonnet 4.6, FastMCP, FastAPI, FHIR R4, HAPI FHIR, Synthea, Pydantic v2, structlog, httpx, tenacity, Google Cloud Run, Google Cloud Build, Google Artifact Registry, Google Secret Manager, Python 3.11, Docker, Prompt Opinion
```

### Try it out (links)

- GitHub: https://github.com/arkhangio10/MaternaSquad
- Live orchestrator (Cloud Run): https://maternasquad-orchestrator-mdf575wm2q-ez.a.run.app/healthcheck
- Live MCP server: https://maternasquad-mcp-mdf575wm2q-ez.a.run.app/mcp
- Architecture: https://github.com/arkhangio10/MaternaSquad/blob/main/docs/ARCHITECTURE.md
- Demo script: https://github.com/arkhangio10/MaternaSquad/blob/main/docs/DEMO_SCRIPT.md

### Video URL

Paste the YouTube unlisted URL of your demo video after recording.

---

## 3. Recording day checklist (90-150 minutes)

### Before you press record

- [ ] All 7 services healthchecked green from the local terminal:
  ```powershell
  $svcs = "maternasquad-hapi","maternasquad-mcp","maternasquad-orchestrator","maternasquad-risk-agent","maternasquad-coverage-agent","maternasquad-education-agent","maternasquad-postpartum-watch"
  foreach ($svc in $svcs) {
    $url = "https://${svc}-mdf575wm2q-ez.a.run.app"
    if ($svc -eq "maternasquad-hapi") { $path = "/fhir/metadata" }
    elseif ($svc -eq "maternasquad-mcp") { $path = "/mcp" }
    else { $path = "/healthcheck" }
    $code = (curl.exe -s -o $null -w "%{http_code}" --max-time 30 "${url}${path}")
    Write-Host "$code  $svc"
  }
  ```
- [ ] Po Care Coordinator agent is saved in Prompt Opinion with the System Prompt + MCP attached.
- [ ] Test prompt for Cordelia returns a cited handoff inside the chat.
- [ ] Test prompt for Yuri returns Spanish patient material.
- [ ] Test prompt for Cyndi returns the postpartum triage.
- [ ] Browser zoom set to ~125% so the captured text is readable in 1080p.
- [ ] All other tabs / Slack / email closed (no notifications during recording).
- [ ] Microphone level checked. Voice-over script printed or on a second screen.
- [ ] OBS / ScreenStudio / Loom configured for 1080p, 30fps, region capture of the browser.

### Storyboard (timecodes are upper bounds; matches docs/DEMO_SCRIPT.md)

- [ ] 0:00-0:15 Cold open. Black screen + CDC stat. Title card.
- [ ] 0:15-0:35 Meet Cordelia. Synthea-derived patient view in Prompt Opinion. "SYNTHETIC DATA" watermark visible.
- [ ] 0:35-1:00 Squad assembles. Type the Cordelia prompt. Show the orchestrator routing.
- [ ] 1:00-1:30 Risk Agent output. Highlight `[Observation/1371]` BMI citation, ACOG PB 222.
- [ ] 1:30-2:00 Split screen: Coverage agent draft (left) + Education agent Spanish card on phone mockup (right). Show English back-translation.
- [ ] 2:00-2:30 Hard cut. "6 days postpartum. 2:14 AM." Spanish patient message. Postpartum Watch triage card with urgency tier and SBAR.
- [ ] 2:30-2:50 Outcome card. Audit trail JSON lines.
- [ ] 2:50-3:00 Closing card.

### After recording

- [ ] Edit to under 2:55 (give yourself buffer).
- [ ] Add captions in English. Spanish caption track is a plus for the multilingual judges.
- [ ] Upload to YouTube **unlisted** (not public, not private).
- [ ] Copy the URL into the Devpost project's Video field.
- [ ] Share the video URL in this README's Hackathon submission section.

### Fallbacks if something fails on recording day

- If a Cloud Run service cold-starts during recording, hit `/healthcheck` 30 seconds before the take.
- If the Prompt Opinion chat fails, fall back to the curl smoke test displayed in a terminal — the audit trail is still legitimate.
- If Anthropic rate-limits, switch to a pre-recorded JSON response file (record the JSON during a separate take and cut it in).
- If HAPI is slow, the patient bundles are already loaded; just retry once.

---

## 4. Devpost final submission steps

1. Project saved with all fields above filled.
2. Video URL pasted.
3. GitHub repo public.
4. Cloud Run URLs all returning 200 (run the healthcheck loop one more time).
5. Click **Submit** before 2026-05-11 23:00 EDT.
6. Screenshot the confirmation. Done.
