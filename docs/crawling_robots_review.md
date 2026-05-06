# Crawling and Robots Review

Date: 2026-05-07

This document records the current crawling/source policy for Research Helper. It is an operational risk note, not legal advice.

## Current Decision

The following sources are excluded from active smartphone archive collection, public archive listing, topic mining, and preferred external-search source hints:

- Reuters
- Nikkei Asia
- Gartner
- Bloomberg Technology

Existing local historical files or database rows may still exist, but the active code paths no longer include these sources.

## Why These Sources Were Excluded

| Source | Reason | Decision |
|---|---|---|
| Reuters | The archive has no descriptions, so topic quality is mostly title-only. Reuters also blocks many AI/data bots in `robots.txt`. | Exclude from active collection and topic workflows. |
| Nikkei Asia | RSS has title-only quality, with no useful description. Robots also signals broad AI/scraper restrictions. | Exclude from active collection and topic workflows. |
| Gartner | Terms prohibit scraper/robot/data-mining access without prior written consent and prohibit AI input/training/development use. Current smartphone relevance was 0. | Exclude from automated collection. |
| Bloomberg Technology | `robots.txt` blocks Python user agents and many AI/data bots. The RSS feed gives metadata, but policy risk is high and smartphone relevance was weak. | Exclude from active collection and topic workflows. |

## Scope Reviewed

The policy applies to source lists in:

- `scripts/build_all_archives.py`
- `src/server.py` `ARCHIVE_REGISTRY`
- `src/config.py` `RSS_SOURCES`
- `src/services/search.py` preferred publisher stop words / search hints
- `src/services/body_fetcher.py` body-fetch policy

## Baseline Policy

Use these defaults unless a source-specific policy says otherwise.

- Public pages should show only `title`, `source`, `date`, `url`, and short snippets.
- Do not publicly display original article bodies.
- Do not fetch, cache, or send paywalled/login-only content to an LLM.
- Prefer RSS, sitemap, or official APIs over page scraping.
- Follow `robots.txt`, `Crawl-delay`, and explicit site terms.
- Treat AI-specific robots blocks as a signal to avoid using that site's content as LLM input unless licensed or clearly permitted.
- Keep source links visible in reports and avoid long verbatim quotations.

## Active Smartphone Sources

These remain active in smartphone archive/status flows after the exclusion:

| Source | Policy |
|---|---|
| Counterpoint Research | Public metadata and short snippets. Avoid `/api` paths. |
| TrendForce | RSS/page metadata only until robots is rechecked successfully. |
| Omdia | Public metadata only. Do not body-fetch or pass article bodies to LLM unless licensed. |
| IDC | Public metadata only. No paywalled content or body cache. |
| Yole | Public metadata only; recheck robots before expanding. |
| Morgan Stanley | Public pages only. Avoid blocked auth/content paths and body redistribution. |
| DigiTimes Asia | RSS metadata only. Do not body-fetch article pages. |
| TechInsights | Public metadata only. Treat as research-firm metadata source; no body fetch. |
| UBI Research | Public sitemap/metadata only. No body fetch. |
| CCS Insight | Public sitemap/metadata only. No body fetch. |

## Higher-Risk Sources Still Present In Other Domains

| Source | Recommendation |
|---|---|
| arXiv export | Do not scrape `export.arxiv.org` pages. Use official arXiv API and respect rate limits. |
| Automotive World | Metadata/link use only. Respect `Crawl-delay: 10`. Avoid AI/RAG body ingestion. |
| IEEE Spectrum | Metadata/link use only. Avoid PDF crawling and body ingestion. |
| TechCrunch | RSS metadata only. Avoid body cache and LLM ingestion. |
| MIT Technology Review | RSS/sitemap metadata only. Avoid body cache and LLM ingestion. |
| The Verge | RSS metadata only. Avoid body cache and LLM ingestion. |
| WardsAuto | Respect crawl delay. Metadata/link use only. |

## Implementation Notes

Changes made for the exclusion decision:

- Removed Reuters, Gartner, Nikkei Asia, and Bloomberg Technology from `scripts/build_all_archives.py`.
- Removed Reuters, Gartner, Nikkei Asia, and Bloomberg Technology from `src/server.py` `ARCHIVE_REGISTRY`.
- Removed Reuters and Nikkei Asia RSS feeds from `src/config.py`.
- Removed Reuters, Nikkei, Gartner, and Bloomberg publisher hints from `src/services/search.py`.
- Removed Reuters, Nikkei Asia, and Bloomberg Technology from body-fetch policy lists because they are now excluded rather than metadata-only active sources.

The existing files below are not deleted automatically:

- `data/archives/reuters.json`
- `data/archives/nikkei_asia.json`
- `data/archives/gartner.json`
- `data/archives/bloomberg.json`
- existing rows in `data/mi_news/market_dashboard.db`

Delete or archive those manually only if historical data removal is required.

## Suggested Next Step

Add a machine-readable source policy file such as `data/source_policy.json`:

```json
{
  "Reuters": {
    "active": false,
    "allow_metadata": false,
    "allow_body_fetch": false,
    "allow_llm_input": false,
    "reason": "Excluded due to title-only quality and AI/data bot restrictions"
  }
}
```

Then make archive builders and search pipelines consult that policy before fetching or ranking sources.

## Reference URLs

- Reuters robots: https://www.reuters.com/robots.txt
- Gartner Terms: https://www.gartner.com/en/about/policies/terms-of-use
- Bloomberg robots: https://www.bloomberg.com/robots.txt
- Omdia robots: https://omdia.tech.informa.com/robots.txt
- Omdia Terms: https://omdia.tech.informa.com/terms-and-conditions
- Google robots.txt explanation: https://developers.google.com/search/docs/crawling-indexing/robots/robots_txt
- EU database protection overview: https://digital-strategy.ec.europa.eu/en/policies/protection-databases
- U.S. Copyright Office Fair Use: https://copyright.gov/fair-use/
