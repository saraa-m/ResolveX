# ResolveX

Autonomous, multi-agent case app that finds, decides, and resolves invoice-to-PO discrepancies — with a human always in control of the final decision.

Built for UiPath AgentHack 2026 — **Track 1: UiPath Maestro Case**

## The problem

Enterprises lose significant money and analyst time reconciling invoices against purchase orders manually. Mismatches slip through, audits drag on, and customers wait for resolution. ResolveX automates detection and recommendation, while keeping a human in the loop at the financial decision point.

## How it works

ResolveX uses **UiPath Maestro Case** as the orchestration and governance layer across three stages:

1. **Intake** — extraction agent pulls and normalizes invoice + PO data, flags mismatches. If supporting documents are missing, the case automatically loops back for rework rather than stalling.
2. **Validation** — a rule engine runs first-pass checks, then a decision agent (with memory of past similar cases) recommends a resolution. A human analyst reviews the agent's recommendation and rationale before approving — the case cannot close itself.
3. **Closure** — on approval, four agents run in parallel: fulfilment processing, settlement, a memory write-back (so future recommendations improve), and a comms agent that drafts the customer-facing resolution notice. An audit agent logs the full decision trail.

Pending-with-Customer and Rejected branches are designed in the architecture (see diagram below) for handling incomplete data and denials, and are next in line to be wired up.

![ResolveX Maestro Case architecture](docs/architecture.png)
<!-- TODO: add the flow diagram image to /docs and confirm the path above -->

## UiPath components used

- **UiPath Maestro Case** — case orchestration, stage management, governance/audit trail
- **UiPath API Workflows** — the integration layer Maestro uses to call the agent backend below
- **UiPath DataFabric** — the db layer Maestro uses as DB
- **UiPath Agent Builder** — the low code no code service to build agents
- **UiPath App Service** — To build Human in the loop approval steo
<!-- TODO: confirm/add: Agent Builder? Action Center / Task forms for the HITL approval step? Orchestrator? List every UiPath component actually used — judges score this explicitly. -->

## Agent backend (this repo)

A multi-agent invoice-vs-PO discrepancy resolution service built with **FastAPI**, **LangChain**, and **SQLite**. It exposes clean, predictable JSON endpoints meant to be consumed by RPA/orchestration tools — in ResolveX's case, **UiPath Maestro** via API Workflows.

Agents: extraction, mismatch categorization, decision (with memory), fulfilment, settlement, comms, audit.

The backend runs in **mock mode by default** — it works end-to-end with seeded sample data and no external API keys required, making it easy for anyone (including judges) to run it locally. Real LLM calls (OpenAI or Anthropic) can be enabled via environment variables.

This backend was built using **Antigravity**, an agentic coding assistant, working directly in the FastAPI codebase.

### Prerequisites
- Python 3.9+
- pip (or uv)

### Installation

1. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

2. (Optional) Configure environment variables in a `.env` file if you wish to run with real LLM calls instead of mock mode:
   ```env
   MOCK_MODE=false
   OPENAI_API_KEY=your_openai_api_key_here
   # OR
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ```
   *If `MOCK_MODE` is not specified, it defaults to `true` and requires no external API keys or credentials.*

### Running the server

```bash
uvicorn main:app --reload --port 8000
```

On startup, the server automatically initializes an SQLite database (`resolvex.db`) and seeds 3 sample invoice/PO pairs along with prior resolution histories.

### API endpoints

- **`GET /health`** — quick system status check.
- **`POST /seed/reset`** — clears and re-seeds all data tables.
- **`POST /intake`** — submits an `invoice_id` (e.g. `INV-1001`), checks PO matching, runs agent mismatch analysis, and writes an audit log.
- **`POST /memory-lookup`** — searches historical precedents by `vendor_id`.
- **`POST /decide`** — accepts the output of Intake & Memory Lookup, applies decision rules, and generates natural-language rationale.
- **`POST /closure`** — simulates parallel ERP updates, memory writebacks, and drafts vendor communications (via agent/mock).
- **`GET /audit-log`** — retrieves the log of all system transitions (newest first).

### Testing end-to-end

A shell script `curl_examples.sh` is provided in the root directory to run the full flow end-to-end for the `INV-1001` test case:

```bash
chmod +x curl_examples.sh
./curl_examples.sh
```

## Maestro Case App

<!-- TODO: brief steps — e.g. "Import the case app definition from /maestro into your UiPath Automation Cloud tenant via Maestro Case App designer" + how the API Workflow connects to the FastAPI endpoints above (base URL config, auth) -->

## Coding agents disclosure

This solution combines a **coding-agent-built backend** (FastAPI/LangChain, built using Antigravity) with **low-code orchestration** (UiPath Maestro Case, configured via the Maestro Case App designer). Antigravity is not part of UiPath's native "UiPath for Coding Agents" integration (Claude Code / Codex / Cursor / Gemini CLI) — it was used purely as a development tool to write the backend code, separate from the UiPath runtime layer.

## Repo structure
<!-- TODO: adjust to match what you actually push -->
```
/backend        # FastAPI app + LangChain agents (this service)
/maestro        # Maestro Case app export/config (if exportable)
/docs           # architecture diagram, screenshots
README.md
LICENSE
curl_examples.sh
```

## License

MIT — see [LICENSE](LICENSE)

## Demo video

[Link to demo video] <!-- TODO -->
