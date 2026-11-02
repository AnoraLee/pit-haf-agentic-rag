"""Offline price-source fixtures only; no prices here are independent market gold."""

import json
import sys
from copy import deepcopy
from urllib.parse import urlsplit

import pytest

from pit_haf.data.hub import file_sha
from pit_haf.data.market_prices import CapturePlan, audit, decode, source_url
from pit_haf.llm.ollama import write_json
from pit_haf.research import market_snapshot as snapshots


def plan(**updates):
    return CapturePlan.model_validate(
        {
            "protocol": "market_price_snapshot_v0.1",
            "start": "2024-01-01",
            "end": "2024-01-07",
            "instruments": [
                {"symbol": "AAA", "asset_type": "equity"},
                {"symbol": "VNINDEX", "asset_type": "index"},
            ],
            **updates,
        }
    )


def row(day="2024-01-02", **updates):
    return {
        "t": day + " 07:00",
        "o": 62766,
        "h": 63028,
        "l": 62700,
        "c": 62831,
        "v": 1381500,
        **updates,
    }


def payload(symbol="AAA", rows=None):
    return json.dumps(
        {"symbol": symbol, "data_day": rows if rows is not None else [row()]}
    ).encode()


def fetcher(url, hosts, **kwargs):
    symbol = urlsplit(url).path.split("/")[-2]
    assert hosts == {"kbbuddywts.kbsec.com.vn"} and kwargs["max_bytes"] == 8 * 1024 * 1024
    return payload(symbol), {
        "source_url": url,
        "final_url": url,
        "http_status": 200,
        "retrieved_at": "2026-11-02T00:00:00+00:00",
        "headers": {
            "Content-Type": "application/json",
            "Set-Cookie": "test-only-private-cookie",
            "Authorization": "test-only-private-header",
        },
    }


def saved(tmp_path, **kwargs):
    return snapshots.capture(
        tmp_path,
        plan().model_dump_json().encode(),
        fetcher=kwargs.pop("fetcher", fetcher),
        **kwargs,
    )


def test_raw_vnd_and_index_points_stay_separate_without_binary_rounding_or_inferred_availability():
    p = plan()
    data = payload(
        rows=[row(o=62766.123456, h=63028.654321, l=62700.123456, c=62831.123456, v=100.0)]
    )
    n = decode(data, p, p.instruments[0])
    assert n["price_unit"] == "VND" and n["bars"][0]["open"] == "62766.123456"
    assert n["bars"][0]["volume"] == 100 and n["bars"][0]["available_at"] is None
    assert n["bars"][0]["source_time"] == "2024-01-02 07:00"
    assert n["adjustment_status"] == "unknown" and n["historical_availability_validated"] is False
    index = decode(
        payload("VNINDEX", [row(o=1200.1, h=1205, l=1190, c=1201.2)]), p, p.instruments[1]
    )
    assert index["price_unit"] == "points" and index["bars"][0]["close"] == "1201.2"
    assert "/stocks/AAA/data_day?sdate=01-01-2024&edate=07-01-2024" in source_url(
        p, p.instruments[0]
    )
    assert "/index/VNINDEX/data_day" in source_url(p, p.instruments[1])


def test_sort_filter_and_zero_volume_preserve_missing_days_without_filling_or_weekend_invention():
    p = plan()
    rows = [row("2024-01-06", v=0), row("2024-01-04"), row("2024-01-02"), row("2024-01-08")]
    n = decode(payload(rows=rows), p, p.instruments[0])
    assert [b["session_date"] for b in n["bars"]] == ["2024-01-02", "2024-01-04", "2024-01-06"]
    assert n["outside_range_dates"] == ["2024-01-08"]
    assert n["weekend_dates"] == n["zero_volume_dates"] == ["2024-01-06"]


