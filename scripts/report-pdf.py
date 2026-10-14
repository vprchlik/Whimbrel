#!/usr/bin/env python3
"""Build the report as one self-contained PDF.

Pinned dependency: markdown==3.10.2 (Python-Markdown), also pinned with
hashes in scripts/requirements-report.txt. Nothing else outside the
standard library; Python 3.11 or later (tomllib).

Pipeline: report/draft.md plus every file its Appendices section lists
(report/appendix-regenerate.md and report/exhibits/*.md, in that
order) become one HTML document, which a Chromium-family browser in
headless mode prints to PDF. Each listed file is inlined as its own
appendix section headed by its file name; its first line is its own
caption, which names its pin and its regeneration command. In-text
links to an inlined file become links to that section. A link to any
other repository file becomes a code span holding its repository path,
and the title page carries one sentence naming the repository tree
those paths refer to. Title-page fields come from report/metadata.toml.

Two source normalizations bridge GitHub-flavored Markdown and
Python-Markdown; neither changes a word:
- a list item's continuation paragraphs indented to the item's
  content column (three spaces after "8. ") are re-indented to the
  four spaces Python-Markdown requires, so "9." does not fall out of
  the list;
- a text line written directly under a table's last row, with no
  blank line, is separated from the table instead of becoming a row.
  Each instance is reported; the exhibit generators are the place to
  fix it.

The HTML is a function of the inputs: the same sources, metadata, git
state, and date give the same bytes. Every text read and write pins
UTF-8 and LF (docs/DEBUGGING.md, regenerated exhibits). The PDF itself
carries the browser's creation timestamp.

Usage:
  python scripts/report-pdf.py [OUT.pdf]   # default local/build/whimbrel-report.pdf
  python scripts/report-pdf.py --check     # HTML only; fail on a dangling link
                                           # or an exhibit that is not inlined
  python scripts/report-pdf.py --release   # the publication build: also fail
                                           # unless HEAD is tagged and the
                                           # inputs match it
Options: --date YYYY-MM-DD, --browser PATH (or REPORT_PDF_BROWSER),
--browser-arg ARG (repeatable; e.g. --no-sandbox in a root container).
The output never goes under report/: an unapproved PDF must not be
committable by accident.
"""

from __future__ import annotations

import argparse
import datetime
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path, PurePosixPath

try:
    import markdown
except ImportError:  # pragma: no cover - environment message
    sys.exit(
        "report-pdf: the markdown package is missing; run\n"
        "  python -m pip install -r scripts/requirements-report.txt"
    )

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "report"
DRAFT = REPORT / "draft.md"
EXHIBITS = REPORT / "exhibits"
METADATA = REPORT / "metadata.toml"
DEFAULT_OUT = ROOT / "local" / "build" / "whimbrel-report.pdf"

MARKDOWN_VERSION = "3.10.2"
PAGE_SIZE = "Letter"
APPENDICES_HEADING = "Appendices"
# Appendix sections are h3 under the draft's "## Appendices"; headings
# inside an inlined file start one level below.
APPENDIX_LEVEL = 3
# Not Markdown: a key=value block copied from the bench summaries.
# Rendered verbatim, or its lines would run together into paragraphs.
PREFORMATTED = {"exhibits/machine-spec.md"}

METADATA_KEYS = (
    "title",
    "author",
    "affiliation",
    "orcid",
    "version",
    "date",
    "repository",
    "doi",
    "license",
)

