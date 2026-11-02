"""Synthetic vendor fixtures and hand-calculated close comparators, never independent market gold."""

import json
import sys
from datetime import UTC, datetime
from decimal import ROUND_UP, Context, localcontext

import pytest

from pit_haf.data import index_prices as prices
from pit_haf.data.hub import file_sha
from pit_haf.data.market_prices import CapturePlan
from pit_haf.llm.ollama import write_json
from pit_haf.research import index_crosscheck as runner
from pit_haf.research import market_snapshot

DAYS = ["2024-01-02", "2024-01-03", "2024-01-04"]


def plan():
    return prices.IndexPlan(
        protocol="market_index_crosscheck_v0.1",
        start="2024-01-01",
        end="2024-01-07",
        symbol="VNINDEX",
        count_back=1100,
    )


def rows():
    return [
        {"t": d + " 07:00", "o": 10, "h": 13, "l": 8, "c": c, "v": 100}
        for d, c in zip(DAYS, [10, 12, 9])
    ]


def left_payload(data=None):
    return json.dumps({"symbol": "VNINDEX", "data_day": rows() if data is None else data}).encode()


def vector(data=None):
    data = rows() if data is None else data
    return {
        "symbol": "VNINDEX",
        **{k: [r[k] for r in data] for k in ("o", "h", "l", "c", "v")},
        "t": [
            str(int(datetime.fromisoformat(r["t"][:10]).replace(tzinfo=UTC).timestamp()))
            for r in data
        ],
    }


def right_payload(data=None):
    return json.dumps([vector(data)]).encode()


def compare(left=None, right=None):
    p = plan()
    return prices.compare(
        p, prices.kbs(left_payload(left), p), prices.vietcap(right_payload(right), p)
    )


def test_close_comparator_hand_calculation_does_not_validate_execution_or_make_orders():
    result = compare()
    comparator = result["close_comparator"]
    assert result["close_comparator_ready"] is True
    assert (
        result["eligible_for_execution"]
        is result["historical_availability_validated"]
        is result["independent_gold"]
        is False
    )
    assert (
        comparator["observed_close_to_close_return"] == "-0.1"
        and comparator["max_drawdown"] == "0.25"
    )
    assert [r["base_100"] for r in comparator["curve"]] == ["100", "120", "90"]
    assert [r["close_to_previous_return"] for r in comparator["curve"]] == [None, "0.2", "-0.25"]
    assert comparator["orders_generated"] == 0 and comparator["tradable"] is False
    assert comparator["fees"] is comparator["macro_f1"] is None


def test_ohlc_contradictions_and_raw_volume_differences_stay_visible_without_repair():
    left, right = rows(), rows()
    left[0].update(h=9)
    right[1].update(l=13, v=110)
    result = compare(left, right)
    assert result["close_comparator_ready"] is True
    assert result["field_statistics"]["close"]["exact_matches"] == 3
    assert result["field_statistics"]["high"]["differences"] == 1
    assert result["field_statistics"]["low"]["max_absolute_difference"] == "5"
    assert result["field_statistics"]["volume"]["differences"] == 1
    assert [s["ohlc_issues"][0]["session_date"] for s in result["sources"]] == DAYS[:2]
    assert left[0]["h"] == 9 and right[1]["l"] == 13


@pytest.mark.parametrize(
    "change", ["close_disagreement", "micro_disagreement", "missing_day", "single_day"]
)
def test_conflicting_closes_or_date_sets_cannot_be_silently_intersected(change):
    left, right = rows(), rows()
    if change == "close_disagreement":
        right[1]["c"] = 11
    if change == "micro_disagreement":
        right[1]["c"] = 12.000001
    if change == "missing_day":
        right.pop(1)
    if change == "single_day":
        left, right = left[:1], right[:1]
    report = compare(left, right)
    assert report["close_comparator_ready"] is False and report["close_comparator"] is None
    assert report["close_comparator_blockers"]


def test_request_cutoff_is_timezone_explicit_and_window_filter_preserves_source_rows():
    p = plan()
    body = prices.request_body(p)
    assert body == {
        "timeFrame": "ONE_DAY",
        "symbols": ["VNINDEX"],
        "countBack": 1100,
        "to": int(datetime(2024, 1, 8, tzinfo=UTC).timestamp()) - 7 * 3600,
    }
    data = rows() + [{**rows()[0], "t": "2024-01-08 07:00"}]
    parsed = prices.vietcap(right_payload(data), p)
    assert parsed["raw_rows"] == 4 and len(parsed["observations"]) == 3
    assert parsed["outside_range_dates"] == ["2024-01-08"]
    assert all(row["available_at"] is None for row in parsed["observations"])


