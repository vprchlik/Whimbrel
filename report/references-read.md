# Citation record: the references read for Related work

The nine references of `report/draft.md`'s References section, each
read at its source on 2026-10-13 (D-0084). Each row was read once
while searching (from 01:05 ET [05:05 UTC]) and read again in a
verification pass that located every passage the Related work section
relies on by text search on the live page; the time given is the
clock reading taken in the same step as that second read. Figures and
identifiers are given exactly as the page prints them; prose is
paraphrased (verbatim reproduction kept to identifiers and numbers),
and the "find" string in the fourth column lands on the sentence. The
browser used could not display PDFs (the one PDF URL tried, arXiv's,
raised a save dialog and was not retried), and every ACM Digital
Library and ACM Queue page returned a Cloudflare human-verification
check, which was not completed.

| # | URL read | Page or section | Figure or passage relied on (find string) | Conditions as the source states them | Read, ET [UTC] |
|---|---|---|---|---|---|
| 1 | https://arxiv.org/abs/2104.12721 | Abstract, second paragraph | Images boot in around `1ms` on top of the VMM time; total boot time `3ms-40ms`. Find: `on top of the VMM` | The abstract states none; images for nginx, SQLite, and Redis. Conditions from row 2. Related DOI on the page: 10.1145/3447786.3456248. | 2026-10-13 01:19 [05:19] |
| 2a | https://github.com/unikraft/eurosys21-artifacts/blob/d88853d509c43f4bcd1633e9fec49e4d02241985/README.md | §3.1 Hardware | All results were run on Shuttle SH370R6 boxes with an `Intel i7 9700K`; the KVM host is used for most experiments. Find: `Intel i7 9700K`, `KVM enabled` | Three hosts: a Debian Buster Linux host with KVM enabled (kernel 4.19, most experiments); a second Linux host for `fig_19` and CPU-frequency experiments (§3.2 lists `tab_01`, `tab_04`, `fig_19`, `fig_22`); a Xen host for `txt_02`. `fig_10` is in none of the exceptions, so it ran on the KVM host (an inference from the list, not a sentence on the page). Hyper-Threading disabled, cores isolated. | 2026-10-13 01:19 [05:19] |
| 2b | https://github.com/unikraft/eurosys21-artifacts/blob/d88853d509c43f4bcd1633e9fec49e4d02241985/experiments/fig_10_unikraft-boot/README.md | README, quoting the paper | VMM time (Firecracker, QEMU, Solo5) is measured separately from guest boot, which runs from the first guest instruction to `main()`. Find: `first guest instruction` | helloworld unikernel; with no devices, or with one network interface. | 2026-10-13 01:19 [05:19] |
| 3 | https://ieeexplore.ieee.org/document/8911615 | Abstract | Boot time is extended to include the startup of the service inside the instance; the measured end point is a web server's response to an HTTP request. Find: `reachable instance`, `HTTP request` | Not stated in the abstract (no ISA, hypervisor, or hardware). The abstract's own figure is therefore not used. Venue on the page: 2019 IEEE 2nd 5G World Forum (5GWF), conference 30 Sept to 2 Oct 2019. | 2026-10-13 01:19 [05:19] |
| 4 | https://www.usenix.org/conference/nsdi20/presentation/agache | Abstract | A new open-source VMM specialized for serverless workloads, deployed in AWS Lambda and Fargate. Find: `serverless workloads`, `Fargate` | No figures used from this page. | 2026-10-13 01:19 [05:19] |
| 5a | https://github.com/firecracker-microvm/firecracker/blob/fd9fc7a9f164b73002d22065d17c150d8c262d91/SPECIFICATION.md | Overhead bullet; opening paragraph | `<= 125 ms` from receiving the `InstanceStart` API call to the start of the guest's `/sbin/init`. Find: `InstanceStart` | `M5D.metal` (hyperthreading disabled) and `M6G.metal` instances; microVM with `1 CPUs and 128 MiB of RAM`, Firecracker-tuned guest kernel; serial console disabled; minimal kernel and root file system. A bound enforced by integration tests, not a reported median. File last changed in commit `3127cd1`, unchanged at `fd9fc7a`. | 2026-10-13 01:19 [05:19] |
| 5b | https://github.com/firecracker-microvm/firecracker/blob/fd9fc7a9f164b73002d22065d17c150d8c262d91/docs/getting-started.md | Prerequisites; Architecture & OS | Supports `x86_64 and aarch64` Linux; requires the KVM kernel module. Find: `x86_64 and aarch64` | Host-side requirements. | 2026-10-13 01:19 [05:19] |
| 5c | https://github.com/firecracker-microvm/firecracker/blob/fd9fc7a9f164b73002d22065d17c150d8c262d91/README.md | Overview; Tested platforms | The VMM uses the Linux Kernel Virtual Machine (KVM) to create and run microVMs; tested platforms list `m6g.metal (Graviton 2)`. Find: `Kernel Virtual Machine (KVM)` | Supporting row for 5a and 5b; no figure used. | 2026-10-13 01:19 [05:19] |
| 6 | https://www.qemu.org/docs/master/system/introduction.html | Virtualisation Accelerators; Options Overview (Accelerator row) | TCG is a JIT; the default is TCG, purely emulated, and an accelerator must be specified for hardware virtualization; the KVM row's host architectures include `RISC-V`. Find: `purely emulated`, `RISC-V, s390x, x86` | Documentation page served as version `11.1.50` (master), not the pinned QEMU 10.2.1 (`report/exhibits/machine-spec.md`); the statements used are descriptive, not version figures. | 2026-10-13 01:19 [05:19]; version re-checked 01:20 [05:20] |
| 7 | https://www.usenix.org/legacy/event/usenix05/tech/freenix/full_papers/bellard/bellard_html/index.html | §1 Introduction; §3.5 Memory management; §5 Performance | The dynamic translator converts target CPU instructions into host instructions at run time; the software MMU translates at every memory access; user-mode slowdown differed between integer and floating-point code. Find: `runtime conversion`, `every memory access`, `BYTEmark` | §5: QEMU version 0.4.2, BYTEmark on an x86 host, x86 target, user-mode emulation. The section quotes none of §5's factors: they describe a 2005 translator. | 2026-10-13 01:19 [05:19] |
| 8 | https://github.com/unikraft/unikraft/pull/1698 | PR description; commits tab | Open; Architecture(s): `riscv64`; Platform(s): `kvm`; head `e9b1d5496bd9d0678b035dde2986171bf4398c56`, committed `2026-06-15T08:17:11Z`, identical to D-0063's pin. Find: `Platform(s):` | No figures. | 2026-10-13 01:20 [05:20]; head re-checked 01:23 [05:23] |
| 9 | https://github.com/hermit-os/kernel/blob/4fccbbace86ce16c3a38b77ba83d6759d872e3ae/README.md | Building the kernel | The kernel builds for `riscv64` as well as x86_64 and aarch64; the repository describes itself as a Rust-based unikernel. Find: `riscv64` | No figures. | 2026-10-13 01:20 [05:20] |

