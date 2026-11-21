#!/usr/bin/env python3
"""Render demo video: narrated slides from the real demo numbers. Stdlib + PIL + ffmpeg + /opt/hatch/bin/tts."""
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "video")
os.makedirs(OUT, exist_ok=True)
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FM = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

SECTIONS = [
    ("WhyTrace", "Show Your Work — ContextCon Theme 07: Best Auditability",
     ["The problem: agents make real decisions.",
      "A billing agent approves a $900 refund it should not.",
      "The reasoning is scattered across raw logs.",
      "Nobody can answer: why did the agent do that?"],
     "Multi-agent systems make real decisions: approving refunds, escalating cases, rejecting applications. But when a decision is challenged, the reasoning is scattered across raw logs, and nobody can quickly say who decided what, why, and based on which evidence. WhyTrace makes every agent show its work."),
    ("Traces by default", "Every action writes a structured decision trace",
     ["Refund pipeline: triage -> billing -> support",
      "Each action records into one Meko datapack:",
      "  who acted, what was decided, why",
      "  the memory IDs cited as evidence",
      "  tokens used, full agent chain"],
     "In WhyTrace, a refund pipeline of three agents writes a structured decision trace for every action into one shared Meko datapack: who acted, what was decided, why, the exact memories cited as evidence, and the tokens used. One audit surface for the whole team."),
    ("Explain in one query", "The auditor answers: who, what, why, evidence, when",
     ["$ python3 whytrace.py --demo",
      "WHY report for the bad decision:",
      "  WHO: billing-agent   WHAT: APPROVED $900, day 45",
      "  WHY: applied POL-PROMO-LEGACY",
      "  Questions answered: 5 / 5, in 1 query (not 46 log events)"],
     "When the bad refund is challenged, the auditor answers all five questions in a single query: who, what, why, with which evidence, and when, plus the full agent chain. The report is stored back into the datapack as an artifact. Five out of five, from one query, instead of digging through forty-six raw events."),
    ("Root cause, named", "The report points at the exact culprit memory",
     ["Culprit: POL-PROMO-LEGACY",
      "Source: promo-team (expired)",
      "The policy it overrode: POL-REFUND-30D",
      "  approve <= $500 within 30 days, else escalate",
      "A $900 refund at day 45 never stood a chance."],
     "Better, the report names the root cause: the billing agent applied a stale, expired promo memory, instead of the active refund policy, which allows at most five hundred dollars within thirty days. The culprit is a specific memory, with a specific source, not a vague suspicion."),
    ("Replay proves it", "Re-run the decision from its own recorded context",
     ["Replay case A (normal):  outcome matches original",
      "Replay case B (stale):   outcome matches original",
      "Replay fidelity: 2 / 2",
      "Resume: context restored from any checkpoint trace",
      "An explanation that cannot replay itself is decoration."],
     "WhyTrace then proves its own explanations. Replaying each decision from the exact context slice the agent saw reproduces the original outcome, two out of two. And work can resume from any checkpoint trace, with its context restored. An explanation that cannot replay itself is just decoration."),
    ("Measured, live, done", "Results from the recorded demo + live Meko run",
     ["Why-questions:  5/5 in 1 query vs 46 raw events",
      "Replay:         2/2 decisions reproduced",
      "Selftest:       10/10 PASS",
      "Live Meko:      6/6 (traces, artifacts, query log)",
      "",
      "Show your work. Every decision, explained."],
     "The results are measured. Five of five why-questions answered in one query. Replay fidelity two of two. Selftest ten of ten. And the live Meko run passed six of six, with traces, artifacts and the self-learning query log all verified on the real account. Show your work. Every decision, explained. That is WhyTrace."),
]

def slide(idx, title, subtitle, lines):
    img = Image.new("RGB", (1280, 720), (10, 25, 49))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1280, 10], fill=(255, 122, 0))
    d.text((60, 48), title, font=ImageFont.truetype(FB, 44), fill=(255, 255, 255))
    d.text((60, 108), subtitle, font=ImageFont.truetype(FR, 24), fill=(255, 170, 80))
    y = 180
    for ln in lines:
        d.text((60, y), ln, font=ImageFont.truetype(FM, 25), fill=(220, 230, 245))
        y += 44
    d.text((60, 668), f"WhyTrace — ContextCon Theme 07 · {idx+1}/{len(SECTIONS)}", font=ImageFont.truetype(FR, 18), fill=(140, 160, 190))
    p = os.path.join(OUT, f"slide{idx}.png")
    img.save(p)
    return p

def dur(path):
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())

def main():
    concat_v, concat_a = [], []
    for i, (title, sub, lines, narr) in enumerate(SECTIONS):
        png = slide(i, title, sub, lines)
        mp3 = os.path.join(OUT, f"narr{i}.mp3")
        if not os.path.exists(mp3):
            r = subprocess.run(["/opt/hatch/bin/tts", "speak", "--output", mp3, "--text-stdin",
                                "--voice", "avocado_v2:MAI_03", "--language", "en"],
                               input=narr, capture_output=True, text=True)
            if r.returncode != 0:
                print("TTS FAIL", i, r.stderr[-300:]); sys.exit(1)
        d = dur(mp3) + 0.4
        concat_v.append(f"file '{png}'\nduration {d:.2f}")
        concat_a.append(f"file '{mp3}'")
        print(f"section {i}: {d:.1f}s")
    last = os.path.join(OUT, f"slide{len(SECTIONS)-1}.png")
    concat_v.append(f"file '{last}'")
    open(os.path.join(OUT, "vlist.txt"), "w").write("\n".join(concat_v) + "\n")
    open(os.path.join(OUT, "alist.txt"), "w").write("\n".join(concat_a) + "\n")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", os.path.join(OUT, "vlist.txt"),
                    "-f", "concat", "-safe", "0", "-i", os.path.join(OUT, "alist.txt"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                    os.path.join(OUT, "whytrace-demo.mp4")], check=True)
    print("VIDEO OK", os.path.join(OUT, "whytrace-demo.mp4"), f"{dur(os.path.join(OUT,'onememory-demo.mp4')):.1f}s")

if __name__ == "__main__":
    main()
