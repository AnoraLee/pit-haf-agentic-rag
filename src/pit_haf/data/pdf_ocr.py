"""Bounded OCR sidecars, separate from original PDF text and reviewed financial facts."""

import csv
import importlib.metadata
import io
import json
import math
import os
import subprocess
import sys
import urllib.request

import pdfplumber
from PIL import Image

from pit_haf.data.hub import file_sha
from pit_haf.llm.ollama import sha256

PROFILE = "configs/pdf_ocr_v0_1.json"
REGION_PROFILE = "configs/pdf_ocr_v0_2.json"
PROFILES = {"pdf_ocr_preview_v0.1": PROFILE, "pdf_ocr_region_v0.2": REGION_PROFILE,
            "pdf_ocr_sparse_v0.3": "configs/pdf_ocr_v0_3.json"}
MODEL_DIR = "data/cache/ocr/tessdata-fast-8741641"
MODEL_REVISION = "87416418657359cb625c412a48b6e1d6d41c29bd"
MODEL_HASHES = {"vie": "79df64caf7bcfb2a27df5042ecb6121e196eada34da774956995747636d5bfa1",
                "eng": "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2"}


def settings(root, profile_id="pdf_ocr_preview_v0.1"):
    if profile_id not in PROFILES:
        raise ValueError("Unknown OCR profile")
    data = json.loads((root / PROFILES[profile_id]).read_text(encoding="utf-8"))
    expected = {"profile_id": "pdf_ocr_preview_v0.1", "status": "development_not_frozen",
                "tesserocr_version": "2.12.0", "tesseract_version": "tesseract 5.5.3",
                "languages": "vie+eng", "psm": 3, "oem": 1, "dpi": 180, "max_pages": 4,
                "max_pdf_bytes": 128 * 1024 * 1024, "max_render_pixels": 8000000,
                "max_words_per_page": 8000, "page_timeout_seconds": 60, "omp_thread_limit": 1,
                "low_confidence_threshold": 80, "human_review_required": True, "automatic_facts": False,
                "models_revision": MODEL_REVISION, "models": MODEL_HASHES}
    if profile_id in ("pdf_ocr_region_v0.2", "pdf_ocr_sparse_v0.3"):
        expected.update(profile_id=profile_id, dpi=240, psm=6, max_pages=1, require_region=True)
    if profile_id == "pdf_ocr_sparse_v0.3":
        expected["psm"] = 11
    if data != expected:
        raise ValueError("Unknown OCR profile, models or budget")
    return data


def model_directory(root, *, download=False):
    folder = root / MODEL_DIR
    if not folder.resolve().is_relative_to(root.resolve()) or folder.is_symlink():
        raise ValueError("OCR model cache must stay in the project")
    if download:
        folder.mkdir(parents=True, exist_ok=True)
    for lang, digest in MODEL_HASHES.items():
        target = folder / (lang + ".traineddata")
        if target.is_symlink():
            raise ValueError("OCR model must not be a symlink")
        if not target.exists() and download:
            url = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{MODEL_REVISION}/{lang}.traineddata"
            with urllib.request.urlopen(url, timeout=40) as response:
                payload = response.read(15 * 1024 * 1024)
            if len(payload) >= 15 * 1024 * 1024 or sha256(payload) != digest:
                raise ValueError("Downloaded OCR model checksum/size mismatch")
            target.write_bytes(payload)
        if not target.is_file() or file_sha(target) != digest:
            raise ValueError("Missing/changed OCR model; run ocr-preview --setup-models")
    return folder


def validate_pages(numbers, maximum=4):
    if (not 1 <= len(numbers) <= maximum or any(type(n) is not int or not 1 <= n <= 10000 for n in numbers) or
            len(set(numbers)) != len(numbers)):
        raise ValueError(f"OCR requires 1–{maximum} distinct positive PDF page numbers")
    return sorted(numbers)


def validate_region(region, profile):
    if not profile.get("require_region"):
        if region is not None:
            raise ValueError("A region requires the versioned region OCR profile")
        return None
    if (not isinstance(region, (list, tuple)) or len(region) != 4 or
            any(type(v) not in (int, float) or not math.isfinite(v) for v in region) or
            not (0 <= region[0] < region[2] <= 1 and 0 <= region[1] < region[3] <= 1) or
            region[2] - region[0] < .01 or region[3] - region[1] < .01):
        raise ValueError("OCR region requires x0,y0,x1,y1 fractions in [0,1] with positive area")
    return list(region)


def region_pixels(region, width, height):
    return [math.floor(region[0] * width), math.floor(region[1] * height),
            math.ceil(region[2] * width), math.ceil(region[3] * height)]


def crop_input(png, geometry):
    with Image.open(io.BytesIO(png)) as image:
        cropped = image.crop(geometry["ocr_crop_pixels"])
        output = io.BytesIO()
        cropped.save(output, format="PNG")
        return output.getvalue()


