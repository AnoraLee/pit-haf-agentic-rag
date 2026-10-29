"""Synthetic reviewer declarations only; no annotations of real thesis evidence."""

import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from test_table_evidence import runtime, saved_table_run  # noqa: F401

from pit_haf.research.reviews import ReviewConflict
from pit_haf.research.table_reviews import TableReviewInput, database_path, save, state
from pit_haf.research.table_views import detail
from pit_haf.ui.api import create_app


@pytest.fixture
def review_setup(saved_table_run):  # noqa: F811 - shared pytest fixture
    root, folder, result = saved_table_run
    view = detail(root, result["run_id"])
    return root, folder, view


def request(root, view, **updates):
    location = state(root, view)["locations"][0]
    fields = view["cells"][0]["source_alternatives"][0]["fields"]
    return TableReviewInput(**({
        "run_id": view["run"]["run_id"], "candidate_id": location["candidate_id"],
        "source_cell_id": location["source_cell_id"], "binding_sha256": location["binding_sha256"],
        "reviewer": "Synthetic QA fixture", "status": "confirmed", "declaration": True,
        "checks": {k: True for k in ("label", "value", "year", "unit", "statement_scope")},
        "interpretation": {"metric": "Synthetic profit", "year": fields["period"]["text"],
                           "unit": fields["unit"]["value"],
                           "statement_scope": fields["statement_scope"]["value"]},
    } | updates))


def test_read_is_nonmutating_and_confirm_retract_preserves_run_and_history(review_setup):
    root, folder, view = review_setup
    original = {p.name: p.read_bytes() for p in folder.glob("*.json")}
    initial = state(root, view)
    assert initial["revision_count"] == 0 and not database_path(root).exists()
    first = save(root, view, request(root, view))
    revision = first["locations"][0]["latest"]["revision"]
    assert first["declared_confirmed_locations"] == 1 and first["semantic_accuracy"] is None
    second = save(root, view, request(root, view, status="pending", declaration=False, interpretation=None,
                                      previous_revision=revision, notes="Synthetic withdrawal"))
    assert second["revision_count"] == 2 and second["declared_confirmed_locations"] == 0
    assert second["locations"][0]["history"][0]["status"] == "confirmed"
    assert {p.name: p.read_bytes() for p in folder.glob("*.json")} == original
    assert detail(root, view["run"]["run_id"])["human_reviewed_facts"] == 0


@pytest.mark.parametrize("updates", [
    {"declaration": False},
    {"checks": {"label": True, "value": True, "year": True, "unit": True}},
    {"interpretation": None},
    {"interpretation": {"metric": "Synthetic", "year": "2023", "unit": "triệu VND", "statement_scope": "consolidated"}},
    {"interpretation": {"metric": "Synthetic", "year": "2024", "unit": "tỷ VND", "statement_scope": "consolidated"}},
    {"interpretation": {"metric": "Synthetic", "year": "2024", "unit": "triệu VND", "statement_scope": "parent"}},
    {"status": "rejected", "interpretation": None, "notes": "   "},
    {"status": "needs_context", "interpretation": None, "notes": ""},
])
def test_incomplete_or_mismatched_confirmation_cannot_write(review_setup, updates):
    root, _, view = review_setup
    with pytest.raises(ValueError):
        save(root, view, request(root, view, **updates))
    assert not database_path(root).exists()


@pytest.mark.parametrize("saved_table_run", ["grouped_v06"], indirect=True)
def test_review_one_group_location_does_not_confirm_its_siblings(review_setup):
    root, _, view = review_setup
    result = save(root, view, request(root, view))
    assert len(result["locations"]) == 3 and result["declared_confirmed_locations"] == 1
    assert [r["latest"] is None for r in result["locations"]] == [False, True, True]


