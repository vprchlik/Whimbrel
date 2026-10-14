# GLOSSARY

Running list of terms, each defined in 2–3 sentences, in our project's
context. Updated at the end of every milestone (project rule). Alphabetical.

**A/D bits.** The Accessed and Dirty flags in an Sv39 PTE (bits 6 and 7).
Some implementations, QEMU included depending on version and config, fault
instead of setting them in hardware, so every kernel leaf is built with
A=1 and D=1 (D-0019).

**Buildroot.** The embedded-Linux build system the Linux baseline is
built with, pinned by release and tarball sha256 in `bench/linux/PIN`
(D-0062). From `qemu_riscv64_virt_defconfig` it builds the stock kernel
`Image` and the musl cross toolchain that compiles `/init`; the trimmed
`Image` merges the committed `bench/linux/linux-trimmed.fragment` onto
the same config. `just linux-build` runs it on the bench host only, and
`bench/linux/MANIFEST` records the hashes it produced. The root
filesystem is not Buildroot's (see initramfs).

**campaign, batch, trial.** A trial is one boot: a fresh QEMU process
with its own packet capture and serial log, one client request, one row
in `results/runs.csv`, and one row per phase in `results/phases.csv`. A
batch is one pass in which every arm runs its warmup trials round-robin
and then its recorded trials, interleaved and shuffled with a recorded
seed; its rows share a `batch_id`. A campaign is one invocation of a
`just bench-*` recipe: two batches, one canary boot, and host controls
checked at start (D-0055, D-0078, D-0079). The stability criterion and
the same-campaign rules compare only within a campaign.

**canary boot.** A boot of `release-default` that runs before trial 1 of
every campaign and is not itself a trial: its `stvec` and
`page_verify` deltas are recorded in the batch header as
`canary_stvec_ns` and `canary_page_verify_ns`, so the day's serial
regime is visible in the artifacts (D-0078). A canary that prints no `PHASE` dump refuses the
campaign. The D-0078 amendment demoted it from certificate to component
after it disagreed with the recorded witness: a campaign's regime is the
canary joined with the safe arm's per-trial `page_verify` within one
kernel family (`report/exhibits/regime-witness.md`).

**CLINT (Core-Local Interruptor).** The per-hart block on QEMU `virt` (at
0x0200_0000) holding the `mtime` counter, the `mtimecmp` timer comparators, and
software-interrupt registers. It is M-mode hardware: OpenSBI programs it on our
behalf when we call `sbi_set_timer`, so we never touch it directly.

**checksum (Internet).** The 16-bit one's-complement checksum of RFC 1071.
IPv4 headers, ICMP, UDP, and TCP (TCP/UDP over a 12-byte pseudo-header) all
use it. A wrong checksum is a silent drop at slirp: hung curl, clean serial.
The pcap asserts `tcp.checksum.status` good; the kernel self-test is
`CHECKSUM OK`.

**citation record.** `report/references-read.md`, the appendix D-0084
adds beside the reference list: for each reference, the URL read, the
passage relied on, the conditions as the source states them, and the
date and time read. It holds cited work to the rule the regeneration
appendix holds Whimbrel's own numbers to: an external number appears
only with its conditions (ISA, hypervisor or emulator, edges, hardware)
in the same sentence, and a reference whose conditions could not be
read carries no number.

**cliff crossing.** A boot where the guest's first wire TX arrives after
slirp has already dropped the ARP-pending frame (~1 s), so the queued
hostfwd SYN is only retried on slirp's ~6 s RTO grid and E0→E4 jumps by
about six seconds. Measured as `e0→E4 > 3 s`. It is campaign-fatal, and
D-0074 keeps slirp's drop precisely because it is what makes the
underlying loss visible at all.

**CSR (Control and Status Register).** Per-hart special registers (e.g.
`sstatus`, `satp`, `scause`) accessed by dedicated instructions (`csrr`,
`csrw`) rather than loads/stores. They configure privileged behavior and record
trap state; which CSRs are accessible depends on the current privilege level.

**D_fin.** The client's FIN minus the HTTP response frame, both read
from the trial's packet capture on its own clock (`d_fin_ns`; D-0070).
The client closes right after its first nonempty `recv`, so D_fin
bounds publish-to-client delivery from above. It is the delivery figure
the report uses where the retired E3w→E4 once stood, with one
definition on every row of every system.