GENERATED_COMMENT = re.compile(r"^<!--.*-->\s*$")
ATX_HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
FENCE = re.compile(r"^ {0,3}(```|~~~)")
LIST_ITEM = re.compile(r"^( {0,3})(\d{1,9}[.)]|[-*+])( {1,4})(\S.*)$")
TABLE_ROW = re.compile(r"^ {0,3}\|")
TABLE_RULE = re.compile(r"^ {0,3}\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
THEMATIC_BREAK = re.compile(r"^ {0,3}([-*_])(\s*\1){2,}\s*$")
CODE_SPAN = re.compile(r"(`+)(.+?)\1", re.S)
INLINE_LINK = re.compile(r"(?<!!)\[([^\]\n]*)\]\(([^)\s]+)\)")
URL_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
# Rendered text kept on one line: a number with its unit, a decision id,
# and "RISC-V" (a line break after their hyphen or space misreads).
NO_BREAK = re.compile(
    r"(?<![\w.])[-−+~]?\d[\d.,]*\s(?:ns|µs|ms|s|KiB|MiB|GiB|KB|GHz|MHz)\b"
    r"|\bD-\d{4}(?:\.\d+)?\b"
    r"|\bRISC-V\b"
)
SHORT_CODE = 24
APPENDICES_END = "<!-- appendices end -->"

CSS = """\
@page {
  size: %(page)s;
  margin: 20mm 19mm 20mm 19mm;
  @bottom-center {
    content: counter(page) " / " counter(pages);
    font-family: Cambria, Georgia, "Noto Serif", "DejaVu Serif", serif;
    font-size: 8.5pt;
    color: #444;
  }
}
@page :first {
  @bottom-center { content: none; }
}
html {
  font-family: Cambria, Georgia, "Noto Serif", "DejaVu Serif",
    "Liberation Serif", serif;
  font-size: 10.5pt;
  line-height: 1.36;
  color: #000;
  background: #fff;
}
body { margin: 0; }
p, li { orphans: 3; widows: 3; }
p { margin: 0 0 6pt 0; }
ul, ol { margin: 0 0 6pt 0; padding-left: 20pt; }
li { margin-bottom: 3pt; }
li > p { margin-bottom: 4pt; }
a { color: #173f78; text-decoration: none; }
code, pre {
  font-family: Consolas, "DejaVu Sans Mono", "Liberation Mono",
    "Noto Sans Mono", monospace;
  font-size: 0.86em;
}
code { overflow-wrap: anywhere; }
pre {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 7.8pt;
  line-height: 1.3;
  background: #f5f5f5;
  border: 0.5pt solid #ccc;
  padding: 5pt 7pt;
  margin: 0 0 8pt 0;
}
pre code { font-size: inherit; }
h1, h2, h3, h4, h5, h6 {
  font-weight: bold;
  line-height: 1.2;
  break-after: avoid;
  break-inside: avoid;
}
h2 { font-size: 15pt; margin: 20pt 0 8pt 0; }
h3 { font-size: 12pt; margin: 14pt 0 6pt 0; }
h4 { font-size: 10.5pt; margin: 12pt 0 5pt 0; }
h5, h6 { font-size: 10pt; margin: 10pt 0 4pt 0; }
h2 code, h3 code, h4 code { font-size: 0.9em; }
hr { display: none; }
.nb, code.nb { white-space: nowrap; }
table {
  border-collapse: collapse;
  width: auto;
  max-width: 100%%;
  margin: 4pt 0 10pt 0;
  font-size: 8.4pt;
  line-height: 1.25;
  font-variant-numeric: tabular-nums;
  break-before: avoid;
}
thead { display: table-header-group; }
tr { break-inside: avoid; }
th, td {
  padding: 2pt 4pt;
  vertical-align: top;
  text-align: left;
  border-bottom: 0.5pt solid #bbb;
  overflow-wrap: break-word;
}
th { border-bottom: 1pt solid #000; }
td code, th code { font-size: 0.92em; }
.title-page { break-after: page; padding-top: 34%%; }
.title-page h1 {
  font-size: 23pt;
  line-height: 1.18;
  margin: 0 0 22pt 0;
}
.title-page p { margin: 0 0 5pt 0; font-size: 11pt; }
.title-page .repository {
  margin-top: 28pt;
  font-size: 9.5pt;
  color: #222;
}
nav.contents { break-after: page; }
nav.contents h2 { margin-top: 0; }
nav.contents ul { list-style: none; padding-left: 0; margin: 0; }
nav.contents > ul { columns: 2; column-gap: 22pt; }
nav.contents ul ul { padding-left: 12pt; margin: 1pt 0 3pt 0; }
nav.contents li { margin: 0 0 1.5pt 0; font-size: 9.3pt; }
nav.contents > ul > li { margin-top: 4pt; font-weight: bold; }
nav.contents > ul > li li { font-weight: normal; }
section.appendix { break-before: page; }
section.appendix p, section.appendix li { font-size: 9.6pt; }
h3.appendix { font-size: 13pt; margin-top: 0; }
p.exhibit-caption {
  font-size: 9.3pt !important;
  border-left: 2pt solid #888;
  padding-left: 7pt;
}
"""


class BuildError(Exception):
    pass


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def rel_report(path: Path) -> str:
    return path.resolve().relative_to(REPORT.resolve()).as_posix()


def git(*args: str) -> str | None:
    try:
        run = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return None
    if run.returncode != 0:
        return None
    return run.stdout.strip()


# ---------------------------------------------------------------- metadata


def load_metadata() -> dict[str, str]:
    meta = {key: "" for key in METADATA_KEYS}
    if not METADATA.exists():
        raise BuildError(f"{METADATA.relative_to(ROOT).as_posix()} is missing")
    data = tomllib.loads(read_text(METADATA))
    for key, value in data.items():
        if key not in meta:
            raise BuildError(f"report/metadata.toml: unknown key {key!r}")
        if not isinstance(value, str):
            raise BuildError(f"report/metadata.toml: {key} must be a string")
        meta[key] = value.strip()
    return meta


def git_version(meta: dict[str, str]) -> tuple[str, str, str | None, bool]:
    """Return (version line, tree ref for the repository URL, tag, dirty)."""
    tag = git("describe", "--tags", "--exact-match", "HEAD")
    short = git("rev-parse", "--short", "HEAD")
    full = git("rev-parse", "HEAD")
    dirty = git(
        "status",
        "--porcelain",
        "--",
        "report",
        "scripts/report-pdf.py",
        "scripts/requirements-report.txt",
    )
    if meta["version"]:
        version = meta["version"]
    elif tag:
        version = tag
    elif short:
        version = f"{short} (unreleased)"
    else:
        version = "unknown (no git)"
    if dirty:
        version += ", built from a modified working tree"
    ref = tag or full or "main"
    return version, ref, tag, bool(dirty)


# --------------------------------------------------------- source passes


def outside_code(text: str, fn) -> str:
    """Apply fn to the parts of one Markdown block that are not code spans."""
    out = []
    pos = 0
    for m in CODE_SPAN.finditer(text):
        out.append(fn(text[pos : m.start()]))
        out.append(m.group(0))
        pos = m.end()
    out.append(fn(text[pos:]))
    return "".join(out)


def split_fenced(lines: list[str]):
    """Yield (in_fence, line) pairs."""
    fence = None
    for line in lines:
        m = FENCE.match(line)
        if fence is None and m:
            fence = m.group(1)
            yield True, line
        elif fence is not None:
            if line.strip().startswith(fence):
                fence = None
            yield True, line
        else:
            yield False, line


def normalize_list_indent(text: str) -> str:
    """Re-indent list continuation blocks from the content column to 4.

    A list item whose continuation paragraph is followed directly by the
    next item's marker also gets a blank line before that marker; without
    it Python-Markdown reads the marker as more paragraph text.
    """
    out = []
    item_col = None
    item_has_block = False
    after_blank = False
    for in_fence, line in split_fenced(text.split("\n")):
        if in_fence:
            out.append(line)
            continue
        if not line.strip():
            out.append(line)
            after_blank = True
            continue
        m = LIST_ITEM.match(line)
        if m:
            if item_has_block and out and out[-1].strip():
                out.append("")
            item_col = len(m.group(1)) + len(m.group(2)) + len(m.group(3))
            item_has_block = False
            out.append(line)
            after_blank = False
            continue
        indent = len(line) - len(line.lstrip(" "))
        if item_col is not None and after_blank:
            if indent < item_col:
                item_col = None
                item_has_block = False
            else:
                item_has_block = True
        if item_col is not None and item_col < 4 and indent >= item_col:
            line = " " * (4 - item_col) + line
        out.append(line)
        after_blank = False
    return "\n".join(out)


def source_line(name: str, line: str) -> int:
    """1-based line number of the first identical line in report/<name>."""
    raw = read_text(REPORT / name).split("\n")
    return raw.index(line) + 1 if line in raw else 0


def separate_table_tails(text: str, name: str, notes: list[str]) -> str:
    """End a table at a pipe-less line written directly under it."""
    lines = text.split("\n")
    out = []
    in_table = False
    for in_fence, line in split_fenced(lines):
        if in_fence:
            in_table = False
            out.append(line)
            continue
        if TABLE_RULE.match(line) and out and TABLE_ROW.match(out[-1]):
            in_table = True
        elif in_table and line.strip() and "|" not in line:
            notes.append(
                f"report/{name}:{source_line(name, line)}: line directly under "
                "a table row rendered as text, not as a row (no blank line in "
                "the source)"
            )
            out.append("")
            in_table = False
        elif not line.strip():
            in_table = False
        out.append(line)
    return "\n".join(out)


def lint(text: str, name: str, notes: list[str]) -> None:
    """Constructs GitHub renders differently from this build; warn only."""
    lines = text.split("\n")
    prev = ""
    for i, (in_fence, line) in enumerate(split_fenced(lines)):
        if in_fence:
            prev = ""
            continue
        if (
            re.match(r"^ {0,3}-{2,}\s*$", line)
            and prev.strip()
            and not TABLE_ROW.match(prev)
            and not ATX_HEADING.match(prev)
        ):
            notes.append(
                f"report/{name}:{i + 1}: '---' directly under a paragraph "
                "line; GitHub renders that paragraph as a heading (blank "
                "line needed above the rule)"
            )
        if re.search(r"\S\s+-{3}\s*$", line) and not TABLE_ROW.match(line):
            notes.append(
                f"report/{name}:{i + 1}: line ends in ' ---'; it prints "
                "as literal dashes, not as a rule"
            )
        prev = line


def anchor_for(rel: str) -> str:
    stem = rel[:-3] if rel.endswith(".md") else rel
    return "appendix-" + re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")


def rewrite_links(
    text: str,
    rel: str,
    inlined: dict[str, str],
    errors: list[str],
) -> str:
    """Point links at appendix anchors; other repository files become code."""
    base = PurePosixPath(rel).parent

    def one(m: re.Match) -> str:
        label, target = m.group(1), m.group(2)
        if URL_SCHEME.match(target) or target.startswith("#"):
            return m.group(0)
        path_part = target.split("#", 1)[0]
        resolved = (REPORT / base / path_part).resolve()
        if not resolved.exists():
            errors.append(f"report/{rel}: link target {target!r} does not resolve")
            return m.group(0)
        try:
            in_report = resolved.relative_to(REPORT.resolve()).as_posix()
        except ValueError:
            in_report = None
        if in_report in inlined:
            return f"[{label}](#{inlined[in_report]})"
        try:
            repo_path = resolved.relative_to(ROOT).as_posix()
        except ValueError:
            errors.append(f"report/{rel}: link target {target!r} is outside the repository")
            return m.group(0)
        if resolved.is_dir():
            repo_path += "/"
        plain = label.strip().strip("`")
        if plain in (PurePosixPath(path_part).name, path_part, repo_path):
            return f"`{repo_path}`"
        return f"{label} (`{repo_path}`)"

    blocks = text.split("\n\n")
    return "\n\n".join(
        outside_code(block, lambda s: INLINE_LINK.sub(one, s)) for block in blocks
    )


# -------------------------------------------------------------- the draft


def split_title(draft: str) -> tuple[str, str]:
    lines = draft.split("\n")
    m = ATX_HEADING.match(lines[0]) if lines else None
    if not m or len(m.group(1)) != 1:
        raise BuildError("report/draft.md: the first line must be the H1 title")
    title = m.group(2)
    rest = lines[1:]
    while rest and not rest[0].strip():
        rest.pop(0)
    if rest and THEMATIC_BREAK.match(rest[0]):
        rest.pop(0)
    return title, "\n".join(rest)


def appendix_bounds(lines: list[str]) -> tuple[int, int]:
    start = None
    for i, (in_fence, line) in enumerate(split_fenced(lines)):
        if in_fence:
            continue
        m = ATX_HEADING.match(line)
        if not m or len(m.group(1)) != 2:
            continue
        if start is None and m.group(2).strip() == APPENDICES_HEADING:
            start = i
        elif start is not None:
            return start, i
    if start is None:
        raise BuildError(f"report/draft.md: no '## {APPENDICES_HEADING}' section")
    return start, len(lines)


def appendix_order(body: str) -> list[str]:
    lines = body.split("\n")
    start, end = appendix_bounds(lines)
    order = []
    for line in lines[start:end]:
        m = re.match(r"^\s*[-*+]\s+\[[^\]]*\]\(([^)\s]+)\)", line)
        if m:
            target = m.group(1).split("#", 1)[0]
            resolved = (REPORT / target).resolve()
            if not resolved.is_file():
                raise BuildError(
                    f"report/draft.md: appendix entry {target!r} does not resolve"
                )
            rel = rel_report(resolved)
            if rel in order:
                raise BuildError(f"report/draft.md: appendix {rel} is listed twice")
            order.append(rel)
    if not order:
        raise BuildError("report/draft.md: the Appendices section lists no files")
    return order


# --------------------------------------------------------- appendix files


def appendix_markdown(
    rel: str,
    inlined: dict[str, str],
    errors: list[str],
    notes: list[str],
) -> str:
    text = read_text(REPORT / rel)
    lines = text.split("\n")
    while lines and (not lines[0].strip() or GENERATED_COMMENT.match(lines[0])):
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    heading = f"### `{rel}` {{#{inlined[rel]} .appendix}}"

    if rel in PREFORMATTED:
        if any(FENCE.match(line) for line in lines):
            raise BuildError(f"report/{rel}: contains a code fence; cannot inline verbatim")
        return heading + "\n\n```text\n" + "\n".join(lines) + "\n```\n"

    caption_line = None
    m = ATX_HEADING.match(lines[0]) if lines else None
    if m and len(m.group(1)) == 1:
        caption_line = m.group(2)
        lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)

    levels = [
        len(m.group(1))
        for in_fence, line in split_fenced(lines)
        if not in_fence and (m := ATX_HEADING.match(line))
    ]
    shift = (APPENDIX_LEVEL + 1 - min(levels)) if levels else 0
    shifted = []
    for in_fence, line in split_fenced(lines):
        m = None if in_fence else ATX_HEADING.match(line)
        if m:
            level = min(6, len(m.group(1)) + shift)
            line = "#" * level + " " + m.group(2)
        shifted.append(line)
    body = "\n".join(shifted)

    if caption_line is not None:
        caption = caption_line + "\n{: .exhibit-caption }"
    else:
        first, sep, rest = body.partition("\n\n")
        if ATX_HEADING.match(first) or TABLE_ROW.match(first):
            raise BuildError(f"report/{rel}: no caption paragraph before the first table or heading")
        caption = first + "\n{: .exhibit-caption }"
        body = rest
    body = separate_table_tails(body, rel, notes)
    body = normalize_list_indent(body)
    body = rewrite_links(body, rel, inlined, errors)
    caption = rewrite_links(caption, rel, inlined, errors)
    return heading + "\n\n" + caption + "\n\n" + body + "\n"


