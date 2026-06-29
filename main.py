import os
import json
import sqlite3
import datetime
import logging
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("resolvex-backend")

MOCK_MODE = os.environ.get("MOCK_MODE", "true").lower() in ("true", "1", "yes")
DB_FILE = "resolvex.db"

# Helpers for Database
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(reset=False):
    conn = get_db()
    cursor = conn.cursor()
    
    if reset:
        cursor.execute("DROP TABLE IF EXISTS invoices")
        cursor.execute("DROP TABLE IF EXISTS pos")
        cursor.execute("DROP TABLE IF EXISTS prior_cases")
        cursor.execute("DROP TABLE IF EXISTS audit_logs")
        logger.info("Database tables dropped for reset.")
        
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        invoice_id TEXT PRIMARY KEY,
        vendor_id TEXT,
        vendor_name TEXT,
        po_number TEXT,
        invoice_amount REAL,
        line_items TEXT,
        tax_amount REAL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pos (
        po_number TEXT PRIMARY KEY,
        vendor_id TEXT,
        po_amount REAL,
        line_items TEXT,
        tax_amount REAL
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prior_cases (
        case_id TEXT PRIMARY KEY,
        vendor_id TEXT,
        prior_resolution_summary TEXT,
        prior_resolution_date TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        stage TEXT,
        invoice_id TEXT,
        result TEXT
    )
    """)
    
    # Seed Invoice 1 (INV-1001) and PO 1 (PO-5521)
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE invoice_id = 'INV-1001'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO invoices (invoice_id, vendor_id, vendor_name, po_number, invoice_amount, line_items, tax_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "INV-1001", "VEND-77", "Orion Supplies Ltd", "PO-5521", 12400.00,
            json.dumps([
                {"item": "Steel brackets", "qty": 500, "unit_price": 22.40, "total": 11200.00},
                {"item": "Shipping", "qty": 1, "unit_price": 1200.00, "total": 1200.00}
            ]), 0.00
        ))
        cursor.execute("""
        INSERT INTO pos (po_number, vendor_id, po_amount, line_items, tax_amount)
        VALUES (?, ?, ?, ?, ?)
        """, (
            "PO-5521", "VEND-77", 11200.00,
            json.dumps([
                {"item": "Steel brackets", "qty": 500, "unit_price": 22.40, "total": 11200.00}
            ]), 0.00
        ))
        logger.info("Seeded INV-1001 and PO-5521.")

    # Seed Invoice 2 (INV-1002) - Price mismatch and PO 2 (PO-5522)
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE invoice_id = 'INV-1002'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO invoices (invoice_id, vendor_id, vendor_name, po_number, invoice_amount, line_items, tax_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "INV-1002", "VEND-88", "Apex Industry", "PO-5522", 12500.00,
            json.dumps([
                {"item": "Steel brackets", "qty": 500, "unit_price": 25.00, "total": 12500.00}
            ]), 0.00
        ))
        cursor.execute("""
        INSERT INTO pos (po_number, vendor_id, po_amount, line_items, tax_amount)
        VALUES (?, ?, ?, ?, ?)
        """, (
            "PO-5522", "VEND-88", 11200.00,
            json.dumps([
                {"item": "Steel brackets", "qty": 500, "unit_price": 22.40, "total": 11200.00}
            ]), 0.00
        ))
        logger.info("Seeded INV-1002 and PO-5522.")

    # Seed Invoice 3 (INV-1003) - Tax mismatch and PO 3 (PO-5523)
    cursor.execute("SELECT COUNT(*) FROM invoices WHERE invoice_id = 'INV-1003'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO invoices (invoice_id, vendor_id, vendor_name, po_number, invoice_amount, line_items, tax_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "INV-1003", "VEND-99", "Vertex Corp", "PO-5523", 11600.00,
            json.dumps([
                {"item": "Steel brackets", "qty": 500, "unit_price": 22.40, "total": 11200.00}
            ]), 400.00
        ))
        cursor.execute("""
        INSERT INTO pos (po_number, vendor_id, po_amount, line_items, tax_amount)
        VALUES (?, ?, ?, ?, ?)
        """, (
            "PO-5523", "VEND-99", 11200.00,
            json.dumps([
                {"item": "Steel brackets", "qty": 500, "unit_price": 22.40, "total": 11200.00}
            ]), 0.00
        ))
        logger.info("Seeded INV-1003 and PO-5523.")

    # Seed prior case history
    cursor.execute("SELECT COUNT(*) FROM prior_cases")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO prior_cases (case_id, vendor_id, prior_resolution_summary, prior_resolution_date)
        VALUES (?, ?, ?, ?)
        """, ("CASE-5001", "VEND-77", "Vendor short-shipment surcharge \u2014 approved as standard freight add-on, no PO amendment needed.", "2026-05-15"))
        
        cursor.execute("""
        INSERT INTO prior_cases (case_id, vendor_id, prior_resolution_summary, prior_resolution_date)
        VALUES (?, ?, ?, ?)
        """, ("CASE-5002", "VEND-88", "Price variance rejected \u2014 vendor billed incorrect contract price.", "2026-05-20"))
        
        cursor.execute("""
        INSERT INTO prior_cases (case_id, vendor_id, prior_resolution_summary, prior_resolution_date)
        VALUES (?, ?, ?, ?)
        """, ("CASE-5003", "VEND-99", "Tax rate adjustment \u2014 approved as valid state tax update.", "2026-06-01"))
        logger.info("Seeded prior case history.")
        
    conn.commit()
    conn.close()

