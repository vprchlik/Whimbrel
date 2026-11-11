#!/usr/bin/env python3
"""Image bytes per pinned artifact (D-0083 A2).

The cross-system table's image-bytes column is the size of the file
passed to `-kernel` as QEMU loads it: the sum of `PT_LOAD` file sizes
for Whimbrel's ELF, the file length for a flat Linux `Image`. The
Linux arms also load `rootfs.cpio` via `-initrd`; it is recorded as
its own `role=initrd` row and quoted beside the column, never summed
into it (D-0083 A2 defines the column as the `-kernel` file).

`measure` runs on the bench host, where the artifacts are. It reads
the pin's `results/runs.csv` (each arm's `kernel_sha256`) and
`bench/linux/MANIFEST` via `git show`, hashes every file, refuses any
file whose sha256 is not the pin's, and writes `results/image-bytes.csv`.
A Whimbrel ELF that was rebuilt at the pin's `git_sha` under a
toolchain that no longer reproduces the pin's hash can be recorded
only with `--allow-rebuild --note "<toolchain, host>"`; the row then
carries both hashes and the note, and the exhibit discloses it. Linux
Images have no such path: the pinned artifacts exist and must match.

`verify` re-checks a committed record against the pins; it needs git
and nothing else. `selftest` plants failing inputs (no git, no
artifacts). The report generator reads the record as a git object at
its own pin (`IMAGE_BYTES_REV` in scripts/report-exhibits.py) and
cross-checks every row again before printing a cell.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import socket
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "results" / "image-bytes.csv"
RECORD_REL = "results/image-bytes.csv"

FIELDS = (
    "pin",
    "rev",
    "system",
    "config",
    "role",
    "artifact",
    "format",
    "sha256",
    "pin_sha256",
    "file_bytes",
    "loaded_bytes",
    "segments",
    "measured_utc",
    "host",
    "note",
)
FAST = "release-fast-boot"
SAFE = "release-default"
ARMS = (
    ("whimbrel", FAST),
    ("whimbrel", SAFE),
    ("linux", "trimmed"),
    ("linux", "trimmed-instrumented"),
    ("linux", "stock"),
)
LINUX_IMAGE = {
    "trimmed": "Image-trimmed",
    "trimmed-instrumented": "Image-trimmed",
    "stock": "Image-stock",
}
INITRD = "rootfs.cpio"
PT_LOAD = 1
EM_RISCV = 243
ELF64_PHENTSIZE = 56


class Fail(Exception):
    pass


def git_show(rev: str, path: str) -> str:
    proc = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        err = proc.stderr.strip() or "git show failed"
        raise Fail(f"TEST FAIL: git show {rev}:{path}: {err}")
    if not proc.stdout:
        raise Fail(f"TEST FAIL: git show {rev}:{path} was empty")
    return proc.stdout


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def elf_pt_load(data: bytes, label: str) -> tuple[int, int]:
    """Sum of PT_LOAD p_filesz over an ELF64 little-endian RISC-V file,
    and the segment count. That sum is what QEMU's load_elf copies
    into guest memory; p_memsz beyond it is zero-filled, not loaded."""
    if len(data) < 64 or data[:4] != b"\x7fELF":
        raise Fail(f"TEST FAIL: {label} is not an ELF")
    if data[4] != 2:
        raise Fail(f"TEST FAIL: {label} is not ELF64")
    if data[5] != 1:
        raise Fail(f"TEST FAIL: {label} is not little-endian")
    (e_machine,) = struct.unpack_from("<H", data, 0x12)
    if e_machine != EM_RISCV:
        raise Fail(f"TEST FAIL: {label} e_machine {e_machine} is not RISC-V")
    (e_phoff,) = struct.unpack_from("<Q", data, 0x20)
    e_phentsize, e_phnum = struct.unpack_from("<HH", data, 0x36)
    if e_phentsize != ELF64_PHENTSIZE:
        raise Fail(f"TEST FAIL: {label} e_phentsize {e_phentsize} != 56")
    if e_phnum == 0 or e_phoff + e_phnum * ELF64_PHENTSIZE > len(data):
        raise Fail(f"TEST FAIL: {label} program header table out of range")
    total = 0
    count = 0
    for i in range(e_phnum):
        off = e_phoff + i * ELF64_PHENTSIZE
        (p_type, _flags, p_offset, _vaddr, _paddr, p_filesz, p_memsz, _align) = (
            struct.unpack_from("<IIQQQQQQ", data, off)
        )
        if p_type != PT_LOAD:
            continue
        if p_offset + p_filesz > len(data):
            raise Fail(
                f"TEST FAIL: {label} PT_LOAD {count} extends past the file "
                f"(offset {p_offset} + filesz {p_filesz} > {len(data)})"
            )
        if p_memsz < p_filesz:
            raise Fail(f"TEST FAIL: {label} PT_LOAD {count} memsz < filesz")
        total += p_filesz
        count += 1
    if count == 0:
        raise Fail(f"TEST FAIL: {label} has no PT_LOAD segment")
    return total, count


def parse_manifest(text: str) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) == 3 and parts[0] == "artifact":
            artifacts[parts[1]] = parts[2]
    missing = [n for n in ("Image-stock", "Image-trimmed", INITRD) if n not in artifacts]
    if missing:
        raise Fail(f"TEST FAIL: MANIFEST missing {missing}")
    return artifacts


def pin_hashes(rev: str, show=git_show) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
    """Each arm's kernel_sha256 from the pin's runs.csv (one value per
    arm, recorded trials), and the pin's MANIFEST artifact hashes."""
    rows = list(csv.DictReader(io.StringIO(show(rev, "results/runs.csv"))))
    if not rows or "kernel_sha256" not in rows[0]:
        raise Fail(f"TEST FAIL: {rev}:results/runs.csv has no kernel_sha256 column")
    kernels: dict[tuple[str, str], str] = {}
    for system, config in ARMS:
        got = {
            r["kernel_sha256"]
            for r in rows
            if r["system"] == system and r["config"] == config and int(r.get("warmup", "0")) == 0
        }
        if len(got) != 1:
            raise Fail(
                f"TEST FAIL: {rev}:results/runs.csv has {len(got)} kernel_sha256 "
                f"values for {system}/{config}, want exactly 1"
            )
        kernels[(system, config)] = next(iter(got))
    manifest = parse_manifest(show(rev, "bench/linux/MANIFEST"))
    for config, image in LINUX_IMAGE.items():
        if kernels[("linux", config)] != manifest[image]:
            raise Fail(
                f"TEST FAIL: {rev}: runs.csv kernel_sha256 for linux/{config} "
                f"is not MANIFEST {image}"
            )
    return kernels, manifest


