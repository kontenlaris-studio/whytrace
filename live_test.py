#!/usr/bin/env python3
"""Uji live WhyTrace di Meko asli: conversation_create -> conversation_add_message
(jejak keputusan) -> artifact_put (laporan why) -> conversation_get ->
artifact_get -> selflearning_query_log. Key dari .env lokal, tak pernah dicetak."""
import base64, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from whytrace import MekoClient, LocalTraceStore, RefundPipeline, Auditor

def load_key():
    env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env):
        for line in open(env):
            if line.startswith("MEKO_API_KEY="):
                return line.strip().split("=", 1)[1]
    return os.environ.get("MEKO_API_KEY", "")

def text_of(resp):
    try:
        return resp["data"]["result"]["content"][0]["text"]
    except Exception:
        return json.dumps(resp)[:200]

def main():
    key = load_key()
    if not key:
        print("NO KEY"); return 1
    print(f"key loaded: prefix={key[:4]}... len={len(key)}")
    # bangun jejak lokal dulu (sumber laporan why yg diunggah)
    store = LocalTraceStore(); pipe = RefundPipeline(store)
    t = pipe.run_case("B", 900, 45, "stale")
    rep_text = None
    Auditor(store).explain(t["seq"])
    rep_text = store.get_artifact(f"why-report-{t['seq']}")

    c = MekoClient(api_key=key)
    results = {}
    conv = c.call("conversation_create", {"title": "WhyTrace live audit trail", "agent_id": "whytrace"})
    tt = text_of(conv)
    try:
        cid = json.loads(tt).get("conversation_id") or json.loads(tt).get("id")
    except Exception:
        cid = None
    results["conversation_create"] = "ok" if cid else f"unparsed: {tt[:100]}"
    print("conversation_create:", results["conversation_create"])
    if not cid:
        json.dump(results, open("data/live-test.json", "w"), indent=2); return 1

    steps = [
        ("conversation_add_message", lambda: c.call("conversation_add_message", {
            "conversation_id": cid, "agent_id": "whytrace",
            "input": "[billing-agent] refund case B: $900, day 45",
            "output": "APPROVED",
            "reasoning": "applied POL-PROMO-LEGACY (legacy promo) - decision trace recorded by WhyTrace",
            "metadata": json.dumps({"decision_seq": t["seq"], "cited": t["cited"]})})),
        ("artifact_put", lambda: c.call("artifact_put", {
            "conversation_id": cid, "filename": f"why-report-{t['seq']}.txt",
            "content_base64": base64.b64encode(rep_text.encode()).decode(),
            "content_type": "text/plain", "agent_id": "whytrace"})),
        ("conversation_get", lambda: c.call("conversation_get", {"conversation_id": cid, "include_messages": True, "agent_id": "whytrace"})),
        ("selflearning_query_log", lambda: c.call("selflearning_query_log", {"conversation_id": cid})),
    ]
    artifact_hash = None
    for label, fn in steps:
        try:
            txt = text_of(fn())
            bad = "validation error" in txt or txt.startswith('{"error"')
            results[label] = "ok" if not bad else f"server-msg: {txt[:120]}"
            print(f"{label}: {'OK' if not bad else 'MSG'} -> {txt[:150]}")
            if label == "artifact_put" and not bad:
                try:
                    artifact_hash = json.loads(txt).get("content_hash") or json.loads(txt).get("hash")
                except Exception:
                    pass
        except Exception as e:
            results[label] = f"error: {type(e).__name__}"
            print(f"{label}: ERROR {type(e).__name__}: {str(e)[:140]}")
    if artifact_hash:
        try:
            txt = text_of(c.call("artifact_get", {"conversation_id": cid, "content_hash": artifact_hash}))
            results["artifact_get"] = "ok" if "WHY REPORT" in txt or len(txt) > 20 else f"msg: {txt[:120]}"
            print("artifact_get:", results["artifact_get"], "->", txt[:120])
        except Exception as e:
            results["artifact_get"] = f"error: {type(e).__name__}"
            print("artifact_get: ERROR", type(e).__name__, str(e)[:140])
    else:
        results["artifact_get"] = "skipped: no content_hash returned by artifact_put"
        print("artifact_get: SKIPPED (no hash)")
    ok = sum(1 for v in results.values() if v == "ok")
    print(f"LIVE {ok}/{len(results)} OK")
    json.dump(results, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "live-test.json"), "w"), indent=2)
    return 0 if ok >= 4 else 1

if __name__ == "__main__":
    sys.exit(main())
