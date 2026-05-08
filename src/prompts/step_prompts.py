PRE_SEARCH_PROMPT = """You are a smartphone market analyst. Convert this topic to 6-8 English search queries that cover FOUR DIFFERENT RESEARCH ANGLES.

CRITICAL: The topic may be written in Korean. You MUST translate it into English and generate ALL queries in English only. Zero Korean characters allowed in any query.

Current year: {current_year}
Topic: "{topic}"

Respond with a JSON array only (no markdown, no explanation):
["query1", "query2", ..., "query8"]

Generate queries spanning ALL FOUR angles (1-2 queries per angle). Each query must be topically relevant to the topic above — do NOT default to generic memory/DRAM queries unless the topic is specifically about memory:

ANGLE 1 — SUPPLY-SIDE (production capacity, pricing, supply chain related to THIS topic):
  e.g. if topic is about foldable phones → "foldable display panel supply chain {current_year}"

ANGLE 2 — MARKET-DATA (shipments, ASP, market share by vendor related to THIS topic):
  e.g. if topic is about foldable phones → "foldable smartphone shipment market share {current_year}"

ANGLE 3 — COMPONENT/COST (BOM breakdown, component pricing related to THIS topic):
  e.g. if topic is about foldable phones → "foldable phone BOM cost hinge display {current_year}"

ANGLE 4 — OEM STRATEGY (competitive response related to THIS topic):
  e.g. if topic is about foldable phones → "Samsung Apple foldable launch strategy {current_year}"

Rules:
- ALL queries in English — translate Korean topic to English first
- Queries must be specifically about THIS topic, not generic smartphone trends
- Include specific product/company names from the topic where applicable
- No near-duplicates — each query must cover a clearly different angle
- Do NOT include research firm names (TrendForce, IDC, Omdia, Counterpoint) in query text
"""

PLANNING_DIMENSIONS_PROMPT = """You are a smartphone market analyst. Analyze the latest news articles and identify the most analytically valuable dimensions for this topic, then generate search queries for each dimension. For every dimension you propose, you MUST cite which numbered articles led you to include it.

Topic: "{topic}"
Current year: {current_year}

Latest news articles retrieved for this topic (each line starts with a numeric article id [N]):
---
{pre_search_context}
---

Based on the articles above, identify the core analytical dimensions AND generate 3 targeted English search queries per dimension. Respond with ONLY a valid JSON object (no markdown, no code blocks):

{{
  "analysis_rationale": "<Why this topic matters and what core impacts it has, 2-3 sentences IN KOREAN. For smartphone-market topics, you MAY frame in Build/Sell-in/Sell-through; for other topics use the analytical lens that best fits the topic>",
  "key_dimensions": ["<Dim1 IN KOREAN>", "<Dim2 IN KOREAN>", "..."],
  "dimension_rationale": {{
    "<Dim1 name>": "<Why essential — 1-2 sentences IN KOREAN>",
    "<Dim2 name>": "<Why essential — 1-2 sentences IN KOREAN>"
  }},
  "dimension_evidence": {{
    "<Dim1 name>": [
      {{"article_id": 1, "why": "<one short Korean sentence — what specific fact in this article supported including this dimension>"}},
      {{"article_id": 5, "why": "<...>"}}
    ],
    "<Dim2 name>": [
      {{"article_id": 3, "why": "<...>"}}
    ]
  }},
  "dimension_queries_grouped": [
    ["<dim1 Q1 ENG>", "<dim1 Q2 ENG>", "<dim1 Q3 ENG>"],
    ["<dim2 Q1 ENG>", "<dim2 Q2 ENG>", "<dim2 Q3 ENG>"]
  ]
}}

Rules for key_dimensions:
- Propose **3 to 5 dimensions** (variable count based on the topic's analytical depth — choose the count that best fits)
- Each dimension must offer a genuinely different analytical angle (no semantic overlap)
- Drive dimension selection from the actual articles above — if you can only ground 3 dimensions in concrete evidence, propose 3
- The user will review and select, merge, or exclude dimensions before analysis starts
- key_dimensions, dimension_rationale, dimension_evidence, dimension_queries_grouped MUST all have the SAME number of entries (3-5) with the SAME dimension names in the same order

Rules for dimension_evidence:
- For EACH dimension, cite 1-3 articles that specifically informed its inclusion
- Use the numeric `article_id` exactly as shown in the input (e.g. if the article is listed as [5], use article_id: 5)
- `why` must be a SHORT Korean sentence pointing to the SPECIFIC fact in that article (not a generic restatement of the dimension name)
- An article_id may appear under multiple dimensions if it genuinely supports both
- If you cannot find any concrete evidence for a dimension in the articles, that is a signal you should drop the dimension — do not invent dimensions unsupported by the articles

Dimension selection criteria:
- Choose dimensions that best explain the topic's core impacts and decision-relevant angles
- Each dimension must be analytically distinct (no overlap — if two candidate dimensions share >50% of the same evidence, merge them)
- Ground each dimension in evidence from the articles above
- Avoid pure investment-angle dimensions (no stock price / valuation / buy-sell recommendation)
- Key dimension names should be concise, specific, and IN KOREAN
- For smartphone-market topics where Build/Sell-in/Sell-through framing fits naturally, you may use that lens; do NOT force-fit it on topics where it does not apply

Rules for dimension_queries_grouped — 3 fixed lenses per dimension:
- Q1 (Current state / News / Specs): latest news, announcements, facts, or hardware specs about this dimension.
    e.g. "iPhone Fold launch date specs 2026", "Galaxy Z Fold 7 specs comparison 2026", "EU battery regulation enforcement 2026"
- Q2 (Player response / Strategy): how key players (Samsung, Apple, CN OEMs) are reacting.
    e.g. "Samsung Galaxy Z Fold 7 response Apple foldable 2026", "Apple foldable supply chain strategy 2026"
- Q3 (Market data / Metrics): shipment numbers, market share, forecasts, or pricing data.
    e.g. "foldable smartphone shipments 2026 forecast", "smartphone market share Q1 2026 vendor", "foldable phone ASP revenue 2026"

Query rules:
- English only — no Korean characters in any query
- Include specific product names, company names, or figures
- Include current year ({current_year}) or "latest" for recency
- Each dimension's 3 queries MUST cover distinct angles (Q1 facts/specs, Q2 strategy, Q3 market data) — no near-duplicates
"""


