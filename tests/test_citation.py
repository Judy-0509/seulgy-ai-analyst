import pytest
from src.services.citation import CitationRegistry, CitationURLNotFetchedError


def test_register_valid_url():
    registry = CitationRegistry(fetched_urls=frozenset(["https://reuters.com/article"]))
    c = registry.register("Reuters", "https://reuters.com/article", tier=2, excerpt="test content")
    assert c.source_name == "Reuters"
    assert c.id in {c.id for c in registry.all_citations()}


def test_register_rejects_unfetched_url():
    registry = CitationRegistry(fetched_urls=frozenset(["https://reuters.com/article"]))
    with pytest.raises(CitationURLNotFetchedError):
        registry.register("Fake", "https://notfetched.com/x", tier=2, excerpt="bad")


def test_add_fetched_urls():
    registry = CitationRegistry()
    registry.add_fetched_urls(frozenset(["https://new.com/page"]))
    c = registry.register("New", "https://new.com/page", tier=3, excerpt="content")
    assert c.source_url == "https://new.com/page"


def test_validate_all_empty():
    registry = CitationRegistry()
    errors = registry.validate_all()
    assert errors == []


def test_detect_gaps():
    registry = CitationRegistry()
    available = {"country": ["data"], "vendor": []}
    gaps = registry.detect_gaps(["country", "vendor", "segment"], available)
    assert "vendor" in gaps
    assert "segment" in gaps
    assert "country" not in gaps


def test_format_footnotes():
    registry = CitationRegistry(fetched_urls=frozenset(["https://a.com"]))
    registry.register("SiteA", "https://a.com", tier=3, excerpt="stuff")
    footnotes = registry.format_footnotes()
    assert "[1]" in footnotes
    assert "SiteA" in footnotes


def test_two_tier_provenance():
    reg = CitationRegistry()
    reg.add_phase0_archive(["https://a.test/1", "https://b.test/2"])
    reg.add_phase1_fetched(["https://c.test/3"])
    assert reg.is_known("https://a.test/1")
    assert reg.is_known("https://c.test/3")
    assert not reg.is_known("https://unknown.test")
    assert reg.get_provenance("https://a.test/1") == "phase0_archive"
    assert reg.get_provenance("https://c.test/3") == "phase1_fetched"
    assert reg.get_provenance("https://unknown.test") is None


def test_phase1_fetched_overwrites_phase0_archive():
    reg = CitationRegistry()
    reg.add_phase0_archive(["https://a.test"])
    reg.add_phase1_fetched(["https://a.test"])  # same URL re-fetched
    assert reg.get_provenance("https://a.test") == "phase1_fetched"


def test_register_uses_known_set():
    reg = CitationRegistry()
    reg.add_phase0_archive(["https://known.test"])
    cit = reg.register("Test", "https://known.test", 3, "excerpt")
    assert cit.source_url == "https://known.test"


def test_register_unknown_url_raises_url_not_fetched_error():
    reg = CitationRegistry()
    reg.add_phase0_archive(["https://known.test"])
    with pytest.raises(CitationURLNotFetchedError):
        reg.register("Bad", "https://unknown.test", 3, "bad")


def test_add_fetched_urls_backward_compat():
    reg = CitationRegistry()
    reg.add_fetched_urls(frozenset(["https://legacy.test"]))
    assert reg.is_known("https://legacy.test")
    # legacy compat: gets phase1_fetched provenance (not archive)
    assert reg.get_provenance("https://legacy.test") == "phase1_fetched"


def test_liveness_tracking():
    reg = CitationRegistry()
    reg.add_phase0_archive(["https://a.test"])
    assert reg.get_liveness("https://a.test") is None  # unchecked
    reg.set_liveness("https://a.test", True)
    assert reg.get_liveness("https://a.test") is True
    reg.set_liveness("https://a.test", False)
    assert reg.get_liveness("https://a.test") is False