def log_audit(stage: str, invoice_id: str, result: Dict[str, Any]):
    try:
        conn = get_db()
        cursor = conn.cursor()
        timestamp = datetime.datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO audit_logs (timestamp, stage, invoice_id, result) VALUES (?, ?, ?, ?)",
            (timestamp, stage, invoice_id, json.dumps(result))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error logging audit row for stage '{stage}', invoice '{invoice_id}': {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize and seed database
    init_db()
    logger.info("--------------------------------------------------")
    logger.info("ResolveX Backend Service successfully started!")
    logger.info("Database has been initialized and seeded.")
    logger.info(f"Running in MOCK_MODE = {MOCK_MODE}")
    logger.info("--------------------------------------------------")
    yield

app = FastAPI(title="ResolveX-Backend", lifespan=lifespan)

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Models -----------------

class IntakeRequest(BaseModel):
    invoice_id: str

class MemoryLookupRequest(BaseModel):
    vendor_id: str

class ClosureRequest(BaseModel):
    invoice_id: str
    approved_by: str  # "human" | "auto"
    decision_id: str

# ----------------- LangChain Config & Helpers -----------------

def get_llm():
    if os.environ.get("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(temperature=0)
    elif os.environ.get("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(temperature=0)
    else:
        raise ValueError("Missing OpenAI or Anthropic API key. Set MOCK_MODE=true or configure API keys.")

def mock_intake_logic(invoice: dict, po: dict) -> dict:
    inv_items = json.loads(invoice["line_items"])
    po_items = json.loads(po["line_items"])
    
    # Check tax mismatch
    if abs(invoice["tax_amount"] - po["tax_amount"]) > 0.01:
        return {
            "invoice_id": invoice["invoice_id"],
            "po_number": po["po_number"],
            "vendor_id": invoice["vendor_id"],
            "vendor_name": invoice["vendor_name"],
            "mismatch_found": True,
            "mismatch_type": "tax_mismatch",
            "mismatch_detail": f"Tax amount mismatch: Invoice ${invoice['tax_amount']:.2f} vs PO ${po['tax_amount']:.2f}.",
            "amount_delta": round(abs(invoice["tax_amount"] - po["tax_amount"]), 2)
        }
        
    # Check line item additions and unit price mismatches
    po_items_dict = {item["item"]: item for item in po_items}
    for item in inv_items:
        item_name = item["item"]
        if item_name not in po_items_dict:
            return {
                "invoice_id": invoice["invoice_id"],
                "po_number": po["po_number"],
                "vendor_id": invoice["vendor_id"],
                "vendor_name": invoice["vendor_name"],
                "mismatch_found": True,
                "mismatch_type": "line_item_addition",
                "mismatch_detail": f"Line item '{item_name}' for ${item['total']:.2f} is not present on PO.",
                "amount_delta": round(item["total"], 2)
            }
        else:
            po_item = po_items_dict[item_name]
            if abs(item["unit_price"] - po_item["unit_price"]) > 0.01:
                price_diff = abs(item["unit_price"] - po_item["unit_price"])
                total_diff = price_diff * item["qty"]
                return {
                    "invoice_id": invoice["invoice_id"],
                    "po_number": po["po_number"],
                    "vendor_id": invoice["vendor_id"],
                    "vendor_name": invoice["vendor_name"],
                    "mismatch_found": True,
                    "mismatch_type": "price_mismatch",
                    "mismatch_detail": f"Item '{item_name}' unit price mismatch: Invoice ${item['unit_price']:.2f} vs PO ${po_item['unit_price']:.2f}.",
                    "amount_delta": round(total_diff, 2)
                }
                
    return {
        "invoice_id": invoice["invoice_id"],
        "po_number": po["po_number"],
        "vendor_id": invoice["vendor_id"],
        "vendor_name": invoice["vendor_name"],
        "mismatch_found": False,
        "mismatch_type": None,
        "mismatch_detail": "No mismatch found between invoice and PO.",
        "amount_delta": 0.0
    }

def run_real_intake_agent(invoice: dict, po: dict) -> dict:
    llm = get_llm()
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
    
    class IntakeOutput(BaseModel):
        mismatch_found: bool = Field(description="True if a mismatch exists")
        mismatch_type: str = Field(description="One of: 'line_item_addition', 'price_mismatch', 'tax_mismatch', or null if mismatch_found is False")
        mismatch_detail: str = Field(description="A human-readable one-sentence explanation")
        amount_delta: float = Field(description="The numeric amount difference caused by the mismatch")
        
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an AI invoice auditing agent. Compare the following invoice and PO and determine if there is a discrepancy. "
                   "Classify the mismatch into one of: 'line_item_addition', 'price_mismatch', or 'tax_mismatch'. "
                   "Provide the mismatch detail as a short one-sentence explanation and calculate the amount delta. "
                   "Respond ONLY with a JSON object matching the requested schema. No markdown wrapping, just the raw JSON."),
        ("user", "Invoice: {invoice}\n\nPO: {po}")
    ])
    
    parser = JsonOutputParser(pydantic_object=IntakeOutput)
    chain = prompt | llm | parser
    
    res = chain.invoke({
        "invoice": json.dumps(dict(invoice), indent=2),
        "po": json.dumps(dict(po), indent=2)
    })
    
    return {
        "invoice_id": invoice["invoice_id"],
        "po_number": po["po_number"],
        "vendor_id": invoice["vendor_id"],
        "vendor_name": invoice["vendor_name"],
        "mismatch_found": res.get("mismatch_found", False),
        "mismatch_type": res.get("mismatch_type"),
        "mismatch_detail": res.get("mismatch_detail", ""),
        "amount_delta": res.get("amount_delta", 0.0)
    }

