"""Hand-computed entitlements and synthetic notice provenance, no human gold."""

import hashlib
import json
import subprocess
import sys
from decimal import ROUND_UP, Context, localcontext
from io import BytesIO

import pytest
from pypdf import PdfWriter

from pit_haf.backtest.corporate_ledger import CorporateLedger, Entitlement, demo
from pit_haf.data.corporate_actions import Book, audit, parse_token
from pit_haf.data.hub import file_sha
from pit_haf.data.session_calendar import notice_text
from pit_haf.llm.ollama import write_json
from pit_haf.research import corporate_runner as runner
from pit_haf.research.market_snapshot import capture


def instruction(**updates):
    return Entitlement.model_validate(
        {
            "kind": "synthetic_entitlement_instruction",
            "event_id": "synthetic_action",
            "symbol": "SYN_A",
            "economic_at": "2024-01-03T09:00:00+07:00",
            "cash_per_share": "1000",
            "cash_tax_bps": 500,
            "cash_available_at": "2024-01-05T13:00:00+07:00",
            "ratio_old": 20,
            "ratio_new": 3,
            "shares_available_at": "2024-01-10T09:00:00+07:00",
            "fraction_policy": "floor_holder_total_discard_fraction",
            **updates,
        }
    )


def test_cash_tax_and_holder_total_rounding_match_hand_calculation():
    ledger = CorporateLedger()
    event = instruction()
    ledger.recognize(event, 21, at=event.economic_at)
    state = ledger.state()
    recognition = state["journal"][0]
    assert recognition["gross_cash"] == "21000" and recognition["cash_tax"] == "1050"
    assert recognition["net_cash"] == "19950" and recognition["new_shares"] == 3
    assert (
        recognition["discarded_fraction_numerator"],
        recognition["discarded_fraction_denominator"],
    ) == (3, 20)
    assert ledger.pending_value({"SYN_A": "100"}) == {
        "net_cash_receivable": "19950",
        "pending_stock_value": "300",
        "total_pending_value": "20250",
    }
    assert state["receipts"] == []
    released = ledger.release("2024-01-05T13:00:00+07:00")
    assert len(released["receipts"]) == 1 and released["receipts"][0]["amount"] == "19950"
    assert len(released["pending"]) == 1
    final = ledger.release("2024-01-10T09:00:00+07:00")
    assert final["pending"] == [] and final["receipts"][-1]["quantity"] == 3
    assert ledger.pending_value({})["total_pending_value"] == "0"


def test_price_drop_for_cash_and_bonus_does_not_create_fake_loss_or_double_credit():
    result = demo()
    assert result["initial_value"] == "2320"
    assert {r["total_value_with_base_position"] for r in result["checkpoints"]} == {"2320"}
    assert [r["tradable_shares"] for r in result["checkpoints"]] == [20, 20, 20, 23]
    assert [r["spendable_dividend_cash"] for r in result["checkpoints"]] == ["0", "0", "20", "20"]
    assert result["assumptions"]["automatic_price_adjustment"] is False
    assert result["research_result"] is False


def test_microsecond_boundary_and_repeat_release_do_not_unlock_early_or_duplicate():
    ledger = CorporateLedger()
    event = instruction()
    ledger.recognize(event, 20, at=event.economic_at)
    assert not ledger.release("2024-01-05T12:59:59.999999+07:00")["receipts"]
    first = ledger.release("2024-01-05T06:00:00Z")
    assert len(first["receipts"]) == 1
    assert ledger.release("2024-01-05T13:00:00+07:00")["receipts"] == first["receipts"]
    assert not any(r["kind"] == "stock" for r in first["receipts"])


def test_duplicate_backward_or_invalid_recognition_does_not_mutate_state():
    ledger = CorporateLedger()
    event = instruction()
    ledger.recognize(event, 20, at=event.economic_at)
    before = ledger.state()
    for quantity, at, ev in [
        (20, event.economic_at, event),
        (True, event.economic_at, event),
        (-1, event.economic_at, event),
        (20, "2024-01-02T09:00:00+07:00", instruction(event_id="other")),
    ]:
        with pytest.raises(ValueError):
            ledger.recognize(ev, quantity, at=at)
        assert ledger.state() == before
    with pytest.raises(ValueError):
        ledger.release("2024-01-02T09:00:00+07:00")
    assert ledger.state() == before