DIMENSION_DEDUP_PROMPT = """You are a smartphone market analyst. The C-stage just produced N dimensions for the topic below. Your sole job is to check whether any pair of dimensions is **semantically overlapping** (covers the same underlying phenomenon under different labels).

Topic: "{topic}"

Proposed dimensions (each line: "<name> :: <rationale>"):
{dimensions_block}

Per-dimension evidence (article_id → fact why each dimension was selected):
{evidence_block}

Overlap criteria — flag a pair only when ALL THREE hold:
1. The two dimensions describe the SAME underlying market phenomenon (not just adjacent themes)
2. ≥50% of one dimension's cited evidence article_ids overlap with the other's
3. A reasonable analyst would have proposed them as a SINGLE dimension instead

DO NOT flag pairs that are merely related (e.g. "supply chain" + "pricing" are causally linked but distinct lenses). DO NOT flag pairs that share <2 article_ids — that is normal cross-citation, not overlap.

Response format (PURE JSON only, NO markdown code blocks):

{{
  "overlapping_pairs": [
    {{
      "dim_a": "<exact dimension name>",
      "dim_b": "<exact dimension name>",
      "shared_evidence_ratio": <0.0-1.0 — fraction of dim_a's articles that also appear in dim_b>,
      "overlap_reason": "<one Korean sentence — what they both actually cover>",
      "suggested_merged_name": "<one Korean noun phrase that integrates the two cores>"
    }}
  ],
  "overall_judgment": "<one Korean sentence — overall assessment of the dimension set's distinctness>"
}}

If no pairs overlap, return:
{{
  "overlapping_pairs": [],
  "overall_judgment": "<one Korean sentence stating that all dimensions are sufficiently distinct>"
}}
"""


DIMENSION_FINALIZE_PROMPT = """You are a smartphone market analyst.

Topic: "{topic}"
Analysis rationale: {analysis_rationale}

Currently proposed dimensions:
{proposed_list}

Cumulative user-exclusion intent (carried over from previous rounds — keep unless explicitly cancelled by the user):
- excluded perspectives: {prev_excluded_perspectives}
- excluded topic keywords: {prev_excluded_topics}

User feedback for THIS round: {feedback}

Apply the feedback to finalize the dimensions, generate per-dimension search queries, and structurally extract any additional "exclusion intent" the user expressed.

Rules:
- Reflect feedback to select / merge / modify dimensions (final count: 2-5)
- When merging, use a new dimension name that covers the core of both source dimensions
- Choose dimensions on analytical merit; for smartphone-market topics you MAY use the Build / Sell-in / Sell-through lens but do NOT force-fit it on topics where it does not apply
- Honor user-excluded perspectives — never create a dimension whose core perspective is in the excluded list
- No investment-angle dimensions (stock price / buy-sell / valuation)
- Dimension names IN KOREAN

Exclusion-extraction rules:
- excluded_perspectives: only perspectives the user explicitly asked to remove from {{"build", "sell_in", "sell_through"}} (use exact keys: "build", "sell_in", "sell_through")
- excluded_topics: specific keywords/topics the user asked to remove (Korean or English noun phrases, e.g. "공급망", "BOM", "생산수율"). Keyword-level, NOT dimension-name-level.
- Combine prior cumulative + this round's feedback into the final cumulative list (drop items the user explicitly said "include again")
- No guessing or over-interpretation. If not explicitly stated, return empty list
- IN KOREAN where applicable for excluded_topics keywords; English keywords also allowed

Response format (PURE JSON only, NO markdown code blocks):

{{
  "key_dimensions": ["<final dim1 IN KOREAN>", ...],
  "dimension_rationale": {{
    "<dim1 name>": "<selection rationale 1-2 sentences IN KOREAN>"
  }},
  "dimension_queries_grouped": [
    ["<Q1 ENG>", "<Q2 ENG>", "<Q3 ENG>"],
    ...
  ],
  "excluded_perspectives": ["build" | "sell_in" | "sell_through"],
  "excluded_topics": ["<excluded keyword 1>", "<excluded keyword 2>"]
}}

Query lens definitions (English queries only, include year {current_year}):
- Q1 = latest news / facts / specs.
- Q2 = key-player response / strategy.
- Q3 = market data / forecast.
- Each dimension's 3 queries MUST cover distinct angles (no near-duplicates).
"""