# ------------------------------------------------------------------- html


def keep_together(fragment: str) -> str:
    """Wrap NO_BREAK matches in text (not code) and short hyphenated code."""
    out = []
    depth = 0
    for part in re.split(r"(<[^>]+>)", fragment):
        if part.startswith("<"):
            m = re.match(r"</?([a-zA-Z0-9]+)", part)
            if m and m.group(1).lower() in ("code", "pre"):
                depth += -1 if part.startswith("</") else 1
            out.append(part)
        elif depth or not part:
            out.append(part)
        else:
            out.append(NO_BREAK.sub(lambda m: f'<span class="nb">{m.group(0)}</span>', part))
    joined = "".join(out)
    return re.sub(
        r"<code>([^<]{1,%d})</code>" % SHORT_CODE,
        lambda m: f'<code class="nb">{m.group(1)}</code>' if "-" in m.group(1) else m.group(0),
        joined,
    )


def wrap_appendices(content: str, anchors: list[str]) -> str:
    """Give each inlined file its own <section> (page break, appendix type size)."""
    starts = []
    for anchor in anchors:
        m = re.search(r'<h3[^>]*\bid="%s"' % re.escape(anchor), content)
        if not m:
            raise BuildError(f"appendix heading #{anchor} missing from the HTML")
        starts.append(m.start())
    end = content.find(APPENDICES_END)
    if end < 0 or starts != sorted(starts) or end < starts[-1]:
        raise BuildError("appendix sections out of order in the HTML")
    bounds = starts + [end]
    parts = [content[: starts[0]]]
    for i, anchor in enumerate(anchors):
        body = content[bounds[i] : bounds[i + 1]].rstrip("\n")
        parts.append(f'<section class="appendix" data-file="{anchor}">\n{body}\n</section>\n')
    parts.append(content[end + len(APPENDICES_END) :])
    return "".join(parts)