def test_zero_holder_and_full_tax_do_not_invent_receipts():
    ledger = CorporateLedger()
    event = instruction()
    ledger.recognize(event, 0, at=event.economic_at)
    assert ledger.release("2024-01-11T09:00:00+07:00")["receipts"] == []
    taxed = CorporateLedger()
    event = instruction(cash_tax_bps=10000, ratio_new=0, shares_available_at=None)
    taxed.recognize(event, 20, at=event.economic_at)
    assert taxed.state()["journal"][0]["cash_tax"] == "20000" and taxed.state()["pending"] == []


def test_immediate_stock_only_receipts_are_copies_and_multiple_events_use_declared_quantity():
    ledger = CorporateLedger()
    event = instruction(
        cash_per_share="0",
        cash_available_at=None,
        cash_tax_bps=0,
        shares_available_at="2024-01-03T09:00:00+07:00",
    )
    ledger.recognize(event, 20, at=event.economic_at)
    copy = ledger.state()
    copy["receipts"][0]["quantity"] = 999
    assert ledger.state()["receipts"][0]["quantity"] == 3
    second = instruction(event_id="second", economic_at="2024-01-04T09:00:00+07:00")
    ledger.recognize(second, 23, at=second.economic_at)
    assert ledger.state()["journal"][-1]["eligible_quantity"] == 23


@pytest.mark.parametrize(
    "updates",
    [
        {"cash_per_share": "5%"},
        {"ratio_old": 0},
        {"ratio_new": True},
        {"cash_tax_bps": -1},
        {"cash_available_at": None},
        {"shares_available_at": None},
        {"cash_available_at": "2024-01-02T09:00:00+07:00"},
        {"economic_at": "2024-01-03T09:00:00"},
        {"fraction_policy": "cash_in_lieu"},
        {"kind": "real_verified_event"},
    ],
)
def test_unsupported_or_ambiguous_entitlement_instructions_fail(updates):
    with pytest.raises(ValueError):
        instruction(**updates)


@pytest.mark.parametrize(
    "marks",
    [
        {},
        {"SYN_A": 0},
        {"SYN_A": "NaN"},
        {"SYN_A": "1e3"},
        {"SYN_A": "0"},
        {"SYN_A": "bad"},
        {"SYN_B": "100"},
    ],
)
def test_invalid_pending_share_marks_fail(marks):
    ledger = CorporateLedger()
    event = instruction()
    ledger.recognize(event, 20, at=event.economic_at)
    with pytest.raises(ValueError):
        ledger.pending_value(marks)


def test_decimal_context_does_not_change_entitlements_or_demo():
    expected = demo()
    with localcontext(Context(prec=3, rounding=ROUND_UP)):
        assert demo() == expected
        ledger = CorporateLedger()
        event = instruction()
        ledger.recognize(event, 21, at=event.economic_at)
        assert ledger.pending_value({"SYN_A": "100"})["total_pending_value"] == "20250"


@pytest.mark.parametrize("basis", ["unknown", "vendor_back_adjusted", "verified_adjusted"])
def test_adjusted_or_unknown_price_basis_cannot_enter_entitlement_ledger(basis):
    with pytest.raises(ValueError, match="unadjusted"):
        CorporateLedger(price_basis=basis)