@pytest.mark.parametrize(
    "change",
    [
        "wrong_symbol",
        "empty",
        "missing",
        "duplicate",
        "bad_date",
        "out_of_range_only",
        "boolean_price",
        "nan",
        "boolean_volume",
        "fractional_volume",
        "negative_volume",
        "invalid_ohlc",
        "tiny_price",
        "huge_price",
        "string_price",
        "ambiguous_time",
        "excess_precision",
        "duplicate_json",
    ],
)
def test_bad_source_rows_fail_without_repairing_numbers_or_dates(change):
    p = plan()
    data = {"symbol": "AAA", "data_day": [row()]}
    r = data["data_day"][0]
    if change == "wrong_symbol":
        data["symbol"] = "HPG"
    if change == "empty":
        data["data_day"] = []
    if change == "missing":
        del r["h"]
    if change == "duplicate":
        data["data_day"].append(deepcopy(r))
    if change == "bad_date":
        r["t"] = "2024-02-30 07:00"
    if change == "out_of_range_only":
        r["t"] = "2024-01-08 07:00"
    if change == "boolean_price":
        r["o"] = True
    if change == "nan":
        r["o"] = float("nan")
    if change == "boolean_volume":
        r["v"] = True
    if change == "fractional_volume":
        r["v"] = 1.1
    if change == "negative_volume":
        r["v"] = -1
    if change == "invalid_ohlc":
        r["h"] = 60000
    if change == "tiny_price":
        r["l"] = 1e-10
    if change == "huge_price":
        r["h"] = 1e100
    if change == "string_price":
        r["o"] = "62766"
    if change == "ambiguous_time":
        r["t"] = "02/01/2024 07:00"
    if change == "excess_precision":
        r["o"] = 62766.1234567
    raw = json.dumps(data).encode()
    if change == "duplicate_json":
        raw = b'{"symbol":"AAA","symbol":"AAA","data_day":[]}'
    with pytest.raises(ValueError):
        decode(raw, p, p.instruments[0])


def test_shared_source_index_alignment_is_a_diagnostic_not_calendar_or_execution_validation():
    p = plan()
    equity = decode(payload(rows=[row(), row("2024-01-04")]), p, p.instruments[0])
    index = decode(
        payload("VNINDEX", [row(), row("2024-01-03"), row("2024-01-04")]), p, p.instruments[1]
    )
    report = audit(
        p,
        [
            {"symbol": "AAA", "normalized": equity, "error": None},
            {"symbol": "VNINDEX", "normalized": index, "error": None},
        ],
    )
    assert report["assets"][0]["missing_vs_observed_index"] == ["2024-01-03"]
    assert (
        report["eligible_for_execution"]
        is report["historical_availability_validated"]
        is report["strategy_returns_computed"]
        is False
    )
    assert report["calendar_basis"].startswith("observed_index_sessions_same_source")


def test_capture_keeps_raw_http_bytes_config_and_readonly_replay_excludes_private_headers(
    tmp_path, monkeypatch
):
    raw_config = b" \n" + plan().model_dump_json().encode() + b"\r\n"
    folder, report = snapshots.capture(tmp_path, raw_config, fetcher=fetcher)
    assert (folder / "config.json").read_bytes() == raw_config
    assert (folder / "AAA/response.raw").read_bytes() == payload()
    http = json.loads((folder / "AAA/http.json").read_bytes())
    assert http["headers"] == {"Content-Type": "application/json"}
    monkeypatch.setattr(
        snapshots, "fetch_public", lambda *a, **kw: pytest.fail("Replay made a request")
    )
    assert snapshots.replay(tmp_path, folder) == report
    assert not (tmp_path / "data").exists()
    assert "AAA,equity,VND" in (folder / "prices.csv").read_text()
    assert "VNINDEX,index,points" in (folder / "prices.csv").read_text()