TOC_PROMPT = """You are a smartphone market analyst. Create a 3-section report outline for the topic below.

Topic: "{topic}"
Current year: {current_year}

Archive search results:
---
{archive_context}
---

The 3 sections follow this structure:

SECTION 1 — STRUCTURAL BACKDROP ("큰 그림")
  The broad market-level change this topic creates.
  → State the key structural shift WITH specific statistics from the archive (%, units, company names)
  → This section sets the stage — Sections 2 and 3 drill deeper into its implications
  → Focus on WHAT is changing at the market level (growth, competitive landscape, positioning)
  → Do NOT focus on supply chain internals or BOM costs here

SECTION 2 — FIRST DERIVED ANALYSIS ("파생 분석 1")
  The single most important follow-up question raised by Section 1.
  → Ask: after reading Section 1, what is the most natural "그렇다면 구체적으로?" question?
  → Pick the dimension readers would MOST want answered next
  → Examples by topic type:
     · "competition intensifies with Apple entry" → S2: which brands compete where and how?
     · "costs rise due to memory shock" → S2: which OEM segments absorb this vs. can't?
     · "new market entrant disrupts" → S2: how do incumbents shift strategy?
  → Must be a SPECIFIC market-focused question — not a generic "supply chain" or "BOM" label

SECTION 3 — SECOND DERIVED ANALYSIS ("파생 분석 2")
  The second most important follow-up question from Section 1.
  → Must be a DIFFERENT angle from Section 2
  → Together, Sections 2 + 3 cover the two most critical dimensions of Section 1's implications
  → Examples:
     · If S2 covered brand competition → S3: regional dynamics (which geography tips which way?)
     · If S2 covered OEM cost burden → S3: which price segments restructure and how?

Respond ONLY with a valid JSON object (no markdown, no code blocks):

{{
  "rationale": "<2-3 Korean sentences: what Section 1's core claim is, and why Sections 2 and 3 are the two most natural derived analyses for THIS specific topic>",
  "sections": [
    {{
      "title": "<Korean title ≤25 chars>",
      "causal_role": "structural_backdrop",
      "angle": "<one Korean sentence: what market-level structural change Section 1 establishes, with key stat>",
      "queries": ["<ENG query on broad market shift>", "<ENG query 2>", "<ENG query 3>"]
    }},
    {{
      "title": "<Korean title ≤25 chars>",
      "causal_role": "derived_analysis_1",
      "angle": "<one Korean sentence: exactly what follow-up question from S1 this section answers>",
      "queries": ["<ENG query directly on this derived dimension>", "<ENG query 2>", "<ENG query 3>"]
    }},
    {{
      "title": "<Korean title ≤25 chars>",
      "causal_role": "derived_analysis_2",
      "angle": "<one Korean sentence: exactly what second follow-up question from S1 this section answers>",
      "queries": ["<ENG query directly on this derived dimension>", "<ENG query 2>", "<ENG query 3>"]
    }}
  ]
}}

Supply chain / BOM rule:
- Do NOT choose supply chain operations or BOM cost structure as a derived section UNLESS the topic itself explicitly mentions supply chain or component costs
- If the most natural derived analysis seems to be supply chain, choose a market-facing alternative instead:
  preferred alternatives: regional competitive dynamics, OEM strategic response, price segment restructuring, consumer demand shifts, brand positioning changes
- BOM cost analysis IS allowed when the topic is directly about cost pressures (e.g., memory price increase, tariff impact)

Query rules:
- Section 1: broad market statistics and structural shift — growth rates, share forecasts, competitive change
- Section 2: queries targeted at the specific derived dimension chosen
- Section 3: queries targeted at the second specific derived dimension
- English only; include current year ({current_year}); no Korean characters in queries
"""


