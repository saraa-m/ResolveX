import urllib.request
import urllib.error
import json

base_url = "http://localhost:8000"

def call_post(endpoint, payload):
    url = f"{base_url}{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"Error {e.code}: {e.read().decode('utf-8')}")
        raise

def call_get(endpoint):
    url = f"{base_url}{endpoint}"
    try:
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"Error {e.code}: {e.read().decode('utf-8')}")
        raise

def main():
    print("==================================================================")
    print("RESOLVEX END-TO-END FLOW (INV-1001)")
    print("==================================================================")
    print()

    print(">>> Stage 0: Health Check")
    print(json.dumps(call_get("/health"), indent=2))
    print()

    print(">>> Stage 0b: Seed Reset")
    print(json.dumps(call_post("/seed/reset", {}), indent=2))
    print()

    print(">>> Stage 1: Intake (/intake)")
    intake_res = call_post("/intake", {"invoice_id": "INV-1001"})
    print(json.dumps(intake_res, indent=2))
    print()

    print(">>> Stage 2: Memory Lookup (/memory-lookup)")
    memory_res = call_post("/memory-lookup", {"vendor_id": intake_res["vendor_id"]})
    print(json.dumps(memory_res, indent=2))
    print()

    print(">>> Stage 3: Decision Logic (/decide)")
    decide_payload = {**intake_res, **memory_res}
    decide_res = call_post("/decide", decide_payload)
    print(json.dumps(decide_res, indent=2))
    print()

    print(">>> Stage 4: Closure & Dispatch (/closure)")
    approved_by = "auto" if decide_res["decision"] == "auto_approve" else "human"
    closure_res = call_post("/closure", {
        "invoice_id": intake_res["invoice_id"],
        "approved_by": approved_by,
        "decision_id": "DEC-9901"
    })
    print(json.dumps(closure_res, indent=2))
    print()

    print(">>> Stage 5: Audit Log Retrieval (/audit-log)")
    print(json.dumps(call_get("/audit-log"), indent=2))
    print()
    
    print("==================================================================")
    print("FLOW COMPLETED SUCCESSFULLY!")
    print("==================================================================")

if __name__ == "__main__":
    main()
