#!/bin/bash

# Exit on any error
set -e

echo "=================================================================="
echo "RESOLVEX END-TO-END FLOW (INV-1001)"
echo "=================================================================="
echo ""

echo ">>> Stage 0: Health Check"
curl -s http://localhost:8000/health | python -m json.tool
echo ""

echo ">>> Stage 0b: Seed Reset"
curl -s -X POST http://localhost:8000/seed/reset | python -m json.tool
echo ""

echo ">>> Stage 1: Intake (/intake)"
INTAKE_RES=$(curl -s -X POST http://localhost:8000/intake \
  -H "Content-Type: application/json" \
  -d '{"invoice_id": "INV-1001"}')
echo "$INTAKE_RES" | python -m json.tool
echo ""

echo ">>> Stage 2: Memory Lookup (/memory-lookup)"
# Extract vendor_id dynamically from intake result
VENDOR_ID=$(python -c "import json; print(json.loads('''$INTAKE_RES''')['vendor_id'])")
MEMORY_RES=$(curl -s -X POST http://localhost:8000/memory-lookup \
  -H "Content-Type: application/json" \
  -d "{\"vendor_id\": \"$VENDOR_ID\"}")
echo "$MEMORY_RES" | python -m json.tool
echo ""

echo ">>> Stage 3: Decision Logic (/decide)"
# Merge intake and memory lookup results into a single payload using Python
DECIDE_PAYLOAD=$(python -c "
import json
intake = json.loads('''$INTAKE_RES''')
memory = json.loads('''$MEMORY_RES''')
merged = {**intake, **memory}
print(json.dumps(merged))
")

DECIDE_RES=$(curl -s -X POST http://localhost:8000/decide \
  -H "Content-Type: application/json" \
  -d "$DECIDE_PAYLOAD")
echo "$DECIDE_RES" | python -m json.tool
echo ""

echo ">>> Stage 4: Closure & Dispatch (/closure)"
# Extract fields dynamically to formulate closure payload
CLOSURE_PAYLOAD=$(python -c "
import json
intake = json.loads('''$INTAKE_RES''')
decide = json.loads('''$DECIDE_RES''')
decision_id = 'DEC-9901'
approved_by = 'auto' if decide['decision'] == 'auto_approve' else 'human'
payload = {
    'invoice_id': intake['invoice_id'],
    'approved_by': approved_by,
    'decision_id': decision_id
}
print(json.dumps(payload))
")

CLOSURE_RES=$(curl -s -X POST http://localhost:8000/closure \
  -H "Content-Type: application/json" \
  -d "$CLOSURE_PAYLOAD")
echo "$CLOSURE_RES" | python -m json.tool
echo ""

echo ">>> Stage 5: Audit Log Retrieval (/audit-log)"
curl -s http://localhost:8000/audit-log | python -m json.tool
echo ""

echo "=================================================================="
echo "FLOW COMPLETED SUCCESSFULLY!"
echo "=================================================================="
