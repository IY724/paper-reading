#!/usr/bin/env python3
"""Locate figure captions in a PDF and crop the artwork above each caption.

Renders page regions instead of pulling embedded bitmaps: journals often store
one image per sub-panel plus masks, so raw extraction yields duplicates and
fragments. Cropping the rendered region keeps vector art and labels intact.
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CAPTION = re.compile(r"^(Figure|Fig\.|Table|TABLE)\s*(\d+)\s*[.:|\u2014\u2013]\s")
CAPTION_LOOSE = re.compile(r"^(Figure|Fig\.|Table|TABLE)\s*(\d+)\s*[.:|]?\s")
PROSE_MIN = 60


def caption_lines(page, loose=False):
    """Return [(number, kind, fitz.Rect)] for every caption paragraph."""
    import fitz
    pattern = CAPTION_LOOSE if loose else CAPTION
    lines = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            text = "".join(s["text"] for s in line["spans"]).strip()
            lines.append((fitz.Rect(line["bbox"]), text))
    lines.sort(key=lambda t: (round(t[0].y0, 1), t[0].x0))

    out, used = [], set()
    for i, (rect, text) in enumerate(lines):
        m = pattern.match(text)
        if not m or i in used:
            continue
        kind = "table" if m.group(1).lower() == "table" else "figure"
        box = fitz.Rect(rect)
        used.add(i)
        for j in range(i + 1, min(i + 5, len(lines))):
            nxt, ntext = lines[j]
            if j in used or pattern.match(ntext):
                break
            if abs(nxt.x0 - rect.x0) > 14 or nxt.y0 - box.y1 > 5 or not ntext:
                break
            box |= nxt
            used.add(j)
        out.append((int(m.group(2)), kind, box))
    return out


def body_prose_bottom(page, top, bottom, x0, x1):
    """Lowest prose line above the caption; used when a figure is pure vector."""
    import fitz
    best = None
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            text = "".join(s["text"] for s in line["spans"]).strip()
            r = fitz.Rect(line["bbox"])
            if r.y1 > bottom or r.y0 < top or r.x1 < x0 or r.x0 > x1:
                continue
            if len(text) >= PROSE_MIN or re.search(r"[.。;:]\s*$", text):
                if best is None or r.y1 > best:
                    best = r.y1
    return best


def propose(page, caps, kind):
    """One crop rect per caption, anchored on image bboxes when present."""
    import fitz
    pr = page.rect
    imgs = []
    for info in page.get_image_info():
        r = fitz.Rect(info["bbox"])
        if r.y0 < -2 or r.y1 > pr.height + 2 or r.x0 < -2 or r.x1 > pr.width + 2:
            continue
        if r.width * r.height < 2500:
            continue
        imgs.append(r)

    plans, prev_bottom = [], 34.0
    for num, k, cap in caps:
        if kind != "both" and k != kind:
            continue
        lower = cap.y0 - 3
        hits = [r for r in imgs if r.y1 <= lower + 2 and r.y0 >= prev_bottom - 2]
        if hits:
            box = fitz.Rect(hits[0])
            for r in hits[1:]:
                box |= r
            basis = "images"
        else:
            prose = body_prose_bottom(page, prev_bottom, lower, cap.x0 - 20, cap.x1 + 20)
            top = (prose + 7) if prose is not None else (prev_bottom + 6)
            box = fitz.Rect(cap.x0 - 12, top, cap.x1 + 12, lower)
            basis = "prose" if prose is not None else "gap"
        box = fitz.Rect(min(box.x0, cap.x0 - 12), box.y0 - 4,
                        max(box.x1, cap.x1 + 12), lower)
        box &= pr
        prev_bottom = cap.y1
        if box.height < 12 or box.width < 24:
            basis += "/TOO-SMALL"
        plans.append({"id": "%s%02d" % ("fig" if k == "figure" else "tab", num),
                      "page": page.number + 1, "kind": k, "basis": basis,
                      "rect": [round(v, 1) for v in box],
                      "caption": cap})
    return plans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", default="figs")
    ap.add_argument("--dpi", type=int, default=220)
    ap.add_argument("--kind", choices=["figure", "table", "both"], default="figure")
    ap.add_argument("--list", action="store_true", help="report proposals, render nothing")
    ap.add_argument("--page-shots", action="store_true",
                    help="also render whole pages (110 dpi) into <out>/pages for eyeballing")
    ap.add_argument("--only", default="", help="comma separated ids, e.g. fig03,fig19")
    ap.add_argument("--loose", action="store_true",
                    help="also accept captions without punctuation (more false positives)")
    ap.add_argument("--rect", action="append", default=[],
                    help="override: figNN=page:x0,y0,x1,y1 (repeatable)")
    a = ap.parse_args()

    try:
        import fitz
    except ImportError:
        print("FAIL pymupdf missing. Install: python -m pip install pymupdf")
        return 2
    if not os.path.isfile(a.pdf):
        print("FAIL no such pdf: " + a.pdf)
        return 2

    overrides = {}
    for item in a.rect:
        m = re.fullmatch(r"(\w+)=(\d+):([\d.,\-]+)", item.strip())
        if not m:
            print("FAIL bad --rect, expected figNN=page:x0,y0,x1,y1 got " + item)
            return 2
        nums = [float(v) for v in m.group(3).split(",")]
        if len(nums) != 4:
            print("FAIL --rect needs exactly 4 coordinates: " + item)
            return 2
        overrides[m.group(1)] = (int(m.group(2)), fitz.Rect(nums))

    doc = fitz.open(a.pdf)
    plans = []
    for page in doc:
        plans.extend(propose(page, caption_lines(page, a.loose), a.kind))
    plans.sort(key=lambda p: (p["page"], p["rect"][1]))
    if not plans:
        print("WARN no captions matched. Try --loose, or --kind both, "
              "or supply --rect figNN=page:x0,y0,x1,y1 manually.")

    seen = {}
    for p in plans:
        if p["id"] in seen:
            p["dup"] = True
        seen.setdefault(p["id"], p)

    only = {s.strip() for s in a.only.split(",") if s.strip()}
    for key, (pageno, rect) in overrides.items():
        plans.append({"id": key, "page": pageno, "kind": "override",
                      "basis": "manual", "rect": [round(v, 1) for v in rect]})

    if a.list:
        for p in plans:
            if only and p["id"] not in only:
                continue
            r = p["rect"]
            print("%s p%-3d %-8s [%7.1f %7.1f %7.1f %7.1f] %5.0fx%-5.0f%s"
                  % (p["id"], p["page"], p["basis"], r[0], r[1], r[2], r[3],
                     r[2] - r[0], r[3] - r[1], "  DUP" if p.get("dup") else ""))
        print("OK %d captions proposed (nothing rendered)" % len(plans))
        doc.close()
        return 0

    os.makedirs(a.out, exist_ok=True)
    written, skipped = [], []
    for p in plans:
        if only and p["id"] not in only:
            continue
        if p.get("dup"):
            skipped.append(p["id"] + "(dup)")
            continue
        rect = fitz.Rect(p["rect"])
        if rect.height < 12 or rect.width < 24:
            skipped.append(p["id"] + "(empty)")
            continue
        page = doc[p["page"] - 1]
        pix = page.get_pixmap(clip=rect, dpi=a.dpi, alpha=False)
        path = os.path.join(a.out, p["id"] + ".png")
        pix.save(path)
        written.append((p["id"], pix.width, pix.height, os.path.getsize(path)))

    if a.page_shots:
        pdir = os.path.join(a.out, "pages")
        os.makedirs(pdir, exist_ok=True)
        for pageno in sorted({p["page"] for p in plans if not only or p["id"] in only}):
            pix = doc[pageno - 1].get_pixmap(dpi=110, alpha=False)
            pix.save(os.path.join(pdir, "page%02d.png" % pageno))
        print("OK page previews -> " + os.path.abspath(pdir))

    with open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump([{k: v for k, v in p.items() if k != "caption"} for p in plans],
                  fh, ensure_ascii=False, indent=1)
    doc.close()

    for wid, w, h, size in written:
        print("%s %4dx%-4d %6.0f KB" % (wid, w, h, size / 1024))
    print("OK %d figures -> %s (%d dpi)" % (len(written), os.path.abspath(a.out), a.dpi))
    if skipped:
        print("WARN skipped: " + ", ".join(skipped))
    small = [w for w in written if w[1] < 300 or w[2] < 120]
    if small:
        print("WARN suspiciously small, verify and override with --rect: "
              + ", ".join(w[0] for w in small))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("FAIL %s: %s" % (type(exc).__name__, exc))
        sys.exit(1)