"""Synthetic OCR assertions; no labels are written against real thesis documents."""

import json
import subprocess

import pytest
from fastapi.testclient import TestClient
from test_pdf_text import pdf_catalog as base_pdf_catalog  # noqa: F401
from test_table_evidence import runtime, synthetic_pdf  # noqa: F401

from pit_haf.data import pdf_ocr
from pit_haf.data.hub import file_sha
from pit_haf.llm.ollama import sha256, write_json
from pit_haf.research import ocr_preview as ocr
from pit_haf.ui.api import create_app

TSV_HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
TSV = (
    TSV_HEADER
    + "5\t1\t1\t1\t1\t1\t10\t20\t50\t20\t95.5\tDoanh\n"
    + "5\t1\t1\t1\t1\t2\t70\t20\t40\t20\t40\t(12)\n"
)


@pytest.fixture
def pdf_catalog(base_pdf_catalog):  # noqa: F811 - shared pytest fixture
    return base_pdf_catalog


@pytest.fixture
def fake_worker():
    def execute(root, raw_path, digest, number, destination, profile, region=None):
        png, geometry = pdf_ocr.render_page(raw_path.read_bytes(), digest, number, profile, region=region)
        (destination / "page.png").write_bytes(png)
        (destination / "page.tsv").write_text(TSV, encoding="utf-8", newline="")
        (destination / "page.txt").write_text("Doanh (12)\n", encoding="utf-8", newline="")
        words = pdf_ocr.parse_tsv(TSV, geometry, profile)
        data = {
            "geometry": geometry,
            "words": words,
            "text_sha256": file_sha(destination / "page.txt"),
            "tsv_sha256": file_sha(destination / "page.tsv"),
            "image_sha256": sha256(png),
            "engine": "tesseract 5.5.3\nsynthetic test only",
            "tesserocr_version": "2.12.0",
            "ocr_performed": True,
            "word_count": len(words),
            "low_confidence_words": 1,
            "semantic_support": "not_assessed",
            "human_reviewed_facts": 0,
        }
        if region is not None:
            cropped = pdf_ocr.crop_input(png, geometry)
            (destination / "ocr-input.png").write_bytes(cropped)
            data["ocr_input_sha256"] = sha256(cropped)
        write_json(destination / "page.json", data)
        return data

    return execute


def start(catalog, worker, **kwargs):
    return ocr.run(
        catalog.root,
        query="lợi nhuận năm 2024",
        ticker="AAA",
        version_id="current",
        pages=kwargs.pop("pages", [1]),
        worker=worker,
        **kwargs,
    )


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


@pytest.mark.parametrize("numbers", [[], [1, 1], [True], [0], [-1], [10001], [1, 2, 3, 4, 5]])
def test_page_budget_is_explicit_and_does_not_truncate_requests(numbers):
    with pytest.raises(ValueError, match="distinct positive"):
        pdf_ocr.validate_pages(numbers)


def test_tsv_preserves_literal_numeric_text_confidence_and_maps_pixels_to_pdf(runtime):  # noqa: F811
    profile = pdf_ocr.settings(runtime)
    geometry = {"image_width": 200, "image_height": 100, "pdf_width": 400.0, "pdf_height": 200.0}
    words = pdf_ocr.parse_tsv(TSV, geometry, profile)
    assert words[1]["text"] == "(12)" and words[1]["confidence"] == 40
    assert words[1]["low_confidence"] and not words[0]["low_confidence"]
    assert words[0]["bbox_pdf"] == [20.0, 40.0, 120.0, 80.0]
    assert not words[0]["human_reviewed"] and words[0]["origin"] == "ocr_unreviewed"