**DBCN (Debug Console).** The SBI extension (EID `0x4442434E`) that replaces
legacy putchar. We use FID 2, `console_write_byte` — one `ecall` per byte —
after probing it via BASE (D-0015). OpenSBI v1.3 implements it and drives the
16550 for us; a missing DBCN is a hard abort, not a fallback to EID `0x01`.

**DTB (Device Tree Blob).** A binary description of the machine's hardware
(RAM size, device addresses, interrupt routing) that QEMU generates and OpenSBI
passes to the kernel in register `a1`. Real kernels parse it for portability;
we print the pointer but hardcode the `virt` layout instead (see D-0012).

**early mode.** The cluster of boots whose Linux `/init` announce lands
at ~156.4 ms guest-mono instead of the ~165.6 ms clean median — about
9 ms early, and the only boots on which the guest's first ARP solicit is
ever lost. Its frequency is a host state, not an image property: 4.73%
of boots one morning and 1.67% the same afternoon on identical sources
(D-0076). Only early-mode boots are *exposed* to the race, which is why
no-event counts must quote the exposed denominator.

**ecall.** The RISC-V instruction that requests service from a higher
privilege level by raising a synchronous exception. From S-mode it is how we
call OpenSBI (SBI calls); from U-mode it will be how the app makes syscalls
into our kernel — same instruction, different trap destination. It has no
compressed encoding, so it is always 4 bytes and OpenSBI advances `mepc` by
exactly 4; that fact does not license our S-mode handler to hardcode `sepc += 4`
(see RVC).

**falsifier.** A pre-registered observable whose occurrence refutes the
hypothesis a campaign or experiment tests, or voids the run, written
into its decision entry with its response before any data exists
(D-0073, D-0074, D-0079). Under D-0055's methodology amendment a
falsifier is either computed by the instrument and fails closed, as the
scan of every trial and canary serial for the shim's `M!` diagnostic is
(falsifier 3, D-0079), or computed from the recorded data at analysis
time. A verdict asserted in prose, without the computation, is
unverified rather than passed (D-0080).

**fast-boot.** A cargo feature (D-0043) that compiles out the boot tick wait,
self-tests, and ordinary `println!`. The panic path, the phase-timestamp
array, map verify (`virtq::verify` and the T1.6 walk), and `M3 UNIKERNEL OK`
stay. The safe/fast delta is the price-of-paranoia finding for M4.

**first-connect.** The client's clock when `connect()` first succeeds.
Under `hostfwd` that is the host kernel completing the handshake into
QEMU's listen backlog, which exists from netdev init, before the guest
runs, so it marks QEMU startup and nothing the guest did (D-0070,
D-0071). E0→first-connect is therefore a same-QEMU control: a
summarize-time gate fails the run unless every arm's median falls
within the registered bound (D-0062 amendment, item 4). It is where the
pre-guest slice S begins.

**first-fit.** The heap walks the free list and takes the first block that
can satisfy the request. Combined with coalescing adjacent frees (D-0027)
it is the K&R allocator: after `Vec` growth the old buffers merge into one
hole rather than a staircase of unusable sizes.

**frame.** A 4 KiB physical page. The frame allocator owns
`[__heap_end, RAM_END)`: a bump for virgin frames and an intrusive list
of recycled frames (D-0065, amending D-0019). The heap's variable-size
blocks live in the 1 MiB carve-out below that and never come from this
pool (D-0024).

**frame freeze.** `frame::freeze()` immediately before the first `sret` to U
(D-0036). After it, `alloc_frame` / `free_frame` panic printing the request.
The 7 frames already gone are 5 page tables (`EXPECTED_TABLES`,
D-0059) plus the two `FRAME OK` self-test leftovers (D-0036).

**GARP (gratuitous ARP).** An ARP request with `spa = tpa` equal to our IP,
Ethernet-broadcast. We send one after the gateway cache is filled (D-0054)
so a capture can see our MAC without waiting to be asked. Distinct from
the ARP *client* request for `10.0.2.2`.

**GlobalAlloc.** Rust's `no_std` heap interface (`alloc` / `dealloc` with a
`Layout` of size plus alignment). Our implementation panics on exhaustion
with those two numbers and never returns null (D-0027).

**hart.** A HARdware Thread — one independent instruction stream with its own
registers and CSRs; a core with hyperthreading would be multiple harts. This
project runs on exactly one hart (hart 0), by constraint D-0007.

