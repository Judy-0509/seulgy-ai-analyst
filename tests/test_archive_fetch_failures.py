import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import _auto_research_helper as auto_helper  # noqa: E402
import _smartglass_research_helper as smartglass_helper  # noqa: E402
import build_all_archives as all_archives  # noqa: E402
import build_counterpoint_archive as counterpoint  # noqa: E402


async def network_failure(*args, **kwargs):
    return 0, "ERR: network down"


def test_auto_sitemap_failure_does_not_rewrite_archive(tmp_path, monkeypatch):
    archive = tmp_path / "archive.json"
    archive.write_text('{"built_at":"last-success"}', encoding="utf-8")
    before = archive.read_bytes()
    monkeypatch.setattr(auto_helper, "fetch", network_failure)

    with pytest.raises(RuntimeError, match=r"all listing fetches failed \(1 tried\)"):
        asyncio.run(auto_helper.build_sitemap(
            source_name="Example", site_base="https://example.com",
            sitemap_url="https://example.com/sitemap.xml", archive_path=archive,
            url_includes=["/news/"],
        ))

    assert archive.read_bytes() == before


def test_auto_rss_failure_does_not_rewrite_archive(tmp_path, monkeypatch):
    archive = tmp_path / "archive.json"
    archive.write_text('{"built_at":"last-success"}', encoding="utf-8")
    before = archive.read_bytes()
    monkeypatch.setattr(auto_helper, "ARCHIVE_DIR", tmp_path)
    feed = SimpleNamespace(
        entries=[], status=None, bozo=True, bozo_exception=OSError("DNS down"),
    )
    monkeypatch.setattr(auto_helper, "feedparser", SimpleNamespace(parse=lambda *a, **k: feed))

    with pytest.raises(RuntimeError, match=r"all listing fetches failed \(1 tried\)"):
        asyncio.run(auto_helper.build_rss_only(
            source_name="Example", site_base="https://example.com",
            rss_url="https://example.com/feed.xml", archive_path=archive,
        ))

    assert archive.read_bytes() == before


def test_smartglass_sitemap_failure_does_not_rewrite_archive(tmp_path, monkeypatch):
    archive = tmp_path / "example.json"
    archive.write_text('{"built_at":"last-success"}', encoding="utf-8")
    before = archive.read_bytes()
    monkeypatch.setattr(smartglass_helper, "ARCHIVE_DIR", tmp_path)
    monkeypatch.setattr(smartglass_helper, "fetch", network_failure)

    with pytest.raises(RuntimeError, match=r"all listing fetches failed \(1 tried\)"):
        asyncio.run(smartglass_helper.build_sitemap_archive(
            source_name="Example", site_base="https://example.com",
            archive_filename=archive.name, sitemaps=["https://example.com/sitemap.xml"],
            apply_keyword_filter=False,
        ))

    assert archive.read_bytes() == before


def test_counterpoint_listing_failure_does_not_rewrite_archive(tmp_path, monkeypatch):
    archive = tmp_path / "counterpoint.json"
    archive.write_text('{"built_at":"last-success"}', encoding="utf-8")
    before = archive.read_bytes()
    monkeypatch.setattr(counterpoint, "ARCHIVE_PATH", archive)
    monkeypatch.setattr(counterpoint, "fetch", network_failure)

    with pytest.raises(RuntimeError, match=r"all listing fetches failed \(1 tried\)"):
        asyncio.run(counterpoint.build(1))

    assert archive.read_bytes() == before


def test_archive_orchestrator_network_failure_skips_builders(monkeypatch, capsys):
    def fail_probe():
        raise OSError("DNS down")

    monkeypatch.setattr(all_archives, "network_probe", fail_probe)
    monkeypatch.setattr(all_archives.subprocess, "run", lambda *a, **k: pytest.fail("builder ran"))

    with pytest.raises(SystemExit) as exc:
        all_archives.main()

    assert exc.value.code == 1
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    assert next(event for event in events if event["type"] == "network_down")["error"] == "OSError: DNS down"
    complete = next(event for event in events if event["type"] == "complete")
    assert complete["failed"] == len(all_archives.BUILDERS)
    assert len(complete["summary"]) == len(all_archives.BUILDERS)
    assert all(not result["ok"] for result in complete["summary"])


def test_archive_orchestrator_exits_after_builder_failure(monkeypatch, capsys):
    monkeypatch.setattr(all_archives, "BUILDERS", [("Example", "example.py", "example.json")])
    monkeypatch.setattr(all_archives, "network_probe", lambda: None)
    monkeypatch.setattr(all_archives, "run_builder", lambda *a: {
        "type": "builder_done", "idx": 1, "name": "Example", "ok": False,
        "before": 0, "after": 0, "added": 0, "elapsed_sec": 0.1, "error": "failure",
    })

    with pytest.raises(SystemExit) as exc:
        all_archives.main()

    captured = capsys.readouterr()
    assert exc.value.code == 1
    complete = next(json.loads(line) for line in captured.out.splitlines()
                    if line.startswith('{') and '"complete"' in line)
    assert complete["failed"] == 1
    assert captured.err.strip() == "FAILED builders: Example"


@pytest.mark.parametrize(
    ("status", "entry_count", "bozo", "expected_error"),
    [
        (301, 10, False, None),
        (200, 0, False, None),
        (202, 0, False, "HTTP 202"),
        (None, 0, False, "no status or entries"),
        (200, 0, True, "HTTP 200"),
    ],
)
def test_auto_feed_success_rule(status, entry_count, bozo, expected_error):
    feed = SimpleNamespace(
        status=status,
        entries=[object() for _ in range(entry_count)],
        bozo=bozo,
        bozo_exception=None,
    )

    assert auto_helper._feed_error(feed) == expected_error