def _row(**kw: object) -> dict[str, str]:
    row = {f: "" for f in FIELDS}
    for k, v in kw.items():
        if k not in row:
            raise Fail(f"internal: unknown field {k}")
        row[k] = str(v)
    return row


def measure(
    *,
    pin: str,
    rev: str,
    whimbrel_fast: Path,
    whimbrel_safe: Path,
    linux_dir: Path,
    host: str,
    allow_rebuild: bool = False,
    note: str = "",
    show=git_show,
    measured_utc: str | None = None,
) -> list[dict[str, str]]:
    kernels, manifest = pin_hashes(rev, show)
    stamp = measured_utc or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows: list[dict[str, str]] = []
    for system, config in ARMS:
        if system == "whimbrel":
            path = whimbrel_fast if config == FAST else whimbrel_safe
            data = path.read_bytes()
            sha = sha256_bytes(data)
            want = kernels[(system, config)]
            loaded, segments = elf_pt_load(data, f"{config} ELF {path}")
            row_note = ""
            if sha != want:
                if not allow_rebuild:
                    raise Fail(
                        f"TEST FAIL: {config}: sha256 {sha} is not the pin's "
                        f"{want}. A rebuild that does not reproduce the pin's "
                        "hash is recorded only with --allow-rebuild --note "
                        "'<toolchain, host>'."
                    )
                if not note.strip():
                    raise Fail("TEST FAIL: --allow-rebuild requires --note naming the toolchain and host")
                row_note = note.strip()
            rows.append(
                _row(
                    pin=pin, rev=rev, system=system, config=config, role="kernel",
                    artifact=str(path), format="elf", sha256=sha, pin_sha256=want,
                    file_bytes=len(data), loaded_bytes=loaded, segments=segments,
                    measured_utc=stamp, host=host, note=row_note,
                )
            )
            continue
        image = LINUX_IMAGE[config]
        path = linux_dir / image
        data = path.read_bytes()
        sha = sha256_bytes(data)
        want = manifest[image]
        if sha != want:
            raise Fail(f"TEST FAIL: {image}: sha256 {sha} is not the pin's {want}")
        if data[:4] == b"\x7fELF":
            raise Fail(f"TEST FAIL: {image} is an ELF; a Linux Image is a flat binary")
        rows.append(
            _row(
                pin=pin, rev=rev, system=system, config=config, role="kernel",
                artifact=str(path), format="flat", sha256=sha, pin_sha256=want,
                file_bytes=len(data), loaded_bytes=len(data), segments="",
                measured_utc=stamp, host=host, note="",
            )
        )
        cpio = linux_dir / INITRD
        cdata = cpio.read_bytes()
        csha = sha256_bytes(cdata)
        cwant = manifest[INITRD]
        if csha != cwant:
            raise Fail(f"TEST FAIL: {INITRD}: sha256 {csha} is not the pin's {cwant}")
        rows.append(
            _row(
                pin=pin, rev=rev, system=system, config=config, role="initrd",
                artifact=str(cpio), format="flat", sha256=csha, pin_sha256=cwant,
                file_bytes=len(cdata), loaded_bytes=len(cdata), segments="",
                measured_utc=stamp, host=host, note="",
            )
        )
    return rows