# ----------------- Endpoints -----------------

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/seed/reset")
def seed_reset():
    try:
        init_db(reset=True)
        return {"status": "database reset and re-seeded"}
    except Exception as e:
        logger.error(f"Error resetting database: {e}")
        raise HTTPException(status_code=500, detail=f"Database reset failed: {str(e)}")

@app.post("/intake")
def intake(payload: IntakeRequest):
    conn = get_db()
    cursor = conn.cursor()
    
    # Retrieve invoice
    cursor.execute("SELECT * FROM invoices WHERE invoice_id = ?", (payload.invoice_id,))
    invoice_row = cursor.fetchone()
    if not invoice_row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Invoice {payload.invoice_id} not found in database.")
        
    invoice = dict(invoice_row)
    
    # Retrieve PO
    cursor.execute("SELECT * FROM pos WHERE po_number = ?", (invoice["po_number"],))
    po_row = cursor.fetchone()
    if not po_row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Matching PO {invoice['po_number']} not found in database.")
        
    po = dict(po_row)
    conn.close()
    
    # Run Agent comparison logic
    try:
        if MOCK_MODE:
            result = mock_intake_logic(invoice, po)
        else:
            result = run_real_intake_agent(invoice, po)
            
        log_audit("intake", payload.invoice_id, result)
        return result
    except Exception as e:
        logger.error(f"Intake agent error: {e}")
        raise HTTPException(status_code=500, detail=f"Intake stage processing error: {str(e)}")