def source_book():
    raw = {
        "fixture_rights": b'<div class="content-category">AAA record 02/01/2024 cash 1.000 pay 05/01/2024 ratio 20:3.</div>',
        "fixture_trade": b'<div class="content-category">AAA tradable 10/01/2024 record 02/01/2024.</div>',
    }
    sources = []
    for i, (key, value) in enumerate(raw.items()):
        sources.append(
            {
                "id": key,
                "url": f"https://vsdc.vn/vi/ad/{123 + i}",
                "raw_sha256": hashlib.sha256(value).hexdigest(),
                "body_sha256": hashlib.sha256(notice_text(value).encode()).hexdigest(),
                "anchors": ["AAA"],
            }
        )

    def proof(field, source, token):
        return {
            "field": field,
            "source_id": source,
            "start": notice_text(raw[source]).index(token),
            "token": token,
        }

    proofs = [proof("symbol", s, "AAA") for s in raw] + [
        proof("record_date", "fixture_rights", "02/01/2024"),
        proof("cash_per_share", "fixture_rights", "1.000"),
        proof("cash_payment_date", "fixture_rights", "05/01/2024"),
        proof("stock_ratio", "fixture_rights", "20:3"),
        proof("stock_tradable_date", "fixture_trade", "10/01/2024"),
        proof("tradable_record_date", "fixture_trade", "02/01/2024"),
    ]
    book = Book.model_validate(
        {
            "protocol": "corporate_action_development_v0.1",
            "coverage": "selected_examples_only_not_complete_history",
            "audit_start": "2024-01-01",
            "audit_end": "2024-01-12",
            "sources": sources,
            "events": [
                {
                    "id": "fixture_distribution",
                    "symbol": "AAA",
                    "record_date": "2024-01-02",
                    "ex_date": None,
                    "cash_per_share": "1000",
                    "cash_payment_date": "2024-01-05",
                    "ratio_old": 20,
                    "ratio_new": 3,
                    "stock_tradable_date": "2024-01-10",
                    "proofs": proofs,
                }
            ],
        }
    )
    return book, raw


def normalized():
    return [
        {
            "symbol": "AAA",
            "normalized": {
                "adjustment_status": "unknown",
                "bars": [{"session_date": "2024-01-02"}, {"session_date": "2024-01-10"}],
            },
        }
    ]


def test_source_audit_keeps_record_payment_and_trading_distinct_with_unknown_ex_date():
    book, raw = source_book()
    result = audit(book, raw, normalized())
    row = result["events"][0]
    assert row["calendar_days_record_to_stock_trading"] == 8
    assert row["cash_payment_date"] == "2024-01-05" and row["stock_tradable_date"] == "2024-01-10"
    assert row["ex_date"] is row["availability_at"] is row["entitlement_quantity"] is None
    assert row["snapshot_adjustment_status"] == "unknown" and row["record_date_in_price_snapshot"]
    assert row["blocking_reasons"] and result["automatic_price_adjustments"] == 0
    assert result["eligible_for_execution"] is result["independent_gold"] is False


@pytest.mark.parametrize(
    "change",
    [
        "offset",
        "token",
        "ratio",
        "cash",
        "record",
        "symbol",
        "missing_proof",
        "source_hash",
        "ex_date",
        "duplicate",
    ],
)
def test_wrong_identity_or_field_bindings_are_rejected(change):
    book, raw = source_book()
    data = book.model_dump()
    event = data["events"][0]
    if change == "offset":
        event["proofs"][2]["start"] += 1
    elif change == "token":
        event["proofs"][2]["token"] = "03/01/2024"
    elif change == "ratio":
        event["ratio_old"], event["ratio_new"] = 3, 20
    elif change == "cash":
        event["cash_per_share"] = "10000"
    elif change == "record":
        event["record_date"] = "2024-01-03"
    elif change == "symbol":
        event["symbol"] = "AAB"
    elif change == "missing_proof":
        event["proofs"].pop(0)
    elif change == "source_hash":
        raw["fixture_rights"] += b" "
    elif change == "ex_date":
        event["ex_date"] = "2024-01-01"
    else:
        data["events"].append(event | {"id": "another_id"})
    with pytest.raises(ValueError):
        audit(Book.model_validate(data), raw, normalized())