def read_record_text(text: str, label: str) -> list[dict[str, str]]:
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise Fail(f"TEST FAIL: {label} is empty")
    got = tuple(rows[0].keys())
    if got != FIELDS:
        raise Fail(f"TEST FAIL: {label} header {got} != {FIELDS}")
    return rows


def write_record(path: Path, new_rows: list[dict[str, str]], pin: str) -> list[dict[str, str]]:
    old: list[dict[str, str]] = []
    if path.is_file() and path.stat().st_size > 0:
        old = read_record_text(path.read_text(encoding="utf-8"), str(path))
    kept = [r for r in old if r["pin"] != pin]
    rows = sorted(kept + new_rows, key=lambda r: (r["pin"], r["system"], r["config"], r["role"]))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(buf.getvalue(), encoding="utf-8", newline="\n")
    return rows


def verify(rows: list[dict[str, str]], show=git_show) -> int:
    """Every row's pin hash is the pin's; measured hashes match the pin
    except a Whimbrel rebuild that carries a note; sizes are sane; every
    pin present has all five kernel rows and three initrd rows."""
    cache: dict[str, tuple[dict, dict]] = {}
    pins: dict[str, set[tuple[str, str, str]]] = {}
    for r in rows:
        if r["rev"] not in cache:
            cache[r["rev"]] = pin_hashes(r["rev"], show)
        kernels, manifest = cache[r["rev"]]
        key = (r["system"], r["config"])
        if key not in kernels:
            raise Fail(f"TEST FAIL: record row {r['pin']}/{key} is not a T4.8-shaped arm")
        if r["role"] == "kernel":
            want = kernels[key]
        elif r["role"] == "initrd":
            if r["system"] != "linux":
                raise Fail(f"TEST FAIL: record row {r['pin']}/{key} has an initrd for a non-Linux arm")
            want = manifest[INITRD]
        else:
            raise Fail(f"TEST FAIL: record row {r['pin']}/{key} has unknown role {r['role']!r}")
        if r["pin_sha256"] != want:
            raise Fail(
                f"TEST FAIL: record row {r['pin']}/{key}/{r['role']} pin_sha256 "
                f"{r['pin_sha256']} is not the pin's {want}"
            )
        if r["sha256"] != r["pin_sha256"]:
            if r["system"] != "whimbrel" or r["role"] != "kernel":
                raise Fail(
                    f"TEST FAIL: record row {r['pin']}/{key}/{r['role']} measured "
                    f"sha256 {r['sha256']} is not the pin's; only a Whimbrel "
                    "kernel may be a noted rebuild"
                )
            if not r["note"].strip():
                raise Fail(
                    f"TEST FAIL: record row {r['pin']}/{key} is a rebuild whose "
                    "sha256 differs from the pin and carries no note"
                )
        file_bytes = int(r["file_bytes"])
        loaded = int(r["loaded_bytes"])
        if file_bytes <= 0 or loaded <= 0:
            raise Fail(f"TEST FAIL: record row {r['pin']}/{key}/{r['role']} has a non-positive size")
        if r["format"] == "flat":
            if loaded != file_bytes:
                raise Fail(f"TEST FAIL: record row {r['pin']}/{key}/{r['role']} flat file loaded != file bytes")
        elif r["format"] == "elf":
            if loaded >= file_bytes:
                raise Fail(f"TEST FAIL: record row {r['pin']}/{key} ELF loaded bytes not below file bytes")
            if int(r["segments"] or "0") < 1:
                raise Fail(f"TEST FAIL: record row {r['pin']}/{key} ELF has no segment count")
        else:
            raise Fail(f"TEST FAIL: record row {r['pin']}/{key} unknown format {r['format']!r}")
        pins.setdefault(r["pin"], set()).add((r["system"], r["config"], r["role"]))
    for pin, have in pins.items():
        want = {(s, c, "kernel") for s, c in ARMS} | {("linux", c, "initrd") for c in LINUX_IMAGE}
        if have != want:
            raise Fail(f"TEST FAIL: record pin {pin} rows {sorted(have ^ want)} missing or extra")
    return len(rows)