SECTION_REPORT_PROMPT = """You are a smartphone market analyst. Write one report section based ONLY on the evidence below.

Topic: "{topic}"
Section title: "{section_title}"
Section angle (what this section must answer): {angle}
Current date: {current_date}
Temporal accuracy rules:
- Events that occurred BEFORE {current_date}: use past tense — ~했습니다, ~됐습니다, ~나타났습니다
- Events confirmed/announced but NOT yet occurred (after {current_date}): use future/expectation — ~예정입니다, ~전망됩니다, ~출시될 것으로 예상됩니다
- Rumored or speculative events (source says "reportedly", "plans to", "expected to", "could"): ~알려져 있습니다, ~보도됩니다, ~것으로 전해집니다
Causal role of this section: {causal_role}
  - structural_backdrop: establish the big-picture market-level change with specific statistics. Answer: what is changing at the market level and at what scale?
  - derived_analysis_1: deep-dive on the first key dimension derived from the structural backdrop. Answer the section angle above specifically with named companies and data.
  - derived_analysis_2: deep-dive on the second key dimension derived from the structural backdrop. Answer the section angle above specifically with named companies and data.
Other sections in this report: {other_sections}

Already cited in previous sections — PREFER different statistics; may re-use a source with a clearly different angle if it is the most relevant evidence for THIS section's causal role:
{already_cited}

Evidence:
---
{evidence_block}
---

CRITICAL RULE: Every statistic must directly answer this section's angle question above.
- For structural_backdrop: statistics must demonstrate the scale and nature of the market-level change
- For derived_analysis_1 / derived_analysis_2: each bullet must name specific companies and connect back to the structural backdrop as the root
- Connect every data point back to the section angle of "{section_title}"

Respond ONLY with a valid JSON object (no markdown, no code blocks):

{{
  "headline": "<one Korean sentence ≤80 chars — the section's single most important CAUSAL conclusion>",
  "narrative": "<Korean prose of 4-5 sentences: explicitly state 원인→메커니즘→결과. Use concrete companies, dates, percentages, shipment figures, revenue figures, prices, market shares, or forecast years whenever they appear in the evidence. Every sentence should include at least one specific company, market, period, number, or measurable market effect when supported by the evidence. Prose only, no bullets, no line breaks.>",
  "bullets": [
    "• \"<VERBATIM quote — copy the exact title or key sentence from the source article, do NOT paraphrase>\" — <article document title> [Source name, YYYY-MM-DD]",
    "• \"<VERBATIM quote>\" — <article document title> [Source name, YYYY-MM-DD]",
    "• \"<VERBATIM quote>\" — <article document title> [Source name, YYYY-MM-DD]"
  ],
  "footnotes": [
    {{"num": 1, "url": "<https://full-url>", "source": "<source name>", "title": "<article document title>", "date": "<YYYY-MM-DD>"}},
    {{"num": 2, "url": "<https://full-url>", "source": "<source name>", "title": "<article document title>", "date": "<YYYY-MM-DD>"}}
  ]
}}

Component rules:
- headline: ≤80 Korean chars; must be a causal conclusion — NOT a topic label
- narrative: 한국어 산문 4-5문장; 원인-메커니즘-결과 명시; 가능한 모든 문장에 근거 기반 수치·기업명·기간·시장명을 포함; 투자 관점(주가/밸류에이션) 제외
- bullets: 3-5 items; each bullet is ONE complete line — do NOT split a single quote across multiple bullets
- each bullet MUST quote ONE verbatim title or ONE complete verbatim sentence from the evidence; do NOT paraphrase
- if the source title is the key claim, use the article title verbatim; if a specific complete sentence is more precise, use that full sentence verbatim
- if a sentence is very long, truncate with "..." at a natural phrase boundary — keep it as ONE bullet, never split into sub-bullets
- include the article document title after the quote, then [Source name, YYYY-MM-DD]
- bullets: PREFER different sources from already-cited list; if re-using an already-cited source, must cite a clearly different quote or angle relevant to THIS section's causal role
- footnotes: every cited URL; numbered sequentially; full https:// URLs only; include article title in "title" field and publication date in "date" field (YYYY-MM-DD format)
- Base ALL claims strictly on the evidence — do NOT invent quotes
- Omit a bullet rather than fabricate a quote
"""