def test_partial_fetch_and_parse_failures_are_kept_with_raw_bad_json_and_no_fabricated_bars(
    tmp_path,
):
    def partial(url, hosts, **kwargs):
        if "/stocks/" in url:
            raise OSError("synthetic transport outage")
        _, meta = fetcher(url, hosts, **kwargs)
        return b"<html>synthetic broken JSON</html>", meta

    folder, report = saved(tmp_path, fetcher=partial)
    assert report["failed_instruments"] == 2 and report["successful_instruments"] == 0
    assert not (folder / "AAA/response.raw").exists()
    assert (folder / "VNINDEX/response.raw").read_bytes().startswith(b"<html>")
    assert len((folder / "prices.csv").read_text().splitlines()) == 1
    assert snapshots.replay(tmp_path, folder) == report


@pytest.mark.parametrize(
    "change",
    [
        "symbol_path",
        "duplicate_symbol",
        "too_many",
        "bad_window",
        "future_end",
        "fake_verification",
    ],
)
def test_invalid_capture_plan_does_not_make_requests_or_create_output(tmp_path, change):
    data = plan().model_dump()
    if change == "symbol_path":
        data["instruments"][0]["symbol"] = "../AAA"
    if change == "duplicate_symbol":
        data["instruments"][1] = data["instruments"][0]
    if change == "too_many":
        data["instruments"] *= 3
    if change == "bad_window":
        data["start"] = "2010-01-01"
    if change == "future_end":
        data.update(start="2099-01-01", end="2099-01-07")
    if change == "fake_verification":
        data["adjustment_status"] = "verified_unadjusted"
    with pytest.raises(ValueError):
        snapshots.capture(
            tmp_path,
            json.dumps(data).encode(),
            fetcher=lambda *a, **kw: pytest.fail("Invalid plan requested data"),
        )
    assert not (tmp_path / "outputs").exists()


def reseal(folder):
    write_json(
        folder / "integrity.json",
        {
            "files": {
                p.relative_to(folder).as_posix(): file_sha(p)
                for p in folder.rglob("*")
                if p.is_file() and p.name != "integrity.json"
            }
        },
    )


@pytest.mark.parametrize(
    "change",
    [
        "raw",
        "normalized_resealed",
        "quality_resealed",
        "csv_resealed",
        "http_resealed",
        "missing_file",
        "extra_file",
    ],
)
def test_snapshot_recompute_rejects_raw_corruption_and_resealed_derived_outputs(tmp_path, change):
    folder, _ = saved(tmp_path)
    if change == "raw":
        (folder / "AAA/response.raw").write_bytes(b"corrupt")
    if change == "normalized_resealed":
        data = json.loads((folder / "normalized.json").read_bytes())
        data[0]["normalized"]["bars"][0]["close"] = "1"
        write_json(folder / "normalized.json", data)
    if change == "quality_resealed":
        data = json.loads((folder / "quality.json").read_bytes())
        data["eligible_for_execution"] = True
        write_json(folder / "quality.json", data)
    if change == "csv_resealed":
        (folder / "prices.csv").write_bytes(b"forged\n")
    if change == "http_resealed":
        data = json.loads((folder / "AAA/http.json").read_bytes())
        data["source_url"] = "https://untrusted.example/"
        write_json(folder / "AAA/http.json", data)
    if change == "missing_file":
        (folder / "AAA/response.raw").unlink()
    if change == "extra_file":
        (folder / "unexpected.txt").write_text("extra", encoding="utf-8")
    if change != "raw":
        reseal(folder)
    with pytest.raises((ValueError, FileNotFoundError)):
        snapshots.replay(tmp_path, folder)


def test_replay_cli_is_offline_and_forbids_config_override(tmp_path, monkeypatch, capsys):
    folder, _ = saved(tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["market-snapshot", "--root", str(tmp_path), "--replay", str(folder)]
    )
    assert snapshots.main() == 0
    assert json.loads(capsys.readouterr().out)["eligible_for_execution"] is False
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "market-snapshot",
            "--root",
            str(tmp_path),
            "--replay",
            str(folder),
            "--config",
            "other.json",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        snapshots.main()
    assert exc.value.code == 2