# --------------------------------------------------------------- selftest


def _synthetic_elf(sizes: tuple[int, ...]) -> bytes:
    """A minimal ELF64/LE/RISC-V with one PT_LOAD per size, plus one
    non-load segment, laid out after the headers."""
    phnum = len(sizes) + 1
    phoff = 64
    data_off = phoff + phnum * ELF64_PHENTSIZE
    header = bytearray(64)
    header[:4] = b"\x7fELF"
    header[4] = 2
    header[5] = 1
    header[6] = 1
    struct.pack_into("<HHI", header, 0x10, 2, EM_RISCV, 1)
    struct.pack_into("<QQQ", header, 0x18, 0x80200000, phoff, 0)
    struct.pack_into("<IHHHHHH", header, 0x30, 0, 64, ELF64_PHENTSIZE, phnum, 0, 0, 0)
    phdrs = bytearray()
    off = data_off
    for sz in sizes:
        phdrs += struct.pack("<IIQQQQQQ", PT_LOAD, 5, off, 0, 0, sz, sz + 16, 4096)
        off += sz
    phdrs += struct.pack("<IIQQQQQQ", 4, 4, off, 0, 0, 8, 8, 4)
    body = bytes(range(256)) * (sum(sizes) // 256 + 1)
    return bytes(header) + bytes(phdrs) + body[: sum(sizes)] + b"NOTEnote" + b"\x00" * 128


def cmd_selftest() -> int:
    fired: list[str] = []

    def expect_fail(fn, needle: str, label: str) -> None:
        try:
            fn()
        except Fail as e:
            if needle not in str(e):
                raise
            fired.append(f"{label}: {e}")
            return
        raise Fail(f"{label} did not fire")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        fast = tmp / "whimbrel-fast"
        safe = tmp / "whimbrel-safe"
        lin = tmp / "artifacts"
        lin.mkdir()
        fast.write_bytes(_synthetic_elf((100, 300)))
        safe.write_bytes(_synthetic_elf((200, 200, 50)))
        (lin / "Image-trimmed").write_bytes(b"RISCV" + b"\x01" * 4000)
        (lin / "Image-stock").write_bytes(b"RISCV" + b"\x02" * 9000)
        (lin / INITRD).write_bytes(b"070701" + b"\x00" * 500)
        h = {p.name: sha256_bytes(p.read_bytes()) for p in (fast, safe, lin / "Image-trimmed", lin / "Image-stock", lin / INITRD)}

        def fake_show(rev: str, path: str, *, hashes=h) -> str:
            if path == "results/runs.csv":
                out = io.StringIO()
                w = csv.DictWriter(out, fieldnames=["batch_id", "warmup", "system", "config", "kernel_sha256"], lineterminator="\n")
                w.writeheader()
                for system, config in ARMS:
                    key = {FAST: "whimbrel-fast", SAFE: "whimbrel-safe"}.get(config, LINUX_IMAGE.get(config))
                    for b in ("b-1", "b-2"):
                        w.writerow({"batch_id": b, "warmup": "0", "system": system, "config": config, "kernel_sha256": hashes[key]})
                return out.getvalue()
            if path == "bench/linux/MANIFEST":
                return (
                    "# fixture\n"
                    f"artifact Image-stock {hashes['Image-stock']}\n"
                    f"artifact Image-trimmed {hashes['Image-trimmed']}\n"
                    f"artifact rootfs.cpio {hashes[INITRD]}\n"
                    f"artifact init {'0' * 64}\n"
                )
            raise Fail(f"TEST FAIL: git show {rev}:{path}: fixture has no such object")

        def run(**over):
            kw = dict(pin="T4.Xi", rev="fixture", whimbrel_fast=fast, whimbrel_safe=safe,
                      linux_dir=lin, host="fixture-host", show=fake_show, measured_utc="2026-01-01T00:00:00Z")
            kw.update(over)
            return measure(**kw)

        total, count = elf_pt_load(fast.read_bytes(), "fixture fast")
        if (total, count) != (400, 2):
            raise Fail(f"TEST FAIL: PT_LOAD sum {total}/{count} want 400/2")
        fired.append("elf_pt_load sums PT_LOAD filesz and skips non-load segments")
        rows = run()
        by = {(r["config"], r["role"]): r for r in rows}
        if int(by[(FAST, "kernel")]["loaded_bytes"]) != 400 or int(by[(FAST, "kernel")]["file_bytes"]) != fast.stat().st_size:
            raise Fail("TEST FAIL: fast row sizes wrong")
        if int(by[("stock", "kernel")]["loaded_bytes"]) != 9005 or int(by[("stock", "initrd")]["loaded_bytes"]) != 506:
            raise Fail("TEST FAIL: linux row sizes wrong")
        if len(rows) != 8:
            raise Fail(f"TEST FAIL: {len(rows)} rows, want 8")
        fired.append("measure accepts a clean fixture (5 kernel rows + 3 initrd rows)")
        verify(rows, show=fake_show)
        fired.append("verify accepts the clean record")

        rebuilt = tmp / "whimbrel-fast-rebuilt"
        rebuilt.write_bytes(_synthetic_elf((100, 301)))
        expect_fail(lambda: run(whimbrel_fast=rebuilt), "is not the pin's", "measure refuses an unpinned Whimbrel hash")
        expect_fail(lambda: run(whimbrel_fast=rebuilt, allow_rebuild=True), "requires --note", "measure refuses --allow-rebuild without a note")
        rows_rb = run(whimbrel_fast=rebuilt, allow_rebuild=True, note="rustc 0.0.0 on fixture-host")
        rb = [r for r in rows_rb if r["config"] == FAST and r["role"] == "kernel"][0]
        if rb["sha256"] == rb["pin_sha256"] or not rb["note"]:
            raise Fail("TEST FAIL: rebuild row did not carry both hashes and the note")
        verify(rows_rb, show=fake_show)
        fired.append("measure records a noted rebuild with both hashes; verify accepts it")
        bad_lin = tmp / "artifacts-bad"
        bad_lin.mkdir()
        (bad_lin / "Image-trimmed").write_bytes(b"RISCV" + b"\x03" * 4000)
        (bad_lin / "Image-stock").write_bytes((lin / "Image-stock").read_bytes())
        (bad_lin / INITRD).write_bytes((lin / INITRD).read_bytes())
        expect_fail(lambda: run(linux_dir=bad_lin, allow_rebuild=True, note="x"), "Image-trimmed: sha256", "measure refuses an unpinned Linux Image even with --allow-rebuild")
        elf_lin = tmp / "artifacts-elf"
        elf_lin.mkdir()
        (elf_lin / "Image-trimmed").write_bytes(fast.read_bytes())
        (elf_lin / "Image-stock").write_bytes((lin / "Image-stock").read_bytes())
        (elf_lin / INITRD).write_bytes((lin / INITRD).read_bytes())
        h_elf = dict(h, **{"Image-trimmed": h["whimbrel-fast"]})
        expect_fail(
            lambda: run(linux_dir=elf_lin, show=lambda rev, path: fake_show(rev, path, hashes=h_elf)),
            "is an ELF",
            "measure refuses an ELF where a flat Image is claimed",
        )

        def show_missing_arm(rev, path):
            text = fake_show(rev, path)
            if path == "results/runs.csv":
                text = "\n".join(l for l in text.splitlines() if ",stock," not in l) + "\n"
            return text

        expect_fail(lambda: run(show=show_missing_arm), "want exactly 1", "measure refuses a pin missing an arm")
        expect_fail(lambda: elf_pt_load(b"RISCV" + b"\x00" * 100, "flat"), "is not an ELF", "elf_pt_load refuses a flat file")
        expect_fail(lambda: elf_pt_load(fast.read_bytes()[:300], "truncated"), "extends past the file", "elf_pt_load refuses a truncated ELF")
        expect_fail(lambda: elf_pt_load(fast.read_bytes()[:200], "headers-cut"), "out of range", "elf_pt_load refuses a cut program header table")
        planted = [dict(r) for r in rows]
        planted[0]["pin_sha256"] = "f" * 64
        expect_fail(lambda: verify(planted, show=fake_show), "is not the pin's", "verify refuses a row whose pin hash is not the pin's")
        planted2 = [dict(r) for r in rows]
        for r in planted2:
            if r["config"] == "stock" and r["role"] == "kernel":
                r["sha256"] = "e" * 64
        expect_fail(lambda: verify(planted2, show=fake_show), "only a Whimbrel kernel may be a noted rebuild", "verify refuses a Linux row whose measured hash differs")
        planted3 = [dict(r) for r in rows]
        for r in planted3:
            if r["config"] == FAST:
                r["sha256"] = "d" * 64
        expect_fail(lambda: verify(planted3, show=fake_show), "carries no note", "verify refuses an unnoted Whimbrel rebuild")
        planted4 = [dict(r) for r in rows]
        planted4[-1]["loaded_bytes"] = "1"
        expect_fail(lambda: verify(planted4, show=fake_show), "loaded != file bytes", "verify refuses a flat row with loaded != file")
        expect_fail(lambda: verify([r for r in rows if r["role"] != "initrd"], show=fake_show), "missing or extra", "verify refuses a pin without its initrd rows")
        rec_path = tmp / "record.csv"
        write_record(rec_path, rows, "T4.Xi")
        again = read_record_text(rec_path.read_text(encoding="utf-8"), "fixture record")
        if len(again) != 8 or "\r" in rec_path.read_bytes().decode():
            raise Fail("TEST FAIL: record round-trip")
        write_record(rec_path, rows_rb, "T4.Xi")
        again = read_record_text(rec_path.read_text(encoding="utf-8"), "fixture record")
        if len(again) != 8 or not any(r["note"] for r in again):
            raise Fail("TEST FAIL: write_record did not replace the pin's rows")
        fired.append("write_record replaces a pin's rows and writes LF")
        expect_fail(lambda: read_record_text("a,b\n1,2\n", "bad header"), "header", "read_record_text refuses a wrong header")

    print("TEST PASS: image-bytes fail-closed selftest")
    for line in fired:
        print(f"  fired: {line}")
    return 0


# -------------------------------------------------------------------- CLI


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure", help="measure pinned artifacts on the bench host and write the record")
    m.add_argument("--pin", required=True, help="campaign label, e.g. T4.8c")
    m.add_argument("--rev", required=True, help="the pin's git object, e.g. t48c")
    m.add_argument("--whimbrel-fast", required=True, type=Path)
    m.add_argument("--whimbrel-safe", required=True, type=Path)
    m.add_argument("--linux-dir", type=Path, default=ROOT / "bench" / "linux" / "artifacts")
    m.add_argument("--host", default=socket.gethostname())
    m.add_argument("--allow-rebuild", action="store_true", help="accept a Whimbrel ELF whose sha256 is not the pin's; requires --note")
    m.add_argument("--note", default="", help="toolchain and host of a rebuild, e.g. 'rustc 1.9x.0 (…) on bench-host'")
    m.add_argument("--record", type=Path, default=RECORD)
    v = sub.add_parser("verify", help="re-check a record against the pins (needs git only)")
    v.add_argument("--record", type=Path, default=RECORD, help="working-tree record")
    v.add_argument("--rev", default=None, help="read the record as a git object at this rev instead")
    sub.add_parser("selftest", help="planted failing inputs; no git, no artifacts")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "selftest":
            return cmd_selftest()
        if args.cmd == "measure":
            rows = measure(
                pin=args.pin, rev=args.rev, whimbrel_fast=args.whimbrel_fast,
                whimbrel_safe=args.whimbrel_safe, linux_dir=args.linux_dir,
                host=args.host, allow_rebuild=args.allow_rebuild, note=args.note,
            )
            verify(rows)
            all_rows = write_record(args.record, rows, args.pin)
            for r in rows:
                print(
                    f"{r['pin']} {r['system']}/{r['config']} {r['role']}: "
                    f"loaded {int(r['loaded_bytes']):,} B, file {int(r['file_bytes']):,} B, "
                    f"sha256 {r['sha256'][:12]}… {'(noted rebuild)' if r['note'] else '= pin'}"
                )
            print(f"TEST PASS: {len(rows)} rows for {args.pin} written; record now holds {len(all_rows)} rows at {args.record}")
            return 0
        if args.cmd == "verify":
            if args.rev:
                text = git_show(args.rev, RECORD_REL)
                label = f"{args.rev}:{RECORD_REL}"
            else:
                if not args.record.is_file():
                    raise Fail(f"TEST FAIL: record missing: {args.record}")
                text = args.record.read_text(encoding="utf-8")
                label = str(args.record)
            n = verify(read_record_text(text, label))
            print(f"TEST PASS: {n} image-bytes rows verified against their pins ({label})")
            return 0
        raise Fail(f"unknown command {args.cmd}")
    except Fail as e:
        print(e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