**hostfwd.** QEMU user-net option that binds a host socket into slirp and
re-originates a connection toward the guest. `hostfwd=tcp::8080-:80` is
how `curl http://127.0.0.1:8080/` becomes a SYN to `10.0.2.15:80`. It is
not a boot dependency (D-0054); the net-init watcher uses it only for the
`net-init-selftest` handshake sibling, after the gateway MAC is learned
(D-0046).

**identity map.** A translation where the virtual address equals the physical
address. The kernel is identity-mapped (D-0006), so the PC, stack pointer,
and return addresses keep their numeric values across the `satp` write —
there is no higher-half trampoline.

**image bytes.** The cross-system column D-0083 A2 defines: the bytes
QEMU loads into guest memory from the file passed to `-kernel`, which is
the sum of the `PT_LOAD` file sizes for Whimbrel's ELF and the file
length for a flat Linux `Image`, with the file length recorded beside
it. It is the quantity the pre-guest slice S scales with (D-0082).
`scripts/image-bytes.py` measures each pinned artifact and verifies its
sha256 into a committed record, `results/image-bytes.csv`; the exhibit
generator re-checks each hash against the pin's CSV and fails closed,
and until the record is pinned the exhibits print the column as pending
(PLAN T4.10 status).

**initramfs.** A cpio archive the Linux kernel unpacks into a RAM
filesystem at boot and runs as its root. The Linux arms' initramfs is
hand-built and deterministic (`bench/linux/initramfs.spec`): a `/dev`
directory with a console node, and `/init`, which is the HTTP server
itself, static musl with no shell (D-0062; `bench/linux/server.c`).
QEMU loads it with `-initrd rootfs.cpio`, and `bench/linux/MANIFEST`
pins its sha256.

**lui sign-extension (RV64).** `lui rd, imm` writes `sext_64(imm << 12)`.
If bit 31 of that result is set (`imm >= 0x80000`), bits 63:32 become 1.
`lui a0, 0x80200` therefore yields `0xffffffff80200000`, not the
identity-mapped kernel address `0x80200000`. Build a PA with bit 31 set
from a positive `lui` plus `addi`/`slli`, or mask the high half after.
This will bite again anywhere a test names a high address.

**loss event.** A boot on which the guest's first ARP solicit never
reaches the TX ring, so the frame on the wire is the `neigh` retransmit
rather than the original. Measured as `ftx_wall − announce_wall >
100 ms`; ~4.5 % of boots on the D-0074 host. The wire shows exactly one
ARP request either way, which is why it needs a stamp rather than a
frame count to detect (D-0074, D-0075).

**mret / sret.** "Return from trap" instructions for M-mode and S-mode
respectively: they restore the previous privilege level and interrupt-enable
state from status-register fields (`MPP`/`SPP`, `MPIE`/`SPIE`) and jump to the
saved PC (`mepc`/`sepc`). They are also the *only* way privilege goes down —
OpenSBI `mret`s into our kernel, and our kernel will `sret` into U-mode.

**M-mode shim.** The 320-byte firmware replacement of the `-bios none`
lane (D-0061/D-0079): a straight-line M-mode program in QEMU's `-bios`
slot that sets the PMP catch-all, transcribes OpenSBI's delegation
masks, enables counters and Sstc, installs both trap diagnostics, and
`mret`s into the unmodified kernel. No resident services — after
`mret`, any M-mode trap is a bug and prints itself. Checkpoint letters
`ZPDCTVM` bisect a silent boot to one block.

**MEDELEG.** The M-mode CSR that chooses which exceptions reach S-mode.
OpenSBI on this platform sets `0xf0b509`: codes 0, 3, 8, 10, 12, 13, 15,
20–23 are delegated; 1, 2, 4, 5, 6, 7, 9 are not. An illegal instruction
from a task (cause 2) therefore dumps in firmware, not in our handler
(D-0034). We read the boot log; we do not write `medeleg`.

**margin.** The announce instant minus the last virtio control-queue
completion before it — the per-boot risk observable for a loss event.
Over 550 boots it is discrete, not continuous: ~0.2 ms on every event,
~12.4 ms on every clean boot, nothing in between (D-0074 Outcome). It
needs a QEMU `virtqueue_pop` trace, so it is a bench-diagnostic
quantity and is deliberately not recorded during a campaign.