@pytest.mark.parametrize(
    "change",
    [
        "symbol",
        "multiple_symbols",
        "array_length",
        "duplicate_date",
        "milliseconds",
        "numeric_epoch",
        "missing_field",
        "boolean_price",
        "negative_price",
        "excess_precision",
        "boolean_volume",
        "fractional_volume",
        "NaN",
        "empty",
        "duplicate_json",
    ],
)
def test_malformed_vietcap_response_is_rejected_without_guessing_or_filling(change):
    p = plan()
    v = vector()
    data = [v]
    if change == "symbol":
        v["symbol"] = "FPT"
    if change == "multiple_symbols":
        data.append(dict(v))
    if change == "array_length":
        v["c"].pop()
    if change == "duplicate_date":
        v["t"][1] = v["t"][0]
    if change == "milliseconds":
        v["t"][0] += "000"
    if change == "numeric_epoch":
        v["t"][0] = int(v["t"][0])
    if change == "missing_field":
        del v["o"]
    if change == "boolean_price":
        v["c"][0] = True
    if change == "negative_price":
        v["l"][0] = -1
    if change == "excess_precision":
        v["c"][0] = 10.1234567
    if change == "boolean_volume":
        v["v"][0] = True
    if change == "fractional_volume":
        v["v"][0] = 0.1
    if change == "NaN":
        v["c"][0] = float("nan")
    if change == "empty":
        data = []
    raw = json.dumps(data).encode()
    if change == "duplicate_json":
        raw = b'[{"symbol":"VNINDEX","symbol":"VNINDEX"}]'
    with pytest.raises(ValueError):
        prices.vietcap(raw, p)


def test_vendor_identity_units_and_decimal_context_are_checked():
    p = plan()
    left = prices.kbs(left_payload(), p)
    right = prices.vietcap(right_payload(), p)
    expected = prices.compare(p, left, right)
    with localcontext(Context(prec=6, rounding=ROUND_UP)):
        assert prices.compare(p, left, right) == expected
    right["price_unit"] = "VND"
    with pytest.raises(ValueError, match="identity and point units"):
        prices.compare(p, left, right)


@pytest.fixture
def kbs_snapshot(tmp_path):
    p = CapturePlan(
        protocol="market_price_snapshot_v0.1",
        start=plan().start,
        end=plan().end,
        instruments=[{"symbol": "VNINDEX", "asset_type": "index"}],
    )

    def fake(url, hosts, **kwargs):
        return left_payload(), {
            "source_url": url,
            "final_url": url,
            "http_status": 200,
            "retrieved_at": "2026-11-02T00:00:00+00:00",
            "headers": {},
        }

    return market_snapshot.capture(tmp_path, p.model_dump_json().encode(), fetcher=fake)[0]


def fetcher(body):
    assert json.loads(body) == prices.request_body(plan())
    return right_payload(), {
        "source_url": prices.VIETCAP_URL,
        "final_url": prices.VIETCAP_URL,
        "http_status": 200,
        "retrieved_at": "2026-11-02T00:00:00+00:00",
        "content_type": "application/json",
    }


def save(tmp_path, kbs_snapshot, **kwargs):
    return runner.capture(
        tmp_path,
        plan().model_dump_json().encode(),
        kbs_snapshot.name,
        fetcher=kwargs.pop("fetcher", fetcher),
        **kwargs,
    )


def test_snapshot_keeps_raw_bytes_and_dependency_binding_and_replays_without_network(
    tmp_path, kbs_snapshot, monkeypatch
):
    before = file_sha(kbs_snapshot / "integrity.json")
    folder, report = save(tmp_path, kbs_snapshot)
    assert (folder / "response.raw").read_bytes() == right_payload()
    monkeypatch.setattr(runner, "fetch_chart", lambda *a: pytest.fail("Replay sent a chart query"))
    assert runner.replay(tmp_path, folder) == report
    assert file_sha(kbs_snapshot / "integrity.json") == before
    assert len((folder / "close_comparator.csv").read_text().splitlines()) == 4
    manifest = json.loads((folder / "manifest.json").read_bytes())
    assert manifest["KBS_source_binding"]["response_sha256"] == file_sha(
        kbs_snapshot / "VNINDEX/response.raw"
    )


@pytest.mark.parametrize("change", ["outage", "invalid_json", "redirect_metadata"])
def test_failed_source_is_persisted_once_without_fabricated_comparator(
    tmp_path, kbs_snapshot, change
):
    calls = []

    def bad(body):
        calls.append(body)
        if change == "outage":
            raise OSError("synthetic outage")
        raw, meta = fetcher(body)
        if change == "invalid_json":
            raw = b"<html>broken source</html>"
        if change == "redirect_metadata":
            meta["final_url"] = "https://unexpected.example/"
        return raw, meta

    folder, report = save(tmp_path, kbs_snapshot, fetcher=bad)
    assert (
        len(calls) == 1
        and report["close_comparator"] is None
        and report["close_comparator_ready"] is False
    )
    assert len((folder / "close_comparator.csv").read_text().splitlines()) == 1
    assert runner.replay(tmp_path, folder) == report