INSIGHTS_PROMPT = """You are a smartphone market analyst. Based on the three-section causal chain report below, generate research background, market insights (시사점), and an executive summary.

Topic: "{topic}"
Current date: {current_date}
Temporal accuracy rules — apply to EVERY sentence in executive_summary and all insight body fields:
- Events that occurred BEFORE {current_date}: past tense — ~했습니다, ~됐습니다, ~나타났습니다
- Events confirmed/announced but NOT yet occurred (after {current_date}): future/expectation — ~예정입니다, ~전망됩니다, ~출시될 것으로 예상됩니다
- Rumored or speculative events (source says "reportedly", "plans to", "expected to"): ~알려져 있습니다, ~보도됩니다, ~것으로 전해집니다
Report (3 sections — structural backdrop → derived analysis 1 → derived analysis 2):
---
{report_summary}
---

Generate EXACTLY 3 insights. Each insight must answer: "이 이슈가 스마트폰 시장에 어떤 영향을 주는가?" Focus on market dynamics, competitive behavior, and consumer-facing outcomes — NOT supply chain internals.

Read the 3 report sections carefully. Section 1 establishes the structural backdrop; Sections 2 and 3 are derived analyses. Choose 3 insight angles that are the most important market-impact implications of THIS specific topic — derived from what the sections actually cover. The 3 angles must be:
- Different from each other (no overlap)
- Directly traceable to named companies and statistics in the report
- Answering "so what does this mean for the smartphone market?" not "what happened?"
- NOT supply chain or manufacturing cost angles — focus on competitive dynamics, market structure, OEM strategy, consumer demand, or regional shifts

Respond ONLY with a valid JSON object (no markdown, no code blocks):

{{
  "research_background": "<Korean prose of 2-4 sentences. Explain the concrete market or industry change that made this topic important. Start directly with the market change, NOT with the act of researching. Do NOT use generic phrases like '이 주제를 조사했습니다', '확인할 필요가 있습니다', '최근 시장 변화와 기업 전략의 연결 관계'. Describe the concrete structural change, competitive shift, technology shift, demand shift, regulation shift, supply chain shift, or business model shift reflected in the report. Include the most important available numbers, dates, companies, or events only when supported by the report. No bullets, no markdown, no citations, no URLs.>",
  "executive_summary": "<Korean prose of MINIMUM 600 Korean characters covering ONLY the 3-section causal chain: 구조적 원인 → 직접 영향 → 시장 결과. Write 6-8 sentences as ONE flowing paragraph — NOT a list of disconnected facts. Connect sentences naturally using transitional phrases such as 이로 인해, 이러한 흐름 속에서, 그 결과, 나아가, 한편 등. DO NOT use English terms or abbreviations — Korean only. Structure: [원인 파트] 첫 문장부터 '구조적 변화', '시장 확장' 같은 추상 표현 금지 — 반드시 구체적 수치와 현상을 직접 서술할 것 (예: '애플의 폴더블 출시 예정으로 2026년 시장이 20% 성장할 것으로 전망됩니다'). [메커니즘 파트] 그 원인이 어떤 경로로 시장에 전달됐는가 — 이전 문장과 이로 인해/이에 따라 등으로 자연스럽게 이어질 것. [결과 파트] 구체적 기업명과 수치로 승자·패자 서술 — 앞 흐름의 귀결로 연결할 것. 원인 재도입 금지 — 원인은 한 번만 언급하고 이후 문장은 그 흐름의 연속으로만 전개할 것. 인사이트·미래 전망 문장은 포함하지 말 것. TENSE: 애플 폴더블의 출시 자체와 그 시장 영향(점유율 확보, 판매량 잠식 등)은 {current_date} 기준 아직 발생하지 않은 미래 사건 — 반드시 ~전망됩니다/예상됩니다/예정입니다 사용. 출시 발표·부품 발주 증대처럼 이미 보도된 사실은 ~했습니다 가능. 합쇼체만: 했습니다/합니다/입니다/됩니다/있습니다. ~다 절대 금지.>",
  "insights": [
    {{
      "title": "<Korean noun phrase ≤20 chars>",
      "body": "<Korean prose of MINIMUM 500 Korean characters — this is NOT 2-3 short sentences. Write a substantial multi-sentence paragraph using this exact structure: [문장1] 핵심 시사점을 인과 관계로 한 문장으로 제시. [문장2-4] 보고서의 구체적 수치·기업명을 자연스럽게 녹여 메커니즘 설명. [문장5-6] 영향 받는 OEM·시장 세그먼트·지역을 구체적으로 지목하고 왜 그러한지 설명. [문장7-8] 향후 6~18개월 전망 — 시장 재편, 경쟁 구도 변화, OEM 전략 수정 등 구체적 함의. 합쇼체만 사용: 했습니다/합니다/입니다/됩니다/있습니다. ~다 절대 금지. 인용 괄호 [출처] 금지.>"
    }}
  ]
}}

Rules:
- EXACTLY 3 insights in the order specified above — do not reorder or replace
- Each body MUST be approximately 500 Korean characters — substantially longer than 2-3 sentences
- 합쇼체 throughout — 했습니다, 합니다, 입니다, 됩니다, 있습니다. NEVER ~다 plain endings
- TEMPORAL RULES (apply to every sentence in executive_summary AND all insight bodies):
  * 2026 full-year market figures (성장률, 점유율 전망치 등) are forecasts not yet confirmed — MUST use ~전망됩니다/예상됩니다, NEVER ~했습니다/됐습니다
  * Events confirmed as having occurred before {current_date} (announcements, shipment data, product launches already reported) MAY use past tense ~했습니다
  * Market impact figures that are projections/forecasts (share gains, shipment forecasts, growth rates for the full year) have NOT been confirmed yet — always use ~전망됩니다/예상됩니다
- No [Source, date] brackets anywhere in the output
- Every claim must be traceable to the report's specific numbers or named companies
- No investment angle whatsoever — do NOT write "Investor Takeaway", 투자자 관점, 선제적 투자 필수, 매수/매도/보유 권고, or any language framing conclusions as advice to investors. Focus ONLY on market structure, competitive dynamics, OEM strategy, and consumer outcomes.
- All text in Korean
- research_background must be specific to this report and must not contain boilerplate research-purpose wording
"""


