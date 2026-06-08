# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import json, re
from pathlib import Path
from collections import defaultdict

ARCHIVES_DIR = Path("C:/Users/jieun/Desktop/Project_2026/22_Research Helper/data/archives")

# ── Load all archives ──────────────────────────────────────────────────────────
all_entries = []
archive_stats = {}

for f in sorted(ARCHIVES_DIR.glob("*.json")):
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        entries = data.get("entries") or []
        valid = []
        for e in entries:
            if not e.get("url"):
                continue
            tier = e.get("tier") if e.get("tier") is not None else data.get("tier", 1)
            valid.append({
                "url": e["url"],
                "title": (e.get("title") or "").encode("ascii","replace").decode("ascii"),
                "description": (e.get("description") or "").encode("ascii","replace").decode("ascii"),
                "lastmod": e.get("lastmod") or "",
                "source": (e.get("source") or data.get("source") or f.stem).encode("ascii","replace").decode("ascii"),
                "tier": tier,
            })
        all_entries.extend(valid)
        tiers = [e["tier"] for e in valid]
        archive_stats[f.stem] = {
            "count": len(valid),
            "tier_values": sorted(set(tiers)),
            "tier_dist": {t: tiers.count(t) for t in sorted(set(tiers))},
        }
    except Exception as ex:
        archive_stats[f.stem] = {"error": str(ex)}

# ── Section 1 ─────────────────────────────────────────────────────────────────
print("=" * 70)
print("SECTION 1: ARCHIVE COMPOSITION")
print("=" * 70)
print(f"Total entries: {len(all_entries)}\n")
print(f"{'Source':<25} {'Count':>6}  {'Tier':>8}  Distribution")
print("-" * 65)
for src, s in archive_stats.items():
    if "error" in s:
        print(f"{src:<25}  ERROR: {s['error']}")
    else:
        dist = ", ".join(f"T{t}:{n}" for t, n in sorted(s["tier_dist"].items()))
        print(f"{src:<25} {s['count']:>6}  {str(s['tier_values']):>8}  {dist}")

tier_counts = defaultdict(int)
for e in all_entries:
    tier_counts[e["tier"]] += 1
print("\nOverall tier distribution:")
total = len(all_entries)
for t in sorted(tier_counts):
    n = tier_counts[t]
    print(f"  Tier {t}: {n:>5} entries  ({100*n/total:.1f}%)")

# ── Scoring logic ─────────────────────────────────────────────────────────────
ACTION_VERBS = {"launch","release","unveil","reveal","announce","introduce","debut","rollout","ship","ships","shipping","start","begin"}
STOP_WORDS = {"the","a","an","of","in","on","at","and","or","for","to","is","are","be","with","by","as","from","this","that","vs","via","bloomberg","counterpoint","idc","gsmarena","reuters","omdia","gartner","trendforce","yole","nikkei","scmp","morgan","stanley"}

def classify_core_terms(eng_topic, current_year=None):
    tokens = re.findall(r"[A-Za-z]+", eng_topic or "")
    required, anchor, seen = [], [], set()
    for t in tokens:
        low = t.lower()
        if low in seen or len(low) < 2: continue
        seen.add(low)
        if low in ACTION_VERBS or low in STOP_WORDS: continue
        if low == "latest": anchor.append(low)
        else: required.append(low)
    if current_year: anchor.append(str(current_year))
    return {"required": required, "anchor": anchor}

def score_text(text, core_terms):
    if not core_terms: return 1.0, True
    low = (text or "").lower()
    required = core_terms["required"]
    anchor = core_terms["anchor"]
    if not required: return 1.0, True
    req_match = sum(1 for t in required if t in low)
    anc_match = sum(1 for t in anchor if t in low)
    score = req_match * 3.0 + anc_match * 0.5
    if req_match == len(required): score *= 1.5
    passes_floor = score >= 0.5
    return score, passes_floor

def search_archive(entries, core_terms, keywords, tier_mult=3.0, top_n=15):
    kw_lower = [k.lower() for k in (keywords or [])]
    scored = []
    for entry in entries:
        text = (entry["title"] + " " + entry["description"]).strip()
        if not text: continue
        low = text.lower()
        if core_terms:
            base, passes = score_text(text, core_terms)
            if not passes: continue
            kw_match = sum(1 for k in kw_lower if k in low)
            score = base + kw_match * 1.5
        else:
            if not kw_lower or not any(k in low for k in kw_lower): continue
            base = score = 1.0
        if (entry.get("tier") or 1) == 1:
            score *= tier_mult
        scored.append((score, base, entry))
    scored.sort(key=lambda x: -x[0])
    return scored[:top_n]

RELEVANT_KW = {"satellite","d2d","direct","globalstar","amazon","spacex","starlink","leo","ntn","non-terrestrial","qualcomm","mediatek","modem","spectrum","itu","fcc","3gpp","nbt","connectivity","sos","emergency","remote","coverage"}
IRRELEVANT_PATTERNS = ["display","production tracker","inventory tracker","panel","oled","lcd","display tracker","dram","memory","storage"]