def test_native_headerless_tsv_api_rows_keep_exact_word_values(runtime):  # noqa: F811
    profile = pdf_ocr.settings(runtime)
    geometry = {"image_width": 200, "image_height": 100, "pdf_width": 400., "pdf_height": 200.}
    native = "1\t1\t0\t0\t0\t0\t0\t0\t200\t100\t-1\t\n" + TSV.removeprefix(TSV_HEADER)
    assert pdf_ocr.parse_tsv(native, geometry, profile) == pdf_ocr.parse_tsv(TSV, geometry, profile)


@pytest.mark.parametrize(
    "change", ["nan", "negative_box", "outside_image", "bad_columns", "extra_field", "wrong_page"]
)
def test_malformed_ocr_geometry_or_scores_fail_closed(runtime, change):  # noqa: F811
    tsv = TSV
    if change == "nan":
        tsv = tsv.replace("95.5", "nan")
    if change == "negative_box":
        tsv = tsv.replace("\t10\t20\t50", "\t-10\t20\t50")
    if change == "outside_image":
        tsv = tsv.replace("\t10\t20\t50", "\t190\t20\t50")
    if change == "bad_columns":
        tsv = tsv.replace("\tconf\t", "\tbad\t")
    if change == "extra_field":
        tsv = tsv.replace("Doanh\n", "Doanh\tEXTRA\n")
    if change == "wrong_page":
        tsv = tsv.replace("5\t1\t1", "5\t2\t1")
    with pytest.raises(ValueError):
        pdf_ocr.parse_tsv(
            tsv,
            {"image_width": 200, "image_height": 100, "pdf_width": 400.0, "pdf_height": 200.0},
            pdf_ocr.settings(runtime),
        )


def test_render_checks_raw_checksum_and_pixel_budget_before_allocating_big_image(runtime):  # noqa: F811
    profile = pdf_ocr.settings(runtime)
    raw = synthetic_pdf()
    with pytest.raises(ValueError, match="checksum"):
        pdf_ocr.render_page(raw, "0" * 64, 1, profile)
    with pytest.raises(ValueError, match="pixel budget"):
        pdf_ocr.render_page(raw, sha256(raw), 1, {**profile, "max_render_pixels": 1})


def test_models_are_verified_and_changed_local_models_are_rejected(runtime):  # noqa: F811
    directory = runtime / pdf_ocr.MODEL_DIR
    directory.mkdir(parents=True)
    (directory / "vie.traineddata").write_bytes(b"not a trained model")
    with pytest.raises(ValueError, match="Missing/changed OCR model"):
        pdf_ocr.model_directory(runtime)