@pytest.mark.parametrize("change", ["missing_unit", "missing_scope", "conflict"])
def test_missing_source_parts_and_conflicts_only_allow_reasoned_nonconfirmation(review_setup, change):
    root, _, view = review_setup
    body = request(root, view).model_dump()
    view = copy.deepcopy(view)
    if change == "conflict":
        view["cells"][0]["conflict_group_id"] = "synthetic-conflict"
    else:
        view["cells"][0]["source_alternatives"][0]["fields"]["unit" if change == "missing_unit" else "statement_scope"] = None
    body["binding_sha256"] = state(root, view)["locations"][0]["binding_sha256"]
    with pytest.raises(ValueError):
        save(root, view, TableReviewInput(**body))
    body.update(status="needs_context", interpretation=None, notes="Synthetic missing context")
    result = save(root, view, TableReviewInput(**body))
    assert result["declared_confirmed_locations"] == 0


def test_unknown_location_and_stale_binding_revision_cannot_overwrite(review_setup):
    root, _, view = review_setup
    good = request(root, view)
    for field in ("run_id", "candidate_id", "source_cell_id"):
        bad = good.model_copy(update={field: "20260101T000000Z-00000000" if field == "run_id" else "0" * 64})
        with pytest.raises(ValueError, match="Unknown"):
            save(root, view, bad)
    with pytest.raises(ReviewConflict, match="binding"):
        save(root, view, good.model_copy(update={"binding_sha256": "0" * 64}))
    save(root, view, good)
    with pytest.raises(ReviewConflict, match="newer"):
        save(root, view, good)
    assert state(root, view)["revision_count"] == 1


@pytest.mark.parametrize("attempt", range(4))
def test_concurrent_first_saves_produce_one_revision_and_one_conflict(review_setup, attempt):
    root, _, view = review_setup
    body = request(root, view)
    barrier = Barrier(2)

    def worker():
        barrier.wait(timeout=10)
        try:
            save(root, view, body)
            return "saved"
        except ReviewConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        assert sorted(f.result(timeout=15) for f in futures) == ["conflict", "saved"]
    assert state(root, view)["revision_count"] == 1


@pytest.mark.parametrize("tamper", ["payload", "remove_first", "source_binding"])
def test_corrupt_or_detached_history_fails_closed(review_setup, tamper):
    from pit_haf.data.snapshots import canonical
    from pit_haf.llm.ollama import sha256

    root, _, view = review_setup
    first = save(root, view, request(root, view))
    save(root, view, request(root, view, previous_revision=first["locations"][0]["latest"]["revision"]))
    with sqlite3.connect(database_path(root)) as db:
        if tamper == "remove_first":
            db.execute("DELETE FROM events WHERE sequence=1")
        else:
            event = json.loads(db.execute("SELECT payload FROM events WHERE sequence=1").fetchone()[0])
            if tamper == "payload":
                event["notes"] = "tampered"
                db.execute("UPDATE events SET payload=? WHERE sequence=1", (canonical(event).decode(),))
            else:
                event["source_binding"]["content_hash"] = "0" * 64
                db.execute("UPDATE events SET payload=?,revision=? WHERE sequence=1",
                           (canonical(event).decode(), sha256(canonical(event))))
    with pytest.raises(ValueError, match="mismatch"):
        state(root, view)


def test_review_api_origin_stale_save_export_and_source_tampering(review_setup):
    root, folder, view = review_setup
    body = request(root, view).model_dump()
    endpoint = f"/api/research/table-evidence/{body['run_id']}"
    with TestClient(create_app(root)) as client:
        assert client.get(endpoint).json()["reviews"]["revision_count"] == 0
        assert not database_path(root).exists()
        assert client.post(endpoint + "/reviews", json=body, headers={"Origin": "https://example.org"}).status_code == 403
        assert client.post(endpoint + "/reviews", json={**body, "declaration": False}).status_code == 422
        assert client.post(endpoint + "/reviews", json={**body, "value": "999"}).status_code == 422
        response = client.post(endpoint + "/reviews", json=body)
        assert response.status_code == 200 and response.json()["declared_confirmed_locations"] == 1
        assert client.post(endpoint + "/reviews", json=body).status_code == 409
        export = client.get(endpoint + "/reviews/export")
        assert export.status_code == 200 and "attachment" in export.headers["content-disposition"]
        assert export.json()["locations"][0]["latest"]["source_binding"]["fields"]["value"]["text"] == "12"
        (folder / "context.json").write_text("[]")
        assert client.post(endpoint + "/reviews", json=body).status_code == 503
        assert client.get(endpoint + "/reviews/export").status_code == 503
