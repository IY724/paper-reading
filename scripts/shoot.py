#!/usr/bin/env python3
"""Headless-browser screenshots of the deliverable at named anchors.

Headless --screenshot does not repaint tiles outside the initial viewport, so
scrolling to a fragment yields blank images. Instead a sibling temp copy shifts
the body up by the anchor offset (clamped like a real scroll), keeping the target
inside the rasterised viewport. The copy sits next to the source so any
not-yet-inlined relative assets still resolve.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
]
FIX = ('<style id="_shotfix">html{scroll-behavior:auto!important}'
       '*,*::before,*::after{animation:none!important;transition:none!important}'
       '.sectionnav{position:fixed!important;left:0;right:0;top:0}'
       '</style>\n</head>')
SHIFT = """<script id="_shotshift">
(function(){
  var h = decodeURIComponent(location.hash.slice(1));
  if (!h) return;
  var el = document.getElementById(h);
  if (!el) return;
  var y = el.getBoundingClientRect().top + window.scrollY - 56;
  var max = document.documentElement.scrollHeight - window.innerHeight;
  y = Math.max(0, Math.min(y, max));
  document.body.style.position = 'relative';
  document.body.style.top = (-y) + 'px';
})();
</script>
</body>"""


def find_browser(explicit):
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    for p in CANDIDATES:
        if os.path.isfile(p):
            return p
    return shutil.which("msedge") or shutil.which("chrome") or shutil.which("chromium")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--at", default="", help="comma separated anchors, e.g. p01,s3,overview")
    ap.add_argument("--size", default="1400x2200", help="viewport WxH")
    ap.add_argument("--out", default="_shots")
    ap.add_argument("--wait", type=int, default=6000, help="virtual time budget ms")
    ap.add_argument("--browser", default="")
    a = ap.parse_args()

    src = os.path.abspath(a.html)
    if not os.path.isfile(src):
        print("FAIL no such html: " + src)
        return 2
    browser = find_browser(a.browser)
    if not browser:
        print("FAIL no Edge/Chrome found; pass --browser <path>")
        return 2
    try:
        w, h = (int(v) for v in a.size.lower().split("x"))
    except ValueError:
        print("FAIL --size must look like 1400x2200")
        return 2

    with open(src, encoding="utf-8") as fh:
        html = fh.read()
    if "</head>" not in html or "</body>" not in html:
        print("FAIL html has no </head> or </body>")
        return 2
    tmp_html = os.path.join(os.path.dirname(src),
                            os.path.splitext(os.path.basename(src))[0] + "._shot.html")
    with open(tmp_html, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html.replace("</head>", FIX, 1).replace("</body>", SHIFT, 1))

    outdir = os.path.abspath(a.out)
    os.makedirs(outdir, exist_ok=True)
    if w < 600:
        print("WARN headless clamps layout width below ~500px; a %dpx request may crop. "
              "Use --size 600x... or browser-use MCP mobile emulation for phone widths." % w)
    profile = tempfile.mkdtemp(prefix="annot-shot-")
    anchors = [s.strip().lstrip("#") for s in a.at.split(",") if s.strip()] or [""]
    url_base = "file:///" + tmp_html.replace("\\", "/")
    ok, bad = 0, []
    try:
        for anchor in anchors:
            name = "%s_%dx%d.png" % (anchor or "top", w, h)
            dest = os.path.join(outdir, name)
            if os.path.exists(dest):
                os.remove(dest)
            cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                   "--force-device-scale-factor=1", "--no-first-run",
                   "--no-default-browser-check", "--disable-extensions",
                   "--user-data-dir=" + profile,
                   "--virtual-time-budget=%d" % a.wait,
                   "--window-size=%d,%d" % (w, h),
                   "--screenshot=" + dest,
                   url_base + ("#" + anchor if anchor else "")]
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=120)
            except subprocess.TimeoutExpired:
                bad.append(name + "(timeout)")
                continue
            if os.path.isfile(dest) and os.path.getsize(dest) > 1000:
                blank = ""
                try:
                    from PIL import Image
                    thumb = Image.open(dest).convert("RGB").resize((24, 24))
                    if len(set(thumb.getdata())) <= 2:
                        blank = "  WARN looks blank"
                except Exception:
                    pass
                print("OK %-24s %6.0f KB %dx%d%s"
                      % (name, os.path.getsize(dest) / 1024, w, h, blank))
                ok += 1
            else:
                tail = (r.stderr or b"").decode("utf-8", "replace").strip().splitlines()
                bad.append(name + ("(" + tail[-1][:120] + ")" if tail else "(no file)"))
            time.sleep(0.2)
    finally:
        for path, isdir in ((tmp_html, False), (profile, True)):
            try:
                shutil.rmtree(path, ignore_errors=True) if isdir else os.remove(path)
            except OSError:
                pass

    print("OK %d/%d screenshots -> %s" % (ok, len(anchors), outdir))
    if bad:
        print("FAIL " + "; ".join(bad))
    return 0 if ok == len(anchors) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("FAIL %s: %s" % (type(exc).__name__, exc))
        sys.exit(1)