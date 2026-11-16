#!/usr/bin/env python3
"""Structural validator for the dual-column annotated HTML deliverable."""
import argparse
import os
import re
import sys
from collections import Counter
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}
MARKS = {"t", "r", "b", "g", "p"}
NOTE_CLASSES = {"c-thesis", "c-concept", "c-evidence", "c-concession", "c-method"}
DIM_OF = {"c-thesis": "t", "c-concept": "r", "c-evidence": "b",
          "c-concession": "g", "c-method": "p"}


class Node:
    def __init__(self, tag, attrs, line):
        self.tag = tag
        self.attrs = dict(attrs)
        self.line = line
        self.kids = []
        self.parent = None

    @property
    def cls(self):
        return set((self.attrs.get("class") or "").split())

    def walk(self):
        yield self
        for k in self.kids:
            yield from k.walk()

    def find(self, cls):
        return [n for n in self.walk() if cls in n.cls and n is not self]

    def text(self):
        out = []
        for n in self.walk():
            out.append(n.attrs.get("_text", ""))
        return "".join(out)


class Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", [], 0)
        self.stack = [self.root]
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            node = Node(tag, attrs, self.getpos()[0])
            node.parent = self.stack[-1]
            self.stack[-1].kids.append(node)
            return
        node = Node(tag, attrs, self.getpos()[0])
        node.parent = self.stack[-1]
        self.stack[-1].kids.append(node)
        self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, attrs, self.getpos()[0])
        node.parent = self.stack[-1]
        self.stack[-1].kids.append(node)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                for j in range(len(self.stack) - 1, i - 1, -1):
                    if j > i:
                        self.errors.append("line %d: <%s> never closed (hit </%s>)"
                                           % (self.stack[j].line, self.stack[j].tag, tag))
                del self.stack[i:]
                return
        self.errors.append("line %d: stray </%s>" % (self.getpos()[0], tag))

    def handle_data(self, data):
        # keep text as ordered children so text() returns document order
        parent = self.stack[-1]
        if parent.kids and parent.kids[-1].tag == "#text":
            parent.kids[-1].attrs["_text"] += data
        else:
            node = Node("#text", [("_text", data)], self.getpos()[0])
            node.parent = parent
            parent.kids.append(node)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--min-marks", type=int, default=0,
                    help="fail if fewer than N highlights exist")
    ap.add_argument("--strict-refs", action="store_true",
                    help="promote cited-but-not-rendered 式/表 from WARN to FAIL")
    a = ap.parse_args()
    if not os.path.isfile(a.html):
        print("FAIL no such html: " + a.html)
        return 2

    with open(a.html, encoding="utf-8") as fh:
        raw = fh.read()
    b = Builder()
    b.feed(raw)
    for n in b.stack[1:]:
        b.errors.append("line %d: <%s> never closed at EOF" % (n.line, n.tag))

    fails, warns = list(b.errors), []
    nodes = list(b.root.walk())
    by_tag = Counter(n.tag for n in nodes)

    ids = [n.attrs["id"] for n in nodes if n.attrs.get("id")]
    for name, cnt in Counter(ids).items():
        if cnt > 1:
            fails.append("duplicate id #%s x%d" % (name, cnt))
    idset = set(ids)

    navs = [n for n in nodes if "sectionnav" in n.cls]
    anchors = [k for n in navs for k in n.walk() if k.tag == "a"]
    for link in anchors:
        href = link.attrs.get("href", "")
        if href.startswith("#") and href[1:] not in idset:
            fails.append("nav anchor %s has no target" % href)
    if not navs:
        warns.append("no .sectionnav found")

    rows = [n for n in nodes if n.tag == "article" and "row" in n.cls]
    notes = [n for n in nodes if n.tag == "aside" and "note" in n.cls]
    marks = [n for n in nodes if n.tag == "mark"]
    figs = [n for n in nodes if n.tag == "figure"]
    imgs = [n for n in nodes if n.tag == "img" and "lbimg" not in (n.attrs.get("id") or "")]
    secs = [n for n in nodes if n.tag == "section"]

    marked_rows = 0
    for row in rows:
        rid = row.attrs.get("id") or "line %d" % row.line
        texts = row.find("text")
        rnotes = row.find("note")
        if len(texts) != 1:
            fails.append("%s: expected 1 .text, found %d" % (rid, len(texts)))
        if len(rnotes) != 1:
            fails.append("%s: expected 1 aside.note, found %d" % (rid, len(rnotes)))
            continue
        note = rnotes[0]
        kind = next((c for c in note.cls if c.startswith("c-")), None)
        if kind not in NOTE_CLASSES:
            fails.append("%s: bad note class %r" % (rid, kind))
        pnum = row.find("pnum")
        no = note.find("no")
        left = re.sub(r"\s+", "", pnum[0].text()) if pnum else ""
        right = re.sub(r"\s+", "", no[0].text()) if no else ""
        ln = re.match(r"¶(\d+)", left)
        rn = re.match(r"¶(\d+)", right)
        if not ln or not rn:
            fails.append("%s: missing ¶ number in .pnum or .note-h .no" % rid)
        elif ln.group(1) != rn.group(1):
            fails.append("%s: ¶%s vs note ¶%s mismatch" % (rid, ln.group(1), rn.group(1)))
        dts = [n.text().strip() for n in note.walk() if n.tag == "dt"]
        dds = [n for n in note.walk() if n.tag == "dd"]
        if len(dts) < 3 or len(dds) < 3:
            fails.append("%s: note needs 3 dt/dd pairs (功能/角色/技巧), got %d/%d"
                         % (rid, len(dts), len(dds)))
        if texts and not texts[0].find("zh"):
            warns.append("%s: no .zh translation block" % rid)
        # one highlight per paragraph, its colour = the note's dimension,
        # and the note names the marked fragment in a 标注 line
        row_marks = [n for n in row.walk() if n.tag == "mark"]
        marked_rows += 1 if row_marks else 0
        if len(row_marks) > 1:
            fails.append("%s: %d marks, at most 1 per paragraph" % (rid, len(row_marks)))
        if row_marks:
            want = DIM_OF.get(kind or "")
            m = row_marks[0]
            frag = re.sub(r"\s+", " ", m.text()).strip()
            if want and m.cls != {want}:
                fails.append("%s: mark class %r != note dimension %r"
                             % (rid, sorted(m.cls), want))
            pairs = [(n.tag, re.sub(r"\s+", " ", n.text()).strip())
                     for n in note.walk() if n.tag in ("dt", "dd")]
            hl = [pairs[i + 1][1] for i, (t, x) in enumerate(pairs)
                  if t == "dt" and x == "标注" and i + 1 < len(pairs)]
            if not hl:
                fails.append("%s: marked paragraph has no 标注 line" % rid)
            elif not any(frag and frag in x for x in hl):
                fails.append("%s: 标注 line does not quote the marked fragment %r"
                             % (rid, frag[:40]))

    for m in marks:
        bad = m.cls - MARKS
        if bad or not m.cls:
            fails.append("line %d: mark class must be one of t/r/b/g/p, got %r"
                         % (m.line, sorted(m.cls)))

    for f in figs:
        if not [n for n in f.walk() if n.tag == "figcaption"]:
            fails.append("line %d: figure without figcaption" % f.line)
        if not [n for n in f.walk() if n.tag == "img"]:
            fails.append("line %d: figure without img" % f.line)
        if "rp-fig" not in f.cls:
            caps = [n for n in f.walk() if n.tag == "figcaption"]
            if caps and not [n for n in caps[0].walk() if "fcap-en" in n.cls]:
                warns.append("line %d: body figure has no .fcap-en original caption" % f.line)
    # "note" is reserved for aside.note; reusing it breaks the pairing check
    for n in nodes:
        if "note" in n.cls and n.tag != "aside":
            fails.append("line %d: class \"note\" on <%s> collides with aside.note"
                         % (n.line, n.tag))
    for im in imgs:
        if not im.attrs.get("alt"):
            warns.append("line %d: img without alt" % im.line)

    eqs = [n for n in nodes if "eq" in n.cls]
    tbls = [n for n in nodes if "tbl" in n.cls]
    for e in eqs:
        if not e.attrs.get("data-eq"):
            fails.append("line %d: .eq missing data-eq number" % e.line)
        if not e.find("body") or not [n for n in e.walk() if "num" in n.cls]:
            fails.append("line %d: .eq needs .body and .num" % e.line)
    for t in tbls:
        if not t.attrs.get("data-tbl"):
            fails.append("line %d: .tbl missing data-tbl number" % t.line)
        tags = {n.tag for n in t.walk()}
        for need in ("table", "caption", "thead", "tbody"):
            if need not in tags:
                fails.append("line %d: .tbl missing <%s>" % (t.line, need))
        if not [n for n in t.walk() if n.tag == "th"]:
            fails.append("line %d: .tbl has no header cells" % t.line)

    repro = [n for n in nodes if "repro" in n.cls]
    if repro:
        RP = ["geometry", "mesh", "material", "umat", "solve", "fail", "results", "env"]
        cards = [n for n in nodes if "rp-card" in n.cls]
        seen = [n.attrs.get("data-rp") for n in cards]
        for kind in RP:
            if seen.count(kind) == 0:
                fails.append("repro dossier missing card data-rp=\"%s\"" % kind)
        for dup in sorted({k for k in seen if seen.count(k) > 1}):
            fails.append("repro card data-rp=\"%s\" duplicated" % dup)
        for c in cards:
            dts = [n for n in c.walk() if n.tag == "dt"]
            dds = [n for n in c.walk() if n.tag == "dd"]
            if len(dts) < 2 or len(dds) < 2:
                fails.append("repro card %s needs >=2 dt/dd pairs, got %d/%d"
                             % (c.attrs.get("data-rp"), len(dts), len(dds)))
            if not [n for n in c.walk() if n.tag == "h3"]:
                fails.append("repro card %s has no title" % c.attrs.get("data-rp"))
        steps = [n for n in nodes if "rp-algo" in n.cls]
        nsteps = sum(len([k for k in s.kids if k.tag == "li"]) for s in steps)
        if nsteps < 3:
            fails.append("repro dossier needs an .rp-algo of >=3 steps, got %d" % nsteps)
        gaps = [n for n in nodes if "rp-gaps" in n.cls]
        ngap = sum(len([k for k in g.kids if k.tag == "li"]) for g in gaps)
        if ngap == 0:
            fails.append("repro dossier needs a non-empty .rp-gaps list")
        if "#repro" not in {l.attrs.get("href") for l in anchors}:
            warns.append("repro dossier present but no nav link to #repro")
        rp_links = [n for n in nodes
                    if n.tag == "a" and (n.attrs.get("href") or "").startswith("#")
                    and n.attrs.get("class") != "fig-frame"
                    and n.attrs.get("href") != "#repro"]
        for lk in rp_links:
            href = lk.attrs["href"]
            if href[1:] not in idset:
                fails.append("repro link %s has no target" % href)
        for c in cards:
            kind = c.attrs.get("data-rp")
            if not [n for n in c.walk() if n.tag == "figure"] and \
               not [n for n in c.walk() if n.tag == "a"]:
                warns.append("repro card %s carries no figure or link" % kind)
        print("repro cards %d | algo steps %d | gaps %d | links %d"
              % (len(cards), nsteps, ngap, len(rp_links)))

    plain = re.sub(r"<[^>]+>", " ", raw)
    plain = re.sub(r"\s+", " ", plain)
    ref_eq = {int(v) for v in re.findall(r"(?:式|Equation|Eq\.)\s*\((\d+)\)", plain)}
    # a number followed by % ~ – - or another digit is not a table number:
    # "本表 7%" and "发表 2018-02-08" must not match (backtracking would yield 201)
    ref_tbl = {int(v) for v in re.findall(r"(?<![代示图])表\s*(\d+)(?![\d%~\u2013\u2014-])", plain)}
    ref_tbl |= {int(v) for v in re.findall(r"Table\s+(\d+)(?![\d%~\u2013\u2014-])", plain)}
    have_eq = {int(n.attrs["data-eq"]) for n in eqs if n.attrs.get("data-eq", "").isdigit()}
    have_tbl = {int(n.attrs["data-tbl"]) for n in tbls if n.attrs.get("data-tbl", "").isdigit()}
    miss_eq = sorted(ref_eq - have_eq)
    miss_tbl = sorted(ref_tbl - have_tbl)
    for label, nums in (("式", miss_eq), ("表", miss_tbl)):
        if not nums:
            continue
        msg = ("%s %s is cited in prose but never rendered"
               % (label, ", ".join(str(v) for v in nums)))
        (fails if a.strict_refs else warns).append(msg)

    tokens = re.findall(r"\{\{[^}]{0,60}\}\}", raw)
    if tokens:
        fails.append("unfilled placeholders: " + ", ".join(sorted(set(tokens))[:8]))
    if a.min_marks and len(marks) < a.min_marks:
        fails.append("only %d marks, expected >= %d" % (len(marks), a.min_marks))
    if not [n for n in nodes if "overview" in n.cls]:
        warns.append("no .overview argument summary")
    if not [n for n in nodes if "lightbox" in n.cls]:
        warns.append("no .lightbox image zoom")
    if len(imgs) < len(figs):
        fails.append("fewer img (%d) than figure (%d)" % (len(imgs), len(figs)))

    print("rows %d | notes %d | figures %d | imgs %d | marks %d | sections %d | nav %d"
          % (len(rows), len(notes), len(figs), len(imgs), len(marks), len(secs), len(anchors)))
    print("marks by dim: " + " ".join("%s=%d" % (k, sum(1 for m in marks if k in m.cls))
                                      for k in "trbgp"))
    print("highlight density: %d marks over %d/%d rows (one per paragraph max)"
          % (len(marks), marked_rows, len(rows)))
    print("notes by dim: " + " ".join(
        "%s=%d" % (k, sum(1 for n in notes if k in n.cls)) for k in sorted(NOTE_CLASSES)))
    print("tags: " + " ".join("%s=%d" % (t, by_tag[t])
                              for t in ("div", "section", "article", "aside", "figure", "p")))
    print("equations %d rendered / %d cited | tables %d rendered / %d cited"
          % (len(have_eq), len(ref_eq), len(have_tbl), len(ref_tbl)))
    print("size %.2f MB" % (os.path.getsize(a.html) / 1048576))
    for w in warns[:10]:
        print("WARN " + w)
    if fails:
        for f in fails[:15]:
            print("FAIL " + f)
        print("FAIL %d problem(s)" % len(fails))
        return 1
    print("PASS structure balanced, pairing and anchors consistent")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("FAIL %s: %s" % (type(exc).__name__, exc))
        sys.exit(1)