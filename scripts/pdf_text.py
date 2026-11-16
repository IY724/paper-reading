#!/usr/bin/env python3
"""Extract per-page text from a PDF for paragraph-by-paragraph annotation."""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

LIGATURES = {
    "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi",
    "\ufb04": "ffl", "\ufb05": "ft", "\ufb06": "st", "\u00ad": "",
    "\u2010": "-", "\u2011": "-", "\u2212": "-",
}


def clean(text):
    for bad, good in LIGATURES.items():
        text = text.replace(bad, good)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", default="_work", help="output directory (default _work)")
    ap.add_argument("--pages", default="", help="1-based inclusive range, e.g. 3-9")
    ap.add_argument("--peek", type=int, default=0, help="print first N chars of each page")
    a = ap.parse_args()

    try:
        import fitz
    except ImportError:
        print("FAIL pymupdf missing. Install: python -m pip install pymupdf")
        return 2
    if not os.path.isfile(a.pdf):
        print("FAIL no such pdf: " + a.pdf)
        return 2

    doc = fitz.open(a.pdf)
    first, last = 1, len(doc)
    if a.pages:
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", a.pages.strip())
        if not m:
            print("FAIL --pages must look like 3 or 3-9")
            return 2
        first = int(m.group(1))
        last = int(m.group(2) or m.group(1))
    first, last = max(1, first), min(len(doc), last)

    os.makedirs(a.out, exist_ok=True)
    txt_path = os.path.join(a.out, "text.txt")
    pages, total = [], 0
    with open(txt_path, "w", encoding="utf-8", newline="\n") as fh:
        for i in range(first - 1, last):
            page = doc[i]
            text = clean(page.get_text("text"))
            fh.write("\n===== PAGE %d =====\n" % (i + 1))
            fh.write(text)
            pages.append({"page": i + 1, "chars": len(text),
                          "width": round(page.rect.width, 1),
                          "height": round(page.rect.height, 1),
                          "images": len(page.get_image_info())})
            total += len(text)
            if a.peek:
                print("--- page %d (%d chars)" % (i + 1, len(text)))
                print(text[:a.peek])

    meta = {"pdf": os.path.abspath(a.pdf), "page_count": len(doc),
            "extracted": [first, last], "chars": total, "pages": pages}
    with open(os.path.join(a.out, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)
    doc.close()

    empty = [p["page"] for p in pages if p["chars"] < 40]
    print("OK pages %d-%d of %d, %d chars" % (first, last, meta["page_count"], total))
    print("OK wrote " + os.path.abspath(txt_path))
    if empty:
        print("WARN near-empty pages (likely scanned, need OCR): "
              + ", ".join(str(p) for p in empty))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("FAIL %s: %s" % (type(exc).__name__, exc))
        sys.exit(1)