DIMENSION_ANALYSIS_PROMPT = """You are a smartphone market analyst. Based ONLY on the search results below, deeply analyze the assigned analytical dimension and produce mindmap-ready JSON.

Topic: {topic}
Analytical dimension: {dimension_name}
Why this dimension was selected: {dimension_rationale}

Items the user explicitly excluded (NEVER include these):

Topic: {topic}
Analytical dimension: {dimension_name}
Why this dimension was selected: {dimension_rationale}

Items the user explicitly excluded (NEVER include these):
- excluded perspectives: {excluded_perspectives}
- excluded topic keywords: {excluded_topics}

Search results:
---
{search_results}
---

Analysis rules:
- Derive 3-5 subtopics (the first-level mindmap branches)
- For each subtopic, label which of the 3 axes is impacted:
    Build (production: components, manufacturing, supply chain) / Sell-in (channel shipment) / Sell-through (final sale)
    If the impact spans multiple axes, use "composite"
- **Enforce user exclusions**:
    · Never create a subtopic whose perspective is in excluded_perspectives (e.g. if "build" is excluded, no build/composite-with-build-only subtopic)
    · Never create a subtopic whose core theme is one of the excluded topic keywords
    · Incidental mentions inside other-perspective subtopics are still allowed
- subtopic.label: noun phrase ≤30 characters IN KOREAN (e.g. "프리미엄 세그먼트 잠식", "공급망 재편")
- subtopic.perspective: one of "build" / "sell_in" / "sell_through" / "composite"
- 3-5 evidence items per subtopic (the second-level mindmap branches)
- evidence.finding: a single Korean sentence with concrete grounding (numerical figures preferred)
- evidence.source_url: MUST be one of the URLs that appeared in the search results above
- **No market-overview duplication**: do NOT create subtopics whose core theme is overall market size, key-player landscape, or general market-share overview — those are handled separately by the Overview section. Focus on this dimension's unique deep analysis.
- No statements unsupported by the search results — exclude speculation / generalities
- No investment-angle analysis (stock price, valuation, buy-sell recommendations)
- All text (label, headline, finding) IN KOREAN
- **JSON output**: inside finding strings, use single quotes (') for inner quotation rather than double quotes (") — prevents escape errors

Response format (close with ONE ```json fenced block at the end):

```json
{{
  "dimension": "{dimension_name}",
  "headline": "<one-sentence core finding for this dimension IN KOREAN, ≤80 chars>",
  "subtopics": [
    {{
      "label": "<subtopic label IN KOREAN>",
      "perspective": "<build|sell_in|sell_through|composite>",
      "evidence": [
        {{"finding": "<one-sentence grounding IN KOREAN>", "source_url": "<https://...>"}}
      ]
    }}
  ]
}}
```
"""


CROSS_DIMENSION_LINKAGE_PROMPT = """You are a smartphone market strategy analyst.
The following are per-dimension analyses for the topic "{topic}":

{dimension_summaries}

Items the user explicitly excluded (NEVER include these in linkages either):
- excluded perspectives: {excluded_perspectives}
- excluded topic keywords: {excluded_topics}

Analyze the causal relationships and interactions between the dimensions above to derive composite market impacts as linkage structures.

Rules:
- Only include real causal relationships between dimensions (no speculation / generalities)
- causal_chain: concise "A → B → C" form (each step ≤15 chars IN KOREAN)
- relationship: noun phrase IN KOREAN, ≤20 chars
- Tag each linkage with whether it occurs on the Build / Sell-in / Sell-through axis
- **Enforce user exclusions**: no linkage whose perspective is excluded; no excluded topic keyword in causal_chain or relationship
- No investment-angle reasoning
- All text IN KOREAN
- Derive at least 2 and at most 4 linkages

Response format (close with ONE ```json fenced block at the end):

```json
{{
  "linkages": [
    {{
      "from_dim": "<source dimension IN KOREAN>",
      "to_dim": "<destination dimension IN KOREAN>",
      "relationship": "<relationship title IN KOREAN, ≤20 chars>",
      "causal_chain": "<A → B → C IN KOREAN>",
      "perspective": "<build|sell_in|sell_through|composite>"
    }}
  ]
}}
```
"""


