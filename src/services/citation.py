import uuid
from datetime import date
from typing import Iterable
from src.models import Citation


class CitationURLNotFetchedError(Exception):
    pass


class CitationRegistry:
    def __init__(self, fetched_urls: frozenset[str] = frozenset()):
        self._citations: dict[str, Citation] = {}
        self._known_urls: set[str] = set(fetched_urls)
        self._provenance_map: dict[str, str] = {}  # url -> "phase0_archive" | "phase1_fetched"
        self._liveness_map: dict[str, bool] = {}   # url -> True/False (HEAD validated)

    def add_phase0_archive(self, urls: Iterable[str]) -> None:
        """Register URLs from Phase 0 mindmap evidence (trusted historical)."""
        for u in urls:
            if not u:
                continue
            self._known_urls.add(u)
            # don't overwrite if already labeled phase1_fetched (later round trumps)
            self._provenance_map.setdefault(u, "phase0_archive")

    def add_phase1_fetched(self, urls: Iterable[str]) -> None:
        """Register URLs newly fetched during Phase 1 refinement search."""
        for u in urls:
            if not u:
                continue
            self._known_urls.add(u)
            self._provenance_map[u] = "phase1_fetched"  # always overwrite

    def is_known(self, url: str) -> bool:
        return url in self._known_urls

    def get_provenance(self, url: str) -> str | None:
        """Returns 'phase0_archive' | 'phase1_fetched' | None."""
        return self._provenance_map.get(url)

    def get_liveness(self, url: str) -> bool | None:
        """Returns True | False | None (None = unchecked)."""
        return self._liveness_map.get(url)

    def set_liveness(self, url: str, alive: bool) -> None:
        self._liveness_map[url] = alive

    def add_fetched_urls(self, urls) -> None:
        """Backward-compat shim. Existing code (Phase 0) calls this — internally
        delegate to add_phase1_fetched. Accept frozenset, set, or iterable."""
        self.add_phase1_fetched(urls)

    def urls_by_provenance(self) -> dict[str, list[str]]:
        """Return all known URLs partitioned by provenance, sorted for determinism."""
        out: dict[str, list[str]] = {"phase0_archive": [], "phase1_fetched": []}
        for url in sorted(self._known_urls):
            prov = self._provenance_map.get(url)
            if prov in out:
                out[prov].append(url)
            else:
                # legacy URLs added without provenance — bucket as phase1_fetched
                # (matches add_fetched_urls shim)
                out["phase1_fetched"].append(url)
        return out

    def register(self, source_name: str, url: str, tier: int, excerpt: str) -> Citation:
        if not self.is_known(url):
            raise CitationURLNotFetchedError(
                f"URL not in known set: {url}. Citation rejected to prevent hallucination."
            )
        citation = Citation(
            source_name=source_name,
            source_url=url,
            source_tier=tier,
            excerpt=excerpt[:500],
            access_date=date.today().isoformat(),
        )
        self._citations[citation.id] = citation
        return citation

    def get(self, citation_id: str) -> Citation | None:
        return self._citations.get(citation_id)

    def all_citations(self) -> list[Citation]:
        return list(self._citations.values())

    def validate_all(self) -> list[str]:
        errors = []
        for c in self._citations.values():
            if not c.source_url:
                errors.append(f"Citation {c.id} missing URL")
            if not c.excerpt:
                errors.append(f"Citation {c.id} missing excerpt")
        return errors

    def format_footnotes(self) -> str:
        lines = []
        for i, c in enumerate(self._citations.values(), 1):
            lines.append(f"[{i}] {c.source_name}. {c.source_url} (accessed {c.access_date})")
        return "\n".join(lines)

    def detect_gaps(self, required_dimensions: list[str], available_data: dict) -> list[str]:
        return [dim for dim in required_dimensions if not available_data.get(dim)]
