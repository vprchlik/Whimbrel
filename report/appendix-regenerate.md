# Appendix — numbers that must be regenerated

Seeded from `docs/AUDIT-2026-08.md` findings 16–23 at T4.3, before
prose could launder them. Disposition is regenerate / historical-only /
structural. Nothing in the historical-only column may appear as a
result.

| finding | claim | disposition |
|---|---|---|
| 16 | `PLAN.md` M2/M3 status rows stale at audit time | **historical-only** — fixed in the T4.0 PLAN edit; not a number |
| 17 | `src/main.rs` module doc still said M2 EXECUTION OK | **historical-only** — cosmetic; T4.3b |
| 18 | D-0026 `__heap_end` `0x8031_8000` not 2 MiB-aligned | **regenerate** — re-derive alignment at the superpage rung, do not quote the M1 address |
| 19 | D-0038 pool size "≈ 64 KiB" | **regenerate** — actual ≈ 49 KiB; fix the entry when the comparison section cites pool size |
| 20 | "~150 ms debug paging" | **historical-only** — labeled not-the-cost-of-paging; must not enter a results table |
| 21 | "E2 offset = 0"; OpenSBI "Firmware Size 322 KB" | **regenerate** under the pinned M4 QEMU (`just measure-e2`); offset is meaningless for `-bios none` |
| 22 | chat-only headline budget (OpenSBI ~24 ms, E2→E3g 42.5 ms, …) | **historical-only** — replaced wholesale by `baseline-t4.3` |
| 23 | 88 KiB/slot reservation; 1 MiB heap; RTO 200 ms; 69 frames = 67+2 | **structural** — 69 = 67+2 died at the superpage rung (finding 24); now 7 = 5 tables + 2 leftovers (D-0059 / D-0036). Slot, heap, and RTO still stand |

Finding 22 is why this appendix exists: a single-run chat budget is
not a result. The generated exhibits are.

## Pins

Every exhibit reads git objects, never the working tree, and `HEAD`
is never a pin. A campaign's pin is frozen at that campaign; a later
campaign is a new pin, not a retarget. Unless a row says otherwise,
the generator reads `git show <pin>:results/{runs,phases}.csv`.

| exhibit column or table | pin | batches | measured kernel |
|---|---|---|---|
| baseline (safe / fast / IQR / min columns); machine-spec baseline block | tag `baseline-t4.3` (CSV freeze commit `bce55a2`); the machine-spec block is copied from `baseline-summary.txt` at that tag | `20260817T041311Z-1` / `-2` | `35861f3` |
| T4.4 ([t44-bump.md](exhibits/t44-bump.md)) | tag `t44` | `20260817T052349Z-1` / `-2` | `83ca9f9` |
| after-ladder and Δ columns; D-0068 "T4.6" column; D-0070 pass, T4.6 rows | `c40945cdb71b5aef68c5e72e292a718b66ec651e` (the T4.6 superpage CSV commit) | `20260817T061753Z-1` / `-2` | `76830e13` |
| D-0068 run 1 | `59e070321ab5` | `20260818T013740Z-1` / `-2` | `c40945cd` |
| D-0068 run 2 | `4755fa3fe2cf` | `20260818T014549Z-1` / `-2` | `59e07032` |
| T4.7 firmware ([t47-firmware.md](exhibits/t47-firmware.md)) | `c2759e245bf7cbcf23dcf43ac228b73f06bb0960` | `20260820T130700Z-1` / `-2` | `346f4c1` |
| T4.8 cross-system ([cross-system.md](exhibits/cross-system.md)); T4.8 Whimbrel edges | `ffb7ac71234e953ae51339a3e1f5e17ba8c3f1b3` | `20260818T073023Z-1` / `-2` | `1005399` |
| T4.8b ([cross-system-t48b.md](exhibits/cross-system-t48b.md)) | tag `t48b` | `20260819T142033Z-1` / `-2` | `06687e2` |
| T4.8c ([cross-system-t48c.md](exhibits/cross-system-t48c.md)); [cross-system-current.md](exhibits/cross-system-current.md) is the generated alias (`CURRENT_COMPARISON`) | tag `t48c` | `20260821T233038Z-1` / `-2` | `1c8816e` |
| Linux boot decomposition ([linux-decomposition.md](exhibits/linux-decomposition.md)) | serial `d705ecb8c67350519f9ce4653a4685a89e20e1d4` (`results/serial/`, T4.8 batch 1, trial 4) plus the D-0072 label pin `93ab617676672f6db7a1d076389f9a049678192a` (one `ignore_loglevel` diagnostic boot of the same `Image-trimmed`) | `20260818T073023Z-1` trial 4; diagnostic boot `20260818T084831Z` | `1005399` (Whimbrel arm of the same batch) |
| ladder ([ladder.md](exhibits/ladder.md)) | `baseline-t4.3`, `t44`, and `c40945c…` above, plus the current comparison pin (`t48c`) for the `virtq_init` row's E0→E4 fraction | | |
| image-bytes column (T4.8b, T4.8c, current comparison) | `IMAGE_BYTES_REV` in `scripts/report-exhibits.py`, the commit that records `results/image-bytes.csv`; unset until the bench-host measurement lands, and the affected exhibits say so | | |
| regime witness ([regime-witness.md](exhibits/regime-witness.md)) | every campaign's pinned CSVs above, read by `scripts/regime-witness.py` | | |
| D-0070 pcap pass ([d0070-pcap.md](exhibits/d0070-pcap.md)) | the T4.6 and D-0068 pins above plus their per-trial pcaps, which are gitignored; generated on the bench host and committed from there | | |

The Linux artifacts behind the T4.8, T4.8b, and T4.8c rows are
pinned by `bench/linux/MANIFEST` at each of those commits (sha256 of
`Image-stock`, `Image-trimmed`, `rootfs.cpio`, `/init`, and both
cmdlines) and by `bench/linux/PIN` (Buildroot 2026.02.3 by tarball
sha256, kernel 6.18.7). The T4.8 Image predates the D-0073 FTRACE
sweep; T4.8b and T4.8c share one Image and one cpio, and differ by
the D-0081 cmdline token.

Regeneration is `just report-exhibits`. The generator's validators
fail closed on a pin whose batches, kernel, or schema disagree with
what the exhibit states, and `just report-exhibits-selftest` proves
each refusal on a planted failing input.
