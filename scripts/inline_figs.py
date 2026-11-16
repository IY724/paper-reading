#!/usr/bin/env python3
"""Inline figure files into a single self-contained HTML deliverable."""
import argparse
import base64
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SRC = re.compile(r"""(?P<pre><img\b[^>]*?\bsrc=")(?P<val>[^"]+)(?P<post>")""", re.I)
TOKEN = re.compile(r"""(?P<pre><img\b[^>]*?\bdata-fig=")(?P<val>[^"]+)(?P<post>")""", re.I)


def encode(path, max_width, quality, fmt):
    from PIL import Image
    raw = os.path.getsize(path)
    im = Image.open(path)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    if max_width and im.width > max_width:
        im = im.resize((max_width, max(1, round(im.height * max_width / im.width))),
                       Image.LANCZOS)
    choice = fmt
    if fmt == "auto":
        choice = "jpeg" if (raw > 100_000 or im.width > 700) else "png"
    buf = io.BytesIO()
    if choice == "jpeg":
        im.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
        mime = "image/jpeg"
    else:
        im.save(buf, "PNG", optimize=True)
        mime = "image/png"
    data = buf.getvalue()
    return "data:%s;base64,%s" % (mime, base64.b64encode(data).decode("ascii")), \
        choice, im.width, im.height, raw, len(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--figs", default="figs")
    ap.add_argument("--out", default="", help="default: overwrite input")
    ap.add_argument("--max-width", type=int, default=1000)
    ap.add_argument("--quality", type=int, default=82)
    ap.add_argument("--format", choices=["auto", "jpeg", "png"], default="auto")
    a = ap.parse_args()

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("FAIL pillow missing. Install: python -m pip install pillow")
        return 2
    if not os.path.isfile(a.html):
        print("FAIL no such html: " + a.html)
        return 2

    with open(a.html, encoding="utf-8") as fh:
        html = fh.read()

    cache, report, missing = {}, [], []

    def resolve(val):
        key = val.strip()
        if key.startswith("data:"):
            return None
        name = os.path.basename(key)
        stem = os.path.splitext(name)[0]
        cand = [key, os.path.join(a.figs, name), os.path.join(a.figs, stem + ".png"),
                os.path.join(a.figs, stem + ".jpg"), os.path.join(a.figs, stem + ".jpeg")]
        path = next((p for p in cand if os.path.isfile(p)), None)
        if path is None:
            missing.append(val)
            return None
        if path not in cache:
            cache[path] = encode(path, a.max_width, a.quality, a.format)
        return cache[path][0]

    def sub_token(m):
        uri = resolve(m.group("val"))
        if uri is None:
            return m.group(0)
        return m.group("pre").replace("data-fig=", "src=") + uri + m.group("post")

    def sub_src(m):
        uri = resolve(m.group("val"))
        return m.group(0) if uri is None else m.group("pre") + uri + m.group("post")

    html = TOKEN.sub(sub_token, html)
    html = SRC.sub(sub_src, html)

    out = a.out or a.html
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)

    for path, (uri, choice, w, h, raw, size) in cache.items():
        report.append((os.path.basename(path), choice, w, h, raw, size))
    for name, choice, w, h, raw, size in sorted(report):
        print("%-14s %-4s %4dx%-4d %6.0f KB -> %6.0f KB"
              % (name, choice, w, h, raw / 1024, size / 1024))

    leftover = re.findall(r'\bsrc="(?!data:)([^"]+)"', html)
    tokens = re.findall(r"\{\{[^}]{0,60}\}\}", html)
    print("OK %d images inlined, %.2f MB -> %s"
          % (len(cache), os.path.getsize(out) / 1048576, os.path.abspath(out)))
    if missing:
        print("FAIL unresolved image refs: " + ", ".join(sorted(set(missing))))
    if leftover:
        print("FAIL still external: " + ", ".join(sorted(set(leftover))[:10]))
    if tokens:
        print("FAIL unfilled placeholders: " + ", ".join(sorted(set(tokens))[:10]))
    return 1 if (missing or leftover or tokens) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("FAIL %s: %s" % (type(exc).__name__, exc))
        sys.exit(1)