# Bench-host runbook, 2026-10-13

This runbook supersedes `docs/RUNBOOK-bench-host-2026-08-26.md`: its
items 1 to 3 are carried over verbatim, its item 0 is updated, and
items 4 to 8 are new. It is everything that needs the bench host or
any Linux, for one evening, in order. No batch run here produces a
number that enters the report (D-0083, scope decision); the one
harness run in it (5d) is optional and its CSVs are discarded. Work
in the Whimbrel checkout on the bench host, branch `m4-evaluation`
(SETUP §7's example clone path is `/home/victor/src/Whimbrel`), from
a plain login shell (SETUP §7, "Measurement shell"). Every step names
what it checks and what counts as a stop. On a stop, do not improvise
past it: record the output and bring it back.

## 0. Preflight (10 min)

Write the hash from "Before you go" step 7 here, by hand, before the
sitting: `________`. When this runbook was written the newest commit
on `m4-evaluation` was `12404d1` ("Add Threats items 22 and 23
(D-0083 A5) and the 2026-08-26 bench-host runbook"); the written hash
is newer, because the audit, the T4.12 catch-up, the revision, and
this file land first.

```
git pull
git log --oneline -3                 # the hand-written hash must be at or below HEAD
git log -1 --format=%h               # want: exactly the hand-written hash
git merge-base --is-ancestor 12404d1 HEAD && echo "12404d1 at or below HEAD"
git status --porcelain               # must print nothing
W=$(git rev-parse --show-toplevel); echo "$W"    # later items cd here
ls scripts/image-bytes.py            # must exist
python3 scripts/image-bytes.py selftest      # want: TEST PASS: image-bytes fail-closed selftest
just report-exhibits-selftest                # want: TEST PASS: report-exhibits fail-closed selftest
python3 scripts/bench.py check-linux-artifacts   # want: every artifact's sha256 equals bench/linux/MANIFEST
python3 --version                    # record
qemu-system-riscv64 --version | head -1
sha256sum "$(command -v qemu-system-riscv64)"
just --version                       # record
tshark --version | head -1           # record
for t in baseline-t4.3 t44 t48b t48c; do
  git rev-parse -q --verify "refs/tags/$t" >/dev/null && echo "$t ok" || echo "$t MISSING"
done
```

Want for QEMU, both from `report/exhibits/machine-spec.md` (the
`qemu_version` and `qemu_hash` lines):

```
QEMU emulator version 10.2.1 (Debian 1:10.2.1+ds-1ubuntu3.2)
89a99b20357ac92b2c6a533fe79d6fab6b507784858299f7109651f2d524d274  /usr/bin/qemu-system-riscv64
```

(the path is whatever `command -v` prints; the hash is what the
harness records as `qemu_hash`, the sha256 of that binary).

Stop if the tree is dirty, either selftest is not `TEST PASS`, or
`check-linux-artifacts` reports a mismatch. The last one means
`bench/linux/artifacts/` no longer holds the T4.8b/T4.8c Images and
cpio; item 1 cannot run and nothing should be rebuilt to "fix" it.

Further stops, new in this runbook:

- HEAD is not the hand-written hash: the pull did not bring what the
  Windows side pushed, or something was pushed after the hash was
  written. Bring back `git log --oneline -5` and stop.
- A tag prints `MISSING`: items 1, 4, and 5 read those tags
  (`scripts/report-exhibits.py`, `scripts/image-bytes.py
  measure --rev`). Stop.
- `just` or `tshark` is missing: items 0 to 5 run `just`, and item
  5's pcap pass and item 3's lane need `tshark`. Stop.
- The QEMU version line or hash differs: the pinned QEMU moved
  (an unattended package upgrade would do it). Do not reinstall or
  downgrade it tonight. Record both lines. Items 1, 2, 4, and 5 boot
  nothing and continue; items 3 and 6 and the optional 5d boot QEMU
  and are skipped.

## Items 1 to 3, carried over

The three sections below are the 2026-08-26 runbook's items 1 to 3,
unchanged. One override: where 1e says to push, do not push yet;
item 7 pushes. Time: item 1, 20 min (45 min if 1c rebuilds both
pins); item 2, 10 min; item 3, 10 min.

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

## 4. Pin the image-bytes record (10 min)

Needs item 1's commit. The generator reads `results/image-bytes.csv`
as a git object at `IMAGE_BYTES_REV` and never from the working tree;
while that constant is `None`, the T4.8b, T4.8c, and
current-comparison exhibits print a "column pending" line instead of
the column (`scripts/report-exhibits.py`, `IMAGE_BYTES_PENDING`).
Pinning it is one line. This item could also be done on Windows after
the push; it is done here so that item 5 reproduces it on a clean
checkout.

```
cd "$W"
IB=<the full hash item 1 brought back from 1e>
git cat-file -e "$IB:results/image-bytes.csv" && echo "record present at $IB"
python3 scripts/image-bytes.py verify --rev "$IB"
    # want: TEST PASS: 16 image-bytes rows verified against their pins (<IB>:results/image-bytes.csv)
grep -n '^IMAGE_BYTES_REV' scripts/report-exhibits.py
    # want: one line, IMAGE_BYTES_REV: str | None = None
sed -i "s/^IMAGE_BYTES_REV: str | None = None\$/IMAGE_BYTES_REV: str | None = \"$IB\"/" scripts/report-exhibits.py
grep -n '^IMAGE_BYTES_REV' scripts/report-exhibits.py
    # want: one line, IMAGE_BYTES_REV: str | None = "<IB>"
git diff --stat                      # want: scripts/report-exhibits.py | 2 +-, 1 file changed
just report-exhibits
    # want first line: TEST PASS: exhibits from baseline-t4.3 + … → …/report/exhibits
    # want last line:  image bytes: from <IB>
git status --porcelain
```

Want, exactly these four lines:

```
 M report/exhibits/cross-system-current.md
 M report/exhibits/cross-system-t48b.md
 M report/exhibits/cross-system-t48c.md
 M scripts/report-exhibits.py
```

Then confirm the column replaced the pending line, and that the
selftest still passes:

```
grep -l 'column pending' report/exhibits/*.md                  # want: no output
grep -l 'D_fin median | image bytes |' report/exhibits/*.md    # want: the three files above
git diff report/exhibits/ | grep '^[-+]' | grep -v '^[-+][-+]' | head -40
just report-exhibits-selftest        # want: TEST PASS: report-exhibits fail-closed selftest
```

The diff should show, per file, the pending paragraph removed, the
table header and each row gaining an image-bytes cell, and a caption
paragraph citing `git show <IB>:results/image-bytes.csv`. A cell with
`†` means item 1 took the 1c fallback for that pin; its caption
carries the `--note`.

Stops:

- `verify --rev` or `just report-exhibits` prints `TEST FAIL`: the
  record and the pins disagree. Bring back the output; do not edit
  the record.
- The `sed` left the line unchanged (second `grep` still shows
  `None`): the constant's line no longer has that exact form. Stop
  and bring back the `grep` output; do not hand-edit around it.
- `git status --porcelain` shows any other file, or misses one of the
  three exhibits. A different exhibit changing means the committed
  exhibits were not regenerated after a generator change on the
  Windows side (DEBUGGING.md, "Regenerated exhibits all show
  modified, with mangled characters": the idempotence check is the
  detector). Bring back `git status --porcelain` and `git diff
  --stat`, then `git checkout -- report/ scripts/report-exhibits.py`
  and go on to item 5, which runs at `HEAD` in this case.
- The pending line is still present, or the header lacks the column.

Commit (the message carries no `Co-authored-by` trailer; commit
`5a2d14c`):

```
git add scripts/report-exhibits.py report/exhibits/cross-system-t48b.md \
    report/exhibits/cross-system-t48c.md report/exhibits/cross-system-current.md
git commit -m "Pin the image-bytes record; the cross-system exhibits gain the column" \
    -m "D-0083 A2. IMAGE_BYTES_REV is $IB, the commit that records results/image-bytes.csv. Regenerated with just report-exhibits; only cross-system-t48b.md, cross-system-t48c.md, and cross-system-current.md changed, each trading its pending line for the column."
git log -1 --format=%H
git status --porcelain               # must print nothing
```

After the sitting, on Windows: `report/draft.md` (the paragraph
ending "the measurement itself is the remaining bench-host task")
and the image-bytes row of `report/appendix-regenerate.md` ("unset
until the bench-host measurement lands") still describe the column
as pending. That edit is not part of this item.

Bring back: the `git log -1 --format=%H` hash (item 5 checks out this
commit), the `verify --rev` line, the `git status --porcelain` output
before the commit, and the `head -40` diff excerpt.

## 5. T4.11 acceptance regeneration on a clean checkout (20 min; 5d adds 15 min)

D-0083 reads gate 1 as byte-identical reproduction of every exhibit
from the pins on a clean checkout. The generators read git objects,
never the working tree (D-0067), so a fresh worktree at item 4's
commit must regenerate every file under `report/exhibits/` (fourteen
at `12404d1`) with no diff. Three generators write them:
`scripts/report-exhibits.py` (twelve files),
`scripts/regime-witness.py` (`regime-witness.md`), and
`scripts/d0070-pcap-pass.py` (`d0070-pcap.md`);
`scripts/image-bytes.py verify` re-checks the record and writes
nothing. The justfile has `regime-witness-selftest` but no recipe
that generates the regime-witness exhibit; the script generates it
when run with no argument (its usage line is `regime-witness.py
[selftest]`).

If item 4 did not commit (item 1 or item 4 stopped), run this item
anyway at `HEAD`; `just report-exhibits` then ends `image bytes:
column pending (IMAGE_BYTES_REV unset; D-0083 A2)`, and `just
image-bytes-verify` is skipped if item 1 made no record. It still
checks every other exhibit.

### 5a. Worktree and pcaps

`just d0070-pcap-pass` reads one pcap per recorded trial at
`results/trials/<batch>/<config>/<NN>/qemu.pcap`, relative to the
checkout it runs in (the `pcap_path` column of the pinned
`runs.csv`). Those files are gitignored and exist only in this
host's checkout, so the worktree gets copies of the six batch
directories the script names (`CAMPAIGNS` in
`scripts/d0070-pcap-pass.py`: T4.6 and both D-0068 runs).

```
cd "$W"
git log -1 --format=%H               # want: item 4's hash
ACCEPT=$(git rev-parse HEAD)
B="20260817T061753Z-1 20260817T061753Z-2 20260818T013740Z-1 20260818T013740Z-2 20260818T014549Z-1 20260818T014549Z-2"
for b in $B; do test -d "results/trials/$b" && echo "$b present" || echo "$b ABSENT"; done
du -sch $(for b in $B; do echo "results/trials/$b"; done) 2>/dev/null | tail -1
df -h /tmp | tail -1
git worktree prune
git worktree add /tmp/wt-accept "$ACCEPT"
mkdir -p /tmp/wt-accept/results/trials
for b in $B; do test -d "results/trials/$b" && cp -a "results/trials/$b" /tmp/wt-accept/results/trials/; done
git -C /tmp/wt-accept status --porcelain     # must print nothing
```

Copy, do not symlink: `results/.gitignore` ignores `trials/`, a
pattern that matches only a directory, and git treats a symlink as a
file, so a symlinked `results/trials` would show as untracked. The
worktree lives under `/tmp` because Ubuntu 26.04's tshark AppArmor
profile reads pcaps under `/tmp` and, with the SETUP §7 override,
under the clone path only.

Any batch `ABSENT`, or `/tmp` too small for the `du` total: the
pcap pass cannot run. That is not a stop. The committed
`report/exhibits/d0070-pcap.md` stands, and the absence is recorded:
bring back the six `present`/`ABSENT` lines (and the `du`/`df`
lines). Skip `just d0070-pcap-pass` in 5b.

### 5b. Regenerate in the worktree

```
cd /tmp/wt-accept
just report-exhibits
    # want first line: TEST PASS: exhibits from baseline-t4.3 + … → /tmp/wt-accept/report/exhibits
    # want last line:  image bytes: from <IB>
just regime-witness-selftest         # want: TEST PASS: regime-witness fail-closed selftest
python3 scripts/regime-witness.py
    # want first line: TEST PASS: regime-witness → /tmp/wt-accept/report/exhibits/regime-witness.md
just d0070-pcap-pass
    # want: the exhibit printed to stdout, its first line
    # <!-- generated by scripts/d0070-pcap-pass.py — do not edit -->, and exit 0;
    # progress lines "d0070-pcap-pass: N/360 trials" go to stderr
just image-bytes-verify
    # want: TEST PASS: 16 image-bytes rows verified against their pins (/tmp/wt-accept/results/image-bytes.csv)
git status --porcelain               # must print nothing
```

The last command is gate 1. It must print nothing: no ` M` line (an
exhibit that did not reproduce) and no `??` line (a generator wrote a
file that is not committed).

Stops:

- Any generator prints `TEST FAIL`. Bring back its full output.
- `git status --porcelain` prints anything. Any existing exhibit
  showing modified after a regeneration is a stop, not noise to work
  around (DEBUGGING.md, the idempotence check). Capture it before
  touching anything, and leave the worktree in place:

  ```
  git -C /tmp/wt-accept status --porcelain > ~/accept-status.txt
  git -C /tmp/wt-accept diff > ~/accept-diff.txt
  ```

  Bring back both files. If the diff touches any of item 4's three
  exhibits or `scripts/report-exhibits.py`, item 7 pushes item 1's
  commit only. Two diffs have a known cause that is not item 4: a
  one-line diff in `regime-witness.md` adding its selftest sentence
  would mean the checkout predates `1ed0918`, which item 0's hash
  check rules out, so any `regime-witness.md` diff here is a real
  stop; a diff in `d0070-pcap.md` may come from its extractor
  changing after the exhibit was generated (exhibit `25e497f`;
  `scripts/d0070-pcap-pass.py` or `scripts/pcap_http.py` changed at
  `7307793`, `1c39556`, `06687e2`, and `7fe27fb`). Either is still a
  stop for gate 1, and nothing regenerated here is committed tonight.
- `just d0070-pcap-pass` prints `TEST FAIL: D-0070 pcap pass: N/360
  recorded per-trial pcaps missing or empty` although 5a printed six
  `present` lines: a batch directory is incomplete. Not a stop for
  gate 1 (the script writes nothing when it fails); record it as for
  an absent batch.

### 5c. Clean up

Only if 5b passed:

```
cd "$W"
git worktree remove /tmp/wt-accept
git worktree list                    # want: only $W
git status --porcelain               # must print nothing
```

Bring back from 5a to 5c: `$ACCEPT` (the commit the worktree
reproduced), the full output of 5b, and the final `git status
--porcelain` of the worktree (empty).

### 5d. Optional: harness liveness (owner's call on the night; run after item 7)

D-0083 reads PLAN's M4 sentence about `just bench` as a
harness-liveness check whose CSVs enter nothing; the criterion gate 1
tests is 5b. The justfile at `12404d1` has no `bench` recipe. The
T4.1 recipe whose comment says it writes `results/runs.csv`,
`results/phases.csv`, and `results/summary.txt` is `just
bench-whimbrel` (two interleaved batches, 3 warmup and 30 recorded
trials per config, D-0055). If the T4.12 amendment to PLAN names a
different recipe, run that one and record which.

Run it only after item 7 has pushed HEAD:
`scripts/bench.py` runs `git fetch origin` and refuses with `TEST
FAIL: HEAD … != origin/m4-evaluation …` unless HEAD is pushed, and it
refuses a dirty tree. It also refuses to start unless the D-0055 host
controls hold (SETUP §7: governor, SMT, boost, virt, steal), so
re-apply them first (SETUP §7, "What persists across reboot"):

```
cd "$W"
git status --porcelain               # must print nothing
git rev-parse HEAD origin/m4-evaluation   # want: the same hash twice
powerprofilesctl set performance
sudo bash -c 'echo off > /sys/devices/system/cpu/smt/control; echo 0 > /sys/devices/system/cpu/cpufreq/boost'
just bench-whimbrel 2>&1 | tee ~/bench-liveness.log
git status --porcelain               # expect: M results/phases.csv and M results/runs.csv
git checkout -- results/
git status --porcelain               # must print nothing
```

Want: the run reaches its summary and ends in `TEST PASS: bench
summary`. Other endings, each recorded and none a stop for anything
else tonight:

- A refusal before trial 1 (`TEST FAIL: host control …`, `dirty
  working tree`, `HEAD … != origin/…`, or the D-0078 canary's `TEST
  FAIL: canary boot produced no PHASE dump …`): the harness's gates
  fired. Run the last three commands anyway; the checkout restores
  whatever was written.
- `TEST FAIL: summarize gates not met` after all trials, listing
  stability metrics: the harness ran end to end; the numbers enter
  nothing either way.

Never commit what this writes. `git checkout -- results/` restores the
two tracked CSVs; `results/summary.txt` is gitignored. The run also
overwrites `results/bin/` (the campaign kernel copies 1b read) and
adds a batch under `results/trials/`; both are gitignored.

Bring back: `~/bench-liveness.log` and which recipe ran.

## 6. Unikraft reproduction at the D-0063 pin (if time allows; capped at 2 h)

D-0063's no-go was reached by source analysis. The Unikraft defect
report (drafted separately) is posted only after the crash is
reproduced at the pin. This item builds the catalog-core `c-http`
application for qemu/riscv64 at the pin and boots it on the pinned
QEMU with Whimbrel's argv. No patch is written to Unikraft in any
case, and no source file is edited to get past an error. Skip the
item if item 0 found the QEMU moved: D-0063's conditions name the
pinned QEMU.

The cap: note the start time (`date`, 6a). At start plus 2 h, stop
wherever you are and record "not reproduced: not done within the
cap", with how far it got. A build that is not done by then is not
forced.

Pins (D-0063, "Pin"):

- unikraft: PR #1698 head `e9b1d5496bd9d0678b035dde2986171bf4398c56`,
  `https://github.com/zzSunil/unikraft`, branch `staging`.
- catalog-core: `7196610a` (full hash
  `7196610a2a6dd5979ebd2f14f7412c4413983093`),
  `https://github.com/unikraft/catalog-core`.
- lib-lwip: `ec55ae17`, `https://github.com/unikraft/lib-lwip`.
- kraftkit prerelease `v0.12.15-11-g5019204e`: on record and off the
  critical path; not installed or used here.

Where each step comes from: read on GitHub at those hashes on
2026-10-13. catalog-core: `README.md`, `setup.sh`,
`c-http/README.md`, `c-http/setup.sh`, `c-http/Makefile`,
`c-http/server.c`, `c-http/.scripts/defconfig/qemu.arm64`. unikraft:
`arch/riscv/riscv64/Compiler.uk`, `plat/kvm/Config.uk`,
`plat/kvm/Linker.uk`, `plat/kvm/riscv/traps.c`,
`lib/ukdebug/Config.uk`, `lib/ukdebug/include/uk/assert.h`,
`lib/ukintctlr/ukintctlr.c`, `drivers/ukintctlr/plic/ukintctlr.c`,
`drivers/virtio/{bus,mmio,net}/Config.uk`. lib-lwip: `Makefile.uk`.
The PR description gives `CONFIG_ARCH_RISCV_64=y` as its only
additional configuration and says "tested on Qemu 10.0.3"; the PR
head on 2026-10-13 was still `e9b1d54`.

What those sources fix:

- catalog-core has no riscv64 defconfig for `c-http` at `7196610a`
  (only qemu, fc, and xen for x86_64 and arm64). The defconfig in 6c
  is `qemu.arm64` with `CONFIG_ARCH_ARM_64=y` replaced by the PR's
  `CONFIG_ARCH_RISCV_64=y` and its three arm64 errata lines dropped:
  a configuration change, inside D-0063's no-core-patches line.
- The top-level `setup.sh` clones upstream `unikraft/unikraft`, not
  the PR fork, plus libraries `c-http` does not use. `c-http/setup.sh`
  only links `../repos/unikraft` and `../repos/libs/lwip`, so 6b
  clones those two, at the pins, and nothing else.
- The cross prefix for riscv64 is `riscv64-linux-gnu-`
  (`arch/riscv/riscv64/Compiler.uk`).
- The image is `workdir/build/c-http_qemu-riscv64` (`plat/kvm/Linker.uk`:
  `$(CONFIG_UK_NAME)_$(KVM_VMM)-$(CONFIG_UK_ARCH)`), entry
  `_libkvmplat_entry`.
- Assertions are `CONFIG_LIBUKDEBUG_ENABLE_ASSERT`, default `y`
  (`lib/ukdebug/Config.uk`); the catalog's own defconfigs write a
  disabled option as `=n`.
- `c-http` listens on guest port 8080 (`server.c`, `LISTEN_PORT
  8080`), prints `Listening on port 8080...`, and replies `Hello from
  Unikraft!`. Whimbrel's argv forwards host 8080 to guest port 80
  (`scripts/qemu-args.sh`, `hostfwd=tcp::${tcp_port}-:80`). The boot
  therefore carries two recorded deltas: `hostfwd=tcp::8080-:8080`,
  and an `-append` giving lwIP Whimbrel's slirp address (10.0.2.15,
  gateway 10.0.2.2) in the README's `netdev.ip=` form. Neither is on
  the path outcomes (a) and (b) predict, which fire before `main`.
- lib-lwip's `Makefile.uk` downloads the lwIP source archive from
  `github.com/unikraft/fork-lwip` during `make`; the build needs the
  network.
- `scripts/bench-client.py` checks for Whimbrel's 92-byte response,
  so the client here is `curl`.

### Pre-registered outcomes

Written before any build; the serial logs decide which fired.

- **(a) Asserts on** (the default): during bus probing, before
  `main`, the serial shows `Assertion failure:
  uk_intctlr->ops->fdt_xlat` (the `UK_ASSERT` at
  `lib/ukintctlr/ukintctlr.c:222` at the pin, inside the lines 212 to
  225 D-0063 cites; `assert.h` prints `Assertion failure: %s` and
  triggers the crash path). Neither `Powered by` (the banner the
  catalog README shows on a good boot) nor `Listening on port
  8080...` appears.
- **(b) Asserts off**: the call through the PLIC driver's `.fdt_xlat =
  __NULL` fetches from address 0. The serial shows `Unhandled Trap …
  scause=0x1, stval=0x0` or `… scause=0xc, stval=0x0` (`traps.c`
  prints `Unhandled Trap %d (%s), scause=0x%lx, stval=0x%lx`; 0x1 and
  0xc are the instruction access and instruction page faults), or a
  crash report naming PC 0, before the banner.
- **(c)** The image boots, prints `Listening on port 8080...`, and
  `curl` gets `Hello from Unikraft!`: D-0063 is refuted. Stop
  everything downstream: the defect report is withdrawn, and a new
  decision entry records the refutation (on Windows, not tonight).

Anything else (no serial output at all, a different assertion, a
trap with another cause or address, a build failure) is recorded as
"not reproduced as registered", with the log. It does not refute
D-0063 and it does not clear the defect report for posting.

### 6a. Toolchain (10 min)

```
date
apt-cache policy gcc-riscv64-linux-gnu | head -3
```

The pinned sources give only the prefix `riscv64-linux-gnu-`;
`gcc-riscv64-linux-gnu` is the Ubuntu package expected to ship
`riscv64-linux-gnu-gcc`, and this runbook did not read that from the
host's archive. Check first: want a `Candidate:` line that is not
`(none)`. If it is `(none)`, run `sudo apt-get update` once and check
again; still `(none)`: stop the item ("not reproduced: no
toolchain").

```
sudo apt-get install -y --no-install-recommends gcc-riscv64-linux-gnu \
    build-essential flex bison libncurses-dev libyaml-dev git wget curl \
    uuid-runtime libarchive-tools
command -v riscv64-linux-gnu-gcc     # must print a path
riscv64-linux-gnu-gcc --version | head -1
make --version | head -1
qemu-system-riscv64 --version | head -1   # want: unchanged from item 0
```

The package list is catalog-core's README apt line minus its QEMU,
`sgabios`, and aarch64 packages, so nothing in it moves the pinned
QEMU. Stop if the QEMU line changed.

### 6b. Sources at the pins (10 min)

Outside the Whimbrel checkout:

```
UKR=$HOME/uk-repro
mkdir -p "$UKR" && cd "$UKR"
git clone https://github.com/unikraft/catalog-core
git -C catalog-core checkout 7196610a2a6dd5979ebd2f14f7412c4413983093
git clone --branch staging https://github.com/zzSunil/unikraft catalog-core/repos/unikraft
git -C catalog-core/repos/unikraft checkout e9b1d5496bd9d0678b035dde2986171bf4398c56
git clone https://github.com/unikraft/lib-lwip catalog-core/repos/libs/lwip
git -C catalog-core/repos/libs/lwip checkout ec55ae17
for r in catalog-core catalog-core/repos/unikraft catalog-core/repos/libs/lwip; do
  echo "$r $(git -C "$r" rev-parse HEAD)"
done
```

Want: `7196610a2a6d…`, `e9b1d5496bd9…`, `ec55ae17…` in that order.
If the unikraft checkout fails (the fork's branch was force-pushed
past the pin), fetch the PR ref once and retry:

```
git -C catalog-core/repos/unikraft fetch https://github.com/unikraft/unikraft pull/1698/head
git -C catalog-core/repos/unikraft checkout e9b1d5496bd9d0678b035dde2986171bf4398c56
```

Any pinned commit still unreachable: stop the item ("not reproduced:
pin unreachable").

### 6c. Configure (15 min)

```
cd "$UKR/catalog-core/c-http"
./setup.sh
ls -l workdir/unikraft workdir/libs/lwip     # want: symlinks into ../repos
cat > "$UKR/defconfig.qemu.riscv64" <<'EOF'
CONFIG_PLAT_KVM=y
CONFIG_KVM_VMM_QEMU=y
CONFIG_ARCH_RISCV_64=y
CONFIG_LIBLWIP=y
CONFIG_LIBUKNETDEV_EINFO_LIBPARAM=y
EOF
make distclean
UK_DEFCONFIG="$UKR/defconfig.qemu.riscv64" make defconfig
ls -l .config
grep -E '^CONFIG_(ARCH_RISCV_64|PLAT_KVM|KVM_VMM_QEMU|LIBLWIP|LIBUKNETDEV|LIBVIRTIO_NET|LIBVIRTIO_BUS|LIBVIRTIO_MMIO|LIBVIRTIO_MMIO_FDT|LIBFDT|LIBUKOFW|LIBUKINTCTLR_PLIC|LIBUKDEBUG_ENABLE_ASSERT|LIBUKCONSOLE|LIBNS16550)=' .config
cp .config "$UKR/config-assert-on"
```

Want `=y` on `ARCH_RISCV_64`, `PLAT_KVM`, `KVM_VMM_QEMU`, `LIBLWIP`,
`LIBUKNETDEV`, `LIBVIRTIO_NET`, `LIBVIRTIO_MMIO`, `LIBVIRTIO_MMIO_FDT`,
`LIBUKINTCTLR_PLIC`, and `LIBUKDEBUG_ENABLE_ASSERT`. Record
`LIBUKCONSOLE` and `LIBNS16550` either way: they are the serial
console, and without them a crash prints nothing.

Stops and the one allowed fix:

- `make defconfig` errors, or `.config` is not in the `c-http`
  directory: stop and record what `make` printed.
- `ARCH_RISCV_64` is not `y`: the fork did not take the arch. Stop.
- `LIBVIRTIO_MMIO` or `LIBVIRTIO_NET` is not `y`: D-0063's trace
  (step 1) predicted both from `LIBLWIP` and `KVM_VMM_QEMU`. Record
  the `.config`, then add the missing line(s) (`CONFIG_LIBVIRTIO_NET=y`,
  `CONFIG_LIBVIRTIO_MMIO=y`) to `$UKR/defconfig.qemu.riscv64` and
  rerun from `make distclean`. That is a configuration change; record
  that the trace's implication did not hold.
- `LIBVIRTIO_MMIO_FDT` is not `y` with `LIBFDT` and `LIBUKOFW` both
  `y`: the promptless default D-0063 relies on did not fire. Record
  and stop; the predicted path is absent.

### 6d. Build, asserts on (up to 45 min)

```
make -j "$(nproc)" 2>&1 | tee "$UKR/build-assert-on.log"
file workdir/build/c-http_qemu-riscv64
sha256sum workdir/build/c-http_qemu-riscv64
cp workdir/build/c-http_qemu-riscv64 "$UKR/c-http_qemu-riscv64.assert-on"
```

Stop on a build failure: bring back the last 50 lines of the log;
the item ends "not reproduced: build failed at the pin". No source
edit, in Unikraft, lib-lwip, or the catalog.

### 6e. Boot, asserts on (5 min)

From the Whimbrel checkout, only to read `scripts/qemu-args.sh`; the
pcap and the serial log go outside the tree:

```
cd "$W"
ss -ltn | grep -q ':8080 ' && echo "PORT 8080 BUSY" || echo "port 8080 free"
ARGS=$(bash scripts/qemu-args.sh /tmp/uk-c-http.pcap | sed 's/hostfwd=tcp::8080-:80,/hostfwd=tcp::8080-:8080,/')
echo "$ARGS"
APPEND='c-http netdev.ip=10.0.2.15/24:10.0.2.2::: -- '
IMG="$UKR/c-http_qemu-riscv64.assert-on"
( timeout 60 qemu-system-riscv64 $ARGS -kernel "$IMG" -append "$APPEND" \
    > "$UKR/serial-assert-on.log" 2>&1; echo "qemu exit=$?" >> "$UKR/serial-assert-on.log" ) &
sleep 20
curl -sS -m 10 -o "$UKR/http-assert-on.body" -w 'http %{http_code}\n' http://127.0.0.1:8080/; echo "curl exit=$?"
wait
cat "$UKR/serial-assert-on.log"
```

Want from `echo "$ARGS"`: `-machine virt -nographic -bios default
-global virtio-mmio.force-legacy=false -netdev
user,id=net0,hostfwd=tcp::8080-:8080,hostfwd=udp::7777-:7 -device
virtio-net-device,netdev=net0,csum=off,…  -object
filter-dump,id=f0,netdev=net0,file=/tmp/uk-c-http.pcap`. If it
still shows `-:80,`, the `sed` did not match: stop and read
`scripts/qemu-args.sh` before booting. `PORT 8080 BUSY`: another
QEMU is running; stop it first.

Read the serial log against (a), (b), and (c). The `curl` runs in
every case and fails under (a) and (b); that is expected. If the log
shows `Listening on port 8080...` but `curl` failed, rerun this block
with `sleep 40` before deciding. A halted guest may keep QEMU alive
until `timeout` (exit 124) or may shut it down; the exit code is
recorded, and the log decides.

(c) fired: stop here (see the outcome above). Otherwise continue.

### 6f. Asserts off: configure, build, boot (30 min)

```
cd "$UKR/catalog-core/c-http"
printf 'CONFIG_LIBUKDEBUG_ENABLE_ASSERT=n\n' >> "$UKR/defconfig.qemu.riscv64"
make distclean
UK_DEFCONFIG="$UKR/defconfig.qemu.riscv64" make defconfig
grep LIBUKDEBUG_ENABLE_ASSERT .config     # want: # CONFIG_LIBUKDEBUG_ENABLE_ASSERT is not set
cp .config "$UKR/config-assert-off"
make -j "$(nproc)" 2>&1 | tee "$UKR/build-assert-off.log"
sha256sum workdir/build/c-http_qemu-riscv64
cp workdir/build/c-http_qemu-riscv64 "$UKR/c-http_qemu-riscv64.assert-off"
```

Then repeat 6e with every `assert-on` replaced by `assert-off`
(`IMG`, the serial log, the `curl` body). Same stops as 6c and 6d.

### Bring back from item 6

- `serial-assert-on.log` and `serial-assert-off.log`.
- `config-assert-on`, `config-assert-off`, and
  `defconfig.qemu.riscv64` (with any 6c additions).
- The build logs, or their last 50 lines where a build failed.
- The exact commands as run: this section plus every deviation, the
  `echo "$ARGS"` line, and the `APPEND` string.
- Toolchain versions (6a's `riscv64-linux-gnu-gcc`, `make`, and QEMU
  lines), the three `rev-parse HEAD` lines (6b), and each image's
  sha256.
- Which outcome fired for each boot: (a), (b), (c), or not
  reproduced as registered.

These files stay out of the Whimbrel tree tonight; where they go
afterwards is decided on Windows.

## 7. Push (5 min)

The sitting makes at most two commits on `m4-evaluation`: item 1's,
then item 4's. Item 5 commits nothing. If time is short, do this item
before item 6, which commits nothing; 5d needs it done.

Normal case (item 5 passed, or only its pcaps were absent):

```
cd "$W"
git status --porcelain               # must print nothing
git log --oneline -3                 # want: item 4's commit on top, item 1's below it
git push origin m4-evaluation
git rev-parse HEAD origin/m4-evaluation   # want: item 4's hash, twice
```

Item 5 stopped on a diff that touches item 4's three exhibits or
`scripts/report-exhibits.py`: item 1's record is verified on its own,
and item 4's regeneration is what failed to reproduce, so push item
1's commit only (a diff confined to other exhibits leaves item 4's
commit reproduced; use the normal case and bring back the diff):

```
git push origin <item 1's hash>:m4-evaluation
git rev-parse origin/m4-evaluation   # want: item 1's hash
```

Item 4's commit stays local and unpushed, and 5d does not run.

Item 4 did not commit (its stop): push item 1's commit with the plain
`git push origin m4-evaluation`; HEAD is item 1's commit.

Item 1 stopped (no commit): there is nothing to push.

Bring back one hash per item:

| item | hash |
|---|---|
| 1 | `git log -1 --format=%H` after 1e (the record) |
| 4 | `git log -1 --format=%H` after its commit (`IMAGE_BYTES_REV` set) |
| 5 | `$ACCEPT`, the commit the clean worktree reproduced (no new commit) |
| 7 | `git rev-parse origin/m4-evaluation` after the push |

## 8. Audit bench-host items (30 min)

Written from `docs/AUDIT-2026-10.md` as it stood on 2026-10-13 at
01:27 EDT [05:27 UTC], uncommitted then: its section 8 ("Bench-host
items", ten entries) and its findings tagged `[bench-host]` (6, 11,
12, 20, 23, 36, 48). "Before you go" step 2 reconciles this item with
the audit as committed.

Already done above:

| audit entry | here |
|---|---|
| §8 item 1, image bytes (finding 42) | items 1 and 4 |
| §8 item 2, kernel hashes | 1b and 1c |
| §8 item 3, `bench-selftest`, `test-mtrap-planted` | item 2 |
| §8 item 4, the trapping shim boot (findings 11, 12) | item 3 |
| §8 item 7, every exhibit regenerated (findings 2, 4, 36) | item 5 |
| §8 item 10, `check-linux-artifacts` | item 0 |

One difference: the audit's §8 item 7 expects exactly one modified
file, `regime-witness.md` by finding 2's one-line diff, "to be
committed from there". That file was regenerated from its generator
and committed on Windows at `1ed0918` (2026-10-13), so this runbook
expects no modified file, and item 5 stops on any diff.

### 8a. Selftest sentinels (finding 6) (2 min)

The selftest helpers in `report-exhibits.py` and `regime-witness.py`
would record a validator that did not fire as fired, printing a
`fired:` line that contains `did not fire`. Latent today: both
selftests printed zero such lines on Windows at `12404d1`.

```
cd "$W"
just report-exhibits-selftest 2>&1 | grep -c 'did not fire'   # want: 0
just regime-witness-selftest 2>&1 | grep -c 'did not fire'    # want: 0
```

Stop: any count above 0. Bring back the matching lines.

### 8b. Shim blob size and hash (§8 item 5; finding 10) (5 min)

```
cd "$W"
command -v llvm-objcopy rust-objcopy riscv64-linux-gnu-objcopy   # record
cargo build --release --features mshim
bash scripts/mshim-blob.sh target/riscv64gc-unknown-none-elf/release/whimbrel \
    target/riscv64gc-unknown-none-elf/release/mshim.bin
sha256sum target/riscv64gc-unknown-none-elf/release/mshim.bin
```

`mshim-blob.sh` uses the first objcopy on its list, which starts with
these three; item 6's toolchain adds `riscv64-linux-gnu-objcopy`, so
record which are present. Want: `mshim-blob:
target/riscv64gc-unknown-none-elf/release/mshim.bin (320 bytes)` (320
is D-0079's figure, the sentence in its execution amendment that
begins "`objcopy -O binary --only-section=.mshim` extracts"; nothing committed
measures it, finding 10) and the sha256
`1698b114daec15f0b6b2d6bc8d71a219897840939b75284d42aa6248ae6985fa`
(the `bios_sha256` on every `m-release-*` row of `git show
c2759e2:results/runs.csv`). The audit records that no kernel file
changed after `346f4c1`, the t47c kernel.

Stops, each recorded with both lines:

- A size other than 320: the report's "320-byte" changes (finding 10).
- A hash other than the pin's: the pinned blob does not rebuild from
  the donor at HEAD. Read it with 1a: a toolchain newer than the t47c
  campaign (batches `20260820T130700Z-*`) can account for it; record
  the toolchain beside it and do not chase it tonight.

### 8c. `just test` on the clean checkout (§8 item 6) (5 min)

`just test-m` already ran in item 3; its output there counts for this
entry. Skip this step if item 0 found the QEMU moved.

```
cd "$W"
just test           # want: TEST PASS: M3 UNIKERNEL OK, curl 200, phases, gateway ARP, pcap HTTP
git status --porcelain   # must print nothing
```

Stop: anything other than `TEST PASS`. Bring back the output and
`serial.log`.

### 8d. pcap-derived columns (§8 item 8) (15 min)

The audit names `python3 scripts/pcap_http.py`, but that script's
command line has only `syn-grid`. The six values come from
`extract_pcap` in the same file (`w_ns`, `d_ack_ns`, `d_fin_ns`,
`synack_to_http_ns`, `guest_ftx_ns`, `guest_arp_req_n`), the function
`bench.py` called at trial time; `pcap_http.py` last changed at
`06687e2`, the T4.8b tree, before all three campaigns. The step calls
it on trial 04 of batch `-1` (the first recorded trial) for every arm
of each pin and prints the pinned row above it. `t48b`'s `runs.csv`
has no `synack_to_http_ns` column; its pinned value prints `None`.

```
cd "$W"
for spec in t48b:20260819T142033Z-1 t48c:20260821T233038Z-1 c2759e245bf7cbcf23dcf43ac228b73f06bb0960:20260820T130700Z-1; do
  pin=${spec%%:*}; batch=${spec#*:}
  test -d "results/trials/$batch" || { echo "$pin $batch ABSENT"; continue; }
  for P in results/trials/$batch/*/04/qemu.pcap; do
    echo "== $pin $P"
    git show "$pin:results/runs.csv" | python3 -c 'import csv,sys; p=sys.argv[1]; k=("w_ns","d_ack_ns","d_fin_ns","synack_to_http_ns","guest_ftx_ns","guest_arp_req_n"); [print("pin ", {x: r.get(x) for x in k}) for r in csv.DictReader(sys.stdin) if r["pcap_path"]==p]' "$P"
    python3 -c 'import sys; from pathlib import Path; sys.path.insert(0, "scripts"); from pcap_http import extract_pcap, require_tshark; d = extract_pcap(Path(sys.argv[1]), require_tshark()); d.pop("http_len"); print("pcap", d)' "$P"
  done
done
```

Want: fourteen `==` blocks (five arms for `t48b`, five for `t48c`,
four for `c2759e2`), and in each the `pin` and `pcap` values equal
digit for digit (the pin prints strings, the pcap integers).

Stops and records:

- Any value differs: stop; bring back the whole block.
- `extract_pcap` raises `TEST FAIL: …`: record it for that arm.
- A pin prints `ABSENT`: not a stop. Record that its columns are not
  re-derivable and the pinned rows are the only record (the audit's
  wording).

### 8e. `just measure-e2` under the pinned QEMU (§8 item 9; finding 15) (5 min)

Skip if item 0 found the QEMU moved; the point is the pinned QEMU.

```
cd "$W"
just measure-e2     # want: E2 reset pc=0x1000 time=… then TEST PASS: E2 offset 0 (rdtime at _start is the OpenSBI phase)
git status --porcelain   # must print nothing
```

The recipe builds the debug kernel itself and needs `gdb-multiarch`
(SETUP §1) and port 1234 free. Stop: `TEST FAIL: reset $time is …,
want 0`, which changes the E2 definition at draft:335-339; record any
other `TEST FAIL` with its output.

### No command

- Finding 12: a shim that parks fails a campaign as a QEMU timeout,
  not as falsifier 3. No shim campaign runs tonight; 5d's
  `bench-whimbrel` has only the `release-default` and
  `release-fast-boot` arms.
- Finding 20: `bench.py`'s summarize step compares a CSV's
  `kernel_sha256` with the current `bench/linux/MANIFEST`. Do not run
  `just bench-summary` on a pinned Linux CSV tonight; the exhibits read
  `MANIFEST` at the pin.
- Finding 23: the SYN-grid gate is Linux-only, as the draft's Threats
  item 19(a) states. Nothing to run.
- Finding 48: the scope decision holds. At the end of the sitting,
  `git log --format=%h -1 -- results/runs.csv results/phases.csv` must
  print `fca2f66` ("Record the T4.8c campaign CSVs"); anything newer
  means 5d's CSVs were committed.

## Done when

- Item 0 passed, or its stop is recorded with its output.
- `results/image-bytes.csv` is committed with 16 rows and `verify`
  passes (item 1), or a stop is recorded with its output.
- `just bench-selftest` and `just test-mtrap-planted` pass with the
  three scan-mtrap lines (item 2).
- The trapping shim boot reports `TEST FAIL` (falsifier 3) with
  cause 9 (item 3).
- `IMAGE_BYTES_REV` is item 1's commit, the T4.8b, T4.8c, and
  current-comparison exhibits carry the column and no pending line,
  and `just report-exhibits-selftest` passes (item 4).
- In a clean worktree at item 4's commit, every exhibit regenerates
  byte-identical and `git status --porcelain` prints nothing (item 5),
  with the pcap pass run or its absent batches recorded.
- Item 6 recorded (a), (b), (c), or "not reproduced", with its
  bring-back files, or was skipped for time.
- `origin/m4-evaluation` is item 4's commit, or item 1's after an
  item 5 diff in item 4's files (item 7).
- Item 8's steps are done or their stops recorded.
- `git status --porcelain` in the checkout prints nothing.

## Total time

Items 0 to 5, 7, and 8: about 1 h 55 min (10 + 20 + 10 + 10 + 10 +
20 + 5 + 30 min), or 2 h 35 min with item 1's rebuild path (45 min)
and 5d (15 min). Item 6 adds up to its 2 h cap. With everything:
about 4 h 35 min.

## Before you go (on Windows)

Preflight passes only if these are committed and pushed first:

1. This runbook, committed under `docs/`.
2. `docs/AUDIT-2026-10.md`, the second audit (PLAN T4.11), committed.
   Item 8 was written from the uncommitted file at 01:27 EDT on
   2026-10-13; if the committed section 8 or the `[bench-host]` tags
   differ, bring item 8 into line before the sitting.
3. The T4.12 catch-up: D-0083's in-place amendment pointers and
   PLAN's M4 acceptance sentence amended per D-0083's scope decision.
   That amendment is where the recipe 5d runs gets its name; the
   justfile has no `bench` recipe.
4. The revision (the audit's blockers fixed before it).
5. On Windows, after the last generator or exhibit change:
   `just report-exhibits` and `python3 scripts/regime-witness.py`,
   then `git status --porcelain` must print nothing. Item 4 stops if
   any exhibit other than its three changes on the host, and item 5
   stops on any diff. `report/exhibits/regime-witness.md` was
   regenerated from its generator and committed at `1ed0918`
   (2026-10-13), so it no longer diffs; expect no diff from either
   generator. (`d0070-pcap.md` cannot be checked here; its pcaps are
   on the bench host, and 5b is its check.)
6. `git push origin m4-evaluation`, then `git ls-remote --tags origin`
   must list `baseline-t4.3`, `t44`, `t48b`, and `t48c` (item 0 checks
   them on the host).
7. Run `git log -1 --format=%h` after the push and write the hash by
   hand into item 0's blank on your copy of this page. Do not commit
   it: committing would move HEAD past the hash.
