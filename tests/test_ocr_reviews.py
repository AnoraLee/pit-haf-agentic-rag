"""Local review declarations on synthetic OCR only; no real thesis data is labelled."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

import pytest
from test_ocr_cells_v02 import SOURCE, page_fixture

from pit_haf.data import ocr_cells_v02
from pit_haf.data.snapshots import canonical
from pit_haf.llm.ollama import sha256
from pit_haf.research import ocr_reviews as reviews
from pit_haf.research.reviews import ReviewConflict


def view_fixture(*, relative=False):
    page = page_fixture(relative=relative)
    if relative:
        page["words"].append(
            {
                **deepcopy(page["words"][-1]),
                "id": "annual",
                "text": "cho năm tài chính kết thúc ngày 31 tháng 12 năm 2024",
                "bbox_pixels": [50, 190, 700, 205],
            }
        )
    linked = ocr_cells_v02.link_page(page, ocr_cells_v02.POLICY, SOURCE)
    return {
        "ocr_run_id": "20261102T000001Z-aaaaaaaa",
        "ocr_run_seal_sha256": "b" * 64,
        "policy_id": "ocr_cell_links_v0.2",
        "policy_sha256": "c" * 64,
        "header_ocr_run_id": None,
        "header_ocr_seal_sha256": None,
        "source": SOURCE,
        "pages": [linked],
    }


def request(view, *, index=0, **updates):
    candidate = view["pages"][0]["cells"][index]
    bound = reviews.bindings(view)[candidate["candidate_id"]]
    method, year = next(iter(reviews.year_options(candidate).items()))
    fields = candidate["fields"]
    return reviews.OcrReviewInput(
        **(
            {
                "run_id": view["ocr_run_id"],
                "policy_id": view["policy_id"],
                "header_run_id": view.get("header_ocr_run_id"),
                "candidate_id": candidate["candidate_id"],
                "binding_sha256": bound["binding_sha256"],
                "status": "confirmed",
                "reviewer": "Synthetic fixture operator",
                "declaration": True,
                "checks": {k: True for k in ("label", "value", "year", "unit", "statement_scope")},
                "interpretation": {
                    "metric": fields["label"]["text"],
                    "value_literal": fields["value"]["text"],
                    "year": year,
                    "unit": fields["unit"]["observed_value"],
                    "statement_scope": fields["statement_scope"]["observed_value"],
                },
                "year_method": method,
                "calendar_mapping_checked": method != "explicit_column",
                "year_basis_note": "Synthetic check of annual calendar mapping"
                if method != "explicit_column"
                else "",
            }
            | updates
        )
    )


def test_read_has_no_writes_and_confirm_withdraw_keeps_original_ocr_and_history(tmp_path):
    view = view_fixture()
    before = deepcopy(view)
    initial = reviews.state(tmp_path, view)
    assert initial["revision_count"] == 0 and not (tmp_path / "outputs").exists()
    result = reviews.save(tmp_path, view, request(view))
    revision = result["cells"][0]["latest"]["revision"]
    assert (
        result["declared_confirmed_cells"] == 1 and result["eligible_for_answer_context"] is False
    )
    assert result["cells"][1]["latest"] is None
    result = reviews.save(
        tmp_path,
        view,
        request(
            view,
            status="pending",
            interpretation=None,
            year_method=None,
            previous_revision=revision,
            notes="Synthetic withdrawal",
        ),
    )
    assert result["revision_count"] == 2 and result["declared_confirmed_cells"] == 0
    assert result["cells"][0]["history"][0]["status"] == "confirmed"
    assert (
        view == before
        and result["semantic_accuracy"] is None
        and result["independent_gold"] is False
    )


@pytest.mark.parametrize(
    "change",
    ["declaration", "checks", "interpretation", "year", "unit", "scope", "literal", "correction"],
)
def test_incomplete_or_mismatched_confirmation_never_creates_database(tmp_path, change):
    view = view_fixture()
    data = request(view).model_dump()
    if change == "declaration":
        data["declaration"] = False
    if change == "checks":
        data["checks"]["year"] = False
    if change == "interpretation":
        data["interpretation"] = None
    if change == "year":
        data["interpretation"]["year"] = "2023"
    if change == "unit":
        data["interpretation"]["unit"] = "billion_VND"
    if change == "scope":
        data["interpretation"]["statement_scope"] = "parent"
    if change == "literal":
        data["interpretation"]["value_literal"] = "1,234oops"
    if change == "correction":
        data["interpretation"]["value_literal"] = "999.000"
    with pytest.raises(ValueError):
        reviews.save(tmp_path, view, reviews.OcrReviewInput(**data))
    assert not reviews.database_path(tmp_path).exists()


@pytest.mark.parametrize(
    "field", ["label", "unit", "statement_scope", "period", "statement_period"]
)
def test_missing_source_fields_cannot_be_filled_by_confirmation_text(tmp_path, field):
    view = view_fixture(relative=True)
    data = request(view).model_dump()
    view["pages"][0]["cells"][0]["fields"][field] = None
    data["binding_sha256"] = reviews.bindings(view)[data["candidate_id"]]["binding_sha256"]
    assert not reviews.state(tmp_path, view)["cells"][0]["requirements"]["can_confirm"]
    with pytest.raises(ValueError):
        reviews.save(tmp_path, view, reviews.OcrReviewInput(**data))
    data.update(
        status="needs_context",
        interpretation=None,
        year_method=None,
        calendar_mapping_checked=False,
        notes="Synthetic source context missing",
    )
    result = reviews.save(tmp_path, view, reviews.OcrReviewInput(**data))
    assert result["declared_confirmed_cells"] == 0


@pytest.mark.parametrize(
    "index,year,method", [(0, "2024", "annual_current"), (1, "2023", "annual_previous")]
)
def test_relative_year_mapping_is_only_a_manual_declaration_with_note_and_check(
    tmp_path, index, year, method
):
    view = view_fixture(relative=True)
    good = request(view, index=index)
    assert good.interpretation.year == year and good.year_method == method
    for updates in ({"calendar_mapping_checked": False}, {"year_basis_note": ""}):
        with pytest.raises(ValueError, match="mapping"):
            reviews.save(tmp_path, view, good.model_copy(update=updates))
    result = reviews.save(tmp_path, view, good)
    assert result["declared_confirmed_cells"] == 1
    assert view["pages"][0]["cells"][index]["resolved_year"] is None
    assert result["historical_availability_validated"] is False


def test_non_calendar_annual_period_and_dash_remain_needs_context(tmp_path):
    view = view_fixture(relative=True)
    candidate = view["pages"][0]["cells"][0]
    candidate["fields"]["statement_period"]["observed_end_date"] = "2024-06-30"
    assert reviews.year_options(candidate) == {}
    assert not reviews.state(tmp_path, view)["cells"][0]["requirements"]["can_confirm"]
    view = view_fixture()
    data = request(view).model_dump()
    view["pages"][0]["cells"][0]["fields"]["value"]["text"] = "-"
    data["binding_sha256"] = reviews.bindings(view)[data["candidate_id"]]["binding_sha256"]
    data["interpretation"]["value_literal"] = "0"
    data["correction_notes"] = "Synthetic attempted conversion of dash"
    with pytest.raises(ValueError):
        reviews.save(tmp_path, view, reviews.OcrReviewInput(**data))


def test_correction_preserves_original_literal_in_source_binding(tmp_path):
    view = view_fixture()
    data = request(view).model_dump()
    original = data["interpretation"]["value_literal"]
    data["interpretation"].update(metric="Synthetic corrected metric", value_literal="(9.999.000)")
    data["correction_notes"] = "Synthetic visual correction fixture only"
    event = reviews.save(tmp_path, view, reviews.OcrReviewInput(**data))["cells"][0]["latest"]
    assert event["interpretation"]["value_literal"] == "(9.999.000)"
    assert event["source_binding"]["fields"]["value"]["text"] == original
    assert view["pages"][0]["cells"][0]["fields"]["value"]["text"] == original


def test_unknown_stale_binding_and_previous_revision_do_not_write(tmp_path):
    view = view_fixture()
    good = request(view)
    for updates in (
        {"candidate_id": "0" * 64},
        {"binding_sha256": "0" * 64},
        {"previous_revision": "0" * 64},
    ):
        with pytest.raises(ValueError):
            reviews.save(tmp_path, view, good.model_copy(update=updates))
    assert not reviews.database_path(tmp_path).exists()
    reviews.save(tmp_path, view, good)
    with pytest.raises(ReviewConflict):
        reviews.save(tmp_path, view, good)


@pytest.mark.parametrize(
    "change", ["payload", "source_resealed", "eligible_resealed", "chain_resealed"]
)
def test_ledger_rejects_corruption_and_false_context_eligibility(tmp_path, change):
    view = view_fixture()
    first = reviews.save(tmp_path, view, request(view))
    if change == "chain_resealed":
        reviews.save(
            tmp_path, view, request(view, previous_revision=first["cells"][0]["latest"]["revision"])
        )
    with sqlite3.connect(reviews.database_path(tmp_path)) as db:
        sequence, payload = db.execute(
            "SELECT sequence,payload FROM events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        data = json.loads(payload)
        if change == "payload":
            data["notes"] = "changed"
        if change == "source_resealed":
            data["source_binding"]["fields"]["value"]["text"] = "999"
        if change == "eligible_resealed":
            data["eligible_for_answer_context"] = True
        if change == "chain_resealed":
            data["previous_revision"] = None
        db.execute(
            "UPDATE events SET payload=?,revision=? WHERE sequence=?",
            (
                canonical(data).decode(),
                "0" * 64 if change == "payload" else sha256(canonical(data)),
                sequence,
            ),
        )
    with pytest.raises(ValueError, match="differs|chain"):
        reviews.state(tmp_path, view)


def test_source_seal_change_invalidates_existing_reviews_instead_of_hiding_them(tmp_path):
    view = view_fixture()
    reviews.save(tmp_path, view, request(view))
    changed = deepcopy(view)
    changed["ocr_run_seal_sha256"] = "d" * 64
    with pytest.raises(ValueError, match="binding"):
        reviews.state(tmp_path, changed)


def test_simultaneous_writers_keep_one_revision_and_report_conflict(tmp_path):
    view = view_fixture()
    body = request(view)
    barrier = Barrier(2)

    def write():
        barrier.wait()
        try:
            reviews.save(tmp_path, view, body)
            return "saved"
        except ReviewConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: write(), range(2)))
    assert sorted(results) == ["conflict", "saved"]
    assert reviews.state(tmp_path, view)["revision_count"] == 1