KEY_QUESTIONS_PROMPT = """You are a smartphone market analyst. Below are per-dimension analyses and cross-dimension causal linkages for the topic "{topic}".

Analysis rationale:
{analysis_rationale}

Per-dimension analysis:
{dimension_summaries}

Cross-dimension linkages:
{linkages_text}

Items the user explicitly excluded (NEVER include these when deriving questions):
- excluded perspectives: {excluded_perspectives}
- excluded topic keywords: {excluded_topics}
- active perspectives (questions/scenarios MUST be confined to these): {active_perspectives}

Synthesize the analysis above to derive **5 key questions** that the final report must answer. Also use the analysis to independently judge an appropriate time horizon, and add scenarios if scenario-branching is clearly warranted.

Core principles:
- All 5 questions must support decision-making strictly within the active_perspectives
- Never derive a question whose core perspective is in excluded_perspectives (even composite questions are forbidden if their core is an excluded perspective)
- Excluded topic keywords must not appear as the core subject of any question
- Each question, when answered, should change the analyst's judgment on production planning / channel strategy / market-share outlook (whichever is in active_perspectives)
- No investment-angle questions (stock price, buy-sell, valuation)
- All text IN KOREAN

Distribution of the 5 questions (within active_perspectives only):
- 1 question per dimension (so N dimensions → N dimension questions)
- 1 composite linkage-based question — causal relationships among active-perspective dimensions
- 1 active-perspective synthesis question — include scenario branching if scenarios exist
- Adjust so the total is 5 (4 dims → 4 dim qs + 1 synthesis; 2 dims → 2 dim qs + 1 linkage + 2 synthesis; etc.)
- For scenario.build_impact / sell_in_impact / sell_through_impact: leave **empty string ("") for any field whose perspective is excluded**

Question quality:
- Answerable form (figures, dates, comparisons must be possible)
- Concrete rather than abstract (e.g. "어떤 영향?" → "2026년 폴더블 출하량은 전년 대비 몇 % 증가할 것인가?")
- Tag each question with its perspective (build / sell_in / sell_through / composite)

Time horizon:
- Decide based on the timing of events in the analysis
- Choose short-term (6-12 months) / mid-term (1-2 years) / long-term (3+ years), or a custom label
- rationale: 1-2 Korean sentences explaining why this horizon fits

Scenarios:
- Only when there is a clear branching point or high volatility
- If unnecessary, return empty array []
- Two or three scenarios (e.g. optimistic / base / pessimistic, or event branches)

Response format (close with ONE ```json fenced block at the end):

```json
{{
  "time_horizon": {{
    "label": "<short / mid / long term label IN KOREAN, judged independently>",
    "rationale": "<why this horizon fits, 1-2 sentences IN KOREAN>"
  }},
  "scenarios": [
    {{
      "name": "<scenario name IN KOREAN, ≤20 chars>",
      "trigger": "<one-sentence trigger condition IN KOREAN>",
      "build_impact": "<production-side impact, one sentence IN KOREAN>",
      "sell_in_impact": "<channel-shipment-side impact, one sentence IN KOREAN>",
      "sell_through_impact": "<final-sale-side impact, one sentence IN KOREAN>"
    }}
  ],
  "key_questions": [
    {{
      "id": "Q1",
      "question": "<one-sentence question IN KOREAN, concrete & quantitative>",
      "rationale": "<why this question matters, 1-2 sentences IN KOREAN>",
      "perspective": "<build|sell_in|sell_through|composite>",
      "related_dimensions": ["<related dim name IN KOREAN>"],
      "related_linkages": []
    }}
  ]
}}
```
"""


