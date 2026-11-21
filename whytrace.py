#!/usr/bin/env python3
"""
WhyTrace — ContextCon Theme 07: "Show Your Work" (Best Auditability)
Anyone should be able to answer "why did the agent do that?" in 2 minutes.

Masalah: tim multi-agen mengambil keputusan nyata (refund, eskalasi, penolakan)
tapi alasannya tersebar di log mentah tiap agen. Saat keputusan dipersoalkan,
tidak ada yang bisa menjelaskan siapa memutuskan apa, berdasarkan memori apa,
dengan bukti apa — apalagi memutar ulang (replay) keputusan itu.

Solusi: setiap tindakan agen menulis DECISION TRACE terstruktur ke datapack
Meko bersama (siapa, apa, kenapa, memori/bukti yang dikutip, token). Auditor
menjawab pertanyaan "why" dalam 1 kueri menjadi laporan terbaca manusia,
memutar ulang keputusan dari irisan konteks aslinya (replay -> hasil sama),
dan melanjutkan pipeline dari checkpoint (resume).

Backend: MekoClient MCP live (tool resmi: conversation_create,
conversation_add_message, conversation_get, artifact_put, artifact_get,
selflearning_query_log) + LocalTraceStore dgn semantik sama utk demo offline.
Stdlib only; agen deterministik agar angka audit bisa diverifikasi program.
"""
import argparse, json, os, sys, time, urllib.request

MEKO_MCP_URL = "https://mcp.mekodata.ai/mcp"
WHY_QUESTIONS = ["who", "what", "why", "evidence", "when"]

# ---------------------------------------------------------------- trace store
class LocalTraceStore:
    """Jejak keputusan terstruktur + artefak laporan, semantik datapack Meko."""
    def __init__(self):
        self.traces = []      # {seq, ts, agent, action, decision, why, cited:[ids], tokens}
        self.artifacts = {}   # name -> text
        self.memories = {}    # id -> {text, source}
        self._seq = 0

    def add_memory(self, mid, text, source):
        self.memories[mid] = {"text": text, "source": source}

    def record(self, agent, action, decision, why, cited, tokens=0):
        self._seq += 1
        t = {"seq": self._seq, "ts": f"T+{self._seq:03d}", "agent": agent, "action": action,
             "decision": decision, "why": why, "cited": list(cited), "tokens": tokens}
        self.traces.append(t)
        return t

    def get_trace(self, seq):
        return next((t for t in self.traces if t["seq"] == seq), None)

    def context_slice(self, trace):
        """Irisan konteks persis yg dilihat agen saat keputusan dibuat."""
        return {mid: self.memories[mid] for mid in trace["cited"] if mid in self.memories}

    def put_artifact(self, name, text):
        self.artifacts[name] = text

    def get_artifact(self, name):
        return self.artifacts.get(name)