def is_relevant(entry):
    text = (entry["title"] + " " + entry["description"]).lower()
    return any(k in text for k in RELEVANT_KW)

def is_irrelevant(entry):
    text = (entry["title"] + " " + entry["description"]).lower()
    return any(p in text for p in IRRELEVANT_PATTERNS)

# ── Section 2: Query classification ──────────────────────────────────────────
QUERIES = [
    ("Q1", "Globalstar satellite production capacity Amazon acquisition 2026"),
    ("Q2", "D2D satellite modem supply chain availability 2026"),
    ("Q3", "Direct-to-Device smartphone shipment forecast 2026"),
    ("Q4", "Satellite communication D2D market size growth 2026"),
]

print("\n" + "=" * 70)
print("SECTION 2: QUERY TOKEN CLASSIFICATION")
print("=" * 70)
query_data = []
for qid, q in QUERIES:
    terms = classify_core_terms(q)
    query_data.append((qid, q, terms))
    print(f"\n{qid}: {q}")
    print(f"  required ({len(terms['required'])}): {terms['required']}")
    print(f"  anchor   ({len(terms['anchor'])}):   {terms['anchor']}")
    n_req = len(terms["required"])
    n_anc = len(terms["anchor"])
    max_base = (n_req * 3.0 + n_anc * 0.5) * 1.5
    print(f"  Max base score (all matched, *1.5 bonus): {max_base:.2f}")
    print(f"  At x3.0 multiplier ceiling: {max_base * 3.0:.2f}")

# ── Section 3: Current x3.0 simulation ───────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 3: CURRENT SCORING (tier_multiplier=3.0) — top 15")
print("=" * 70)

for qid, q, terms in query_data:
    kws = q.split()
    results = search_archive(all_entries, terms, kws, tier_mult=3.0, top_n=15)
    print(f"\n{qid}: \"{q[:60]}\"")
    print(f"  {'Rk':>2}  {'Score':>7}  {'Base':>6}  {'Source':<20}  {'SAT':>4}  {'IRREL':>5}  Title (55 chars)")
    print(f"  {'--':>2}  {'-----':>7}  {'----':>6}  {'-'*20}  {'---':>4}  {'-----':>5}  {'-'*55}")
    for rank, (sc, base, e) in enumerate(results, 1):
        sat = "YES" if is_relevant(e) else ""
        irr = "IRRL" if is_irrelevant(e) else ""
        title = e["title"][:55]
        src = e["source"][:20]
        print(f"  {rank:>2}  {sc:>7.2f}  {base:>6.2f}  {src:<20}  {sat:>4}  {irr:>5}  {title}")

# ── Section 4: Multiplier comparison matrix ───────────────────────────────────
MULTIPLIERS = [1.0, 1.5, 2.0, 3.0]

print("\n" + "=" * 70)
print("SECTION 4: MULTIPLIER COMPARISON MATRIX")
print("=" * 70)
print(f"\n{'Q':>2}  {'Mult':>5}  {'N':>3}  {'1st-SAT-Rank':>13}  {'1st-IRREL-Rank':>15}  {'IRREL-in-Top10':>15}")
print("-" * 65)

all_results = {}
for qid, q, terms in query_data:
    all_results[qid] = {}
    kws = q.split()
    for mult in MULTIPLIERS:
        res = search_archive(all_entries, terms, kws, tier_mult=mult, top_n=15)
        n = len(res)
        first_sat = next((i+1 for i, (sc,base,e) in enumerate(res) if is_relevant(e)), None)
        first_irr = next((i+1 for i, (sc,base,e) in enumerate(res) if is_irrelevant(e)), None)
        irr_top10 = sum(1 for i, (sc,base,e) in enumerate(res) if is_irrelevant(e) and i < 10)
        all_results[qid][mult] = {"n":n,"first_sat":first_sat,"first_irr":first_irr,"irr_top10":irr_top10,"res":res}
        sat_s = str(first_sat) if first_sat else "N/A"
        irr_s = str(first_irr) if first_irr else "N/A"
        print(f"{qid:>2}  {mult:>5.1f}  {n:>3}  {sat_s:>13}  {irr_s:>15}  {irr_top10:>15}")
    print()

# ── Section 5: Detailed rank table — Q1 all multipliers ──────────────────────
print("=" * 70)
print("SECTION 5: DETAILED RANK TABLE — Q1 ACROSS ALL MULTIPLIERS (top 10)")
print("=" * 70)
q1terms = query_data[0][2]
q1kws = QUERIES[0][1].split()

