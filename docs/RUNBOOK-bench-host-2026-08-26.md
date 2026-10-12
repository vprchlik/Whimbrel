# Bench-host runbook, 2026-08-26

Three items, all read-only against the pinned campaigns; nothing here
boots a campaign or writes results/runs.csv. Work in the Whimbrel
checkout on the bench host, branch `m4-evaluation`, at the commit
that adds `scripts/image-bytes.py` (subject "Add the image-bytes
record, its script, and the generator column"). Every step names
what it checks and what counts as a stop. On a stop, do not improvise
past it: record the output and bring it back.

## 0. Preflight

```
git pull
git log --oneline -3                 # the image-bytes commit must be at or below HEAD
git status --porcelain               # must print nothing
ls scripts/image-bytes.py            # must exist
python3 scripts/image-bytes.py selftest      # want: TEST PASS: image-bytes fail-closed selftest
just report-exhibits-selftest                # want: TEST PASS: report-exhibits fail-closed selftest
python3 scripts/bench.py check-linux-artifacts   # want: every artifact's sha256 equals bench/linux/MANIFEST
```

Stop if the tree is dirty, either selftest is not `TEST PASS`, or
`check-linux-artifacts` reports a mismatch. The last one means
`bench/linux/artifacts/` no longer holds the T4.8b/T4.8c Images and
cpio; item 1 cannot run and nothing should be rebuilt to "fix" it.

## 1. Image bytes (D-0083 A2)

The report's cross-system table gains an image-bytes column: the
`-kernel` file as QEMU loads it (sum of `PT_LOAD` file sizes for
Whimbrel's ELF, file length for a Linux `Image`). The sizes are not
derivable from anything committed; they must be measured on the
files the campaigns booted, each verified by sha256 against the pin.
The script refuses any file whose hash is not the pin's.

### 1a. Toolchain state, first

This decides whether a Whimbrel rebuild could reproduce the pin.
Record all three outputs verbatim.

```
rustc --version
rustup show active-toolchain
ls -la --time-style=long-iso ~/.rustup/toolchains/
```

If the stable toolchain directory's timestamp is after 2026-08-21
(the T4.8c campaign day), a rebuild at the pin's `git_sha` will
probably not hash to the pin. That is not a stop by itself; it
decides which path 1c takes.

### 1b. Campaign copies of the Whimbrel kernels

The harness copies each arm's kernel to `results/bin/<config>` per
campaign, overwriting the previous campaign's. If T4.8c was the last
campaign run here, these are the T4.8c ELFs and no rebuild is needed.

```
sha256sum results/bin/release-fast-boot results/bin/release-default
```

Want, for T4.8c (pin `t48c`):

```
e5e304136e26f115e719478997af560d9a94486a702ea88772e4aaa38fb479fc  release-fast-boot
1e65498521caf38a8e0ae2e5f26ea032dd81ce040d16a94b7ca84ce7a25d6827  release-default
```

Both match: set `FAST=results/bin/release-fast-boot` and
`SAFE=results/bin/release-default` and skip to 1c only for T4.8b.
Either differs, or the files are missing: 1c for both pins.

### 1c. Rebuild path (only where 1b did not match)

T4.8b's Whimbrel kernels are the same two files T4.8 booted (git_sha
`1005399`; the T4.8b tree `06687e2` changed no kernel file). T4.8c's
are built at `1c8816e`. Wanted hashes:

```
T4.8b / T4.8:  1e43a31023ec25f0154b3bc325554109fb988c451e0288b995f5295675fd19ca  release-fast-boot
               801cae40af49e67cbd44bdaf14879a598e85f3f46ee39c5e4cdbe46ce2b503bf  release-default
T4.8c:         e5e304136e26f115e719478997af560d9a94486a702ea88772e4aaa38fb479fc  release-fast-boot
               1e65498521caf38a8e0ae2e5f26ea032dd81ce040d16a94b7ca84ce7a25d6827  release-default
```

For each pin you need (`SHA` = `1005399` for T4.8b, `1c8816e` for
T4.8c):

```
git worktree add /tmp/wt-$SHA $SHA
( cd /tmp/wt-$SHA \
  && cargo build --release --features fast-boot \
  && cp target/riscv64gc-unknown-none-elf/release/whimbrel /tmp/whimbrel-fast-$SHA \
  && cargo build --release \
  && cp target/riscv64gc-unknown-none-elf/release/whimbrel /tmp/whimbrel-safe-$SHA )
sha256sum /tmp/whimbrel-fast-$SHA /tmp/whimbrel-safe-$SHA
```

Hashes match the wanted pair: use those two paths in 1d.

Hashes differ (the toolchain moved): this is the disclosed fallback,
not a silent substitution. Measure anyway with `--allow-rebuild` and
a `--note` naming the toolchain and host, taken from 1a:

```
--allow-rebuild --note "rebuilt at $SHA under $(rustc --version) on $(hostname); sha256 differs from the pin"
```

The row then records both hashes and the note, `verify` accepts it
only because the note is present, and the exhibit marks the cell (†)
and discloses the rebuild in its caption. There is no such path for
Linux: the Images and cpio on this host must hash to the pin, and
the script refuses otherwise (that is a stop; see 0).

### 1d. Measure

One command per pin. Each reads the pin's `results/runs.csv` and
`bench/linux/MANIFEST` via `git show`, hashes every file, refuses a
mismatch, and writes `results/image-bytes.csv` (5 kernel rows plus 3
initrd rows per pin).

```
python3 scripts/image-bytes.py measure --pin T4.8c --rev t48c \
    --whimbrel-fast "$FAST_T48C" --whimbrel-safe "$SAFE_T48C" \
    --linux-dir bench/linux/artifacts
python3 scripts/image-bytes.py measure --pin T4.8b --rev t48b \
    --whimbrel-fast "$FAST_T48B" --whimbrel-safe "$SAFE_T48B" \
    --linux-dir bench/linux/artifacts
```

Want, each: eight `loaded … B, file … B, sha256 … = pin` lines (or
`(noted rebuild)` on a Whimbrel row from 1c's fallback) and
`TEST PASS: 8 rows for T4.8x written`. Any `TEST FAIL` is a stop.

### 1e. Verify and commit

```
python3 scripts/image-bytes.py verify      # want: TEST PASS: 16 image-bytes rows verified against their pins
git add results/image-bytes.csv
git commit -m "Record image bytes for the T4.8b and T4.8c pins (D-0083 A2)"
git log -1 --format=%H
git worktree remove /tmp/wt-1005399 2>/dev/null; git worktree remove /tmp/wt-1c8816e 2>/dev/null
```

Push the branch or sync the commit however you normally do.

### Bring back from item 1

- The commit hash from `git log -1 --format=%H` (it becomes
  `IMAGE_BYTES_REV` in `scripts/report-exhibits.py`; the exhibits
  regenerate with the column from it).
- The full output of 1a, 1b, both 1d commands, and 1e's verify.
- Whether either pin took the 1c fallback, and the exact `--note`.

## 2. `just bench-selftest`

What it checks: the harness's fail-closed gates on planted inputs
(missing tshark, malformed PHASE, zero-trial CSV, QEMU/git mismatch,
dirty tree, host controls, D-0071 schema and intervals, T4.8 argv),
and, new since F8, that the `scan-mtrap` CLI refuses a planted `M!`
serial through the real `bench.py` entry point.

```
just bench-selftest
just test-mtrap-planted
```

Want: `TEST PASS: bench fail-closed selftest`, with these three among
the `fired:` lines:

```
scan-mtrap plant: TEST FAIL: M-mode trap diagnostic 'M!' in serial (falsifier 3): …
scan-mtrap clean serial passes
scan-mtrap missing file: TEST FAIL: serial log missing …
```

and `test-mtrap-planted` ending in `TEST PASS`. A nonzero exit or any
of the three lines absent is a stop.

Bring back: both outputs.

## 3. A shim boot that actually traps (D-0079 F8)

F8 changed `scripts/boot-test.sh` to run `scan-mtrap` on the shim
lane after QEMU, on every exit path including a timeout, so an
M-mode trap in the shim is reported as `TEST FAIL` (falsifier 3)
rather than `TEST HANG`. That integration has only been desk-checked.
This item runs a shim boot that is known to trap.

First confirm the lane itself passes, so a failure below is the trap
and not the lane:

```
just test-m
```

Want: two `TEST PASS: found "M3 UNIKERNEL OK"` lines and the lane's
curl checks passing. Anything else is a stop (the lane is broken,
and item 3 cannot be read).

Now the trapping boot. Build the shim blob exactly as `test-m` does,
then boot the DEFAULT kernel under it. The default kernel is the
OpenSBI-lane image: its first SBI call (`sbi::require_dbcn`, an
`ecall` from S-mode) is the one exception the shim does not delegate,
so it lands in the shim's `mtvec` diagnostic, which prints
`M! <cause> <epc> <tval>` with cause `9` and parks in `wfi`. QEMU
never exits, `timeout` returns 124, and `boot-test.sh` must scan the
serial before classifying that 124.

```
cargo build --release --features mshim
blob=target/riscv64gc-unknown-none-elf/release/mshim.bin
bash scripts/mshim-blob.sh target/riscv64gc-unknown-none-elf/release/whimbrel "$blob"
QEMU_BIOS="$blob" PROFILE=release EXPECT="M3 UNIKERNEL OK" TIMEOUT_S=12 \
    bash scripts/boot-test.sh ""; echo "boot-test exit=$?"
grep -a 'M!' serial.log
```

Want:

- boot-test prints `TEST FAIL: M-mode trap diagnostic 'M!' in serial
  (falsifier 3): 'M! 0000000000000009 …'` and `boot-test exit=1`.
- `grep` shows one `M! 0000000000000009 <epc> <tval>` line (cause 9,
  environment call from S-mode).

Stops, each meaning something specific:

- `TEST HANG: timed out …` and exit 2: the 124 path did not scan.
  The F8 integration is wrong; bring back `serial.log` and the full
  output.
- `TEST PASS`: the boot did not trap. Either the kernel booted was
  not the default image or the blob was not used; check that the
  build had no `--features` and that `QEMU_BIOS` pointed at
  `mshim.bin`.
- `M!` with a cause other than `0000000000000009`: a real shim
  problem, not this test. Stop and bring back the serial.

This boot is a deliberate falsifier-3 hit inside a gate, not a
campaign; it records nothing and the `serial.log` / `whimbrel.pcap`
it leaves in the repo root are gitignored.

Bring back: the boot-test output, the `M!` line, and the `test-m`
output from the first step.

## Done when

- `results/image-bytes.csv` is committed with 16 rows and `verify`
  passes (item 1), or a stop is recorded with its output.
- `just bench-selftest` and `just test-mtrap-planted` pass with the
  three scan-mtrap lines (item 2).
- The trapping shim boot reports `TEST FAIL` (falsifier 3) with
  cause 9 (item 3).
- `git status --porcelain` shows nothing but the item-1 commit's
  effects.