KEY_QUESTIONS_GAP_FILL_PROMPT = """You are a smartphone market analyst. The user has ALREADY provided their own questions for this analysis. Your job is to (a) decide an appropriate time horizon, (b) optionally produce scenarios, and (c) generate **0 to N supplementary key_questions** that fill genuine gaps not already covered by the user's questions.

Topic: "{topic}"

Analysis rationale:
{analysis_rationale}

Per-dimension analysis:
{dimension_summaries}

Cross-dimension linkages:
{linkages_text}

User-provided questions (TREAT AS GIVEN — do NOT duplicate, paraphrase, or wrap them):
{user_questions_block}

User-question → dimension coverage map (each user question is tagged with the dimensions it covers):
{user_q_dimension_map}

Items the user explicitly excluded (NEVER include these):
- excluded perspectives: {excluded_perspectives}
- excluded topic keywords: {excluded_topics}
- active perspectives (questions/scenarios MUST be confined to these): {active_perspectives}

Gap-fill principle:
- A "gap" is a high-importance angle from the analysis (specific dimension / linkage / perspective imbalance) that the user's questions do NOT already address
- Use the dimension-coverage map as a STRUCTURAL signal: dimensions absent from the map are obvious candidates for supplementary questions
- Do NOT supplement just to hit a target count. Quality > quantity. If the user's M questions already provide thorough coverage, return 0 supplementary questions.
- If you DO supplement, prefer 1-3 questions. Never exceed 5 supplementary questions.
- Never paraphrase, mirror, or split a user question
- Never derive a question whose core perspective is in excluded_perspectives
- Excluded topic keywords must not appear as the core subject of any question
- All text IN KOREAN

Question quality (same as the standard 5-question mode):
- Answerable form (figures / dates / comparisons must be possible)
- Concrete rather than abstract
- Tag each question with its perspective (build / sell_in / sell_through / composite)
- Each supplementary question must reference at least one dimension in related_dimensions (use the exact dimension names from the analysis above)

Time horizon: judge independently based on the analysis (same rules as standard mode).

Scenarios: only if a clear branching point exists; otherwise empty array.

Response format (close with ONE ```json fenced block at the end):

```json
{{
  "time_horizon": {{
    "label": "<short / mid / long term label IN KOREAN>",
    "rationale": "<why this horizon fits, 1-2 sentences IN KOREAN>"
  }},
  "scenarios": [
    {{
      "name": "<scenario name IN KOREAN, ≤20 chars>",
      "trigger": "<one-sentence trigger IN KOREAN>",
      "build_impact": "<one sentence IN KOREAN — empty string if 'build' is excluded>",
      "sell_in_impact": "<one sentence IN KOREAN — empty string if 'sell_in' is excluded>",
      "sell_through_impact": "<one sentence IN KOREAN — empty string if 'sell_through' is excluded>"
    }}
  ],
  "key_questions": [
    {{
      "id": "Q1",
      "question": "<one-sentence supplementary question IN KOREAN, concrete & quantitative>",
      "rationale": "<why this gap matters and why the user's questions don't cover it, 1-2 sentences IN KOREAN>",
      "perspective": "<build|sell_in|sell_through|composite>",
      "related_dimensions": ["<exact dimension name IN KOREAN>"],
      "related_linkages": []
    }}
  ],
  "gap_fill_summary": "<one-sentence IN KOREAN summary of WHICH gaps were filled or WHY no supplement was needed — required even when key_questions is []>"
}}
```
"""


USER_Q_DIMENSION_TAG_PROMPT = """You are a smartphone market analyst. Map each user-provided question to the relevant analytical dimensions.

Topic: "{topic}"

Available dimensions (only these names are valid in related_dimensions output):
{available_dimensions}

User questions to map (each has an id and the verbatim text):
{user_questions_block}

Mapping rules:
- For each user question, infer which dimension(s) the question is asking about
- A question may map to 0 dimensions (general / cross-cutting), 1 dimension (specific), or multiple dimensions
- Use ONLY the exact dimension names listed above in related_dimensions — no new names, no paraphrasing
- Do not modify the question text; preserve verbatim
- Do not add or remove user questions; output exactly the same number with the same ids in the same order

Response format (PURE JSON only, NO markdown code blocks):

{{
  "tagged_questions": [
    {{
      "id": "<user_question id, e.g. Q_user1>",
      "question": "<verbatim user question text>",
      "related_dimensions": ["<exact dim name>", "<exact dim name>"]
    }}
  ]
}}
"""


OVERVIEW_QUESTION_PROMPT = """You are a smartphone market analyst. Using the analysis context below, generate **ONE market-overview question** that helps a reader who is new to this topic understand the market as a whole.

Topic: {topic}
Current year: {current_year}

Analysis rationale:
{analysis_rationale}

Question generation rules:
- Output exactly ONE question IN KOREAN (NOT JSON, plain text)
- The question MUST cover all three of the following:
  1. Total market size and growth trajectory of the relevant market
  2. Current key players and their positioning within the market
  3. The position of the topic product/event within this market
- It should be a question that elicits a concrete and quantitative answer
- No investment-angle (stock price / valuation / buy-sell)
- Output ONLY the question sentence — no explanations, numbering, or bullets
"""