def reseal(folder):
    write_json(
        folder / "integrity.json",
        {
            "files": {
                p.name: file_sha(p)
                for p in folder.iterdir()
                if p.is_file() and p.name != "integrity.json"
            }
        },
    )


@pytest.mark.parametrize(
    "change",
    [
        "raw",
        "report_resealed",
        "csv_resealed",
        "binding_resealed",
        "request_resealed",
        "normalized_resealed",
        "missing_entry",
        "source_changed",
    ],
)
def test_replay_rejects_corruption_or_resealed_inconsistent_sources_and_outputs(
    tmp_path, kbs_snapshot, change
):
    folder, _ = save(tmp_path, kbs_snapshot)
    if change == "raw":
        (folder / "response.raw").write_bytes(b"corrupt")
    if change == "report_resealed":
        data = json.loads((folder / "comparison.json").read_bytes())
        data["eligible_for_execution"] = True
        write_json(folder / "comparison.json", data)
    if change == "csv_resealed":
        (folder / "close_comparator.csv").write_bytes(b"forged\n")
    if change == "binding_resealed":
        data = json.loads((folder / "manifest.json").read_bytes())
        data["KBS_source_binding"]["response_sha256"] = "0" * 64
        write_json(folder / "manifest.json", data)
    if change == "request_resealed":
        data = json.loads((folder / "request.json").read_bytes())
        data["countBack"] = 1
        write_json(folder / "request.json", data)
        manifest = json.loads((folder / "manifest.json").read_bytes())
        manifest["request_sha256"] = file_sha(folder / "request.json")
        write_json(folder / "manifest.json", manifest)
    if change == "normalized_resealed":
        data = json.loads((folder / "normalized.json").read_bytes())
        data["KBS"]["observations"][0]["close"] = "1"
        write_json(folder / "normalized.json", data)
    if change == "source_changed":
        (kbs_snapshot / "VNINDEX/response.raw").write_bytes(b"changed dependency")
    if change != "raw":
        reseal(folder)
    if change == "missing_entry":
        data = json.loads((folder / "integrity.json").read_bytes())
        del data["files"]["response.raw"]
        write_json(folder / "integrity.json", data)
    with pytest.raises(ValueError, match="differ"):
        runner.replay(tmp_path, folder)


def test_invalid_source_or_window_is_rejected_before_chart_request(tmp_path, kbs_snapshot):
    for run in ("../escape", "20260101T000000Z-aaaaaaaa"):
        with pytest.raises((ValueError, FileNotFoundError)):
            runner.capture(
                tmp_path,
                plan().model_dump_json().encode(),
                run,
                fetcher=lambda *a: pytest.fail("Invalid source queried chart"),
            )
    data = plan().model_dump()
    data["start"] = "2024-01-02"
    with pytest.raises(ValueError, match="requested window"):
        runner.capture(
            tmp_path,
            json.dumps(data).encode(),
            kbs_snapshot.name,
            fetcher=lambda *a: pytest.fail("Mismatched window queried chart"),
        )
    assert not (tmp_path / "outputs/index-crosschecks").exists()


@pytest.mark.parametrize("change", ["status", "partial", "size", "truncated", "redirect"])
def test_public_chart_transport_enforces_status_size_length_and_no_redirect(monkeypatch, change):
    class Response:
        status = 200
        url = prices.VIETCAP_URL
        headers = {"Content-Type": "application/json", "Content-Length": "2"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit):
            assert limit == 8 * 1024 * 1024 + 1
            return b"[" if change == "truncated" else b"[]"

    response = Response()
    if change == "status":
        response.status = 206
    if change == "partial":
        response.headers = {"Content-Range": "bytes 0-1/4"}
    if change == "size":
        response.headers = {"Content-Length": str(9 * 1024 * 1024)}

    class Opener:
        def open(self, request, timeout):
            assert (
                request.full_url == prices.VIETCAP_URL
                and request.method == "POST"
                and timeout == 30
            )
            if change == "redirect":
                runner.NoChartRedirect().redirect_request(None, None, None, None, None, None)
            return response

    monkeypatch.setattr(runner.urllib.request, "build_opener", lambda *a: Opener())
    with pytest.raises(ValueError):
        runner.fetch_chart(b"{}")


def test_replay_cli_displays_close_only_readiness_and_rejects_overrides(
    tmp_path, kbs_snapshot, monkeypatch, capsys
):
    folder, _ = save(tmp_path, kbs_snapshot)
    monkeypatch.setattr(
        sys, "argv", ["index-crosscheck", "--root", str(tmp_path), "--replay", str(folder)]
    )
    assert runner.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["close_comparator_ready"] is True and result["eligible_for_execution"] is False
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "index-crosscheck",
            "--root",
            str(tmp_path),
            "--replay",
            str(folder),
            "--kbs-run",
            kbs_snapshot.name,
        ],
    )
    with pytest.raises(SystemExit) as exc:
        runner.main()
    assert exc.value.code == 2
