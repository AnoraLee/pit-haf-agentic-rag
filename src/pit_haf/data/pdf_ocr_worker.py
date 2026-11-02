"""One bounded native OCR process; invoked by the parent only after source authorization."""

import argparse
import io
import json
from pathlib import Path

from PIL import Image

from pit_haf.data.hub import file_sha
from pit_haf.data.pdf_ocr import crop_input, model_directory, parse_tsv, render_page, settings
from pit_haf.llm.ollama import write_json


def main():
    import tesserocr

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", default="pdf_ocr_preview_v0.1")
    parser.add_argument("--region", type=float, nargs=4)
    args = parser.parse_args()
    profile = settings(args.root, args.profile)
    version = tesserocr.tesseract_version()
    if version.splitlines()[0] != profile["tesseract_version"]:
        raise ValueError("Tesseract engine version differs from the OCR profile")
    png, geometry = render_page(args.pdf.read_bytes(), args.sha256, args.page, profile, region=args.region)
    (args.output / "page.png").write_bytes(png)
    ocr_png = crop_input(png, geometry) if profile.get("require_region") else png
    if profile.get("require_region"):
        (args.output / "ocr-input.png").write_bytes(ocr_png)
    with tesserocr.PyTessBaseAPI(path=str(model_directory(args.root)), lang=profile["languages"],
                                psm=profile["psm"], oem=profile["oem"]) as api:
        with Image.open(io.BytesIO(ocr_png)) as image:
            api.SetImage(image)
            api.SetSourceResolution(profile["dpi"])
            api.Recognize()
            text = api.GetUTF8Text()
            tsv = api.GetTSVText(0)
    (args.output / "page.txt").write_bytes(text.encode("utf-8"))
    (args.output / "page.tsv").write_bytes(tsv.encode("utf-8"))
    words = parse_tsv(tsv, geometry, profile)
    result = {"geometry": geometry, "words": words,
               "text_sha256": file_sha(args.output / "page.txt"), "tsv_sha256": file_sha(args.output / "page.tsv"),
               "image_sha256": file_sha(args.output / "page.png"), "engine": version,
               "tesserocr_version": tesserocr.__version__, "ocr_performed": True,
               "word_count": len(words), "low_confidence_words": sum(w["low_confidence"] for w in words),
              "semantic_support": "not_assessed", "human_reviewed_facts": 0}
    if profile.get("require_region"):
        result["ocr_input_sha256"] = file_sha(args.output / "ocr-input.png")
    write_json(args.output / "page.json", result)
    print(json.dumps({"page": args.page, "words": len(words)}))


if __name__ == "__main__":
    main()