@app.post("/memory-lookup")
def memory_lookup(payload: MemoryLookupRequest):
    conn = get_db()
    cursor = conn.cursor()
    
    # Query history
    cursor.execute(
        "SELECT * FROM prior_cases WHERE vendor_id = ? ORDER BY prior_resolution_date DESC LIMIT 1",
        (payload.vendor_id,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        result = {
            "found": True,
            "prior_case_id": row["case_id"],
            "prior_resolution_summary": row["prior_resolution_summary"],
            "prior_resolution_date": row["prior_resolution_date"]
        }
    else:
        result = {
            "found": False,
            "prior_case_id": None,
            "prior_resolution_summary": None,
            "prior_resolution_date": None
        }
        
    # Log to audit log
    log_audit("memory-lookup", f"VENDOR-{payload.vendor_id}", result)
    return result

@app.post("/decide")
async def decide(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")
        
    # Standardize inputs supporting both flat and nested inputs
    if "intake_result" in body and "memory_lookup_result" in body:
        intake_data = body["intake_result"]
        memory_data = body["memory_lookup_result"]
    else:
        intake_data = body
        memory_data = body
        
    invoice_id = intake_data.get("invoice_id")
    if not invoice_id:
        raise HTTPException(status_code=400, detail="Missing invoice_id in decide request payload.")
        
    amount_delta = intake_data.get("amount_delta", 0.0)
    mismatch_type = intake_data.get("mismatch_type")
    mismatch_detail = intake_data.get("mismatch_detail", "")
    vendor_id = intake_data.get("vendor_id")
    
    has_precedent = memory_data.get("found", False)
    prior_summary = memory_data.get("prior_resolution_summary", "")
    prior_date = memory_data.get("prior_resolution_date", "")
    
    # Apply rules
    # "If amount_delta < 500 AND a similar prior case was found and approved -> auto_approve"
    # Approved check: we check if has_precedent is True and "approved" is in summary
    is_approved_precedent = has_precedent and "approved" in str(prior_summary).lower()
    
    if (amount_delta < 500) and is_approved_precedent:
        decision = "auto_approve"
    else:
        decision = "needs_human"
        
    try:
        if MOCK_MODE:
            # Generate deterministic mock rationale
            if decision == "auto_approve":
                rationale = (
                    f"Discrepancy delta of ${amount_delta:.2f} is under $500 threshold, "
                    f"and similar prior case ({memory_data.get('prior_case_id')}) for vendor {vendor_id} "
                    f"was approved on {prior_date}. Recommending auto-approval."
                )
                confidence = 0.95
            else:
                reasons = []
                if amount_delta >= 500:
                    reasons.append(f"delta ${amount_delta:.2f} meets or exceeds $500 threshold")
                if not has_precedent:
                    reasons.append("no prior precedent found for this vendor")
                if mismatch_type == "tax_mismatch":
                    reasons.append("discrepancy type is tax_mismatch")
                
                reason_str = " OR ".join(reasons)
                rationale = (
                    f"Decision escalated to needs_human because: {reason_str}. "
                    f"Prior lookup details: {prior_summary if has_precedent else 'No precedent found'}."
                )
                confidence = 0.90
                
            result = {
                "decision": decision,
                "confidence": confidence,
                "rationale": rationale
            }
        else:
            # Run Real LangChain decide agent
            llm = get_llm()
            from langchain_core.prompts import ChatPromptTemplate
            from langchain_core.output_parsers import JsonOutputParser
            from pydantic import BaseModel as PydanticBaseModel
            
            class DecisionOutput(PydanticBaseModel):
                decision: str = Field(description="Must be 'auto_approve' or 'needs_human'")
                confidence: float = Field(description="Confidence score between 0.0 and 1.0")
                rationale: str = Field(description="Rationale mentioning mismatch details and precedent details")
                
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are an AI decision agent deciding if invoice discrepancies can be auto-approved based on precedents.\n"
                           "Rules:\n"
                           "- If amount_delta < 500 AND a similar prior case was found and approved -> decision = 'auto_approve'\n"
                           "- If amount_delta >= 500 OR no prior precedent found OR mismatch_type is 'tax_mismatch' -> decision = 'needs_human'\n"
                           "Provide a natural-language rationale referencing both discrepancy detail and memory lookup.\n"
                           "Respond ONLY with a JSON object matching the requested schema. No markdown wrapping."),
                ("user", "Intake Result:\n{intake}\n\nMemory Lookup Result:\n{memory}")
            ])
            
            parser = JsonOutputParser(pydantic_object=DecisionOutput)
            chain = prompt | llm | parser
            
            res = chain.invoke({
                "intake": json.dumps(intake_data, indent=2),
                "memory": json.dumps(memory_data, indent=2)
            })
            
            result = {
                "decision": res.get("decision", "needs_human"),
                "confidence": res.get("confidence", 0.0),
                "rationale": res.get("rationale", "")
            }
            
        log_audit("decide", invoice_id, result)
        return result
    except Exception as e:
        logger.error(f"Decision agent error: {e}")
        raise HTTPException(status_code=500, detail=f"Decision stage processing error: {str(e)}")