def render_page(payload, digest, number, profile, region=None):
    region = validate_region(region, profile)
    if sha256(payload) != digest or len(payload) > profile["max_pdf_bytes"]:
        raise ValueError("OCR raw PDF checksum/byte budget mismatch")
    if type(number) is not int or number < 1:
        raise ValueError("Invalid OCR page number")
    with pdfplumber.open(io.BytesIO(payload)) as pdf:
        if number > len(pdf.pages):
            raise ValueError("OCR page is outside the PDF")
        page = pdf.pages[number - 1]
        width, height = float(page.width), float(page.height)
        pixels = math.ceil(width * profile["dpi"] / 72) * math.ceil(height * profile["dpi"] / 72)
        if not 0 < pixels <= profile["max_render_pixels"]:
            raise ValueError("OCR image pixel budget exceeded")
        image = page.to_image(resolution=profile["dpi"], antialias=True).original.convert("RGB")
        if image.width * image.height > profile["max_render_pixels"]:
            raise ValueError("OCR image pixel budget exceeded")
        output = io.BytesIO()
        image.save(output, format="PNG")
        geometry = {"page": number, "pdf_width": width, "pdf_height": height,
                    "rotation": page.rotation, "image_width": image.width,
                    "image_height": image.height, "dpi": profile["dpi"]}
        if region is not None:
            geometry.update(ocr_region_normalized=region, ocr_crop_pixels=region_pixels(region, image.width, image.height))
        return output.getvalue(), geometry


def parse_tsv(text, geometry, profile):
    columns = ("level", "page_num", "block_num", "par_num", "line_num", "word_num", "left", "top",
               "width", "height", "conf", "text")
    first = text.split("\n", 1)[0].rstrip("\r").split("\t")
    # GetTSVText returns the raw page rows; the command-line TSV writer adds a header.
    if first == list(columns):
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    elif len(first) == len(columns) and first[:2] == ["1", "1"]:
        reader = csv.DictReader(io.StringIO(text), delimiter="\t", fieldnames=columns)
    else:
        raise ValueError("Invalid OCR TSV columns")
    words = []
    iw, ih = geometry["image_width"], geometry["image_height"]
    if (type(iw) is not int or type(ih) is not int or min(iw, ih) <= 0 or
            iw * ih > profile["max_render_pixels"] or
            any(not math.isfinite(geometry[k]) or geometry[k] <= 0 for k in ("pdf_width", "pdf_height"))):
        raise ValueError("Invalid OCR image geometry")
    crop = geometry.get("ocr_crop_pixels", [0, 0, iw, ih])
    if profile.get("require_region"):
        region = validate_region(geometry.get("ocr_region_normalized"), profile)
        if crop != region_pixels(region, iw, ih):
            raise ValueError("OCR crop geometry differs from requested region")
    elif "ocr_crop_pixels" in geometry or "ocr_region_normalized" in geometry:
        raise ValueError("Legacy OCR geometry must not contain a region")
    cw, ch = crop[2] - crop[0], crop[3] - crop[1]
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Malformed OCR TSV row")
        if int(row["level"]) != 5 or not row["text"].strip():
            continue
        if len(words) >= profile["max_words_per_page"]:
            raise ValueError("OCR word budget exceeded")
        x, y, w, h = (int(row[k]) for k in ("left", "top", "width", "height"))
        confidence = float(row["conf"])
        if (int(row["page_num"]) != 1 or any(int(row[k]) < 1 for k in ("block_num", "par_num", "line_num", "word_num")) or
                not math.isfinite(confidence) or not 0 <= confidence <= 100 or
                not (0 <= x < x + w <= cw and 0 <= y < y + h <= ch)):
            raise ValueError("OCR word confidence/geometry is invalid")
        original_bbox = [x, y, x + w, y + h]
        x, y = x + crop[0], y + crop[1]
        words.append({"id": f"W{len(words) + 1}", "text": row["text"], "confidence": confidence,
                      "low_confidence": confidence < profile["low_confidence_threshold"],
                      "bbox_pixels": [x, y, x + w, y + h],
                      "bbox_pdf": [round(v * size / total, 4) for v, size, total in (
                          (x, geometry["pdf_width"], iw), (y, geometry["pdf_height"], ih),
                          (x + w, geometry["pdf_width"], iw), (y + h, geometry["pdf_height"], ih))],
                      "reading_order": {k: int(row[k]) for k in ("block_num", "par_num", "line_num", "word_num")},
                      "origin": "ocr_unreviewed", "human_reviewed": False})
        if profile.get("require_region"):
            words[-1]["bbox_ocr_pixels"] = original_bbox
    return words


def run_worker(root, raw_path, digest, number, destination, profile, region=None):
    try:
        if importlib.metadata.version("tesserocr") != profile["tesserocr_version"]:
            raise ValueError("OCR package version differs from the profile")
    except importlib.metadata.PackageNotFoundError as exc:
        raise ValueError("OCR optional dependency missing; install the ocr extra") from exc
    model_directory(root)  # No network access during extraction.
    command = [sys.executable, "-X", "utf8", "-m", "pit_haf.data.pdf_ocr_worker", "--root", str(root),
               "--pdf", str(raw_path), "--sha256", digest, "--page", str(number), "--output", str(destination),
               "--profile", profile["profile_id"]]
    selected_region = validate_region(region, profile)
    if selected_region is not None:
        command.extend(["--region", *[str(v) for v in selected_region]])
    environment = {**os.environ, "OMP_THREAD_LIMIT": str(profile["omp_thread_limit"])}
    try:
        completed = subprocess.run(command, timeout=profile["page_timeout_seconds"], env=environment,
                                   capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as exc:
        (destination / "worker.stderr").write_bytes(exc.stderr or b"")
        (destination / "worker.stdout").write_bytes(exc.stdout or b"")
        raise ValueError("OCR page timed out; partial artifacts kept, no retry") from exc
    (destination / "worker.stderr").write_bytes(completed.stderr)
    (destination / "worker.stdout").write_bytes(completed.stdout)
    if completed.returncode:
        raise ValueError(f"OCR worker failed (exit {completed.returncode}); inspect saved diagnostics")
    return json.loads((destination / "page.json").read_text(encoding="utf-8"))