for mult in MULTIPLIERS:
    res = all_results["Q1"][mult]["res"]
    print(f"\n  --- Multiplier = {mult:.1f}x ---")
    print(f"  {'Rk':>2}  {'Score':>8}  {'Base':>6}  {'Source':<22}  {'SAT':>4}  {'IRREL':>5}  Title")
    print(f"  {'--':>2}  {'------':>8}  {'----':>6}  {'-'*22}  {'---':>4}  {'-----':>5}  {'-'*45}")
    for rank, (sc, base, e) in enumerate(res[:10], 1):
        sat = "YES" if is_relevant(e) else ""
        irr = "IRRL" if is_irrelevant(e) else ""
        title = e["title"][:50]
        src = e["source"][:22]
        print(f"  {rank:>2}  {sc:>8.2f}  {base:>6.2f}  {src:<22}  {sat:>4}  {irr:>5}  {title}")

# ── Section 6: Score compression analysis ─────────────────────────────────────
print("\n" + "=" * 70)
print("SECTION 6: SCORE GAP — RELEVANT vs IRRELEVANT ARTICLES")
print("=" * 70)
print("Base score is the relevance signal BEFORE tier multiplier.\n")

for qid, q, terms in query_data:
    kws = q.split()
    res_raw = search_archive(all_entries, terms, kws, tier_mult=1.0, top_n=50)
    sat_items = [(sc,base,e) for sc,base,e in res_raw if is_relevant(e)]
    irr_items = [(sc,base,e) for sc,base,e in res_raw if is_irrelevant(e)]

    print(f"{qid}: {q[:60]}")
    if sat_items:
        print(f"  Best relevant (pre-mult):   base={sat_items[0][1]:.2f}  \"{sat_items[0][2]['title'][:50]}\"")
    else:
        print(f"  Best relevant (pre-mult):   NOT IN TOP-50")
    if irr_items:
        print(f"  Best irrelevant (pre-mult): base={irr_items[0][1]:.2f}  \"{irr_items[0][2]['title'][:50]}\"")
    else:
        print(f"  Best irrelevant (pre-mult): NONE in top-50")

    # Key insight: if both are Tier-1, the multiplier does NOT change their relative order
    # It only changes their order relative to non-Tier-1 sources
    if sat_items and irr_items:
        gap_raw = sat_items[0][1] - irr_items[0][1]
        print(f"  Base score gap (relevant - irrelevant): {gap_raw:+.2f}")
        print(f"  >>> With x3.0: both scaled equally, gap becomes {gap_raw*3.0:+.2f}")
        print(f"  >>> Multiplier does NOT change RELATIVE ORDER between Tier-1 articles")
    print()

# ── Section 7: The real problem — query token mismatch ───────────────────────
print("=" * 70)
print("SECTION 7: ROOT CAUSE — REQUIRED TOKEN MISMATCH ANALYSIS")
print("=" * 70)
print("How many required tokens match in irrelevant Omdia vs relevant articles?\n")

for qid, q, terms in query_data:
    kws = q.split()
    res_raw = search_archive(all_entries, terms, kws, tier_mult=1.0, top_n=50)
    required = terms["required"]
    print(f"{qid}: required = {required}")
    print(f"  {'Article (40 chars)':<42}  {'Source':<18}  {'SAT':>4}  {'IRREL':>5}  {'Req matches'}")
    print(f"  {'-'*42}  {'-'*18}  {'---':>4}  {'-----':>5}  {'-'*20}")
    for sc, base, e in res_raw[:12]:
        text = (e["title"] + " " + e["description"]).lower()
        matched = [t for t in required if t in text]
        sat = "YES" if is_relevant(e) else ""
        irr = "IRRL" if is_irrelevant(e) else ""
        print(f"  {e['title'][:42]:<42}  {e['source'][:18]:<18}  {sat:>4}  {irr:>5}  {matched}")
    print()

# ── Section 8: Recommended fix ───────────────────────────────────────────────
print("=" * 70)
print("SECTION 8: IMPACT SIMULATION — what changes at different multipliers")
print("=" * 70)
print("Focus: position displacement of irrelevant articles across multipliers\n")

# Count for each query how many irrelevant articles appear in top 5, 10, 15
print(f"{'Q':>2}  {'Mult':>5}  {'IRREL in top-5':>15}  {'IRREL in top-10':>16}  {'IRREL in top-15':>16}")
print("-" * 60)
for qid, q, terms in query_data:
    kws = q.split()
    for mult in MULTIPLIERS:
        res = search_archive(all_entries, terms, kws, tier_mult=mult, top_n=15)
        irr5  = sum(1 for i,(sc,b,e) in enumerate(res) if is_irrelevant(e) and i < 5)
        irr10 = sum(1 for i,(sc,b,e) in enumerate(res) if is_irrelevant(e) and i < 10)
        irr15 = sum(1 for i,(sc,b,e) in enumerate(res) if is_irrelevant(e))
        print(f"{qid:>2}  {mult:>5.1f}  {irr5:>15}  {irr10:>16}  {irr15:>16}")
    print()

print("=== ANALYSIS COMPLETE ===")
