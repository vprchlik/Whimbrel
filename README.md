# Whimbrel

Whimbrel is a small RISC-V (rv64gc) unikernel in Rust, written from scratch for QEMU's `virt` machine. There is one application compiled into the image. In the normal one-shot run it serves a pinned HTTP response and exits; the persistent demo has a separate command below.

## Run the demo

The environment is described in [docs/SETUP.md](docs/SETUP.md). Use the Rust toolchain pinned in `rust-toolchain.toml`, with `qemu-system-riscv64`, `just` and `tshark` installed. The tests check packet captures as well as boot output, so `tshark` is needed for the gates.

```bash
just build     # cross-compile the kernel
just test      # headless gate: boot markers, curl the HTTP demo, pcap assertions
just run       # boot the one-shot image: serve one GET, then exit
just run-http  # persist the image on host :8080 …
curl -v http://127.0.0.1:8080/   # … and fetch it from another terminal
```

Use `just --list` to see the remaining recipes. `test-panic`, `test-net-tcp` and `check-utext` run individual gates; `just debug` and `just gdb` give the GDB-stub workflow. Running the demo and reproducing a measurement campaign have different host requirements. See "Check the measurements" below for the measurement commands and host checks.

## Inside the image

The kernel has one hart, one address space and Sv39 paging. It can boot with OpenSBI or the project's own M-mode shim. The application runs in U-mode and calls the kernel through seven syscalls: `write`, `exit`, `sbrk`, `gettime`, `yield`, `recv` and `send`.

At boot, the kernel starts its hand-written virtio-net driver and network stack. The stack handles Ethernet, ARP, IPv4, ICMP, UDP and TCP. Doing this without smoltcp was a deliberate project choice.

## Where the project stands

The kernel milestones M0-M3 are complete and merged: boot, traps, paging, U-mode execution, virtio-net and HTTP. M4 covers evaluation: the harness, measurement campaigns and generated exhibits. The kernel changes in M4 are phase-stamp instrumentation, the T4.7 M-mode shim with its allowlisted kernel seams, and the `check_dtb` boot assert.

The campaigns discussed here have been measured and pinned.

## Read the timings

These are measurements of one workload on one emulated machine shape. For the measured one-shot workload, Whimbrel serves a request and exits. All timing values below are medians from a pinned AMD Ryzen 7 7800X3D bench host running QEMU 10.2.1; see [machine-spec](report/exhibits/machine-spec.md). There are n=60 recorded runs per arm, with warmup excluded.

The guest runs as **RISC-V under QEMU TCG software emulation, with no KVM**. Published unikernel and microVM boot figures use x86_64 or aarch64 with KVM and different timing edges. Their absolute times cannot be compared directly with these. The [cross-system](report/exhibits/cross-system.md) ratios compare arms within this emulated setup; they do not establish what the ratios would be on another host or under KVM.

### From process spawn to the first HTTP byte

E0→E4 starts when the QEMU process is spawned and ends when the first response byte reaches the client. This is the boot-to-first-HTTP-byte interval. All arms in the table were interleaved in one campaign, [cross-system-t48c](report/exhibits/cross-system-t48c.md).

| system | E0→E4 median | IQR |
|---|---:|---:|
| Whimbrel `release-fast-boot` | **51.95 ms** | 258.3 µs |
| Whimbrel `release-default` (boot-time verification on) | 139.34 ms | 631.6 µs |
| Linux, minimal, tuned in good faith (Buildroot 2026.02.3 / kernel 6.18.7, config published) | 263.75 ms | 1.43 ms |
| Linux, stock defconfig | 923.70 ms | 3.33 ms |

Trimmed Linux took **5.1×** the Whimbrel time to reach that first byte; stock Linux took **17.8×**. The host and QEMU were the same for all arms: RISC-V TCG, no KVM. There is a measured bias in Whimbrel's favor here. The D-0075 `/init` neighbor-table round trip adds 2.87 ms to every Linux row, as disclosed in the exhibit.

The ratios also include image loading. Linux has a pre-guest component in slice S that scales with image size and that Whimbrel does not incur. D-0082 brackets it at roughly **6–13 ms for trimmed Linux** and **10–20 ms for stock Linux**, within E0→E4. Those brackets came from two read-only methods which agreed on direction but differed in precision. They cannot be regenerated from the pinned CSVs. The cost has not been subtracted from the ratios: loading a small image is part of this single-purpose design.

### Two other campaigns