@app.post("/closure")
def closure(payload: ClosureRequest):
    conn = get_db()
    cursor = conn.cursor()
    
    # Retrieve invoice to verify and fetch vendor info
    cursor.execute("SELECT * FROM invoices WHERE invoice_id = ?", (payload.invoice_id,))
    invoice_row = cursor.fetchone()
    if not invoice_row:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Invoice {payload.invoice_id} not found in database.")
        
    invoice = dict(invoice_row)
    
    # Fetch details for communications and writeback
    vendor_id = invoice["vendor_id"]
    vendor_name = invoice["vendor_name"]
    invoice_amount = invoice["invoice_amount"]
    
    # Compute discrepancy info for drafting (using mock logic locally or querying PO)
    cursor.execute("SELECT * FROM pos WHERE po_number = ?", (invoice["po_number"],))
    po_row = cursor.fetchone()
    po = dict(po_row) if po_row else {}
    conn.close()
    
    # Run mock comparison to get detail for comms
    comp = mock_intake_logic(invoice, po) if po else {"mismatch_detail": "discrepancy", "amount_delta": 0.0}
    mismatch_detail = comp.get("mismatch_detail", "discrepancy")
    amount_delta = comp.get("amount_delta", 0.0)
    
    # 1. Simulate parallel actions: fulfilment and settlement
    fulfilment = {
        "status": "completed",
        "detail": f"ERP status updated. Invoice {payload.invoice_id} cleared for fulfillment settlement."
    }
    
    settlement = {
        "status": "completed",
        "detail": f"Payment run batch scheduled for vendor {vendor_id} sum ${invoice_amount:.2f}."
    }
    
    # 2. Memory Writeback: Insert this resolution to prior_cases database table
    try:
        conn = get_db()
        cursor = conn.cursor()
        new_case_id = f"CASE-{payload.invoice_id.split('-')[-1]}" # E.g. CASE-1001
        res_summary = f"Discrepancy resolved ({mismatch_detail}) - approved by {payload.approved_by} (decision {payload.decision_id})."
        res_date = datetime.date.today().isoformat()
        
        cursor.execute("""
        INSERT OR REPLACE INTO prior_cases (case_id, vendor_id, prior_resolution_summary, prior_resolution_date)
        VALUES (?, ?, ?, ?)
        """, (new_case_id, vendor_id, res_summary, res_date))
        conn.commit()
        conn.close()
        memory_writeback = {
            "status": "completed",
            "detail": f"Case {payload.invoice_id} added to vendor {vendor_id} history"
        }
    except Exception as e:
        logger.error(f"Memory writeback error: {e}")
        memory_writeback = {
            "status": "failed",
            "detail": f"Failed memory writeback: {str(e)}"
        }
        
    # 3. Comms drafted message via LangChain or Mock
    try:
        if MOCK_MODE:
            drafted_message = (
                f"Dear {vendor_name},\n\n"
                f"We have successfully resolved the discrepancy regarding invoice {payload.invoice_id}. "
                f"The difference ({mismatch_detail}) has been cleared via our {payload.approved_by} verification system. "
                f"Your invoice has been processed for settlement and scheduled in the next billing run.\n\n"
                f"Best regards,\n"
                f"Accounts Payable Automated Resolution System"
            )
        else:
            # Real LangChain drafting
            llm = get_llm()
            from langchain_core.prompts import ChatPromptTemplate
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a customer/vendor support representative drafting a short, professional billing update email.\n"
                           "Input details:\n"
                           "- Invoice ID: {invoice_id}\n"
                           "- Vendor Name: {vendor_name}\n"
                           "- Resolution Type: {approved_by} approval\n"
                           "- Mismatch Detail: {detail}\n"
                           "Draft a warm but professional notification. Reply ONLY with the drafted email message. No surrounding chat text."),
                ("user", "Draft email for vendor {vendor_name} regarding invoice {invoice_id}.")
            ])
            
            chain = prompt | llm
            res = chain.invoke({
                "invoice_id": payload.invoice_id,
                "vendor_name": vendor_name,
                "approved_by": payload.approved_by,
                "detail": mismatch_detail
            })
            
            drafted_message = res.content.strip() if hasattr(res, "content") else str(res).strip()
            
        comms = {
            "status": "completed",
            "drafted_message": drafted_message
        }
    except Exception as e:
        logger.error(f"Comms generation error: {e}")
        comms = {
            "status": "failed",
            "drafted_message": f"Dear Vendor, invoice {payload.invoice_id} resolution completed. (Failed to draft dynamic update: {str(e)})"
        }
        
    result = {
        "fulfilment": fulfilment,
        "settlement": settlement,
        "memory_writeback": memory_writeback,
        "comms": comms
    }
    
    # Log audit logs
    log_audit("closure", payload.invoice_id, result)
    return result

@app.get("/audit-log")
def audit_log():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, stage, invoice_id, result FROM audit_logs ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    
    logs = []
    for r in rows:
        try:
            res_val = json.loads(r["result"])
        except Exception:
            res_val = r["result"]
            
        logs.append({
            "timestamp": r["timestamp"],
            "stage": r["stage"],
            "invoice_id": r["invoice_id"],
            "result": res_val
        })
    return logs