Whimbrel-side facts the section uses come from the tree: E0, E4, and
what E0→E4 contains (`report/draft.md`, Methodology, Edges); rv64gc
(D-0002); QEMU 10.2.1 and the host CPU (`report/exhibits/machine-spec.md`);
the Unikraft pin (D-0063).

## Candidates read or sought and not cited

| Candidate | What happened | Why not cited |
|---|---|---|
| Unikraft paper, evaluation text (EuroSys '21) | ACM page: Cloudflare check. arXiv has no HTML for 2104.12721; its PDF opens as a download. | Cited through its arXiv abstract (row 1) and its artifact repository (row 2) instead. |
| Firecracker paper, evaluation text (NSDI '20) | USENIX page read (abstract); paper is PDF only. | The paper is cited for what its abstract says; figures come from the project specification (row 5a). |
| LightVM (Manco et al., SOSP 2017) | Full text on ACM only (Cloudflare check); no HTML copy at an origin. | Not read at source. |
| ClickOS (Martins et al., NSDI 2014) | USENIX abstract read 01:09 ET [05:09 UTC]. | Its boot figure names no hypervisor, ISA, or edge, so it cannot carry conditions; no qualitative claim the section needs. |
| MirageOS (Madhavapeddy et al., ASPLOS 2013) | ACM only; the authors' ACM Queue article also returned the Cloudflare check; the project site, mirage.io, read (Xen or KVM; a start-up claim with no conditions). | Paper not read at source; the project site adds no condition the section uses. |
| OSv (Kivity et al., USENIX ATC 2014) | USENIX abstract read 01:09 ET [05:09 UTC]. | Abstract says only "sub-second" boot; no conditions. |
| IncludeOS (Bratterud et al., CloudCom 2015) | IEEE Xplore abstract read 01:22 ET [05:22 UTC]. | The abstract carries image size and CPU time, no boot time; full text requires sign-in. |
| Unikernels as Processes (Williams et al., SoCC 2018) | ACM only; not attempted after the ACM check had blocked two pages. | Not read at source. |
| HermitCore / RustyHermit papers (Lankes et al.) | Not read (ACM and Springer). | The Hermit kernel README (row 9) carries the only fact used, the riscv64 target. |
| Kata Containers, Cloud Hypervisor: van Rijn and Rellermeyer, "A Fresh Look at the Architecture and Performance of Contemporary Isolation Platforms" (Middleware, arXiv:2110.11462) | arXiv abstract read; no HTML full text. | The abstract makes no boot-time claim. |
| microVM snapshot restore studies | Not pursued. | Restore from a snapshot is a different interval from a cold boot. |
| RISC-V unikernel or microVM boot studies | Searches found none; a RISC-V hypervisor-extension study (arXiv:2103.14951) surfaced and was not read. | No published RISC-V boot figure located; rows 8 and 9 carry the RISC-V point. |
| Kaiser et al., "Exploring the Viability of Unikernels for ARM-powered Edge Computing" (arXiv:2412.03030) | arXiv abstract read; no HTML full text, no venue on the page. | No boot figure readable at source. |