def test_ratio_and_cash_tokens_are_unambiguous_and_missing_prices_stay_unavailable():
    assert parse_token("stock_ratio", "1.000 : 181") == (1000, 181)
    assert parse_token("cash_per_share", "1.000") == "1000"
    for field, token in [
        ("stock_ratio", "15%"),
        ("cash_per_share", "10%"),
        ("record_date", "2024-01-02"),
    ]:
        with pytest.raises(ValueError):
            parse_token(field, token)
    book, raw = source_book()
    row = audit(book, raw, [])["events"][0]
    assert (
        row["snapshot_adjustment_status"] == "unavailable"
        and not row["record_date_in_price_snapshot"]
    )


def conflict_book():
    book, raw = source_book()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buffer = BytesIO()
    writer.write(buffer)
    pdf = buffer.getvalue()
    digest = hashlib.sha256(pdf).hexdigest()
    data = book.model_dump()
    data["disagreements"] = [
        {
            "event_id": "fixture_distribution",
            "issuer_symbol": "AAA",
            "other_record_date": "2024-01-03",
            "source_url": "https://file.hoaphat.com.vn/synthetic-fixture.pdf",
            "content_hash": digest,
            "pdf_page": 1,
            "basis": "assistant_visual_read_of_original_pdf_page",
            "independent_confirmation": False,
        }
    ]
    return data, raw, digest, pdf


def test_pdf_disagreement_is_preserved_without_overwriting_notice_date():
    data, raw, digest, pdf = conflict_book()
    result = audit(Book.model_validate(data), raw, normalized(), external_pdfs={digest: pdf})
    row = result["events"][0]
    assert (
        row["record_date"] == "2024-01-02"
        and row["record_date_status"] == "unresolved_disagreement"
    )
    assert "record_date_disagrees_with_issuer_report" in row["blocking_reasons"]
    assert result["cross_source_disagreements"][0]["other_record_date"] == "2024-01-03"
    assert not result["eligible_for_execution"]


@pytest.mark.parametrize("change", ["missing_pdf", "pdf_hash", "page", "issuer", "same_date"])
def test_pdf_disagreement_dependency_and_identity_are_checked(change):
    data, raw, digest, pdf = conflict_book()
    external = {digest: pdf}
    if change == "missing_pdf":
        external = {}
    elif change == "pdf_hash":
        external[digest] = b"changed"
    elif change == "page":
        data["disagreements"][0]["pdf_page"] = 2
    elif change == "issuer":
        data["disagreements"][0]["issuer_symbol"] = "AAB"
    else:
        data["disagreements"][0]["other_record_date"] = "2024-01-02"
    with pytest.raises(ValueError):
        audit(Book.model_validate(data), raw, normalized(), external_pdfs=external)


def reseal(folder):
    write_json(
        folder / "integrity.json",
        {"files": {p.name: file_sha(p) for p in folder.iterdir() if p.name != "integrity.json"}},
    )


def dependencies(root):
    book, raw = source_book()
    source = root / "outputs/calendar-sources/20261106T000000Z-abcdef12"
    source.mkdir(parents=True)
    metadata = []
    for s in book.sources:
        payload = raw[s.id]
        (source / (s.id + ".raw")).write_bytes(payload)
        meta = {
            "id": s.id,
            "url": s.url,
            "status": "captured",
            "http_status": 200,
            "captured_at": "2026-11-06T00:00:00Z",
            "certificate_verification_disabled": False,
            "authentication_used": False,
            "automatic_retries": 0,
            "sha256": s.raw_sha256,
            "bytes": len(payload),
        }
        write_json(source / (s.id + ".json"), meta)
        metadata.append(meta)
    write_json(
        source / "source_plan.json",
        {
            "protocol": "calendar_source_capture_v0.1",
            "sources": [{"id": s.id, "url": s.url} for s in book.sources],
        },
    )
    write_json(
        source / "manifest.json",
        {"protocol": "calendar_source_capture_v0.1", "research_result": False, "sources": metadata},
    )
    (source / "capture-calendar-sources.ps1").write_bytes(b"# synthetic fixture; not executed\n")
    reseal(source)
    plan = {
        "protocol": "market_price_snapshot_v0.1",
        "start": book.audit_start,
        "end": book.audit_end,
        "instruments": [{"symbol": "AAA", "asset_type": "equity"}],
    }

    def fetcher(url, *args, **kwargs):
        rows = [
            {"t": d + " 07:00", "o": 10, "h": 11, "l": 9, "c": 10, "v": 100}
            for d in ["2024-01-02", "2024-01-10"]
        ]
        return json.dumps({"symbol": "AAA", "data_day": rows}).encode(), {
            "source_url": url,
            "final_url": url,
            "http_status": 200,
            "retrieved_at": "2026-11-06T00:00:00Z",
            "headers": {},
        }

    market, _ = capture(root, json.dumps(plan).encode(), fetcher=fetcher)
    return book, source, market