def test_worker_timeout_preserves_logs_and_does_not_retry(runtime, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(pdf_ocr.importlib.metadata, "version", lambda _: "2.12.0")
    monkeypatch.setattr(pdf_ocr, "model_directory", lambda _: runtime)
    calls = []

    def expired(*args, **kwargs):
        calls.append(kwargs)
        raise subprocess.TimeoutExpired(args[0], 60, output=b"partial", stderr=b"diagnostic")

    monkeypatch.setattr(pdf_ocr.subprocess, "run", expired)
    directory = tmp_path / "worker"
    directory.mkdir()
    with pytest.raises(ValueError, match="timed out"):
        pdf_ocr.run_worker(
            runtime, tmp_path / "not-read.pdf", "a" * 64, 1, directory, pdf_ocr.settings(runtime)
        )
    assert len(calls) == 1 and calls[0]["env"]["OMP_THREAD_LIMIT"] == "1"
    assert (directory / "worker.stdout").read_bytes() == b"partial"


def test_scope_and_empty_temporal_gate_precede_any_pdf_or_native_ocr(pdf_catalog, monkeypatch):
    monkeypatch.setattr(
        ocr, "catalog_for", lambda *a: pytest.fail("Undelivered OCR opened catalog")
    )
    with pytest.raises(ValueError, match="Point-in-Time gateway"):
        start(
            pdf_catalog,
            lambda *a: pytest.fail("Undelivered native OCR"),
            mode="strict_point_in_time",
            decision_at="2025-01-01T00:00:00Z",
        )


@pytest.mark.parametrize("version", ["other", "past", "future", "absent"])
def test_explicit_document_does_not_override_company_or_period(pdf_catalog, monkeypatch, version):
    monkeypatch.setattr(ocr, "catalog_for", lambda _: pdf_catalog)
    monkeypatch.setattr(
        pdf_catalog.store, "read_blob", lambda *a: pytest.fail("Invalid OCR source read raw PDF")
    )
    with pytest.raises(ValueError, match="outside"):
        ocr.run(
            pdf_catalog.root, query="lợi nhuận 2024", ticker="AAA", version_id=version, pages=[1]
        )


def test_preview_and_full_ocr_replay_preserve_original_catalog_and_run(pdf_catalog, fake_worker):
    before = file_sha(pdf_catalog.path)
    folder, result = start(pdf_catalog, fake_worker)
    seal = file_sha(folder / "integrity.json")
    view = ocr.detail(pdf_catalog.root, result["run_id"])
    assert view["pages"][0]["words"][1]["text"] == "(12)"
    assert (
        result["llm_calls"] == result["human_reviewed_facts"] == 0
        and not result["used_in_report_context"]
    )
    assert ocr.replay(pdf_catalog.root, folder, worker=fake_worker) == result
    assert file_sha(folder / "integrity.json") == seal and file_sha(pdf_catalog.path) == before
    assert not (pdf_catalog.root / "outputs/table-reviews/reviews.sqlite3").exists()


def test_partial_failure_is_kept_without_retry_or_replacing_a_requested_page(
    pdf_catalog, fake_worker
):
    folder, result = start(pdf_catalog, fake_worker, pages=[1, 2])
    assert result["status"] == "partial_failure" and result["requested_pages"] == [1, 2]
    assert result["pages"][1]["status"] == "failed"
    assert ocr.replay(pdf_catalog.root, folder, worker=fake_worker) == result
    folder, result = start(pdf_catalog, fake_worker, pages=[2])
    assert result["status"] == "failed"
    with pytest.raises(ValueError, match="No successful OCR page"):
        ocr.replay(pdf_catalog.root, folder, worker=fake_worker)


@pytest.mark.parametrize("change", ["word", "image", "consistent_fake_ocr"])
def test_resealed_forged_words_images_and_engine_output_are_rejected(
    pdf_catalog, fake_worker, change
):
    root = pdf_catalog.root
    folder, result = start(pdf_catalog, fake_worker)
    directory = folder / "page-0001"
    data = json.loads((directory / "page.json").read_text(encoding="utf-8"))
    if change == "word":
        data["words"][0]["text"] = "forged"
    elif change == "image":
        with (directory / "page.png").open("ab") as stream:
            stream.write(b"forged")
        data["image_sha256"] = file_sha(directory / "page.png")
    else:
        (directory / "page.tsv").write_text(
            TSV.replace("Doanh", "forged"), encoding="utf-8", newline=""
        )
        data["words"][0]["text"] = "forged"
        data["tsv_sha256"] = file_sha(directory / "page.tsv")
    write_json(directory / "page.json", data)
    reseal(folder)
    with pytest.raises(ValueError, match="differs|differ"):
        if change == "consistent_fake_ocr":
            ocr.replay(root, folder, worker=fake_worker)
        else:
            ocr.detail(root, result["run_id"])


def test_api_validates_scope_page_limits_origin_and_saved_source_image(
    pdf_catalog, fake_worker, monkeypatch
):
    original = ocr.run_worker
    monkeypatch.setattr(ocr, "run_worker", fake_worker)
    body = {
        "ticker": "AAA",
        "query": "lợi nhuận 2024",
        "document_version_id": "current",
        "pages": [1],
    }
    with TestClient(create_app(pdf_catalog.root)) as client:
        endpoint = "/api/research/ocr-previews"
        assert (
            client.post(
                endpoint, json=body, headers={"Origin": "https://untrusted.example"}
            ).status_code
            == 403
        )
        assert client.post(endpoint, json={**body, "pages": [1, 2, 3, 4, 5]}).status_code == 422
        assert client.post(endpoint, json={**body, "pages": [True]}).status_code == 422
        assert client.post(endpoint, json={**body, "pages": [1, 1]}).status_code == 503
        response = client.post(endpoint, json=body)
        assert response.status_code == 200
        data = response.json()
        run_id = data["run"]["run_id"]
        assert client.get(endpoint + "?version_id=current").json()["runs"][0]["run_id"] == run_id
        assert client.get(endpoint + "/" + run_id).status_code == 200
        image = client.get(data["pages"][0]["image_url"])
        assert image.status_code == 200 and image.content.startswith(b"\x89PNG")
        assert client.get(endpoint + "/" + run_id + "/pages/2/image").status_code == 404
        assert client.get(endpoint + "/bad-id").status_code == 503
    monkeypatch.setattr(ocr, "run_worker", original)


@pytest.mark.parametrize("region", [None, [0, 0, 1], [True, 0, 1, 1], [-.1, 0, 1, 1],
                                   [0, 0, float("nan"), 1], [.5, 0, .5, 1], [0, 0, .001, 1]])
def test_region_policy_rejects_invalid_coordinates_before_native_ocr(runtime, region):  # noqa: F811
    with pytest.raises(ValueError, match="OCR region"):
        pdf_ocr.validate_region(region, pdf_ocr.settings(runtime, "pdf_ocr_region_v0.2"))


def test_region_policy_does_not_silently_change_legacy_ocr_or_exceed_one_page(pdf_catalog):
    with pytest.raises(ValueError, match="versioned region"):
        start(pdf_catalog, lambda *a: pytest.fail("Unexpected worker"), region=[0, 0, 1, 1])
    with pytest.raises(ValueError, match="1–1 distinct"):
        start(pdf_catalog, lambda *a: pytest.fail("Unexpected worker"), pages=[1, 2],
              profile_id="pdf_ocr_region_v0.2", region=[0, 0, 1, 1])


def test_crop_tsv_restores_full_page_pixel_and_pdf_coordinates(runtime):  # noqa: F811
    profile = pdf_ocr.settings(runtime, "pdf_ocr_region_v0.2")
    geometry = {"image_width": 400, "image_height": 200, "pdf_width": 800., "pdf_height": 400.,
                "ocr_region_normalized": [.25, .25, .75, .75], "ocr_crop_pixels": [100, 50, 300, 150]}
    words = pdf_ocr.parse_tsv(TSV, geometry, profile)
    assert words[0]["bbox_ocr_pixels"] == [10, 20, 60, 40]
    assert words[0]["bbox_pixels"] == [110, 70, 160, 90]
    assert words[0]["bbox_pdf"] == [220., 140., 320., 180.]
    assert pdf_ocr.region_pixels([.15, .12, .85, .84], 1001, 701) == [150, 84, 851, 589]
    with pytest.raises(ValueError, match="crop geometry"):
        pdf_ocr.parse_tsv(TSV, {**geometry, "ocr_crop_pixels": [100, 50, 301, 150]}, profile)
    with pytest.raises(ValueError, match="geometry is invalid"):
        pdf_ocr.parse_tsv(TSV.replace("\t10\t20\t50", "\t190\t20\t50"), geometry, profile)


def test_region_run_replay_and_crop_bytes_remain_separate_from_source(pdf_catalog, fake_worker):
    region = [.1, .1, .9, .9]
    folder, result = start(pdf_catalog, fake_worker, profile_id="pdf_ocr_region_v0.2", region=region)
    view = ocr.detail(pdf_catalog.root, result["run_id"])
    assert result["requested_region"] == region and result["used_in_report_context"] is False
    assert view["pages"][0]["geometry"]["dpi"] == 240
    assert (folder / "page-0001/ocr-input.png").read_bytes() != (folder / "page-0001/page.png").read_bytes()
    assert ocr.replay(pdf_catalog.root, folder, worker=fake_worker) == result
    assert "requested_region" not in start(pdf_catalog, fake_worker)[1]


def test_resealed_forged_crop_is_rejected_against_raw_pdf(pdf_catalog, fake_worker):
    folder, result = start(pdf_catalog, fake_worker, profile_id="pdf_ocr_region_v0.2", region=[.1, .1, .9, .9])
    directory = folder / "page-0001"
    (directory / "ocr-input.png").write_bytes(b"forged but consistently resealed crop")
    data = json.loads((directory / "page.json").read_text(encoding="utf-8"))
    data["ocr_input_sha256"] = file_sha(directory / "ocr-input.png")
    write_json(directory / "page.json", data)
    reseal(folder)
    with pytest.raises(ValueError, match="crop differs from raw"):
        ocr.detail(pdf_catalog.root, result["run_id"])


def test_api_region_budget_and_strict_numbers(pdf_catalog, fake_worker, monkeypatch):
    monkeypatch.setattr(ocr, "run_worker", fake_worker)
    body = {"ticker": "AAA", "query": "lợi nhuận 2024", "document_version_id": "current", "pages": [1],
            "profile_id": "pdf_ocr_region_v0.2", "region": [.1, .1, .9, .9]}
    with TestClient(create_app(pdf_catalog.root)) as client:
        endpoint = "/api/research/ocr-previews"
        assert client.post(endpoint, json=body).status_code == 200
        assert client.post(endpoint, json={**body, "region": [True, 0, 1, 1]}).status_code == 422
        assert client.post(endpoint, json={**body, "region": [0, 0, 1]}).status_code == 422
        assert client.post(endpoint, json={**body, "region": [.9, 0, .1, 1]}).status_code == 503
        assert client.post(endpoint, json={**body, "pages": [1, 2]}).status_code == 503


def test_numeric_audit_preserves_reference_bytes_and_recomputes_saved_results(pdf_catalog, fake_worker):
    from pit_haf.research import ocr_numeric

    root = pdf_catalog.root
    _, result = start(pdf_catalog, fake_worker)
    view = ocr.detail(root, result["run_id"])
    refs = {"provenance": "assistant_visual_transcription", "independent_gold": False,
            "human_confirmed": False, "allowed_use": "development_diagnostic_only", "version_id": "current",
            "content_hash": view["source"]["content_hash"], "page": 1,
            "cells": [{"id": "test", "bbox_normalized": [0, 0, 1, 1], "literal": "12",
                       "column_label": "synthetic", "resolved_year": None}]}
    path = root / "synthetic-references.json"
    write_json(path, refs)
    folder, rows = ocr_numeric.audit(root, path, [result["run_id"]])
    assert rows[0]["literal_matches"] == 0
    assert (folder / "references.json").read_bytes() == path.read_bytes()
    assert ocr_numeric.replay(root, folder) == rows
    saved = json.loads((folder / "audit.json").read_text(encoding="utf-8"))
    saved["results"][0]["literal_matches"] = 1
    write_json(folder / "audit.json", saved)
    reseal(folder)
    with pytest.raises(ValueError, match="differs from saved"):
        ocr_numeric.replay(root, folder)


def test_cell_link_api_and_snapshot_replay_keep_ocr_source_and_never_run_models(
    pdf_catalog, fake_worker, monkeypatch
):
    from test_ocr_cells import fixture_page

    from pit_haf.research import ocr_cell_links

    rows = [TSV_HEADER]
    for word in fixture_page()["words"]:
        x0, y0, x1, y1 = word["bbox_pixels"]
        rows.append(f"5\t1\t1\t1\t{word['reading_order']['line_num']}\t{word['reading_order']['word_num']}\t"
                    f"{x0}\t{y0}\t{x1-x0}\t{y1-y0}\t95\t{word['text']}\n")
    monkeypatch.setitem(globals(), "TSV", "".join(rows))

    def synthetic(root, raw, digest, number, dest, profile):
        data = fake_worker(root, raw, digest, number, dest, profile)
        data["low_confidence_words"] = 0
        write_json(dest / "page.json", data)
        return data

    root = pdf_catalog.root
    folder, result = start(pdf_catalog, synthetic)
    seal_before = file_sha(folder / "integrity.json")
    monkeypatch.setattr(ocr, "run_worker", lambda *a, **kw: pytest.fail("Cell links invoked native OCR"))
    with TestClient(create_app(root)) as client:
        endpoint = f"/api/research/ocr-previews/{result['run_id']}/cell-links"
        response = client.get(endpoint)
        assert response.status_code == 200
        view = response.json()
        assert len(view["pages"][0]["cells"]) == 6
        assert view["source"]["version_id"] == "current"
        assert view["new_ocr_calls"] == view["new_llm_calls"] == view["human_reviewed_facts"] == 0
        assert not (root / "outputs/ocr-cell-links").exists()
        saved, same = ocr_cell_links.save(root, result["run_id"])
        assert same == view and ocr_cell_links.replay(root, saved) == same
        assert file_sha(folder / "integrity.json") == seal_before
        data = json.loads((saved / "links.json").read_text(encoding="utf-8"))
        data["pages"][0]["cells"][0]["fields"]["unit"]["text"] = "forged"
        write_json(saved / "links.json", data)
        reseal(saved)
        with pytest.raises(ValueError, match="differ from saved"):
            ocr_cell_links.replay(root, saved)
        (folder / "page-0001/page.tsv").write_text("forged", encoding="utf-8")
        assert client.get(endpoint).status_code == 503


def test_cell_links_preserve_failed_pages_and_zero_candidate_diagnostics(pdf_catalog, fake_worker):
    from pit_haf.research.ocr_cell_links import detail

    _, result = start(pdf_catalog, fake_worker, pages=[1, 2])
    view = detail(pdf_catalog.root, result["run_id"])
    assert [p["cells"] for p in view["pages"]] == [[], []]
    assert view["pages"][1]["diagnostics"] == [{"reason": "ocr_page_failed"}]


def test_sparse_profile_changes_segmentation_only_and_replays_without_changing_region_geometry(pdf_catalog, fake_worker):
    root = pdf_catalog.root
    dense = pdf_ocr.settings(root, "pdf_ocr_region_v0.2")
    sparse = pdf_ocr.settings(root, "pdf_ocr_sparse_v0.3")
    assert sparse == {**dense, "profile_id": "pdf_ocr_sparse_v0.3", "psm": 11}
    folder, result = start(pdf_catalog, fake_worker, profile_id="pdf_ocr_sparse_v0.3", region=[.1, .1, .9, .9])
    view = ocr.detail(root, result["run_id"])
    assert view["run"]["profile_id"] == "pdf_ocr_sparse_v0.3"
    assert ocr.replay(root, folder, worker=fake_worker) == result
    (root / "configs/pdf_ocr_v0_3.json").write_text(json.dumps({**sparse, "psm": 6}), encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown OCR profile"):
        ocr.detail(root, result["run_id"])


def test_sparse_api_requires_one_page_and_explicit_region(pdf_catalog, fake_worker, monkeypatch):
    monkeypatch.setattr(ocr, "run_worker", fake_worker)
    body = {"ticker": "AAA", "query": "dòng tiền 2024", "document_version_id": "current", "pages": [1],
            "profile_id": "pdf_ocr_sparse_v0.3", "region": [0, 0, 1, 1]}
    with TestClient(create_app(pdf_catalog.root)) as client:
        endpoint = "/api/research/ocr-previews"
        response = client.post(endpoint, json=body)
        assert response.status_code == 200 and response.json()["run"]["profile_id"] == "pdf_ocr_sparse_v0.3"
        assert client.post(endpoint, json={**body, "pages": [1, 2]}).status_code == 503
        assert client.post(endpoint, json={**body, "region": None}).status_code == 503


def test_spatial_header_api_snapshot_provenance_and_legacy_replay(pdf_catalog, fake_worker, monkeypatch):
    from test_ocr_cells import fixture_page

    from pit_haf.research import ocr_cell_links

    source_words = fixture_page(relative=True)["words"]

    def synthetic(root, raw, digest, number, destination, profile, region=None):
        _, geometry = pdf_ocr.render_page(raw.read_bytes(), digest, number, profile, region)
        crop = geometry.get("ocr_crop_pixels", [0, 0, geometry["image_width"], geometry["image_height"]])
        rows = [TSV_HEADER]
        for i, word in enumerate(source_words, 1):
            x0, y0, x1, y1 = word["bbox_pixels"]
            if not (crop[0] <= x0 < x1 <= crop[2] and crop[1] <= y0 < y1 <= crop[3]):
                continue
            rows.append(f"5\t1\t{i}\t1\t1\t1\t{x0-crop[0]}\t{y0-crop[1]}\t{x1-x0}\t{y1-y0}\t95\t{word['text']}\n")
        monkeypatch.setitem(globals(), "TSV", "".join(rows))
        data = fake_worker(root, raw, digest, number, destination, profile, region)
        data["low_confidence_words"] = 0
        write_json(destination / "page.json", data)
        return data

    root = pdf_catalog.root
    body_folder, body = start(pdf_catalog, synthetic, profile_id="pdf_ocr_region_v0.2", region=[0, 0, 1, 1])
    legacy_folder, legacy = ocr_cell_links.save(root, body["run_id"])
    geom = ocr.detail(root, body["run_id"])["pages"][0]["geometry"]
    _, header = start(pdf_catalog, synthetic, profile_id="pdf_ocr_region_v0.2",
                      region=[0, 150 / geom["image_height"], 1, 185 / geom["image_height"]])
    monkeypatch.setattr(ocr, "run_worker", lambda *a, **kw: pytest.fail("Header linking called native OCR"))
    with TestClient(create_app(root)) as client:
        endpoint = f"/api/research/ocr-previews/{body['run_id']}/cell-links"
        params = {"policy_id": "ocr_cell_links_v0.2", "header_run_id": header["run_id"]}
        response = client.get(endpoint, params=params)
        assert response.status_code == 200
        cells = response.json()["pages"][0]["cells"]
        assert len(cells) == 6 and all(c["fields"]["period"] for c in cells)
        assert cells[0]["fields"]["period"]["word_refs"][0]["ocr_run_id"] == header["run_id"]
        assert client.get(endpoint, params={**params, "policy_id": "ocr_cell_links_v0.1"}).status_code == 503
        assert client.get(endpoint, params={**params, "header_run_id": body["run_id"]}).status_code == 503
        assert client.get(endpoint, params={**params, "header_run_id": "wrong"}).status_code == 422
        saved, view = ocr_cell_links.save(root, body["run_id"], "ocr_cell_links_v0.2", header["run_id"])
        assert ocr_cell_links.replay(root, saved) == view
        assert ocr_cell_links.replay(root, legacy_folder) == legacy
        # Resealing a forged per-field OCR origin cannot make it replayable.
        view["pages"][0]["cells"][0]["fields"]["period"]["word_refs"][0]["ocr_run_id"] = body["run_id"]
        write_json(saved / "links.json", view)
        reseal(saved)
        with pytest.raises(ValueError, match="differ from saved"):
            ocr_cell_links.replay(root, saved)
        (root / "outputs/ocr-previews" / header["run_id"] / "page-0001/page.tsv").write_bytes(b"changed")
        assert client.get(endpoint, params=params).status_code == 503
    assert body_folder.is_dir()


@pytest.mark.parametrize("policy_id", ["ocr_cell_links_v0.1", "ocr_cell_links_v0.2"])
def test_review_api_source_validation_revision_conflicts_and_export(
    pdf_catalog, fake_worker, monkeypatch, policy_id
):
    from test_ocr_cells import fixture_page
    from test_ocr_reviews import request

    from pit_haf.research.ocr_reviews import database_path

    rows = [TSV_HEADER]
    for word in fixture_page()["words"]:
        x0, y0, x1, y1 = word["bbox_pixels"]
        rows.append(f"5\t1\t1\t1\t{word['reading_order']['line_num']}\t{word['reading_order']['word_num']}\t"
                    f"{x0}\t{y0}\t{x1-x0}\t{y1-y0}\t95\t{word['text']}\n")
    monkeypatch.setitem(globals(), "TSV", "".join(rows))

    def synthetic(root, raw, digest, number, destination, profile):
        data = fake_worker(root, raw, digest, number, destination, profile)
        data["low_confidence_words"] = 0
        write_json(destination / "page.json", data)
        return data

    root = pdf_catalog.root
    folder, result = start(pdf_catalog, synthetic)
    seal_before = file_sha(folder / "integrity.json")
    monkeypatch.setattr(ocr, "run_worker", lambda *a, **kw: pytest.fail("Review invoked native OCR"))
    monkeypatch.setattr("pit_haf.ui.api.run_table_evidence", lambda *a, **kw: pytest.fail("Review invoked a model"))
    with TestClient(create_app(root)) as client:
        base = f"/api/research/ocr-previews/{result['run_id']}/cell-links"
        endpoint = base + "/reviews"
        params = {"policy_id": policy_id}
        view = client.get(base, params=params).json()
        body = request(view).model_dump()
        initial = client.get(endpoint, params=params)
        assert initial.status_code == 200 and initial.json()["revision_count"] == 0
        assert not database_path(root).exists()
        assert client.get(endpoint + "/export", params=params).json() == initial.json()
        assert not database_path(root).exists()
        assert client.post(endpoint, json=body, headers={"Origin": "https://untrusted.example"}).status_code == 403
        assert client.post(endpoint, json={**body, "run_id": "20261102T000001Z-aaaaaaaa"}).status_code == 422
        assert client.post(endpoint, json={**body, "declaration": False}).status_code == 422
        assert client.post(endpoint, json={**body, "binding_sha256": "0" * 64}).status_code == 409
        assert not database_path(root).exists()
        saved = client.post(endpoint, json=body)
        assert saved.status_code == 200 and saved.json()["declared_confirmed_cells"] == 1
        assert saved.json()["eligible_for_answer_context"] is False
        assert client.post(endpoint, json=body).status_code == 409
        revision = saved.json()["cells"][0]["latest"]["revision"]
        withdrawn = {**body, "status": "pending", "interpretation": None, "year_method": None,
                     "previous_revision": revision, "notes": "Synthetic withdrawal"}
        response = client.post(endpoint, json=withdrawn)
        assert response.status_code == 200 and response.json()["declared_confirmed_cells"] == 0
        exported = client.get(endpoint + "/export", params=params)
        assert exported.json() == response.json() and exported.json()["revision_count"] == 2
        assert "attachment" in exported.headers["content-disposition"]
        assert exported.headers["cache-control"] == "no-store"
        assert file_sha(folder / "integrity.json") == seal_before
        db_before = file_sha(database_path(root))
        (folder / "page-0001/page.tsv").write_bytes(b"changed")
        assert client.get(endpoint, params=params).status_code == 503
        assert client.post(endpoint, json=withdrawn).status_code == 503
        assert file_sha(database_path(root)) == db_before