def contents_html(tokens: list[dict]) -> str:
    def items(entries: list[dict], depth: int) -> str:
        parts = []
        for t in entries:
            sub = ""
            if depth == 0 and t.get("children"):
                sub = items(t["children"], depth + 1)
            parts.append(f'<li><a href="#{t["id"]}">{t["name"]}</a>{sub}</li>')
        return "<ul>" + "".join(parts) + "</ul>"

    top = []
    for t in tokens:
        if t["level"] == 2:
            top.append(t)
        elif t["level"] == 1:
            top.extend(c for c in t.get("children", []) if c["level"] == 2)
    return '<nav class="contents">\n<h2>Contents</h2>\n' + items(top, 0) + "\n</nav>"


def title_page_html(title: str, meta: dict[str, str], version: str, date: str, ref: str) -> str:
    esc = html.escape
    lines = [f"<h1>{esc(title)}</h1>"]
    if meta["author"]:
        lines.append(f'<p class="author">{esc(meta["author"])}</p>')
    if meta["affiliation"]:
        lines.append(f'<p class="affiliation">{esc(meta["affiliation"])}</p>')
    if meta["orcid"]:
        url = "https://orcid.org/" + meta["orcid"]
        lines.append(f'<p class="orcid">ORCID <a href="{esc(url)}">{esc(url)}</a></p>')
    lines.append(f'<p class="version">Version {esc(version)}</p>')
    lines.append(f'<p class="date">{esc(date)}</p>')
    if meta["doi"]:
        url = "https://doi.org/" + meta["doi"]
        lines.append(f'<p class="doi">DOI <a href="{esc(url)}">{esc(meta["doi"])}</a></p>')
    if meta["license"]:
        lines.append(f'<p class="license">{esc(meta["license"])}</p>')
    if meta["repository"]:
        tree = meta["repository"].rstrip("/") + "/tree/" + ref
        lines.append(
            '<p class="repository">Files and decision entries (D-NNNN, in '
            "<code>docs/DECISIONS.md</code>) refer to the repository at "
            f'<a href="{esc(tree)}">{esc(tree)}</a>.</p>'
        )
    return '<section class="title-page">\n' + "\n".join(lines) + "\n</section>"


