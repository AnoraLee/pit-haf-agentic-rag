"""Synthetic notice/market fixtures; source hashes are not independent calendar gold."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from pit_haf.data.hub import file_sha
from pit_haf.data.session_calendar import (
    Profile,
    build_calendar,
    notice_text,
    reconcile,
    validate_sources,
)
from pit_haf.llm.ollama import write_json
from pit_haf.research import calendar_audit as audits
from pit_haf.research.market_snapshot import capture

SOURCE_RUN = "20261103T000000Z-abcdef12"
OPEN_DATES = ["2024-04-24", "2024-04-25", "2024-04-26", "2024-05-02", "2024-05-03"]
RAW = b'<html><div class="content-category">Synthetic notice: 27/4 to 1/5. No equity settlement 4/5.</div></html>'


def closure(start="2024-04-30", end="2024-05-01", reason="april_may"):
    return {"start": start, "end": end, "reason": reason, "source_id": "fixture_source"}


def profile():
    return Profile.model_validate(
        {
            "protocol": "settlement_calendar_audit_v0.1",
            "basis": "candidate_weekdays_minus_curated_VSDC_closures",
            "scope": "cash_equity_settlement_dates_only",
            "audit_start": "2024-04-24",
            "audit_end": "2024-05-03",
            "sources": [
                {
                    "id": "fixture_source",
                    "url": "https://vsdc.vn/vi/ad/123",
                    "raw_sha256": hashlib.sha256(RAW).hexdigest(),
                    "body_sha256": hashlib.sha256(notice_text(RAW).encode()).hexdigest(),
                    "anchors": ["Synthetic notice", "27/4"],
                }
            ],
            "revisions": [
                {
                    "id": "calendar_initial",
                    "start": "2024-04-24",
                    "end": "2024-05-08",
                    "supersedes": None,
                    "closures": [closure()],
                },
                {
                    "id": "calendar_amended",
                    "start": "2024-04-24",
                    "end": "2024-05-08",
                    "supersedes": "calendar_initial",
                    "closures": [
                        closure(start="2024-04-27"),
                        closure("2024-05-04", "2024-05-04", "no_equity_settlement_on_makeup_day"),
                    ],
                },
            ],
            "selected": ["calendar_amended"],
        }
    )


def reseal(folder):
    write_json(
        folder / "integrity.json",
        {"files": {p.name: file_sha(p) for p in folder.iterdir() if p.name != "integrity.json"}},
    )


def dependencies(root, observed=None, fail_equity=False):
    p = profile()
    source = root / "outputs/calendar-sources" / SOURCE_RUN
    source.mkdir(parents=True)
    (source / "fixture_source.raw").write_bytes(RAW)
    meta = {
        "id": "fixture_source",
        "url": p.sources[0].url,
        "captured_at": "2026-11-03T00:00:00Z",
        "status": "captured",
        "http_status": 200,
        "certificate_verification_disabled": False,
        "authentication_used": False,
        "automatic_retries": 0,
        "bytes": len(RAW),
        "sha256": hashlib.sha256(RAW).hexdigest(),
    }
    write_json(source / "fixture_source.json", meta)
    write_json(
        source / "source_plan.json",
        {
            "protocol": "calendar_source_capture_v0.1",
            "sources": [{"id": "fixture_source", "url": p.sources[0].url}],
        },
    )
    write_json(
        source / "manifest.json",
        {"protocol": "calendar_source_capture_v0.1", "research_result": False, "sources": [meta]},
    )
    (source / "capture-calendar-sources.ps1").write_bytes(
        b"# synthetic capture fixture; not executed\n"
    )
    reseal(source)
    plan = {
        "protocol": "market_price_snapshot_v0.1",
        "start": p.audit_start,
        "end": p.audit_end,
        "instruments": [
            {"symbol": "AAA", "asset_type": "equity"},
            {"symbol": "VNINDEX", "asset_type": "index"},
        ],
    }

    def fetcher(url, hosts, **kwargs):
        symbol = urlsplit(url).path.split("/")[-2]
        rows = [
            {"t": d + " 07:00", "o": 10, "h": 11, "l": 9, "c": 10, "v": 100}
            for d in (OPEN_DATES if observed is None else observed)
        ]
        if symbol == "VNINDEX" or fail_equity:
            rows[0]["h"] = 1
        return json.dumps({"symbol": symbol, "data_day": rows}).encode(), {
            "source_url": url,
            "final_url": url,
            "http_status": 200,
            "retrieved_at": "2026-11-03T00:00:00Z",
            "headers": {},
        }

    market, _ = capture(root, json.dumps(plan).encode(), fetcher=fetcher)
    return p, source, market


def test_hand_calendar_applies_replacement_and_keeps_full_date_mismatches():
    p = profile()
    rows, changes = build_calendar(p)
    assert [r["date"] for r in rows if r["candidate_settlement_day"]][:5] == OPEN_DATES
    assert changes == [
        {
            "date": "2024-04-29",
            "prior_revision": "calendar_initial",
            "revision": "calendar_amended",
            "prior_open": True,
            "revised_open": False,
        }
    ]
    report = reconcile(p, rows, {"AAA": OPEN_DATES[1:] + ["2024-04-29"]})
    asset = report["assets"][0]
    assert asset["missing_candidate_dates"] == ["2024-04-24"]
    assert asset["unexpected_observed_dates"] == ["2024-04-29"]
    assert asset["observed_sessions"] == report["candidate_sessions"] == 5
    assert not report["date_sets_match"]
    assert report["eligible_for_execution"] is report["venue_calendar_verified"] is False


def test_hand_t2_skips_holidays_weekends_and_never_assigns_broker_time():
    p = profile()
    rows, _ = build_calendar(p)
    result = reconcile(p, rows, {"AAA": OPEN_DATES})
    mapped = {r["trade_date"]: r for r in result["candidate_T2_dates"]}
    assert mapped["2024-04-25"]["candidate_T2_date"] == "2024-05-02"
    assert mapped["2024-04-26"]["candidate_T2_date"] == "2024-05-03"
    assert mapped["2024-05-03"]["candidate_T2_date"] == "2024-05-07"
    assert all(
        r["shares_available_at"] is r["sale_cash_available_at"] is None for r in mapped.values()
    )
    assert result["date_sets_match"] and not result["research_result"]


def test_curated_profile_keeps_all_three_amendments_and_cross_year_tail():
    p = Profile.model_validate_json(Path("configs/settlement_calendar_v0_1.json").read_bytes())
    rows, changes = build_calendar(p)
    assert {c["date"] for c in changes} == {
        "2021-02-10",
        "2021-02-17",
        "2023-09-01",
        "2023-09-05",
        "2024-04-29",
    }
    mapped = reconcile(p, rows, {})["candidate_T2_dates"]
    assert mapped[-2]["candidate_T2_date"] == "2025-01-02"
    assert mapped[-1]["candidate_T2_date"] == "2025-01-03"


@pytest.mark.parametrize(
    "change",
    [
        "obsolete",
        "missing_leaf",
        "duplicate_selected",
        "fork",
        "unknown_parent",
        "cycle",
        "duplicate_revision",
        "duplicate_source",
        "missing_source",
        "overlap",
        "reversed",
        "window",
        "gap",
        "bad_date",
        "wrong_scope",
    ],
)
def test_ambiguous_or_incomplete_profiles_are_rejected(change):
    data = profile().model_dump()
    if change == "obsolete":
        data["selected"] = ["calendar_initial"]
    elif change == "missing_leaf":
        data["selected"] = []
    elif change == "duplicate_selected":
        data["selected"] *= 2
    elif change == "fork":
        data["revisions"].append(data["revisions"][-1] | {"id": "another_fork"})
    elif change in {"unknown_parent", "cycle"}:
        data["revisions"][0]["supersedes"] = (
            "unknown" if change == "unknown_parent" else "calendar_amended"
        )
    elif change == "duplicate_revision":
        data["revisions"].append(data["revisions"][0])
    elif change == "duplicate_source":
        data["sources"] *= 2
    elif change == "missing_source":
        data["revisions"][0]["closures"][0]["source_id"] = "unknown"
    elif change == "overlap":
        data["revisions"][1]["closures"].append(closure())
    elif change == "reversed":
        data["revisions"][0]["closures"][0]["end"] = "2024-04-20"
    elif change == "window":
        data["revisions"][1]["end"] = "2024-05-09"
    elif change == "gap":
        data["revisions"].append(
            {
                "id": "tail",
                "start": "2024-05-10",
                "end": "2024-05-12",
                "supersedes": None,
                "closures": [closure("2024-05-11", "2024-05-11")],
            }
        )
        data["selected"].append("tail")
    elif change == "bad_date":
        data["audit_start"] = "20240424"
    else:
        data["scope"] = "all_markets_and_bonds"
    with pytest.raises(ValueError):
        Profile.model_validate(data)


@pytest.mark.parametrize("change", ["raw", "body_hash", "anchor", "missing_body", "source_set"])
def test_notice_bytes_and_body_binding_are_checked(change):
    data = profile().model_dump()
    payloads = {"fixture_source": RAW}
    if change == "raw":
        payloads["fixture_source"] += b" "
    elif change == "body_hash":
        data["sources"][0]["body_sha256"] = "0" * 64
    elif change == "anchor":
        data["sources"][0]["anchors"] = ["absent phrase"]
    elif change == "missing_body":
        payloads["fixture_source"] = b"<html>Missing notice</html>"
    else:
        payloads = {}
    with pytest.raises(ValueError):
        validate_sources(Profile.model_validate(data), payloads)
    assert (
        validate_sources(profile(), {"fixture_source": RAW})[0]["semantic_review"]
        == "assistant_curation_not_independent_gold"
    )


def test_missing_tail_mutation_and_duplicate_or_outside_observations_fail():
    p = profile()
    rows, _ = build_calendar(p)
    for values in [OPEN_DATES + [OPEN_DATES[0]], OPEN_DATES + ["2024-05-08"], ["20240424"]]:
        with pytest.raises(ValueError):
            reconcile(p, rows, {"AAA": values})
    altered = [dict(r) for r in rows]
    altered[0]["candidate_settlement_day"] = False
    with pytest.raises(ValueError, match="differ"):
        reconcile(p, altered, {"AAA": OPEN_DATES})
    data = p.model_dump()
    for r in data["revisions"]:
        r["end"] = "2024-05-04"
    shortened = Profile.model_validate(data)
    with pytest.raises(ValueError, match="tail"):
        reconcile(shortened, build_calendar(shortened)[0], {"AAA": OPEN_DATES})
    p.selected.append("calendar_initial")
    with pytest.raises(ValueError):
        build_calendar(p)


def test_snapshot_offline_replay_preserves_bytes_and_reports_quarantined_index(tmp_path):
    p, source, market = dependencies(tmp_path)
    raw = b" \n" + p.model_dump_json().encode()
    folder, report = audits.run(tmp_path, raw, source.name, market.name)
    assert audits.replay(tmp_path, folder) == report
    assert (folder / "profile.json").read_bytes() == raw
    assert report["date_sets_match"] and report["assets"][0]["observed_sessions"] == 5
    assert report["unassessed_instruments"][0]["symbol"] == "VNINDEX"
    assert (folder / "settlement_dates.csv").read_text().startswith("trade_date,candidate_T2_date,")
    assert not (tmp_path / "data").exists()


def test_failed_equity_or_missing_dates_cannot_disappear_from_coverage(tmp_path):
    p, source, market = dependencies(tmp_path, fail_equity=True)
    _, report = audits.run(tmp_path, p.model_dump_json().encode(), source.name, market.name)
    assert not report["date_sets_match"] and report["assets"] == []
    assert {v["symbol"] for v in report["unassessed_instruments"]} == {"AAA", "VNINDEX"}


@pytest.mark.parametrize(
    "change", ["report", "csv", "provenance", "source_raw", "source_metadata", "market", "file_set"]
)
def test_tampering_and_dependency_reseal_cannot_replay(tmp_path, change):
    p, source, market = dependencies(tmp_path)
    folder, _ = audits.run(tmp_path, p.model_dump_json().encode(), source.name, market.name)
    if change == "report":
        report = json.loads((folder / "report.json").read_bytes())
        report["candidate_T2_dates"] = []
        write_json(folder / "report.json", report)
    elif change == "csv":
        (folder / "settlement_dates.csv").write_bytes(b"forged\n")
    elif change == "provenance":
        manifest = json.loads((folder / "manifest.json").read_bytes())
        manifest["eligible_for_execution"] = True
        write_json(folder / "manifest.json", manifest)
    elif change == "source_raw":
        (source / "fixture_source.raw").write_bytes(RAW + b" ")
        reseal(source)
    elif change == "source_metadata":
        meta = json.loads((source / "fixture_source.json").read_bytes())
        meta["certificate_verification_disabled"] = True
        write_json(source / "fixture_source.json", meta)
        manifest = json.loads((source / "manifest.json").read_bytes())
        manifest["sources"] = [meta]
        write_json(source / "manifest.json", manifest)
        reseal(source)
    elif change == "market":
        (market / "AAA/response.raw").write_bytes(b"{}")
    else:
        (folder / "unexpected.txt").write_bytes(b"extra")
    reseal(folder)
    with pytest.raises(ValueError, match="differ"):
        audits.replay(tmp_path, folder)


def test_invalid_dependencies_do_not_create_runs_and_replay_refuses_external_path(tmp_path):
    with pytest.raises(ValueError):
        audits.run(tmp_path, profile().model_dump_json().encode(), "../escape", SOURCE_RUN)
    assert not (tmp_path / "outputs/calendar-audits").exists()
    with pytest.raises(ValueError):
        audits.replay(tmp_path, tmp_path)


def test_cli_reports_date_match_only_and_rejects_replay_overrides(tmp_path):
    p, source, market = dependencies(tmp_path)
    config = tmp_path / "profile.json"
    config.write_text(p.model_dump_json(), encoding="utf-8")
    command = [
        sys.executable,
        "-X",
        "utf8",
        "-m",
        "pit_haf.research.calendar_audit",
        "--root",
        str(tmp_path),
    ]
    built = subprocess.run(
        [
            *command,
            "--build",
            "--config",
            str(config),
            "--sources-run",
            source.name,
            "--market-run",
            market.name,
        ],
        capture_output=True,
        check=True,
    )
    saved = json.loads(built.stdout)
    assert saved["date_sets_match"] and saved["eligible_for_execution"] is False
    replayed = subprocess.run(
        [*command, "--replay", saved["path"]], capture_output=True, check=True
    )
    assert json.loads(replayed.stdout) == saved
    rejected = subprocess.run(
        [*command, "--replay", saved["path"], "--sources-run", source.name], capture_output=True
    )
    assert rejected.returncode == 2 and b"omit overrides" in rejected.stderr