In the [firmware campaign](report/exhibits/t47-firmware.md), the project's M-mode boot shim replaces OpenSBI in QEMU's `-bios` slot. D-0079 records the shim as 320 bytes. Under the same QEMU TCG conditions, fast-boot E0→E4 changes from 52.27 / 52.19 ms to 28.58 / 28.50 ms per batch, a signed change of −23.69 ms (1.8×). Use this campaign's own OpenSBI arm for that comparison, not the earlier table.

The pooled change in guest kernel work, E2→E3g, accounts for −0.714 ms of the change. The rest includes firmware and host-side effects; it is not an independent measurement of time spent executing firmware. The firmware window is volatile, so its values are reported per batch and never pooled. The [exhibit reading notes](docs/EXHIBIT-READING-NOTES.md) explain the historical decomposition's sign convention and limits.

The kernel-work result uses another interval: E2→E3g, from the first kernel instruction to publication of the HTTP response. It went from 21.42 ms at the pre-optimization freeze to 6.43 ms after the preregistered optimization ladder. Every phase in that interval is attributed, with no phase above 19% of the total. The details are in [edges](report/exhibits/edges.md) and [phase-decomposition](report/exhibits/phase-decomposition.md).

## Check the measurements

Measurement discipline is the main contribution of this project. Each campaign is preregistered before it runs, including what would falsify its claim, and the gates fail closed. The claims here are backed by those campaigns. The decision log also retains the unsuccessful work: a headline metric retired because its name implied something it did not measure, an aborted campaign, a diagnosis refuted by data already on disk, and an expectation model retired after three consecutive misses in the same direction.

To regenerate the main exhibits, use `just report-exhibits`. It reads pinned git objects, not the changing working tree. The regime witness has a separate generator, `python3 scripts/regime-witness.py`. For the D-0070 pcap exhibit, use `just d0070-pcap-pass`; that also needs the saved packet captures on the bench host. A figure that cannot be reproduced from pins alone states the limitation where it appears.

Running a measurement campaign is a different job from regenerating its tables. The `just bench-*` campaigns fail closed away from the dedicated bench host. D-0055 requires bare metal, the performance governor, SMT off, boost off and zero steal. The harness refuses a report-grade batch if those controls do not hold and records them with every batch.

## What's in the repo

| path | what it is |
|---|---|
| `src/` | the kernel: boot, trap handling, Sv39 paging, scheduler, virtio-net driver, the network stack |
| `app/` | the single U-mode application (the HTTP responder), linked into the kernel image |
| `usys/` | the seven syscall stubs |
| `linker.ld` | image layout, including the dedicated user sections `check-utext` enforces |
| `scripts/` | the harness: boot gates, pcap assertions, `bench.py`, the exhibit generator |
| `bench/linux/` | pinned inputs for the Linux baseline: Buildroot pin, kernel-config fragments, `/init` |
| `docs/` | `DECISIONS.md` (the 87-entry decision log), `DEBUGGING.md` (rv64/QEMU field guide), `GLOSSARY.md`, `SETUP.md`, `EXHIBIT-READING-NOTES.md`, `AUDIT-2026-08.md` (the pre-M4 audit, with its pre-registered predictions) |
| `report/` | generated exhibits (`report/exhibits/`) |
| `results/` | latest-run CSVs, overwritten per run; campaign data lives only in pinned git objects (see [results/README.md](results/README.md)) |
| `justfile` | every gate and campaign as a recipe |

## Reading further

- [docs/EXHIBIT-READING-NOTES.md](docs/EXHIBIT-READING-NOTES.md) explains corrections and interpretation limits for the preserved campaign exhibits.
- [report/exhibits/](report/exhibits/) contains the generated tables. Each caption names the exact git objects used and the command that regenerates the table.
- [docs/DECISIONS.md](docs/DECISIONS.md) records every nontrivial choice: alternatives, rationale, consequences and any subsequent refutation.
- [docs/DEBUGGING.md](docs/DEBUGGING.md) is the symptom → cause field guide for rv64/QEMU work.
- [results/README.md](results/README.md) explains the measurement-data pins and why the working tree is never a source.

## How this was built

I signed off the preregistrations before their campaigns ran (D-0062, D-0079). My dispositions are in the decision log, including the decision to sustain a campaign abort (D-0079). Every campaign cited here ran on the dedicated bench host, with the D-0055 controls checked and recorded for each batch. Scripts generate the exhibit tables from pinned git objects; the numbers are not entered by hand.

## License

`SPDX-License-Identifier: MIT OR Apache-2.0`. Dual-licensed under
[MIT](LICENSE-MIT) or [Apache-2.0](LICENSE-APACHE), at your option.

Developed in part with AI assistance.