def build_html(date_override: str | None) -> tuple[str, list[str], list[str], dict]:
    errors: list[str] = []
    notes: list[str] = []
    meta = load_metadata()
    draft = read_text(DRAFT)
    lint(draft, "draft.md", notes)
    h1, body = split_title(draft)
    title = meta["title"] or h1

    order = appendix_order(body)
    inlined = {rel: anchor_for(rel) for rel in order}
    for path in sorted(EXHIBITS.glob("*.md")):
        if rel_report(path) not in inlined:
            errors.append(
                f"report/{rel_report(path)} is not inlined: the draft's "
                f"{APPENDICES_HEADING} section does not list it"
            )
    regen = REPORT / "appendix-regenerate.md"
    if regen.exists() and "appendix-regenerate.md" not in inlined:
        errors.append("report/appendix-regenerate.md is not inlined")

    body = separate_table_tails(body, "draft.md", notes)
    body = normalize_list_indent(body)
    body = rewrite_links(body, "draft.md", inlined, errors)
    lines = body.split("\n")
    _, end = appendix_bounds(lines)
    appendices = [appendix_markdown(rel, inlined, errors, notes) for rel in order]
    document = (
        "\n".join(lines[:end]).rstrip("\n")
        + "\n\n"
        + "\n\n".join(appendices)
        + "\n\n"
        + APPENDICES_END
    )
    if end < len(lines):
        document += "\n\n" + "\n".join(lines[end:])

    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "toc", "attr_list", "sane_lists"],
        extension_configs={"toc": {"toc_depth": "2-3"}},
        output_format="html",
    )
    content = md.convert(document)

    # Backstop: anything the passes above missed. A link already reported
    # as dangling is left in place and not reported twice.
    ids = set(re.findall(r'\sid="([^"]+)"', content))
    reported = " ".join(errors)
    for href in re.findall(r'href="([^"]+)"', content):
        if href.startswith("#"):
            if href[1:] not in ids:
                errors.append(f"internal link {href} has no target")
        elif not URL_SCHEME.match(href) and repr(href) not in reported:
            errors.append(f"relative link {href!r} survived into the HTML")
    for frag in re.findall(r"<p>[^<]*\|\s*-{3}", content):
        errors.append(f"unrendered table text in the HTML: {frag[:60]!r}")
    if not errors:
        content = keep_together(wrap_appendices(content, [inlined[rel] for rel in order]))

    version, ref, tag, dirty = git_version(meta)
    date = date_override or meta["date"] or datetime.date.today().isoformat()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise BuildError(f"date {date!r} is not YYYY-MM-DD")

    page = "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            f"<title>{html.escape(title)}</title>",
            f'<meta name="generator" content="scripts/report-pdf.py; Python-Markdown {MARKDOWN_VERSION}">',
            f"<style>\n{CSS % {'page': PAGE_SIZE}}</style>",
            "</head>",
            "<body>",
            keep_together(title_page_html(title, meta, version, date, ref)),
            contents_html(md.toc_tokens),
            '<main class="report">',
            content,
            "</main>",
            "</body>",
            "</html>",
            "",
        ]
    )
    info = {
        "title": title,
        "version": version,
        "date": date,
        "appendices": order,
        "tag": tag,
        "dirty": dirty,
        "version_override": bool(meta["version"]),
    }
    return page, errors, notes, info