def test_real_source_audit_and_demo_remain_separate_and_replay_offline(tmp_path):
    book, source, market = dependencies(tmp_path)
    raw = b" \n" + book.model_dump_json().encode()
    folder, result = runner.run(
        tmp_path, mode="audit", book_bytes=raw, sources_run=source.name, market_run=market.name
    )
    assert runner.replay(tmp_path, folder) == result and (folder / "book.json").read_bytes() == raw
    assert (
        result["orders_generated"] == 0
        and len((folder / "receipts.csv").read_text().splitlines()) == 1
    )
    synthetic, result = runner.run(tmp_path, mode="demo")
    assert runner.replay(tmp_path, synthetic) == result
    assert (
        len((synthetic / "events.csv").read_text().splitlines()) == 1
        and len(result["checkpoints"]) == 4
    )
    assert not (tmp_path / "data").exists()
    with pytest.raises(ValueError):
        runner.run(tmp_path, mode="demo", book_bytes=raw)
    with pytest.raises(ValueError):
        runner.replay(tmp_path, tmp_path)


@pytest.mark.parametrize(
    "change", ["result", "csv", "provenance", "source", "source_resealed", "market", "extra_file"]
)
def test_artifact_and_dependency_tampering_cannot_replay(tmp_path, change):
    book, source, market = dependencies(tmp_path)
    folder, _ = runner.run(
        tmp_path,
        mode="audit",
        book_bytes=book.model_dump_json().encode(),
        sources_run=source.name,
        market_run=market.name,
    )
    if change == "result":
        data = json.loads((folder / "result.json").read_bytes())
        data["events"] = []
        write_json(folder / "result.json", data)
    elif change == "csv":
        (folder / "events.csv").write_bytes(b"forged\n")
    elif change == "provenance":
        data = json.loads((folder / "manifest.json").read_bytes())
        data["research_result"] = True
        write_json(folder / "manifest.json", data)
    elif change in {"source", "source_resealed"}:
        (source / "fixture_rights.raw").write_bytes(b"changed")
        if change == "source_resealed":
            reseal(source)
    elif change == "market":
        (market / "AAA/response.raw").write_bytes(b"{}")
    else:
        (folder / "unexpected.txt").write_bytes(b"extra")
    reseal(folder)
    with pytest.raises(ValueError, match="differ|Missing"):
        runner.replay(tmp_path, folder)


def test_cli_demo_and_replay_reject_overrides(tmp_path):
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        "-m",
        "pit_haf.research.corporate_runner",
        "--root",
        str(tmp_path),
    ]
    built = subprocess.run([*cmd, "--demo"], capture_output=True, check=True)
    saved = json.loads(built.stdout)
    assert (
        saved["kind"] == "synthetic_corporate_ledger_diagnostic"
        and saved["research_result"] is False
    )
    replayed = subprocess.run([*cmd, "--replay", saved["path"]], capture_output=True, check=True)
    assert json.loads(replayed.stdout) == saved
    refused = subprocess.run(
        [*cmd, "--replay", saved["path"], "--market-run", "override"], capture_output=True
    )
    assert refused.returncode == 2 and b"omit overrides" in refused.stderr
