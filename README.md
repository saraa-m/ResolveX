# ResolveX Backend Service

A simulated multi-agent invoice-vs-PO discrepancy resolution system built with **FastAPI**, **LangChain**, and **SQLite**. It exposes clean, predictable JSON endpoints meant to be consumed by robotic process automation tools like **UiPath Maestro**.

## Prerequisites
- Python 3.9+
- pip (or uv)

## Installation

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
   *Note: If `MOCK_MODE` is not specified, it defaults to `true` and does not require any external API keys or credentials.*

## Running the Server

Start the FastAPI application using Uvicorn:
```bash
uvicorn main:app --reload --port 8000
```

Upon startup, the server automatically initializes an SQLite database (`resolvex.db`) and seeds 3 sample invoice/PO pairs along with prior resolution histories.

## API Endpoints

- **`GET /health`** - Quick system status check.
- **`POST /seed/reset`** - Clears and re-seeds all data tables.
- **`POST /intake`** - Submits an `invoice_id` (e.g. `INV-1001`), checks PO matching, runs agent mismatch analysis, and writes an audit log.
- **`POST /memory-lookup`** - Searches historical precedents by `vendor_id`.
- **`POST /decide`** - Accepts the output of Intake & Memory Lookup, applies decision rules, and generates natural-language rationale.
- **`POST /closure`** - Simulates parallel ERP updates, memory writebacks, and drafts vendor communications (via agent/mock).
- **`GET /audit-log`** - Retrieves the log of all system transitions (newest first).

## Testing the Endpoints End-to-End

A shell script `curl_examples.sh` is provided in the root directory to run the full flow end-to-end for the `INV-1001` test case. To execute it:

```bash
chmod +x curl_examples.sh
./curl_examples.sh
```
