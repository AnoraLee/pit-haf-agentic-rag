"""Small synthetic CSVs only; imported mirrors never assert publisher or historical proof."""

import csv
import json

import pytest

from pit_haf.data.dataset_import import import_dataset
from pit_haf.data.hub import file_sha
from pit_haf.data.snapshots import SnapshotStore


def fixture_config(tmp_path):
    base = tmp_path / "input/processed"
    base.mkdir(parents=True)
    rows = [{"id": str(i), "title": "FPT và Hòa Phát: tài liệu giả lập", "description": "Dữ liệu kiểm thử ngoại tuyến.",
             "content": ("Nội dung tài chính giả lập. " * 30) + str(i), "category": "Kinh doanh"} for i in (1, 2, 3)]
    rows[1]["content"] = rows[0]["content"]
    metadata = [{"id": str(i), "url": f"https://fixture.example/article/{i}", "source": "Synthetic publisher",
                 "public_date": "2024-04-03 09:30:00+07:00", "category": "Kinh doanh", "author": "Synthetic author"} for i in (1, 2, 3)]
    for name, records in (("train.csv", rows), ("news_metadata.csv", metadata)):
        with (base / name).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    config = {"dataset_id": "synthetic/news", "dataset_revision": "a" * 40, "release_id": "fixture",
              "dataset_url": "https://fixture.example/dataset", "target_documents": 2,
              "categories": ["Kinh doanh"], "splits": ["train"], "min_body_chars": 400, "max_body_chars": 5000,
              "allowed_original_hosts": ["fixture.example"], "ticker_aliases": {"FPT": [], "HPG": ["Hòa Phát"]},
              "license_observed": "synthetic fixture", "rights_note": "Synthetic test data only.", "data_kind": "test_fixture",
              "files": [{"path": "processed/" + p.name, "size": p.stat().st_size, "sha256": file_sha(p)} for p in base.glob("*.csv")]}
    return tmp_path / "input", config


def test_dataset_join_dedup_provenance_and_resume(tmp_path):
    input_root, config = fixture_config(tmp_path)
    store = SnapshotStore(tmp_path / "store")
    result = import_dataset(config, input_root=input_root, store=store, output=tmp_path / "first")
    assert result["run_kind"] == "test_fixture" and result["success_documents"] == 2
    assert result["selection_counts"]["duplicate_url_or_body"] == 1
    versions = store.versions()
    assert len(versions) == 2
    for version in versions:
        assert version.origin == "dataset_mirror" and version.media_type == "application/json"
        assert version.related_tickers == ("FPT", "HPG")
        assert version.published_at.isoformat() == "2024-04-03T02:30:00+00:00"
        assert version.available_at is None and version.version_basis == "observation_only"
        original = json.loads(store.read_blob(version.content_hash))
        assert original["source_metadata_row"]["url"] == version.source_url
    replay = import_dataset(config, input_root=input_root, store=store, output=tmp_path / "replay")
    assert replay["pages_sha256"] == result["pages_sha256"]
    assert len(store.versions()) == 2


def test_dataset_input_checksum_failure_does_not_register_rows(tmp_path):
    input_root, config = fixture_config(tmp_path)
    (input_root / "processed/train.csv").write_bytes(b"tampered fixture")
    store = SnapshotStore(tmp_path / "store")
    with pytest.raises(ValueError, match="checksum"):
        import_dataset(config, input_root=input_root, store=store, output=tmp_path / "bad")
    assert store.versions() == ()