# ---------------------------------------------------------------- browser


def browser_candidates() -> list[str]:
    found = []
    if sys.platform == "win32":
        bases = [
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("PROGRAMFILES"),
            os.environ.get("LOCALAPPDATA"),
        ]
        for rel in (
            ("Microsoft", "Edge", "Application", "msedge.exe"),
            ("Google", "Chrome", "Application", "chrome.exe"),
        ):
            for base in bases:
                if base:
                    found.append(str(Path(base, *rel)))
        names = ["msedge", "chrome"]
    elif sys.platform == "darwin":
        found += [
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
        names = []
    else:
        names = [
            "chromium",
            "chromium-browser",
            "google-chrome",
            "google-chrome-stable",
            "microsoft-edge",
            "microsoft-edge-stable",
        ]
    for name in names:
        hit = shutil.which(name)
        if hit:
            found.append(hit)
    return found


def find_browser(explicit: str | None) -> str:
    if explicit:
        if not Path(explicit).is_file() and not shutil.which(explicit):
            raise BuildError(f"browser {explicit!r} not found")
        return shutil.which(explicit) or explicit
    for cand in browser_candidates():
        if Path(cand).is_file():
            return cand
    raise BuildError(
        "no Chromium-family browser found (Edge, Chrome, chromium, google-chrome); "
        "pass --browser PATH or set REPORT_PDF_BROWSER"
    )


def print_pdf(browser: str, html_path: Path, out: Path, extra: list[str]) -> None:
    if out.exists():
        out.unlink()
    with tempfile.TemporaryDirectory(prefix="report-pdf-", ignore_cleanup_errors=True) as profile:
        cmd = [
            browser,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            f"--user-data-dir={profile}",
            *extra,
            f"--print-to-pdf={out}",
            html_path.resolve().as_uri(),
        ]
        try:
            run = subprocess.run(
                cmd,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise BuildError(f"{browser} did not finish printing in 300 s") from exc
    if not out.exists() or out.stat().st_size == 0 or out.read_bytes()[:5] != b"%PDF-":
        detail = (run.stderr or run.stdout).strip()[-2000:]
        raise BuildError(f"{browser} wrote no PDF (exit {run.returncode})\n{detail}")


def page_count(pdf: Path) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![A-Za-z])", pdf.read_bytes()))


# ------------------------------------------------------------------- main


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out", nargs="?", default=str(DEFAULT_OUT), help="output PDF path")
    ap.add_argument("--check", action="store_true", help="render HTML only and validate")
    ap.add_argument(
        "--release",
        action="store_true",
        help="the publication build: refuse unless HEAD is tagged and the inputs are unmodified",
    )
    ap.add_argument("--date", help="title-page date, YYYY-MM-DD")
    ap.add_argument("--browser", default=os.environ.get("REPORT_PDF_BROWSER"))
    ap.add_argument("--browser-arg", action="append", default=[])
    args = ap.parse_args(argv)

    if markdown.__version__ != MARKDOWN_VERSION:
        print(
            f"report-pdf: markdown {markdown.__version__} installed, "
            f"{MARKDOWN_VERSION} pinned; the HTML may differ",
            file=sys.stderr,
        )
    out = Path(args.out).resolve()
    if out.suffix.lower() != ".pdf":
        print("report-pdf: the output path must end in .pdf", file=sys.stderr)
        return 2
    if out.is_relative_to(REPORT.resolve()) or out.parent == ROOT:
        print("report-pdf: refusing to write under report/ or at the repository root", file=sys.stderr)
        return 2

    try:
        page, errors, notes, info = build_html(args.date)
    except BuildError as exc:
        print(f"report-pdf: {exc}", file=sys.stderr)
        return 1
    for note in notes:
        print(f"report-pdf: note: {note}", file=sys.stderr)
    if args.release:
        if not info["tag"]:
            errors.append("--release: HEAD carries no tag")
        if info["dirty"]:
            errors.append("--release: report/ or the build script differs from HEAD")
        if info["version_override"]:
            errors.append("--release: report/metadata.toml sets version; the tag is the version")
    if errors:
        for err in errors:
            print(f"report-pdf: error: {err}", file=sys.stderr)
        return 1

    html_path = out.with_suffix(".html")
    write_text(html_path, page)
    print(f"html: {html_path}")
    print(f"title: {info['title']}")
    print(f"version: {info['version']}  date: {info['date']}")
    print(f"appendices inlined: {len(info['appendices'])}")
    if args.check:
        print("check: ok")
        return 0

    try:
        browser = find_browser(args.browser)
        print(f"browser: {browser}")
        print_pdf(browser, html_path, out, args.browser_arg)
    except BuildError as exc:
        print(f"report-pdf: {exc}", file=sys.stderr)
        return 1
    print(f"pdf: {out} ({page_count(out)} pages, {PAGE_SIZE})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