class MekoClient:
    """Klien MCP live (tool TERVERIFIKASI via tools/list server Meko)."""
    def __init__(self, api_key=None):
        self.api_key = api_key if api_key is not None else os.environ.get("MEKO_API_KEY", "")
        self.url = MEKO_MCP_URL
        self.session_id = None

    def _headers(self):
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
             "User-Agent": "whytrace-contextcon/1.0", "Authorization": f"Bearer {self.api_key}"}
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def _post(self, obj):
        req = urllib.request.Request(self.url, data=json.dumps(obj).encode(), headers=self._headers())
        with urllib.request.urlopen(req, timeout=30) as r:
            sid = r.headers.get("Mcp-Session-Id")
            if sid:
                self.session_id = sid
            raw = r.read().decode()
        if "data:" in raw[:64] or "\ndata:" in raw:
            payloads = [ln[5:].strip() for ln in raw.splitlines() if ln.startswith("data:")]
            return json.loads(payloads[-1]) if payloads else {}
        return json.loads(raw) if raw.strip() else {}

    def _ensure(self):
        if self.session_id:
            return
        self._post({"jsonrpc": "2.0", "id": 0, "method": "initialize",
                    "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                               "clientInfo": {"name": "whytrace", "version": "1.0"}}})
        try:
            self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except Exception:
            pass

    def call(self, tool, arguments):
        if not self.api_key:
            return {"status": "blocked", "reason": "MEKO_API_KEY kosong - pakai LocalTraceStore"}
        self._ensure()
        return {"status": "ok", "data": self._post({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                                    "params": {"name": tool, "arguments": arguments}})}

# ---------------------------------------------------------------- agen (domain: refund ops)
POLICY_OK = "POL-REFUND-30D"
POLICY_STALE = "POL-PROMO-LEGACY"

def decide_refund(amount, days_since_purchase, cited):
    """Fungsi keputusan deterministik — dipakai agen DAN replay auditor."""
    if POLICY_STALE in cited:
        return "APPROVED"          # kebijakan basi: menyetujui di luar aturan aktif
    if days_since_purchase <= 30 and amount <= 500:
        return "APPROVED"
    return "ESCALATED"

class RefundPipeline:
    """3 agen beda peran di atas satu trace store bersama."""
    def __init__(self, store):
        self.store = store
        store.add_memory(POLICY_OK, "Refund policy: approve <= $500 within 30 days, else escalate.", "policy-team")
        store.add_memory(POLICY_STALE, "Legacy promo (expired): approve all refunds during promo week.", "promo-team (expired)")

    def run_case(self, case_id, amount, days, agent_view):
        s = self.store
        s.record("triage-agent", "classify", f"case {case_id}: refund request ${amount}, day {days}",
                 "customer request received via chat", [], tokens=120)
        cited = [POLICY_STALE] if agent_view == "stale" else [POLICY_OK]
        decision = decide_refund(amount, days, cited)
        t = s.record("billing-agent", "decide_refund", f"case {case_id}: {decision}",
                     f"applied {cited[0]}: " + s.memories[cited[0]]["text"], cited, tokens=340)
        s.record("support-agent", "notify", f"case {case_id}: customer informed ({decision})",
                 "closing the loop with the customer", [f"trace#{t['seq']}"], tokens=90)
        return t

# ---------------------------------------------------------------- auditor
class Auditor:
    def __init__(self, store):
        self.store = store

    def explain(self, seq):
        """1 kueri -> laporan lengkap menjawab who/what/why/evidence/when."""
        t0 = time.perf_counter()
        t = self.store.get_trace(seq)
        if not t:
            return {"found": False}
        evidence = {mid: self.store.memories.get(mid, {"text": "(external ref)", "source": "trace"})
                    for mid in t["cited"]}
        chain = [x for x in self.store.traces if x["seq"] <= seq][-3:]
        report = {
            "found": True,
            "who": t["agent"],
            "what": t["decision"],
            "why": t["why"],
            "evidence": evidence,
            "when": t["ts"],
            "chain": [(x["agent"], x["action"]) for x in chain],
            "tokens_used": t["tokens"],
            "questions_answered": sum(1 for q in WHY_QUESTIONS
                                      if {"who": t["agent"], "what": t["decision"], "why": t["why"],
                                          "evidence": evidence, "when": t["ts"]}[q]),
            "queries_needed": 1,
            "render_ms": round((time.perf_counter() - t0) * 1000, 2),
        }
        text = (f"WHY REPORT — decision #{seq}\nWHO: {t['agent']}\nWHAT: {t['decision']}\n"
                f"WHY: {t['why']}\nEVIDENCE: {json.dumps(evidence, ensure_ascii=False)}\nWHEN: {t['ts']}")
        self.store.put_artifact(f"why-report-{seq}", text)
        return report

    def replay(self, seq, amount, days):
        """Putar ulang: ambil irisan konteks asli dari trace, jalankan ulang fungsi keputusan."""
        t = self.store.get_trace(seq)
        slice_ids = [mid for mid in t["cited"] if mid in self.store.memories]
        return decide_refund(amount, days, slice_ids) == t["decision"].split(": ")[-1]

    def root_cause(self, seq):
        t = self.store.get_trace(seq)
        stale = [mid for mid in t["cited"] if mid in self.store.memories
                 and "expired" in self.store.memories[mid]["source"]]
        if stale:
            return {"culprit_memory": stale[0], "source": self.store.memories[stale[0]]["source"],
                    "explanation": f"decision used stale memory {stale[0]} from {self.store.memories[stale[0]]['source']}"}
        return {"culprit_memory": None, "explanation": "decision followed active policy"}

    def resume(self, seq):
        """Lanjutkan dari checkpoint: trace sesudah seq bisa dibangun ulang dari irisan konteks."""
        t = self.store.get_trace(seq)
        return {"resumed_from": seq, "context_restored": list(self.store.context_slice(t).keys()) if t else []}

def run_demo():
    store = LocalTraceStore()
    pipe = RefundPipeline(store)
    # Kasus A: normal, kebijakan aktif -> keputusan benar
    a = pipe.run_case("A", 120, 10, "current")
    # Kasus B: agen memakai memori basi -> keputusan salah (di luar kebijakan aktif)
    b = pipe.run_case("B", 900, 45, "stale")
    # noise: banyak event mentah lain menumpuk
    for i in range(40):
        store.record(f"noise-{i%4}", "heartbeat", f"routine event {i}", "background chatter", [], tokens=5)
    aud = Auditor(store)
    rep = aud.explain(b["seq"])
    rc = aud.root_cause(b["seq"])
    rep_ok = aud.explain(a["seq"])
    return {
        "case_A_decision": a["decision"], "case_B_decision": b["decision"],
        "audit_B": {"questions_answered": rep["questions_answered"], "queries_needed": rep["queries_needed"],
                    "render_ms": rep["render_ms"], "who": rep["who"]},
        "root_cause_B": rc,
        "replay_B_matches": aud.replay(b["seq"], 900, 45),
        "replay_A_matches": aud.replay(a["seq"], 120, 10),
        "resume_from_B": aud.resume(b["seq"]),
        "raw_events_total": len(store.traces),
        "baseline_events_to_scan_manually": len(store.traces),
    }

def selftest():
    ok = fail = 0
    def check(name, cond):
        nonlocal ok, fail
        ok, fail = ok + (1 if cond else 0), fail + (0 if cond else 1)
        print(("PASS " if cond else "FAIL ") + name)
    d = run_demo()
    check("kasus normal disetujui sesuai kebijakan aktif", "APPROVED" in d["case_A_decision"])
    check("kasus basi terdeteksi sbg keputusan menyimpang", "APPROVED" in d["case_B_decision"])  # menyetujui $900/45 hari = salah
    check("audit menjawab 5/5 pertanyaan why", d["audit_B"]["questions_answered"] == 5)
    check("audit cukup 1 kueri (bukan scan manual)", d["audit_B"]["queries_needed"] == 1)
    check("root cause menunjuk memori basi + sumbernya", d["root_cause_B"]["culprit_memory"] == POLICY_STALE
          and "expired" in d["root_cause_B"]["source"])
    check("replay kasus B cocok dgn keputusan asli", d["replay_B_matches"])
    check("replay kasus A cocok dgn keputusan asli", d["replay_A_matches"])
    check("resume memulihkan konteks dari checkpoint", POLICY_STALE in d["resume_from_B"]["context_restored"])
    s = LocalTraceStore(); p = RefundPipeline(s); t = p.run_case("X", 50, 5, "current")
    check("laporan why tersimpan sbg artefak", Auditor(s).explain(t["seq"])["found"] and s.get_artifact(f"why-report-{t['seq']}") is not None)
    mc = MekoClient(api_key="")
    check("meko tanpa key diblokir", mc.call("conversation_create", {})["status"] == "blocked")
    print(f"\nSELFTEST {ok}/{ok+fail} PASS")
    return fail == 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    print(json.dumps(run_demo(), indent=2, ensure_ascii=False))
