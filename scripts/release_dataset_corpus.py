"""Assemble, verify and atomically publish a large mixed-source development corpus."""

import argparse
import gzip
import hashlib
import json
import os
import platform
from collections import Counter
from pathlib import Path

from pit_haf.data.catalog import Catalog, build_catalog
from pit_haf.data.corpus import merge_snapshots
from pit_haf.data.coverage import build_release
from pit_haf.data.evidence import EvidencePage, EvidenceVersion
from pit_haf.data.hub import file_sha
from pit_haf.data.pilot import publish_summary
from pit_haf.data.snapshots import SnapshotStore


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-sources", type=Path, required=True)
    parser.add_argument("--base-summary", type=Path, required=True)
    parser.add_argument("--import-summary", type=Path, required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--activate", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path, required=True)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    root = Path.cwd().resolve()
    for path in (args.staging, args.activate, args.metadata_output):
        if not path.resolve().is_relative_to(root):
            raise ValueError("Publication paths must remain in this workspace")
    if args.activate.exists() or args.metadata_output.exists():
        raise FileExistsError("Publication destination already exists")
    args.staging.mkdir(parents=True, exist_ok=args.resume)
    manifest = read(args.base_sources)
    incoming = read(args.import_summary.parent / "sources.json")
    imported = read(args.import_summary)
    if imported["target_shortfall"]:
        raise ValueError("Requested dataset import is incomplete")
    release_id = imported["selection_config"]["release_id"]
    manifest.update(schema_version="0.5", release_id=release_id)
    manifest["selection_note"] = "Unchanged v0.4 selected publisher snapshots plus pinned, provenance-joined VietOnlineNews business/real-estate mirrors. Current development evidence; no inferred historical availability or return-based selection."
    manifest["documents"].extend(incoming["documents"])
    manifest["sources"].extend(incoming["sources"])
    manifest["allowed_hosts"] = sorted(set(manifest["allowed_hosts"]) | set(incoming["allowed_hosts"]))
    manifest["target_documents"] = len(manifest["documents"])
    manifest_path = args.staging / "sources.json"
    if args.resume and manifest_path.exists():
        if read(manifest_path) != manifest:
            raise ValueError("Resume manifest differs from pinned inputs")
    else:
        write(manifest_path, manifest)
    store = SnapshotStore(root / "data/cache/evidence")
    snapshot = args.staging / "snapshot"
    if args.resume and (snapshot / "summary.json").exists():
        summary_path = snapshot / "summary.json"
        prior = read(summary_path)
        if prior["manifest_hash"] != file_sha(manifest_path) or {
            row["summary_sha256"] for row in prior["input_snapshots"]
        } != {file_sha(args.base_summary), file_sha(args.import_summary)}:
            raise ValueError("Resume snapshot input identity mismatch")
    else:
        summary_path = merge_snapshots(manifest_path, [args.base_summary, args.import_summary], store=store, output=snapshot)
    summary = read(summary_path)
    summary["pages_file"] = str((args.activate / "pages.jsonl").resolve())
    summary["dataset_selection_audit"] = {k: imported[k] for k in (
        "selection_counts", "rejected_candidate_rows", "source_descriptor_hash", "selection_config")}
    publish_summary(snapshot, summary)
    print(json.dumps({"stage": "merged_verified", "documents": summary["success_documents"]}), flush=True)
    if args.resume and (snapshot / "catalog.json").exists():
        pointer = read(snapshot / "catalog.json")
        if file_sha(snapshot / "pages.jsonl") != pointer["pages_sha256"]:
            raise ValueError("Resume page snapshot checksum mismatch")
    else:
        pointer = build_catalog(summary_path, store=store, output=snapshot / "catalog.sqlite3")
        write(snapshot / "catalog.json", pointer)
    print(json.dumps({"stage": "catalog_built", **pointer}), flush=True)
    catalog = Catalog(root, summary_path)
    with catalog.connect() as db:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Catalog SQLite quick_check failed")
    stats = catalog.stats()
    if stats["documents"] != summary["success_documents"] or stats["dataset_articles"] != imported["success_documents"]:
        raise ValueError("Catalog and acquisition document counts disagree")
    # The historical pilot remains byte-for-byte unchanged, including its old metadata JSON.
    with store._connect() as db:
        registry_hashes = dict(db.execute("SELECT version_id,metadata_hash FROM versions"))
    pilot_path = Path("data/pilot/snapshot_index.json")
    pilot_index = read(pilot_path)
    pilot_ids = set()
    for entry in pilot_index["versions"]:
        version_id = entry["metadata"]["version_id"]
        if registry_hashes[version_id] != entry["registry_metadata_sha256"]:
            raise ValueError("Frozen pilot metadata changed")
        pilot_ids.add(version_id)
    retained = {}
    with (snapshot / "pages.jsonl").open("rb") as stream:
        for line in stream:
            page = EvidencePage.model_validate_json(line)
            if page.version_id in pilot_ids:
                retained[(page.version_id, page.page)] = page.text_hash
    checked = 0
    with Path("outputs/milestone-1/data-pilot/20261017-final-offline/pages.jsonl").open("rb") as stream:
        for line in stream:
            page = EvidencePage.model_validate_json(line)
            if retained.get((page.version_id, page.page)) != page.text_hash:
                raise ValueError("Frozen pilot page missing or changed")
            checked += 1
    universe = read(args.universe)
    universe["release_id"] = release_id
    index, coverage = build_release(store, summary, universe)
    coverage["summary_sha256"] = pointer["summary_sha256"]
    metadata = args.staging / "metadata"
    metadata.mkdir()
    write(metadata / "universe.json", universe)
    coverage["universe_sha256"] = file_sha(metadata / "universe.json")
    write(metadata / "coverage.json", coverage)
    active = {r["version_id"]: r for r in summary["documents"] if r.get("version_id")}
    active_sizes = {r["metadata"]["version_id"]: r["raw_byte_count"] for r in index["versions"]}
    del index
    mirror_dates, splits, publishers = [], Counter(), Counter()
    with (metadata / "registry_index.jsonl.gz").open("xb") as compressed:
        with gzip.GzipFile(filename="", mode="wb", fileobj=compressed, mtime=0) as stream, store._connect() as db:
            for original in db.execute("SELECT version_id,metadata_json,metadata_hash FROM versions ORDER BY record_id,version_id"):
                version = EvidenceVersion.model_validate_json(original["metadata_json"])
                if version.version_id not in active:
                    continue
                if hashlib.sha256(original["metadata_json"].encode()).hexdigest() != original["metadata_hash"]:
                    raise ValueError("Registry metadata hash mismatch during export")
                row = active[version.version_id]
                data = {k: v for k, v in version.model_dump(mode="json").items() if v is not None}
                record = {"metadata": data, "registry_metadata_sha256": registry_hashes[version.version_id],
                          "registry_metadata_json": original["metadata_json"],
                          "active_status": row["status"], "raw_byte_count": active_sizes.get(version.version_id,
                              store.blob_path(version.content_hash).stat().st_size),
                          "active_error": row.get("error")}
                stream.write((json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode())
                if version.origin == "dataset_mirror" and row["status"] == "extracted":
                    mirror_dates.append(str(version.publication_date))
                    splits[version.dataset_split] += 1
                    publishers[version.publisher] += 1
    source_files = [Path("src/pit_haf/data") / name for name in (
        "catalog.py", "dataset_import.py", "hub.py", "evidence.py", "snapshots.py", "corpus.py", "coverage.py", "news.py")]
    verification = {"run_kind": "local_integrity_checks_not_semantic_validation", "research_prediction_results": False,
                    "summary_sha256": pointer["summary_sha256"], "pages_sha256": summary["pages_sha256"],
                    "catalog_sha256": pointer["catalog_sha256"], "catalog_documents": stats["documents"],
                    "frozen_pilot_registry_versions_unchanged": len(pilot_ids), "frozen_pilot_page_text_hashes_unchanged": checked,
                    "source_file_sha256": {p.as_posix(): file_sha(p) for p in source_files},
                    "python": platform.python_version(), "platform": platform.platform(),
                    "dataset_counts_by_original_split": dict(splits), "dataset_counts_by_publisher": dict(publishers),
                    "source_config_sha256": file_sha(Path("configs/dataset_sources_v0_5.json")),
                    "merged_manifest_sha256": file_sha(manifest_path), "import_summary_sha256": file_sha(args.import_summary),
                    "selection_counts": imported["selection_counts"], "rejected_candidate_rows": imported["rejected_candidate_rows"],
                    "not_validated": ["Independent human gold", "OCR/table/semantic accuracy", "Historical time/revision availability", "Predictive performance"]}
    write(metadata / "verification.json", verification)
    dates = sorted(mirror_dates)
    card = f"""# Corpus phát triển v0.5 — quy mô 30 nghìn bài nhập thêm

Kho hoạt động có **{stats['documents']:,} tài liệu**, gồm {stats['pdf_documents']} PDF, {stats['articles'] - stats['dataset_articles']} bài thu thập trực tiếp và **{stats['dataset_articles']:,} bài toàn văn nhập từ dataset**. Giữ nguyên {stats['pdf_pages']:,} trang PDF; bài viết có 1 section riêng, không cộng thành trang PDF.

Nguồn nhập: [VLUS06/VietOnlineNews](https://huggingface.co/datasets/VLUS06/VietOnlineNews), revision `bd8d2a865c8981d34cb9d85f69f62bda7c40b520`. Lọc các nhãn nguồn `Kinh doanh` và `Bất động sản`, ghép ID với `processed/news_metadata.csv` để giữ URL, tác giả, báo đăng và ngày công bố. Bài không đủ body 600 ký tự, lỗi join/ngày, trùng URL hoặc hash body chuẩn hóa bị loại; không dùng tóm tắt sinh để tăng số lượng. Kho không huấn luyện một LLM mới.

## Số liệu đã kiểm tra

- Mới nhập: {stats['dataset_articles']:,} bài; ngày đăng quan sát {dates[0]} đến {dates[-1]}.
- Phân bố báo của bài mới: {json.dumps(dict(publishers), ensure_ascii=False)}.
- Split phân loại gốc được giữ để truy vết: {dict(splits)}. Đây chưa phải split đánh giá tài chính độc lập.
- Selection: {dict(imported['selection_counts'])}; {imported['rejected_candidate_rows']} dòng ứng viên bị từ chối. Các dòng ngoài hai nhóm chủ đề không được tính là tài liệu đã nhập.
- Mẫu số manifest sau ghép: {summary['configured_documents']:,} records; {summary['failed_documents']} record lỗi/exclusion cũ vẫn được giữ. Bộ đếm selection CSV ở trên là mẫu số riêng.
- PiT strict: {coverage['strict_eligible_documents']}. Không suy `available_at` từ ngày đăng/URL hoặc thời điểm tải dataset.
- Pilot đóng băng: {len(pilot_ids)} metadata registry và {checked} hash văn bản trang giữ nguyên. Không chạy LLM/dự báo/backtest trong đợt nhập này.

## Provenance và quyền nội dung

`origin=dataset_mirror`, raw snapshot là JSON của dòng CSV và metadata ghép, **không phải HTML tải trực tiếp từ báo**. `source_url` vẫn trỏ đến bài gốc; dataset ID/revision/file/row/split được lưu riêng. Giờ/ngày xuất bản là quan sát của bên tổng hợp, chưa có bằng chứng revision lịch sử. Việc có nhiều tài liệu không tự chứng minh chất lượng dự báo.

Dataset ghi license `other`; file LICENSE rỗng tại revision đã pin. Chưa xác lập quyền phân phối lại toàn văn. Dữ liệu chỉ lưu local cho nghiên cứu KLTN; ghi công VLUS06/VietOnlineNews và ba báo gốc. Git chỉ chứa mã, cấu hình, metadata/checksum nén, không chứa body bài báo, CSV, PDF hoặc database.

`registry_index.jsonl.gz` là JSONL metadata không chứa nội dung bài, gồm cả version lỗi/đã loại; dùng gzip để tránh lặp metadata lớn trong Git. Hash registry là hash JSON gốc trước các default mới. `coverage.json` tách PDF/HTML/bản nhập dataset. `verification.json` ghi integrity, nguồn và môi trường; không phải đánh giá ngữ nghĩa/human gold.

## Truy xuất và giới hạn

Catalog SQLite/FTS5 phục vụ phân trang/lọc trên server; trình duyệt nhận tối đa 20 hàng mỗi trang, API chặn limit trên 100. Truy xuất hiện tại dùng FTS5 BM25, offset trỏ nguyên văn. Chế độ lịch sử lọc gateway trước, chỉ nạp tập được giao và dùng BM25 trên tập đó; không dùng thống kê FTS toàn kho để xếp hạng lịch sử. Raw hash được kiểm khi tạo index và khi mở đoạn/trang, không đọc toàn bộ raw ở mỗi request.

Thiên lệch nguồn, phân bố năm/ngành và selection vẫn tồn tại. Nhãn chuyên mục và liên kết 13 mã trong cấu hình chưa được người độc lập duyệt. `MARKET` là bối cảnh chưa gắn một trong 13 mã, không phải kết luận bài không nhắc doanh nghiệp khác. Chưa dedup ngữ nghĩa giữa các báo; chưa có protocol/split/gold đóng băng hoặc full agents/graph/memory/backtest.

Python 3.11 cũ trên máy bị Windows Application Control chặn khởi chạy. Tạo `.venv312` riêng từ runtime Python {platform.python_version()} có sẵn, không tắt bảo vệ hoặc sửa `.venv` cũ. Giữ các phiên bản dependency đã khóa; pilot LLM cũ thuộc môi trường cũ, không gộp số đo hiệu năng.

Xem [quy trình nhập và chạy lại](../../../docs/research/13-large-corpus-v05.md).
"""
    (metadata / "DATA_CARD.md").write_text(card, encoding="utf-8", newline="\n")
    write(metadata / "release.json", {"release_id": release_id, "summary_sha256": pointer["summary_sha256"],
                                      "registry_index_sha256": file_sha(metadata / "registry_index.jsonl.gz"),
                                      "source_config_sha256": verification["source_config_sha256"],
                                      "configured_records": summary["configured_documents"], "active_documents": stats["documents"],
                                      "dataset_articles": len(mirror_dates), "research_prediction_results": False})
    if args.publish:
        args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
        args.activate.parent.mkdir(parents=True, exist_ok=True)
        # Resolved source/destination paths were checked above; no overwrite or recursive delete.
        os.rename(metadata, args.metadata_output)
        os.rename(snapshot, args.activate)
    print(json.dumps({"stage": "published" if args.publish else "verified_preview", **stats,
                      "metadata_output": str(args.metadata_output), "snapshot": str(args.activate)}), flush=True)


if __name__ == "__main__":
    main()