**measurement edges (E0–E4).** Named timestamps for boot-to-first-HTTP-byte
(D-0043): E0 = host clock at QEMU exec; E1 = machine start (`mtime` ≈ 0);
E2 = kernel entry (`rdtime` at `_start`); E3g = `rdtime` at response-TX
publish; E3w = pcap timestamp of that frame (constructed on the E0
timeline as first-connect plus the pcap-relative SYN/ACK→HTTP
interval); E4 = first byte at the client. "E4−E3w" is retired as a
reported metric: the pcap pass (D-0070, confirmed) showed the
construction's anchor is false under hostfwd — connect-success is
the host kernel accepting into QEMU's listen backlog, not the guest
handshake — so the term was QEMU startup (D-0071's S, ~6.8 ms) plus
the accepted connection waiting for the guest to boot to net-init
(W), both already counted once in E0→E4. True publish→client
delivery is bounded by `D_fin` at 63–155 µs. The PHASE dump yields
once after `wait_tx`, then prints (D-0068); the D-0068 null was
this in disguise — there was never tens of ms of post-publish host
work to reorder.
T3.12(a) measured the E2 offset as 0, so `_start` *is* the OpenSBI phase.
Headline E2→E3g uses a client retrying before E0; `just test`'s
curl-after-`HTTP READY` E3g is harness wait (D-0043).

**median, IQR, minimum.** The three statistics every reported metric
carries (D-0055; PLAN M4 concept 1). The median of the recorded trials
is the comparison and before/after statistic, and the IQR, the 25th to
75th percentile computed inclusive (type 7), is its spread. Noise on
this platform is one-sided and additive, so the minimum approaches the
floor and is shown as the observed floor bound; it also improves with N
and is unfair across systems with different noise, so no comparison
rests on it. Means are never used, because one descheduled trial moves
a mean invisibly, and a phase's share is its median over the E2→E3g
median, not a median of ratios.

**MMIO (Memory-Mapped I/O).** Device registers exposed at physical addresses,
accessed with ordinary load/store instructions instead of special I/O
instructions. On `virt`, the UART, PLIC, CLINT, and virtio devices are all
MMIO; a wrong MMIO address typically faults or silently does nothing.

**no_std.** A Rust crate attribute declaring independence from the standard
library, leaving only `core` (language essentials, no OS assumptions) and
optionally `alloc` (heap types, once we provide an allocator). It's the
language-level statement that *we* are the operating system.

**observer cost.** The E0→E4 cost of the Linux instrumented cmdline:
the `trimmed-instrumented` median minus the `trimmed` median within one
campaign, on the same `Image-trimmed`. It contains in-window console
output, whose per-byte cost is a per-boot host variable, so the cell is
day-scoped and compares across campaigns only when their serial regimes
agree (D-0078; `report/exhibits/cross-system-t48c.md`). Whimbrel's
observer effects are the stamp overhead, measured on every boot by
`stamp_a` and `stamp_b`, and the post-response `PHASE` dump (Threats
item 10).

**OpenSBI.** The reference open-source implementation of the SBI spec — the
M-mode firmware QEMU bundles as `-bios default`. It initializes the machine,
protects itself with PMP, delegates traps to S-mode, jumps to our kernel, and
then stays resident to service our `ecall`s.

**pin.** A recorded, immutable identifier for an input a number depends
on. A data pin is a git object, an annotated tag such as
`baseline-t4.3` or a full commit hash, from which a generator reads
`results/*.csv` with `git show`; the working tree and `HEAD` are never
pins, because the harness overwrites the CSVs on every run (D-0067; the
Pins section of `report/appendix-regenerate.md`). Input pins are the
QEMU version, the Buildroot release and tarball sha256
(`bench/linux/PIN`), the artifact hashes in `bench/linux/MANIFEST`, and
the Unikraft commit (D-0063).

**PLIC (Platform-Level Interrupt Controller).** The chip (at 0x0C00_0000 on
`virt`) that gathers external device interrupts (UART, virtio), prioritizes
them, and routes them to a hart as the "supervisor external interrupt". We only
touch it if M3 chooses interrupt-driven networking over polling.

**PMP (Physical Memory Protection).** M-mode CSRs that grant/deny physical
address ranges to lower privilege levels, checked before paging even applies.
OpenSBI uses PMP to protect its own RAM (first ~322 KiB at 0x8000_0000,
observed on OpenSBI v1.3) — the reason an S-mode read of that region
access-faults.

**PPN / VPN.** Physical and virtual page numbers. An Sv39 VA splits into
VPN[2]/VPN[1]/VPN[0] (9 bits each) plus a 12-bit offset; a leaf PTE's PPN
concatenated with that offset is the PA. `satp.PPN` is the root table's
address shifted right 12 — writing the address itself is a factor-of-4096
error (PLAN M1 concept 11).

**PTE (page-table entry).** A 64-bit Sv39 word: V/R/W/X/U/G/A/D in the low
bits, PPN in [53:10]. Any of R/W/X set makes it a leaf (including a 2 MiB
or 1 GiB superpage); a non-leaf must have V=1 and R=W=X=0 or the walk
stops early (concept 11.4). The RAM interior uses 2 MiB L1 leaves
(D-0059); 4 KiB L0 everywhere the map distinguishes at 4 KiB grain.
1 GiB L2 leaves are still rejected (D-0026).

**RVC (compressed instructions).** The C extension gives 16-bit encodings for
common integer operations; a trap can land on either a 2-byte or a 4-byte
instruction. `ecall` / `ebreak` / CSR ops have no C encoding and are always
4 bytes — OpenSBI can therefore advance `mepc` by 4 after an S-mode `ecall`.
Our S-mode handler (M1/T1.2) must not copy that shortcut: inspect the
instruction at `sepc` (low two bits `0b11` ⇒ 32-bit, otherwise 16-bit) and
advance by that width, or a compressed trap will skip a byte and a later
`sret` will land mid-instruction.

**RTO (retransmission timeout).** How long TCP waits for an ACK of its one
unacked segment before posting a copy. Ours is 200 ms of `rdtime` from the
`recv` poll loop, 8 attempts then RST (D-0041 / D-0053). The drop-first-tx
selftest is what proves the timer fires.

**S (pre-guest slice).** The part of QEMU startup between the `hostfwd`
listener coming up, where first-connect stamps, and the main loop going
live, where slirp sends its first ARP request for the guest (D-0071).
It is computed per trial as `(E4 − first-connect) − pcap(ARP→FIN)` from
the recorded columns. It is a property of the host, the QEMU build, and
the image size, and it scales with image bytes, which makes it a
disclosed Linux-side component of E0→E4 (D-0082). S is reported per
system and per firmware lane and never pooled across them.

**satp (Supervisor Address Translation and Protection).** The CSR that turns
paging on: it holds the translation mode (8 = Sv39) and the physical page
number of the root page table. Writing it (plus `sfence.vma`) is the single
instant the kernel goes from physical to virtual addressing.

**SBI (Supervisor Binary Interface).** The calling convention between an
S-mode OS and M-mode firmware: extension ID in `a7`, function ID in `a6`,
arguments in `a0..a5`, then `ecall`. It is to firmware what the syscall ABI is
to a kernel; we use it for console output, timers, and shutdown.

**sbrk / break window.** Per-task 64 KiB NOLOAD region already mapped `U+R+W`.
`sbrk(delta)` moves a pointer inside `[brk_base, brk_wall)` and does not
allocate or edit PTEs (D-0036). The validator accepts only the live prefix
`[brk_base, brk)`.

**scause / sepc / stval.** The three CSRs the hardware fills on every trap
into S-mode: *why* (interrupt bit + cause code), *where* (PC of the
interrupted instruction), and *what* (faulting address or offending
instruction bits). Reading them as a triple is the first move of all debugging
here (see DEBUGGING.md §3).

**serial regime.** The state of the host's per-byte cost of guest serial
output during one campaign, deflated or inflated: two clusters of the
safe arm's recorded `page_verify` witness (D-0078 and its amendment).
The cost moved between host boots with kernel, QEMU, argv, and pins
identical, and every recorded campaign is internally uniform, so the
regime is campaign-scoped and the stability criterion cannot see it.
Numbers that contain in-window console output, the safe profile and the
observer-cost cell, compare across campaigns only when the regimes
agree; `release-fast-boot` prints nothing in its window and is not
exposed (Threats item 21; `report/exhibits/regime-witness.md`).

**sfence.vma.** The instruction that synchronizes the TLB with page-table
memory: after changing PTEs or `satp`, older translations may still be cached
until you execute it. Project rule: fence after every PTE change — cheap
insurance on one hart.

**slirp (libslirp).** QEMU's user-mode NAT, our TCP/UDP/ICMP peer under
`-netdev user`. The guest is `10.0.2.15`, the gateway `10.0.2.2`, and a
`hostfwd` connection is terminated on the host side then re-originated
into the guest (D-0042). Curl's kernel-grade TCP options never reach us.

**sscratch.** Supervisor scratch CSR. We use it as the U/S stack discriminator
(D-0029): nonzero = current task's `kstack_top` while in U; 0 while in S.
Trap entry `csrrw`s it with `sp`. A nonzero value in S-mode turns a kernel
fault into a frame pushed at a stale kstack top.

**sstatus.SPP.** The S-mode "previous privilege" bit (sstatus bit 8): 0 = U,
1 = S. It records where `sret` will return, not the privilege the hart is
running at now. Observed 0 at `kmain` — OpenSBI's initial value after `mret`
into S-mode, not evidence that we are in U-mode. Becomes load-bearing in M2
when we set SPP=U before `sret` into the app.

**sstatus.SUM.** Supervisor User Memory: when set, S-mode loads/stores may
access `U=1` pages. Raised only around an already-validated `memcpy` in
`copy_from_user` / `copy_to_user`, then cleared (D-0034). It does not
*restrict* S-mode from `U=0` pages — validation is software or it does not
exist.

**SRST (System Reset).** The SBI extension (EID `0x53525354`) that asks
firmware to reset or shut down the machine. We probe it, then call FID 0 with
type=shutdown (D-0017). QEMU exits 0; there is no guest-controlled fail code.
If the `ecall` returns, we print the error and park.

**Sstc.** The RISC-V extension that gives S-mode a `stimecmp` CSR, so the
supervisor can arm timer interrupts without an `ecall` into M-mode. OpenSBI
v1.3 on QEMU `virt` advertises it as `Boot HART ISA Extensions: time,sstc`.
M1 arms through SBI TIME instead (D-0018); Sstc is the M4 comparison, not
the M1 mechanism.

**stability criterion.** D-0055's numeric test that the harness
reproduces itself: within one campaign, the two batches' per-metric
medians agree within max(2%, 200 µs) for every metric of 1 ms or more
(D-0055), compared per config, batch 1 against batch 2, never arm
against arm. It was T4.1's finish line, and a campaign that fails it
publishes nothing (t47b aborted at it). It cannot see a host state that
holds for a whole campaign (serial regime), and what it should do about
E0-side drift is open (D-0080; D-0083 A5).

**superpage.** An Sv39 leaf at level 1 (2 MiB) or level 2 (1 GiB). The PPN
must be aligned to that size or the walk faults. We map the aligned
KERNEL_RW RAM interior (`[0x80400000, RAM_END)`) with 2 MiB L1 leaves
(D-0059) and keep 4 KiB L0 for W^X, guards, user slots/sections,
virtio-mmio, and alignment fragments. 1 GiB leaves are still rejected
(D-0026): one PTE would span OpenSBI, the guard, and every W^X
boundary. A mixed path whose verifier does not know the expected
level per region is how a non-leaf with R/W/X set accidentally
becomes a misaligned superpage — that is a panic, not a pass.

**Sv39.** The smallest rv64 virtual-memory mode: 39-bit virtual addresses
translated through three levels of 512-entry page tables to 4 KiB pages, with
2 MiB L1 leaves on the RAM interior (D-0059) and 1 GiB L2 leaves unused
(D-0026).
512 GiB of address space — absurdly more than our 128 MiB of RAM, which is
why we don't need Sv48.

**TCG (Tiny Code Generator).** QEMU's software accelerator: a
just-in-time translator that converts guest instructions into host
instructions at run time and caches the result. It is QEMU's default
when no hardware accelerator is named, and every number in this project
is under TCG, with no KVM. TCG time is not hardware time: compute-dense
and MMIO-dense work are taxed differently than on silicon, so phase
shares would differ on hardware, and only the ratio between arms on one
host transfers (PLAN M4 concept 2; Threats item 1; D-0083 A3; D-0084).

**TIME (SBI).** The SBI extension we use to arm the supervisor timer
(`sbi_set_timer`, absolute `rdtime` deadline). Re-arming is also how S-mode
acknowledges `sip.STIP`, which is not write-clearable here (D-0018). 10 ms
is 100_000 ticks at this platform's 10 MHz timebase.

**timebase.** The rate of the `rdtime` / `mtime` counter. On QEMU `virt`,
OpenSBI reports `Platform Timer Device: aclint-mtimer @ 10000000Hz` — 10 MHz,
so 100 ns per tick. M1's timeslice is `rdtime() + 100_000` (D-0018).

**timeslice.** Here, exactly one supervisor timer interrupt (D-0035). Kernel
code runs with `SIE=0`, so a pending tick cannot preempt a syscall; that
stretches the slice for syscall-heavy tasks (a known fairness property, not
a bug). There is no idle loop: an empty ready set shuts down.

**TLB (Translation Lookaside Buffer).** The hart's cache of recent
virtual→physical translations, consulted before walking page tables in memory.
It is what makes paging fast and what makes *stale* mappings possible — hence
`sfence.vma`.

**TrapFrame.** The 272-byte register save area built on the kernel stack
at trap entry: `x[0..31]` at `8 * regnum`, then `sepc` and `sstatus`
(D-0020). `x[2]` is the pre-trap `sp`. The frame *is* the task context
(D-0032): the TCB stores a pointer to `kstack_top - 272`, and `__trap_return`
does `mv sp, a0` to switch. `sscratch` holds that kstack top in U-mode and
0 in S-mode (D-0029).

**U bit.** PTE flag that marks a user page. User fetch/load/store of a `U=0`
page faults; S-mode access of a `U=1` page faults unless `SUM` is set. It
never stops the kernel reading its own pages, which is why user pointers
are checked in software.

**unikernel.** A single application linked with exactly the OS services it
needs into one bootable image — no processes, no dynamic loading, no
general-purpose userland. Our variant deliberately keeps a U/S privilege
boundary and a 5-syscall interface so the isolation cost can be measured
(D-0010).

**vDSO (virtual dynamic shared object).** A small shared library the
Linux kernel maps into every process so that calls such as
`clock_gettime` run in user mode without a trap. PLAN T4.10 planned to
time Linux's `clock_gettime` both ways, forced through the trap path
with `syscall(SYS_clock_gettime)` and through the vDSO, the latter
approximating the function-call system call a single-privilege
unikernel gets, against Whimbrel's trap-based `gettime` (D-0010). D-0083
A2 descoped that measurement, and the report's future work carries it.

**virtio / virtio-mmio.** A standard family of paravirtual devices where guest
and hypervisor share ring buffers (virtqueues) in guest memory instead of
emulating real hardware registers. On `virt`, devices appear as virtio-mmio
slots at 0x1000_1000–0x1000_8000; our M3 NIC is a `virtio-net-device`. M1
maps none of that MMIO (D-0025).

**virtqueue.** The split virtio ring in guest RAM: a descriptor table, an
avail ring (driver→device), and a used ring (device→driver). We own two
(RX and TX). Every address handed over is guest-physical; the identity
map makes `&static as usize` the PA. `virtq::verify` runs before
`QueueReady` (D-0038) and stays in `fast-boot`.

**W.** The guest's SYN/ACK minus slirp's first ARP request for the
guest, both read from the trial's packet capture on its own clock
(`w_ns`; D-0070): the time an already-accepted connection waits for the
guest to boot far enough to answer. It spans the guest's whole boot to
first transmit, so it fuses boot time with any egress delay, and only a
guest-internal stamp separates them (Threats item 19). It appears
beside Whimbrel rows only, since next to a Linux row it would be boot
wait under another name.

**W^X.** Write xor execute: a page is never both writable and executable.
Kernel `.text` is R+X, `.rodata` is R, `.data`/`.bss`/stack/heap/frames are
R+W. The identity map enforces this at page granularity (D-0019).

**warm-up discard (warmup trials).** The first trials of each arm in
every batch, run round-robin before the recorded trials, marked
`warmup` = 1 in both CSVs, and excluded from every statistic (D-0055).
Their count is registered and enforced at launch
(`require_registered_counts`, D-0079). They are still boots under every
per-trial gate, and the two pcap gates on the Linux arms read their
captures: the T4.8b lost-ARP trial that aborted its batch was a warmup
trial (D-0074).

**wfi (Wait For Interrupt).** The instruction that hints the hart to sleep
until an interrupt arrives — the polite form of an idle loop, and what our
parked hart executes. With `sie.STIE` set it wakes every 10 ms; that is not
quiescence. QEMU actually idles the host CPU on it, unlike a spin loop.
D-0068 uses one `wfi` after first-HTTP `wait_tx` so slirp can deliver
before DBCN occupies TCG. That `wfi` asserts `sie.STIE` first (finding 13):
with ticks not armed and nothing pending, `wfi` never returns.
