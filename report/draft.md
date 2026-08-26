# Floor-finding: boot to first HTTP byte on a RISC-V unikernel

---

## Abstract

Whimbrel is a from-scratch rv64gc unikernel that serves one HTTP
response, built to measure how much of the time from virtual-machine
spawn to first HTTP byte a single-purpose kernel must spend. On
RISC-V under QEMU TCG software emulation, with no KVM, on the same
host and QEMU for every arm, its fast-boot image
(`release-fast-boot`) reaches first HTTP byte in 51.95 ms, 5.1×
faster than a minimal Linux tuned in good faith (263.75 ms) and
17.8× faster than a stock defconfig Linux (923.70 ms)
([exhibits/cross-system-current.md](exhibits/cross-system-current.md)).
Its guest work, first kernel instruction to the published response,
is 6.38 ms at the T4.8c pin, with every phase attributed (Results).
In a second lane, replacing OpenSBI with a 320-byte M-mode shim in
the `-bios` slot cuts the fast-boot image's spawn-to-first-byte from
52.27 / 52.19 ms to 28.58 / 28.50 ms per batch (−23.69 ms in each
batch, 1.8×), of which −0.714 ms is guest work; the remainder is the
removed firmware window, reported per batch and never pooled
([exhibits/t47-firmware.md](exhibits/t47-firmware.md)). That lane is
reported beside the comparison, because no Linux row can swap its
firmware for a purpose-built shim. Campaigns were pre-registered
with falsifiers, gates fail closed, and every number regenerates
from pinned git objects.

A three-way comparison including Unikraft was attempted and ended
at a pre-registered no-go, not a schedule limit (D-0063). At the
pinned riscv64 port — unikraft/unikraft PR #1698, head `e9b1d549`
— no networked build can boot: the port's PLIC driver registers no
`fdt_xlat` operation, the generic interrupt layer asserts on that
NULL pointer while probing virtio-mmio transports, and QEMU's
`virt` machine always presents those transports, so the crash
lands during bus probing, before `main`. The fix is roughly
fifteen lines of new Unikraft driver code, which the spike's
no-core-patches rule forbids: the measurement would then describe
our fork, not Unikraft. This is a regression in the port's 2026
rebase, not an absence of riscv64 support. The quantitative
comparison is therefore two-way against Linux; Unikraft appears as
a qualitative boot-path analysis from source at the same pin
(Results). A Unikraft build on another ISA was available and
deliberately not run: a cross-ISA number cannot share the
same-host, same-QEMU conditions that make the Linux ratios
meaningful.

---

## Background

A unikernel links one application with exactly the operating-system
services it needs into one bootable image: no processes, no dynamic
loading, no general-purpose userland. The claim made for that shape
is that a machine which does one thing should reach that thing
quickly. This report asks how quickly, and what the time is made of.
Between the moment a virtual machine is spawned and the moment its
first HTTP byte reaches a client, how much of the elapsed time is
work a single-purpose kernel must do, how much is work it can still
shed, and how much of what a general-purpose kernel does on the same
path never needed doing? The answer is a floor in D-0064's sense,
the minimum structurally necessary under stated conditions, bounded
below by the phases argued necessary row by row, together with a
ratio against a minimal Linux under the same conditions.

Whimbrel exists to answer that question. It is a from-scratch rv64gc
kernel in Rust, built to be explained and then measured (D-0001,
D-0002): a hand-rolled network stack, so that each cost on the
response path lands on a line the project wrote (D-0037); a kept U/S
privilege boundary, so that the syscall cost a single-privilege
unikernel would hide sits inside the measured interval (D-0010); and
boot-path stamps whose own overhead is measured. The platform is
QEMU's `virt` machine under TCG software emulation, chosen for a
pinned binary, one machine shape, and instrumentation the guest
cannot see; real boards were declined for bring-up variance
(D-0003). Every number in the report is therefore emulated time, and
the conditions travel with every claim.

The comparison rests on conditions that hold for every arm at once.
All systems boot on the same QEMU binary and machine shape, with the
same user-mode network, the same host, and the same client. The
edges that define the headline number are stamped by that client and
need nothing from the guest: E0, the spawn, and E4, the first
response byte. Every system serves the same 92-byte response over
the same handshake. Arms are interleaved within one campaign, so
host drift lands on all of them, and each campaign's gates are
registered with their responses before it runs. The Linux side is a
minimal Linux tuned in good faith, with its configuration published
and a stock row beside it so that the tuning claim can be checked
(D-0062). Guest-internal decompositions are per-system evidence
taken with different instruments, and no cell of one is compared
with a cell of the other.

Under emulation the absolute times mean little outside these
conditions. Published unikernel and microVM boot figures come from
x86 under KVM hardware virtualization, and a TCG absolute compares
with none of them. The ratio between arms is the comparable
quantity, because the emulation penalty applies to both arms on the
same host. A third arm, Unikraft, was attempted and ended at a
pre-registered no-go at the pinned riscv64 port; it appears as a
source-level analysis (Results), and no cross-ISA Unikraft number
was taken, since it could not share the conditions that make the
ratio meaningful (D-0063).

The report's second subject is the measuring itself. Campaigns are
pre-registered with falsifiers before they run, gates fail closed,
and every published number regenerates from pinned git objects. The
decision log keeps the misses beside the results, and the retired
metric, the aborted campaign, and the refuted diagnoses are reported
where they happened.

---

## Architecture of the apparatus

The apparatus is the kernel. It runs on QEMU's `virt` machine: one
hart, rv64gc, entered in S-mode by OpenSBI (the T4.7 lane replaces
OpenSBI with the D-0079 shim and is described with its exhibit) with
the hart id and a device-tree pointer whose header is checked and
whose contents are not parsed; the memory map is a set of named
constants cited to QEMU's `hw/riscv/virt.c` (D-0003, D-0012,
D-0023). Paging is Sv39 with one root table for the life of the
system; the kernel is identity-mapped with W^X, and the application
shares that address space, separated from the kernel by the U bit
(D-0005, D-0006). The application is one crate compiled into the
image and linked into sections of its own (`.utext`, `.urodata`,
`.udata`, `.ubss`), with a build check that every symbol those
sections reference resolves inside them (D-0044). It runs as the
only U-mode task over seven syscalls: `write`, `exit`, `sbrk`,
`gettime`, and `yield` from D-0010, `recv` and `send` from D-0040.
The devices are the console, reached through SBI's debug-console
call at one `ecall` per byte (D-0004, D-0015), and one virtio-net
device on virtio-mmio (D-0008). There is no filesystem, no loader,
no POSIX layer, no DHCP, no second device, and no interrupt path
from the NIC: the PLIC is neither mapped nor initialized (D-0009,
D-0040, D-0042). What follows is the kernel after the optimization
ladder; where a rung replaced a component, the phase table's "what
the work is" column names both forms.

### Boot path in phase order

The phase table
([exhibits/phase-decomposition.md](exhibits/phase-decomposition.md))
stamps `rdtime` at each step below; its row names are in code font.
`_start` is the origin and `stamp_a` / `stamp_b` are the
instrumentation-overhead pair (Methodology).

`stvec`. The trap handler is installed in Direct mode. A trap saves
all thirty-one general registers plus `sepc` and `sstatus` into a
272-byte frame on the current kernel stack (D-0020). `sscratch`
holds that stack's top while the hart is in U-mode and zero while it
is in S-mode, so the handler's first instruction learns which mode
it came from without needing a free register (D-0029). The handler
returns the frame to resume; a context switch is the handler
returning a different frame than it was given, and there is no
separate switch routine (D-0032). Nothing on the trap path allocates
(D-0028, D-0036).

`frame_init`. Physical frames above the image are a bump pointer
plus a recycled list for frames freed after allocation (D-0065). On
the measured path the allocator serves page-table construction and
nothing else.

`task_init`. Four task slots, each an 8 KiB kernel stack, an 8 KiB
user stack, a 64 KiB break window, and two 4 KiB guard holes, are
placed by the linker and populated without allocation (D-0030). The
HTTP image fabricates a trap frame for each; slot 3 holds the
application, and the other three are created and marked Exited. The
count is a compile-time constant shared with the self-test images.

`page_build`, `page_verify`, `activate`. The identity map uses 4 KiB
leaves wherever it distinguishes anything at that grain (the
kernel's W^X regions, guard holes, the user sections and task slots,
the virtio-mmio window) and 2 MiB leaves for the aligned interior of
RAM (D-0059); the production image needs five page tables.
`page_verify` is a second, independent software walk of the whole
map that checks every leaf at its expected level, kept deliberately
(D-0043). `satp` is written once, and no page-table entry is edited
afterward (D-0031).

`virtq_init`, `DRIVER_OK`. The virtio-mmio window is a hardcoded
range mapped during `page_build` and probed after activation
(D-0039). The driver speaks modern virtio-mmio with split virtqueues
of sixteen descriptors, negotiates `VIRTIO_F_VERSION_1` and
`VIRTIO_NET_F_MAC` and declines every other feature, and points both
rings at a static pool in `.bss`: sixteen 2 KiB receive buffers and
eight transmit buffers, never freed or grown (D-0038). The rings are
programmed and verified twice: once at `virtq_init`, and again after
the device reset that opens `net::init` has wiped the first pass
(audit finding 4; the row stays in the table).

`first_rx`, `serving_ready`, `net_init_done`. Addressing is static:
`10.0.2.15` behind gateway `10.0.2.2`, QEMU user-net's contract
(D-0042). Init transmits an ARP request for the gateway and waits
for the reply; `first_rx` is that reply arriving, and
`serving_ready` is the cache entry it fills, which every later
transmit uses; an empty entry at transmit time is a panic, not a
queue (D-0047, D-0054). A gratuitous ARP and a diagnostic ping of
the gateway follow (`net_init_done`).

`heap_init`. A 1 MiB kernel heap is carved out beside the frame
allocator (D-0024). Nothing on the measured path allocates from it
(audit finding 11).

`accounting`, `freeze`, `sret`. Before the first `sret`, the kernel
checks that the frames handed out are exactly the page tables it
expects, then freezes the frame allocator so that any later
`alloc_frame` or `free_frame` panics (D-0036). The first `sret`
enters the application. From here on the trap handler is the only
kernel code that runs, and it runs with interrupts disabled
(D-0020).

`syn_rx`, `established`, `E3g`, `E3g_doorbell`. The application
writes `HTTP READY` and spins on `recv`. Each `recv` is an `ecall`:
the kernel validates the buffer, polls the receive ring, runs the
stack, and returns a payload, an EOF, or "nothing yet" (D-0040). The
NIC is touched only from that syscall context, and TCP's one timer
is checked there against `rdtime`. The SYN and the handshake are
handled inside those polls; the application sees only the request
payload, copied into its buffer by the `recv` that finds it. It
checks for `GET ` and a line ending in that one segment and then
`send`s a fixed 92-byte `HTTP/1.0 200 OK` carrying
`Connection: close` and the FIN flag. The response segment placed on
the transmit ring is E3g; the `QueueNotify` store that hands it to
the device model is priced as its own row (D-0056). The application
then waits for EOF and exits.

### The U/S boundary

The usual unikernel shape runs the application and the kernel at one
privilege level, so a system call is a function call, and it is
faster. Whimbrel keeps the application in U-mode behind a trap-based
interface (D-0010, D-0033): the syscall number travels in `a7`,
arguments in `a0`–`a5`, and an error/value pair returns in
`a0`/`a1`, the convention the kernel itself uses toward OpenSBI.
Every user pointer is checked against the task's static intervals
before use, and `sstatus.SUM` is raised only around a bounded copy
inside the kernel (D-0034). A bad pointer, an unknown syscall
number, or a U-mode fault kills the task; none of them panics the
kernel.

That buys two things. The first is isolation the hardware enforces:
the application cannot reach kernel memory, cannot touch the device
or the rings, and is stopped by permission bits when it misbehaves
(D-0006, D-0040). The second is a comparison that is not vacuous.
The flagship interval contains a privilege transition of the same
kind Linux pays on its own response path; a function-call "syscall"
would leave nothing on Whimbrel's side for Linux's trap-and-return
to be set against (D-0010).

It costs in three places. The phase table carries two as rows, both
marked structurally necessary: `task_init`, the fabrication of the
four U-mode slots, and `sret`, the first transition. The third is
spread across `page_build` and `page_verify`: the user sections,
user stacks, break windows, and their guards are why part of the map
is at 4 KiB grain. On the response path the boundary is crossed once
per `recv` poll and once for `send`; the request is copied out to
user memory and the response copied back in. The price of one
crossing was not isolated: D-0010 asked for a syscall-latency
exhibit, and that measurement was descoped before sign-off (D-0083);
Future work carries it.

### The TCP

The stack (Ethernet, ARP, IPv4, ICMP echo, UDP echo, TCP) is written
from scratch, with no third-party stack and no TLS (D-0037). It
serves one request over one connection, and then the application
exits. The report claims nothing for it beyond that: no throughput,
no robustness.

The TCP is a passive-open, single-connection state machine (D-0041,
D-0053). One control block listens on port 80. It parses the MSS
option from the SYN, assumes 536 when none is offered, and skips
every other option by honoring the data offset; it advertises a
fixed 8 KiB window; it checksums in both directions with the
pseudo-header; it acknowledges every in-order segment on arrival.
Transmission is stop-and-wait, one unacknowledged segment in flight,
retransmitted on a fixed 200 ms `rdtime` deadline for eight attempts
in all and then reset. SYN and FIN each consume a sequence number.
The close runs FIN_WAIT_1 → FIN_WAIT_2 → a truncated TIME_WAIT that
logs and returns to LISTEN, or CLOSE_WAIT → LAST_ACK when the peer
closes first. A payload is at most 512 bytes in either direction; a
second data segment arriving before `recv` has consumed the first is
dropped; an out-of-order segment is dropped and the current ACK
repeated; a SYN on a second four-tuple is dropped while a connection
is live; the application may `send` once per connection.

What it does not implement: congestion control of any kind (no
window growth, no slow start, no loss-driven backoff); no
retransmission-timer estimation (the RTO is a constant); no
reassembly (nothing out of order is buffered); no reading of the
peer's advertised window; no window scaling, selective
acknowledgment, or timestamps; no delayed ACK, persist timer,
keep-alive, or urgent data; no active open; no full TIME_WAIT; no
listen queue.

At this workload none of that is reachable. The request is one
segment: the bench client's `GET / HTTP/1.0` in campaigns, curl's in
the gate. The response is 92 bytes: one segment, smaller than the
536-byte default MSS and far inside the fixed window. With one
segment in flight, stop-and-wait and a congestion window are the
same policy. The peer is libslirp inside the QEMU process: a
`hostfwd` connection is terminated on the host side and
re-originated from the gateway, so the leg the guest's TCP talks
over has no link to congest and delivers frames in the order slirp
emits them (D-0042; Threats item 2). Curl's options (window scaling,
SACK, timestamps) are negotiated with the host kernel and never
reach the guest. A loss on the slirp leg would surface as a 200 ms
retransmission on serial and in the per-trial capture; the HTTP
gates fail on one, and the timer's own behavior is exercised by a
self-test image that withholds acknowledgments until one
retransmission has been captured (D-0053). The client opens one
connection, so the dropped second SYN is never exercised in the
measured protocol.
---

## Methodology

Conditions, stated once: QEMU TCG (software emulation, no KVM), the
`virt` machine, one hart, the default 128 MiB, slirp as the TCP
peer, one dedicated Ubuntu 26.04 host with boost off, and
`-bios default` (OpenSBI) on every comparison campaign. The T4.7
firmware exhibit is the one place a second lane replaces OpenSBI
with the D-0079 M-mode shim in the `-bios` slot, and it states its
own conditions. None of this is hardware time. The host, the QEMU
build, and the client's measured granularity are in
[exhibits/machine-spec.md](exhibits/machine-spec.md).

### Edges

The edges are named in D-0043 and stamped on two clocks: the
client's monotonic clock on the host, and the guest's `rdtime`
counter at 10 MHz.

E0 is the host clock immediately before QEMU is spawned. E1 is
machine start, `mtime` ≈ 0. E2 is the first kernel instruction,
`rdtime` at `_start`; T3.12(a) read `time` under the GDB stub before
the first guest instruction and found 0, so E2 measured from zero is
the OpenSBI phase with nothing to subtract. E3g is `rdtime` when the
response segment is published to the transmit ring; the
`QueueNotify` store that follows is stamped separately
(`E3g_doorbell`). E4 is the client's clock at the first nonempty
`recv` chunk. First-connect is the client's clock when `connect()`
succeeds; under `hostfwd` that is the host kernel completing the
handshake into QEMU's listen backlog, which exists from netdev init,
before the guest runs (D-0071).

Three intervals are reported. E0→E4 is the comparison number: two
client-clock stamps, identical on every system, needing nothing from
the guest. E0→first-connect is a same-QEMU control, bounded to 1 ms
across the arms of a campaign. E2→E3g is guest work, decomposed by
phase at 100 ns resolution, and exists for Whimbrel only.

Four quantities are read from each trial's packet capture on the
capture's own clock (D-0070; `scripts/pcap_http.py`). W is the
guest's SYN/ACK minus the first slirp ARP request for the guest: the
time an accepted connection waits for the guest to become reachable.
D_ack is slirp's ACK of the response minus the HTTP frame. D_fin is
the client's FIN minus the HTTP frame; the client closes right after
`recv`, so D_fin bounds publish-to-client delivery from above. S is
the slice of QEMU startup between the listener coming up and the
main loop going live, `(E4 − first-connect) − pcap(ARP→FIN)` per
trial (D-0071); it is a property of the host, the QEMU build, and
the image size (D-0082). W appears beside Whimbrel rows only, since
next to a Linux row it would be boot wait under another name. S is
reported per system and per firmware lane and never pooled across
them. D_fin uses one definition on every row. Whimbrel's
host-observed edges for each campaign are in
[exhibits/edges.md](exhibits/edges.md).

Two metrics were retired before the cross-system campaigns. E3w
anchored the capture's SYN/ACK→HTTP interval to first-connect on the
assumption that connect success coincided with the guest handshake;
under `hostfwd` it does not, so "E3w→E4" was S plus W under a
host-side name (D-0070, D-0071; Threats item 17). The freeze, T4.4,
T4.6, and D-0068 exhibits keep those columns as the record of the
mislabeling. No E3w-derived column appears in a cross-system table.

### Protocol

D-0055 fixed the protocol before any optimization ran. A campaign is
two batches. In each batch every arm runs 3 warmup trials, marked
and excluded, then 30 recorded trials, so each arm has 60 recorded
trials per campaign; warmup is round-robin across arms, and the
recorded trials of all arms are interleaved and shuffled with a
recorded seed, so elapsed-time drift lands on every arm. Each trial
boots a fresh QEMU with its own packet capture
(`-object filter-dump`) and serial log. Per batch the harness
records the QEMU version and binary hash, the kernel's git SHA and
dirty flag, the host kernel, the CPU model, the governor, and the
1-minute load average, and it refuses to aggregate rows whose QEMU
version differs or whose tree was dirty. Host controls (no
virtualization, the `performance` governor, SMT off, boost off,
steal 0) fail closed at batch start, and steal is re-read per trial:
a nonzero steal tick fails the trial. Data is long/tidy CSV, one row
per trial and one row per trial × phase; every reported table is
generated from it.

Statistics are median and IQR, with the minimum shown as the
observed floor bound; means are never used. A phase's share is its
median divided by the E2→E3g median, not a median of ratios.

The stability criterion: the two batches' per-metric medians agree
within max(2%, 200 µs) for every metric of 1 ms or more. It passed
for both Whimbrel profiles on the freeze, T4.4, T4.6, and both
D-0068 invocations, and for all five arms of T4.8, T4.8b, and T4.8c
(the latter two ran the T4.8 gate set). T4.7's Claim A is
stability-gated by construction and its Claim B is per batch (Shim
lane, below). One campaign, t47b, aborted at this gate on its
E0-side edge and published nothing; D-0080 registered a
characterization of that drift, whose first run was invalidated by
an instrument defect and has not been repeated (Threats). The
criterion failed on a KVM pod, and nothing from that pod is cited.

D-0068 ran twice: four batches, two invocations, different seeds,
kernels one CSV commit apart;
[exhibits/dump-placement.md](exhibits/dump-placement.md) reports the
pairwise disagreement, inside max(2%, 200 µs) on every compared
median. Whimbrel's guest number also held across the three
cross-system campaigns: `release-fast-boot` E2→E3g is 6.43 ms at
T4.8, within 550 ns of the T4.6 pin
([exhibits/cross-system.md](exhibits/cross-system.md)), then 6.38 ms
at T4.8b and 6.38 ms at T4.8c
([exhibits/cross-system-t48c.md](exhibits/cross-system-t48c.md)),
across two Linux-side changes the Whimbrel arms do not carry.

Boost-off is a dedicated-host override of D-0055's runs-anywhere
alternative: peak clock 4.2 GHz against 5.05 GHz, roughly 17% lower,
so absolute numbers are larger and boost-state and thermal variance
are gone. Every compared system runs under the same policy.

### Client

The measurement client (`scripts/bench-client.py`) is one persistent
Python process stamping `time.monotonic_ns()`. It starts before E0
and retries `connect()` at a 1 ms cadence, measured at 1.000 ms
(`client_granularity_ns` in the machine-spec block). The cadence
ends at connect: the client then `sendall`s a fixed `GET / HTTP/1.0`
and blocks in `recv`, and E4 is the first nonempty chunk. The
response is pinned at 92 bytes on every system, and the recv timeout
is one value per campaign for every system. QEMU and the client are
pinned with `taskset` to separate cores. The same client and the
same QEMU user-net serve every arm.

### Guest instrumentation

Whimbrel stamps `rdtime` into a static array at 22 points on the
boot path (`src/phase.rs`); the phase table's rows are those stamps
in order. The array is printed after the response has left and after
one `wfi`: `timer::yield_once` asserts that ticks are armed,
re-arms, waits one tick, then prints (D-0068), because the console
is one `ecall` per byte and a dump between publish and E4 would sit
inside the measured interval. The harness parses the `PHASE` lines,
and a line that fails to parse fails the batch. Stamp overhead is
measured on every boot by two adjacent stamps, `stamp_a` and
`stamp_b`; the pair reads 5.5 µs on `release-fast-boot`
([exhibits/edges.md](exhibits/edges.md)) and is quoted against every
attributed delta, with a floor of 100 ns. `release-default` prints
its boot log inside the measured window and `release-fast-boot`
prints nothing before the response; per D-0078 the cost of a serial
byte is a per-boot host variable, so safe-profile numbers compare
across campaigns only with a same-day control (Linux arms, below).

### Linux arms

The Linux baseline is D-0062. Buildroot 2026.02.3 is pinned by
tarball sha256 (`bench/linux/PIN`), kernel 6.18.7. The `stock` row
is `qemu_riscv64_virt_defconfig` untouched. The `trimmed` row merges
the committed fragment `bench/linux/linux-trimmed.fragment` onto
that config with `merge_config.sh`, keeping the serial console,
virtio-mmio and virtio-net, IPv4 TCP, initramfs, devtmpfs, ELF
loading, and futexes, and unsetting what the build could show
unused; each keep is asserted on the final `.config`. The initramfs
is a hand-built cpio (`bench/linux/initramfs.spec`) holding `/init`
and a console node. `/init` is the server (`bench/linux/server.c`):
static musl, no busybox, no shell. It opens, binds, and listens on
port 80 before bringing the interface up; sends one UDP datagram
toward the gateway right after, so the guest's first wire frame
teaches slirp its MAC and flushes the queued `hostfwd` SYN; writes
the 6-byte `READY`; accepts, reads once, writes the same 92-byte
response, and closes. Between interface-up and that datagram one
`RTM_SETNEIGHTBL` shortens the ARP retransmit from 1 s to 50 ms
(D-0075), stamped as `neigh`: a measured 2.87 ms on the Linux side
of every T4.8b and T4.8c row, a bias toward Whimbrel applied
identically to both Linux rows (Threats item 20). Eight `/init`
stamps (`listen`, `ifup`, `neigh`, `announce`, `ready`, `accept`,
`read`, `resp`) are held in memory and printed after close.

Both Linux rows boot with `-kernel Image -initrd rootfs.cpio` on the
same QEMU argv as Whimbrel (`scripts/qemu-args.sh`; checksum and
segmentation offload are off on the virtio-net device, a no-op for
Whimbrel). The quiet cmdline is
`console=ttyS0 quiet loglevel=0 rdinit=/init unaligned_scalar_speed=fast`;
the last token skips the kernel's boot-time unaligned-access
benchmark, a jiffies-clocked wait (D-0081; T4.8c onward). A third
arm, `trimmed-instrumented`, runs the same `Image-trimmed` under
`console=ttyS0 loglevel=7 printk.time=1 initcall_debug rdinit=/init`
plus that token; instrumented minus trimmed is the observer-cost
cell, day-scoped because it contains in-window console output.
`bench/linux/MANIFEST` records the sha256 of both Images, the cpio,
`/init`, and both cmdlines at each pin.

Linux's guest decomposition
([exhibits/linux-decomposition.md](exhibits/linux-decomposition.md))
is a different instrument from Whimbrel's: printk gaps and `/init`
stamps from the instrumented arm's serial, plus labels from one
diagnostic boot of the same Image under `ignore_loglevel` (D-0072).
Those labels are UART-inflated and name the gaps; the cells measured
under `loglevel=7` stand. The diagnostic boot is not an arm and
enters no table.

Four gates on the Linux arms are pre-registered with their responses
(D-0062 amendment; D-0077). Two read every trial's pcap, warmup
included. The SYN-grid gate: the first SYN into the guest arrives
within 1 ms of the guest's first IPv4-teaching frame (the ARP
request, or the announce datagram on a warm cache), so the SYN was
flushed by that frame and not by slirp's retransmit grid; one
gridded trial fails the batch. The RST gate: any RST in a trial's
pcap fails the run. Two run at summarize time on recorded trials.
The first-connect control: every arm's E0→first-connect median
within 1 ms, a miss failing the run. The trimmed-versus-stock
tripwire: a batch in which trimmed's E0→E4 median is not below
stock's does not publish the trimmed row. A trial that trips a gate
is recorded to `results/gate-failures.csv` before the gate re-raises
and never enters `runs.csv`. Two passive per-trial columns,
`guest_ftx_ns` and `guest_arp_req_n`, are recorded on every trial of
every system so that a lost ARP solicit is countable (D-0075). A
per-system QEMU hang watchdog bounds a stuck boot.

Each campaign includes one canary boot of `release-default` that is
not a trial: its `stvec` and `page_verify` deltas go into the batch
header (`canary_stvec_ns`, `canary_page_verify_ns`) as the day's
serial-cost regime (D-0078). Per D-0078 and its amendment, a
campaign's regime is the canary joined with the safe arm's recorded
per-trial `page_verify` witness
([exhibits/regime-witness.md](exhibits/regime-witness.md));
safe-profile numbers and the observer-cost cell compare across
campaigns only when the regimes agree.

### Shim lane

T4.7 (D-0079, executing D-0061) replaces OpenSBI with a 320-byte
M-mode shim in the `-bios` slot and measures the two firmware lanes
as one campaign: four Whimbrel arms (`release-default`,
`release-fast-boot`, and their `m-` counterparts) interleaved in one
invocation with one shared canary; the exhibit refuses a pair whose
lanes come from different campaigns. The lane is a variant, never a
replacement: `-bios default` keeps every gate and every primary
number, the cross-system table's Whimbrel rows stay OpenSBI, and a
registered falsifier makes any movement of those rows a stop.

The exhibit ([exhibits/t47-firmware.md](exhibits/t47-firmware.md))
reports two claims of different kinds. Claim A is the pooled
guest-side change, ΔE2→E3g, stability-gated and pooled across both
batches, with the per-batch figures beside it. Claim B is ΔE0→E4 per
batch, never pooled, because the quantity removed is the
OpenSBI-side firmware window, which moves across campaigns. ΔE0→E4
decomposes as guest firmware execution removed, plus ΔS (the
host-side firmware load, per lane from the fast pair, quoted from
the batch header), plus the seam envelope; S is never pooled across
lanes. The shim lane's console is polled S-mode UART, so its
per-byte serial cost differs by construction and safe-profile
numbers never compare across lanes; the comparison profile is
`release-fast-boot`, which prints nothing in its window. The shim
lane's S is profile-dependent, an open D-0079 item with no consumer.

### Pins and regeneration

Every number in this report is generated from git objects by
`scripts/report-exhibits.py` (`just report-exhibits`); the working
tree is never read, `HEAD` is never a pin, and a campaign's pin is
frozen at that campaign. The pin behind each exhibit column is
listed in [appendix-regenerate.md](appendix-regenerate.md) under
"Pins". The generator's validators fail closed when a pin's batches,
kernel, or schema disagree with what an exhibit states, and
`just report-exhibits-selftest` proves each refusal on a planted
failing input. Numbers that no pin regenerates are labeled where
they appear: D-0082's image-size bracket, and D-0071's per-boot
mechanism check.

---

## Results

The centerpiece is [exhibits/phase-decomposition.md](exhibits/phase-decomposition.md).
Host-observed edges: [exhibits/edges.md](exhibits/edges.md). D-0068
dump placement: [exhibits/dump-placement.md](exhibits/dump-placement.md).
Cross-system: [exhibits/cross-system.md](exhibits/cross-system.md).
Figures in the findings below are those generated tables, in prose.

### Two walks, one root cause (T4.3 freeze)

On release+fast-boot, `frame_init` (7.20 ms, 34% of E2→E3g) and
`accounting` (4.79 ms, 22%) were 56% of boot-to-publish (11.99 ms of
21.42 ms). They were the same underlying cost: two separate walks of
~31k frames. The first linked remaining RAM into the free list at
`frame::init`; the second was `free_count()` before freeze. Bump /
lazy free-list (T4.4) subsumed O(1) accounting. D-0060 is
declined-by-subsumption. Paging was not the dominant kernel term
on the freeze; T4.4 made it 42% of what remained; T4.6 took that.

### Verification costs more than the thing verified

`page_verify` is 2.57 ms on the freeze, 2.39 ms after T4.4, 731 µs
after T4.6; `page_build` is 1.45 ms through T4.4 and 386 µs after
T4.6 — still ~1.9×. The second walk of the identity map, kept
deliberately (D-0043), is more expensive than constructing the map
at every rung that has measured it. Combined paging 3.84 ms = 42%
of T4.4 fast E2→E3g was the re-evaluation condition for superpages
(D-0059). After T4.6 the pair is 1.12 ms = 17% of 6.43 ms.

### Safe vs fast is still a large factor, concentrated

Release-default E2→E3g was 94.88 ms against 21.42 ms fast on the
freeze (4.4×). After T4.4 it is 78.25 ms against 9.17 ms. The delta
is still concentrated in the remaining walks (`frame_init` under
opt-level=0, `page_verify`) plus the safe profile's extra
`free_count()` in `freeze()`'s println — which T4.4 collapsed from
4.88 ms to 100.0 µs. The safe build is the control; it is not the
flagship number.

### T4.4 prediction outcome

Pre-registered against `baseline-t4.3` in D-0065 before the
dedicated-host rerun; the actual column is generated in
[exhibits/t44-bump.md](exhibits/t44-bump.md). Mechanism and
magnitude were correct. The
headline arithmetic beat the ~9.5 ms projection. Three tight leftover
bounds were missed. Every falsification line (≥ 1 ms, or a third
phase vanishing) held. Point estimates on those leftovers were
~40% optimistic — a second data point on the same estimate bias
the audit recorded as finding 10 (`task_init` / `virtq_init` /
`stvec` predicted µs, measured sub-ms).

| metric | predicted | actual (pooled n=60) | verdict |
|---|---|---|---|
| fast `frame_init` | < 100 µs (expected ~10–50 µs) | 141.2 µs | bound missed; falsify-if ≥ 1 ms held |
| fast `accounting` | < 20 µs (expected ~5–15 µs) | 24.9 µs | bound missed; falsify-if ≥ 1 ms held |
| fast E2→E3g | ~9.5 ms | 9.17 ms | beat the projection |
| safe `freeze` | < 50 µs | 100.0 µs | bound missed; still collapsed from 4.88 ms |
| unnamed phase vanishes | would falsify | none vanished | held |

Headline edges, generated in
[exhibits/t44-bump.md](exhibits/t44-bump.md): fast E2→E3g
21.42 → 9.17 ms (−57%); fast E0→E4 67.05 → 54.52 ms; safe E2→E3g
94.88 → 78.25 ms.

Two unnamed phases moved without vanishing, so they do not falsify.
`page_verify` 2.57 → 2.39 ms (−7%). `E3g` 1.42 → 1.24 ms (−13% in
the pooled CSV; not the same 7%). That movement is the warm-cache
half of the matched TCG pair (Matched TCG secondaries, below;
Threats item 15), not a second hypothesis.

### T4.6 prediction outcome

Pre-registered against T4.4 in D-0059 as ranges, not optimistic
bounds, because T4.4 leftovers were ~40% optimistic. Mechanism
(mixed granularity, grain-aware verify) was correct: `tables_used`
= 5, and `page_verify` 731 µs is far from the 1.5–2.2 ms
4K-stepping band. Headline E2→E3g landed in range. Both paging
phase ranges overran (D-0069). Every falsification line held.

| metric | predicted | actual (pooled n=60) | verdict |
|---|---|---|---|
| `page_build` | 50–300 µs | 386 µs | over range; falsify-if ≥ 0.8 ms held |
| `page_verify` | 80–400 µs grain-correct; 1.5–2.2 ms if 4K-stepping | 731 µs | over range; grain-correct confirmed; ≥ 1.0 ms / < 30 µs held |
| combined paging | 0.15–0.70 ms | 1.12 ms | over range |
| fast E2→E3g | 5.5–8.0 ms | 6.43 ms | **in range** |
| `tables_used` | 5–8 | 5 | hit |
| unnamed phase vanishes | would falsify | none vanished | held |

Headline edges: fast E2→E3g 9.17 → 6.43 ms (−30%); cumulative from
`baseline-t4.3` 21.42 → 6.43 ms (3.3×); fast E0→E4 54.52 → 51.66 ms.
Arithmetic remainder if only paging moved: 9.17 − 2.72 = 6.45 ms;
actual 6.43 ms.

`freeze` 7.3 µs (T4.4 pin) → 12.2 µs is the cold-translation half
of the matched TCG pair (next subsection; Threats item 15).
Linear-vs-measured `page_verify` (~40 µs extrapolated, 731 µs
measured, ~75 ns/leaf over ~32k becoming ~1.3 µs/leaf over ~580) is
the D-0069 worked example (Threats item 14).

### Matched TCG secondaries (T4.4 and T4.6)

T4.4 made later phases faster: warm data cache and TLB after not
touching ~125 MiB. T4.6 made `freeze` slower: cold instruction
translation after the hot loop's removal. Same cause, opposite
signs, both sub-instrumentation-noise in absolute terms. Together
they illustrate threats item 16 — measuring inside an emulator
means the measurement apparatus and the measured system share
state. Named in the ladder rows; not rungs.

### D-0068: dump placement did not move E3w→E4

Pre-registered: the PHASE dump between publish and the client's
first byte occupied TCG on the loop that pumps slirp, so E0→E4
measured instrumentation, and that occupancy was the natural
account of tens of milliseconds of E3w→E4 — including why safe
is ~3× worse than fast on that term. The mechanism landed (one
`wfi` after `wait_tx`, then dump, same boot). The generated
comparison is [exhibits/dump-placement.md](exhibits/dump-placement.md).

E2→E3g unchanged is correct: the stamps did not move. E0→E4 did
not improve in either invocation. E3w→E4 is untouched in both
profiles. The pre-registered claim is refuted for this
implementation.

Before keep / extend / revert, two possibilities.

**The yield is ineffective, not the hypothesis wrong.** One `wfi`
returns on the next armed tick (~10 ms). If dump occupancy D is
serialized with remaining host time H, the observed gap is D+H.
A yield Y < H reorders the same work: Y of delivery, then D of
dump, then H−Y of delivery. Total still D+H. No change is what
both a too-short yield and a dump-irrelevant gap predict. The
discriminating test is a yield long enough to bracket the entire
fast gap (~31 ms). If that collapses E3w→E4, the mechanism was
right and one tick under-shot. That test is not this change and
is not a kernel rung.

**The gap is host-side but not host *work*.** The E3w construction
anchors the pcap-relative SYN/ACK→HTTP interval to first-connect,
assuming connect-success coincides with the guest's SYN/ACK
(`scripts/bench.py`, "first-connect (≈ SYN/ACK)"). With hostfwd
that fails: `connect()` succeeds at QEMU's host-side accept — the
listener is up during QEMU startup, guest-independent — while the
guest SYN/ACK happens only after firmware plus boot to net-init.
Everything between accept and SYN/ACK lands in "E3w→E4". Three
pieces of recorded evidence fit: first-connect is
profile-independent (18.53 vs 18.55 ms) though serving-readiness
differs by ~70 ms; rung savings partition exactly as anchoring
predicts (pre-net-init savings moved "E3w→E4": `frame_init`
−7.06 ms predicted vs −7.37 observed, paging −2.72 vs −2.83;
post-net-init savings moved E0→E3w: `accounting` −4.77 vs −5.08);
and the affine form const + boot-to-net-init reproduces the 3×
safe/fast ratio against the ~12× boot ratio. Under this reading
the D-0068 null is expected: there was never tens of ms of
post-publish host work to reorder — true delivery is
sub-millisecond. This is D-0070, pre-registered with a
falsifiable pcap-internal test (below) and **confirmed** by the
bench-host pcap pass.

The yield stays. Instrumentation off the measured path is
defensible on principle even when it costs nothing (the flagship
edges moved by a fraction of a millisecond, inside stability). A
`wfi` does not occupy TCG the way a post-publish spin would.
Reverting would put DBCN back on the interval under test.

**The discriminating test (D-0070)** was read-only over per-trial
pcaps that already existed for T4.6 and both D-0068 campaigns — no
new boots, no kernel or harness code. On one pcap clock, per
trial: `W` = guest SYN/ACK − first slirp ARP request for the
guest (accept-to-handshake wait); `D_ack` = ACK-of-response −
HTTP frame; `D_fin` = client FIN − HTTP frame (the client closes
after `recv`, so this bounds publish→client). Predictions:
`D_fin` ≤ 5 ms, profile ratio < 2; `W` ≈ E3w→E4 − `D_fin`.
Falsify lines: `D_fin` ≥ 10 ms, or scaling ≥ 2× with profile.

**Outcome** (generated: [exhibits/d0070-pcap.md](exhibits/d0070-pcap.md);
n=60 per config per campaign): `D_fin` 63–155 µs in all six
campaign-configs; safe/fast ratio 0.41–0.91 — delivery does not
scale with profile at all; `D_ack` 24–40 µs; `W_safe − W_fast`
61.40 / 61.84 / 61.65 ms against the predicted ≈ 61.5 ms. One
pre-registered line failed as written: `W + D_fin` under-reconstructs
E3w→E4 by a constant −6.70 to −7.00 ms in every cell, profile-
independent, IQRs under ~1 ms. That constant was diagnosed before
anything was amended (D-0071): it is the slice of QEMU startup
between the hostfwd listener coming up — where first-connect stamps,
because the host kernel completes the client handshake into the
listen backlog the moment `listen()` exists — and the main loop
going live, when slirp first services the queued connection and
emits the ARP that starts `W`'s clock. A one-clock mechanism check
(polling filter-dump's incremental pcap writes against the client's
own stamps; recorded in D-0071, not an exhibit) closed the
accounting per boot to +0.05…+0.32 ms, and a late-connect control
(same record) showed slirp forwards an accepted connection's SYN
in 60–160 µs once startup is over. So the former "E3w→E4"
decomposes with nothing left over: **QEMU startup (~6.8 ms) +
waiting for our own guest to boot (`W`) + sub-millisecond delivery
(`D_fin`)** — the first two already counted once, correctly, in
E0→E4. E3w→E4 is retired as a reported metric; delivery is
reported as `D_fin`.

### Ladder

The ladder is [exhibits/ladder.md](exhibits/ladder.md): rung × fast
E2→E3g after × cumulative Δ vs `baseline-t4.3` × disposition,
generated from the `baseline-t4.3`, `t44`, and `c40945c` pins, with
the declined rungs (D-0060 by subsumption; `virtq_init` as a
stopping decision) as rows carrying their reasons, and the
`virtq_init` row showing its share against the 5% bar.

### Superpage outcome (D-0059; T4.6)

The projection table below is the pre-registered prediction. Measured
values are the T4.6 prediction-outcome table above and the generated
exhibits. Mixed granularity as decided: 2 MiB L1 leaves for the
aligned KERNEL_RW RAM interior, 4 KiB for W^X image, guards, user
slots/sections, virtio-mmio window, and alignment fragments.
`EXPECTED_TABLES` is 5. `assert_range` steps by leaf grain — the
4K-stepping co-edit failure did not occur.

### Ladder read after T4.6

The profile flattened. No phase exceeds 19%. Seven clear the 5%
bar (322 µs): `E3g` 1.24 ms, `virtq_init` 842 µs, `page_verify`
731 µs, `task_init` 582 µs, `DRIVER_OK` 543 µs, `page_build`
386 µs, `serving_ready` 357 µs. Seven-above-bar is not seven
rungs:

| phase | why it is or is not a candidate |
|---|---|
| `E3g` 19% | the byte; removable only if `syn_rx`→`E3g` shows kernel waste |
| `virtq_init` 13% | discarded first pass — **the remaining E2→E3g candidate** |
| `page_verify` 11% | D-0043 paranoia; keep |
| `task_init` 9% | four U-mode slots; structurally necessary |
| `DRIVER_OK` 8% | live NIC pass; not bundled with virtq_init |
| `page_build` 6% | leftover after mixed granularity |
| `serving_ready` 6% | ARP wait; not kernel compute |

By D-0058's letter `virtq_init` still clears 5% of E2→E3g; the
ladder closed with it declined as a stopping decision (D-0083;
[exhibits/ladder.md](exhibits/ladder.md)). D-0068 was the next
*action* and has been measured: it did not move E0→E4. The Linux
campaigns have since run (T4.8 → T4.8b → T4.8c), and T4.7 measured
the firmware window — not a rung: it changes the boot contract (see
"Firmware removal" below). Fast E0→E4 is 51.66 ms on the T4.6
after-ladder pin; skipping the discarded virtqueue pass is ~0.8 ms
of that (1.6%). `virtq_init` stays eligible on the ladder's record
(Future work). The floor is not declared. The former ~31 ms "E3w→E4"
of that 52 ms is resolved: QEMU startup + guest boot wait + sub-ms
delivery (D-0070/D-0071), each counted once in E0→E4 — there is no
separate host term to take.

Leaf-count derivation — arithmetic from the T4.4 exhaust line,
not a measurement: `total=31823` → `__heap_end` ≈ `0x803B1000`;
62 × 2 MiB leaves on `0x80400000..0x88000000`; ~520 4 KiB leaves
for `0x80200000..0x80400000` plus the virtio window;
`tables_used` 67 → 5 (landed; a code-verified constant).

The pre-registered ranges, kept as the prediction record:

| metric | T4.4 | projected range | falsify if |
|---|---|---|---|
| `page_verify` | 2.39 ms | 80–400 µs if grain-correct; 1.5–2.2 ms if still 4 KiB-stepping (failed co-edit) | ≥ 1.0 ms (walk did not shrink) or < 30 µs (something else dropped) |
| `page_build` | 1.45 ms | 50–300 µs | ≥ 0.8 ms |
| combined paging | 3.84 ms (42% of 9.17) | 0.15–0.70 ms | — |
| fast E2→E3g | 9.17 ms | 5.5–8.0 ms | still > 8.5 ms, or a phase this hypothesis does not name vanishes |
| `tables_used` | 67 | 5–8 | still 67 |

Co-edit checklist, walked in the same change:
`walk()` accepts aligned L1, panics on 1 GiB and on a misaligned
2 MiB PPN (D-0026); `assert_range` expected level **and** grain
(not `level == 0` + 4 KiB step); `require_leaf` L0; virtq
`require_identity_rw*` untouched; `EXPECTED_TABLES` and
`held = tables + leftover`; D-0036 / D-0039 prose (7 = 5 + 2);
justfile virtio probe greps (row format unchanged, greps did not
move); DEBUGGING.md superpage first-response note.

### Firmware removal (T4.7 / D-0079)

Not a ladder rung: the D-0079 M-mode shim changes the boot
contract — a second lane in the `-bios` slot — rather than
removing guest work under the same contract, so it is a labeled
per-system result beside the ladder, not a row in it. All numbers:
[exhibits/t47-firmware.md](exhibits/t47-firmware.md) (pin
`c2759e2`, four Whimbrel arms, two firmware lanes, one batch set,
n=60 per arm).

Replacing OpenSBI with the shim cuts fast-boot
spawn-to-first-HTTP-byte from 52.27 / 52.19 ms to
28.58 / 28.50 ms per batch (ΔE0→E4 −23.691 / −23.689 ms, 1.8×).
The exhibit's two claims are different kinds of number and stay
separate: **Claim A**, the pooled guest-side change, is ΔE2→E3g
**−0.714 ms** (stability-gated; 6.40 → 5.69 ms); **Claim B**,
ΔE0→E4, is reported per batch and never pooled, because the
quantity being removed — the OpenSBI-side firmware window — is
volatile across campaigns. The decomposition is three terms, not
one firmware number: guest firmware execution removed
(−22.972 / −22.984 ms per batch), ΔS — host-side firmware load —
at −0.002 ms, and the −0.714 ms seam envelope. The seams are
itemised inside that envelope from D-0079's registered set
(replaced-SBI call sites or in-window print): `stvec` −222.1 µs,
`frame_init` −74.1 µs, `E3g` −517.5 µs.

The cross-system comparison uses the OpenSBI lane, not this one.
That is D-0079's measurement framing, restating D-0061: variant,
never replacement — `-bios default` keeps every gate and every
primary number, the cross-system table's Whimbrel rows stay
OpenSBI, and a registered falsifier makes any movement of the
`-bios default` cross-system rows a stop. Linux structurally
cannot take this rung — no Linux row can swap its firmware for a
purpose-built M-mode shim — and that asymmetry is the finding,
reported as a labeled per-system result rather than folded into
the ratio. Two boundaries carry over: the shim lane's console is
polled S-mode UART, so safe-profile numbers never compare across
lanes (the comparison profile is fast-boot, zero in-window
bytes), and the shim lane's S is profile-dependent — an open
D-0079 item with no consumer.

### Cross-system

Three campaigns, one lineage: T4.8 (`ffb7ac7`) → T4.8b (`t48b`,
the D-0073 FTRACE sweep and D-0075 `/init`) → T4.8c (`t48c`, the
D-0081 cmdline token). Each is frozen under its own pin; the
current comparison is
[exhibits/cross-system-current.md](exhibits/cross-system-current.md),
and the campaign exhibits carry the before/after at each seam.
Table rules, unchanged across the lineage: no E3w-derived column;
W is never next to a Linux row; E0→first-connect is a same-QEMU
control (T4.8c medians 18.54–18.64 ms, span 100.3 µs, bound
1 ms). Pre-registered gates held on every campaign: no SYN-grid
failure, no RST, first-connect bound, trimmed-vs-stock tripwire
silent. The confound-A evidence is T4.8's: Linux `trimmed` W was
718.53 ms with a 2.95 ms IQR — smooth, not snapped to a 1 s grid
— so the announce mitigation did what it was registered to do;
that check belongs to the campaign that introduced it and is not
re-litigated per seam.

On RISC-V under QEMU TCG software emulation, same host, same QEMU,
`release-fast-boot` reaches first HTTP byte 5.1× faster than
trimmed Linux and 17.8× faster than stock
([exhibits/cross-system-current.md](exhibits/cross-system-current.md)).
Published unikernel and microVM boot figures come from x86 under KVM
hardware virtualization, and a TCG absolute such as 51.95 ms or
263.75 ms compares with none of them; the ratio is the comparable
quantity, because the emulation penalty applies to both arms on the
same host.

Instrumentation cost is measured, not caveated:
trimmed-instrumented − trimmed = 23.66 ms for
`loglevel=7 printk.time=1 initcall_debug` on the same
`Image-trimmed` binary (identical `kernel_sha256`). The cell
contains in-window console output, so it is day-scoped (D-0078)
and holds within the T4.8c campaign, not across campaigns.

S — the pre-guest QEMU-startup slice — is reported per system,
never pooled across systems. D-0071 pools Whimbrel safe and fast
on the OpenSBI lane because S is profile-independent on one ELF
(the ~6.8 ms constant of
[exhibits/d0070-pcap.md](exhibits/d0070-pcap.md); the T4.7 shim
lane recorded a profile-dependent S, an open D-0079 item with no
consumer — [exhibits/t47-firmware.md](exhibits/t47-firmware.md)).
Pooling S across systems would mix populations: image load lands
in S (D-0062), and D-0082 brackets the Linux-side cost at roughly
6–13 ms (trimmed) and 10–20 ms (stock) of E0→E4 that Whimbrel
does not pay — a disclosed Linux-side component in both current
cross-system exhibits, a unikernel property rather than a
retraction of the ratio. A cross-system S pool's wide spread is
two populations, not noise.

This is floor-finding, not a trophy. The result is what a
single-purpose VM's structure buys under those stated conditions.
Whimbrel's guest work in this campaign is E2→E3g 6.38 ms; the
phase decomposition
([exhibits/phase-decomposition.md](exhibits/phase-decomposition.md))
shows where that interval goes. No "fastest" without its conditions
attached.

The trimmed row's good-faith claim is now backed by measurement: it
beats stock by 659.96 ms, so the trim removed real work rather than
hobbling Linux. The published config is
`bench/linux/linux-trimmed.fragment` on `qemu_riscv64_virt_defconfig`
(Buildroot 2026.02.3, kernel 6.18.7). A Linux boot-time specialist
could likely do better — we claim *a* minimal Linux, not *the*
minimal Linux (D-0062). The D-0072 labels named one miss: `FTRACE`
defaults y from `DEBUG_KERNEL`, the T4.8 fragment never unset it,
and `trace_eval_sync` labeled 68% of the 327 ms hole. D-0073 acted
on the miss (`# CONFIG_FTRACE is not set` plus the printk
leftovers); T4.8b measured it. Trimmed E0→E4 fell 759.79 →
284.68 ms (−475.10 ms) against the pre-registered 540–740 ms
orientation range — **below the low end**; no falsifier fired
([exhibits/cross-system-t48b.md](exhibits/cross-system-t48b.md)).
Per D-0069 the miss is stated with its direction: the sweep
removed more quiet-row work than the UART-inflated diagnostic
could bound — the expected direction, at a magnitude the range
did not allow for. The 222.6 ms label was a name for the hole,
never a quiet-row prediction; the measured saving was 475.10 ms.
The T4.8 exhibit stays the before. D-0081 then skipped the
RISC-V unaligned-access probe via a cmdline token on every Linux
arm (trimmed −20.94 ms, stock −24.40 ms); the current trimmed
row is 263.75 ms
([exhibits/cross-system-current.md](exhibits/cross-system-current.md)).

### Linux boot decomposition

Generated from the T4.8 instrumented serial plus the D-0072
`ignore_loglevel` labels
([exhibits/linux-decomposition.md](exhibits/linux-decomposition.md);
`d705ecb` + `93ab617`, same `Image-trimmed`). The finding inverts
the intuition: the virtio path Linux actually needs is 4.9 ms
(UART-inflated; `virtio_net_driver_init` + `virtio_mmio_init`).
The 327.24 ms hole is not that path. `trace_eval_sync` is 222.6 ms
UART-inflated on the diagnostic boot — 68.0% of the T4.8 cell,
which those microseconds label and do not replace. Full-file,
`of_platform_serial_driver_init` is 163.0 ms UART-inflated
(generic DT serial-bus probe, not in the hole). Kind, not
magnitude: named subsystems a single-purpose kernel never runs,
not "Linux is slower."

`initcall_debug` produced nothing on the T4.8 pin. Two factors,
this order (D-0072): `loglevel=7` filters `KERN_DEBUG` (necessary
and sufficient for the missing lines); `# CONFIG_KALLSYMS is not
set` affects names only (`PM: Calling 0xffffffff800614ec` in the
same log). A kernel trimmed this hard cannot be fully
instrumented by its own debug facility. No sixth arm.

`trace_eval_sync` is the tracing subsystem's enum-to-string sync
pass (`late_initcall_sync` flushing `eval_map_work_func`). No
tracing consumer is running (`/init` is a static musl HTTP
server; `PROC_FS`/`SYSFS` unset). `FTRACE` defaults y when
`DEBUG_KERNEL=y`; the T4.8 fragment never unsets it. That is a
missed trim on **this** Image, not a documented keep. D-0073
rebuilds trimmed and re-runs as T4.8b; this decomposition stays
the before. `CONFIG_SERIAL_OF_PLATFORM` stays a keep:
`serial8250_init` is 2.0 ms UART-inflated (core register, "4
ports"); `of_platform_serial_driver_init` is the DT probe of
`10000000.serial` (82.5×, UART-inflated).

The printk-visible kernel to `Run /init` is 617.58 ms. The top
ten gaps are 84.1% of that span; gap 1 is 327.24 ms / 53.0%.
`/init` is 627.03 ms of kernel then 26.18 ms of server work.
Printk `Run /init` → shutdown = 43.31 ms = 9.45 + 26.18 + 7.68.
Unmeasured prefix: 63 untimed OpenSBI lines, then 39 kernel lines
at `0.000000` until `sched_clock` at 38 µs. No E2 constructed.

### Unikraft: boot-path analysis at the pin

A three-way comparison including Unikraft was attempted and ended at
a pre-registered no-go, not a schedule limit (D-0063). The spike's
criteria were fixed before the pin. **Go** meant the HTTP example
builds for qemu/riscv64 at the pinned commit, boots on the pinned
QEMU with documented flag deltas, and answers the harness client.
**No-go** meant a build failure surviving config-level fixes, a
nonfunctional riscv64 network path, or any fix requiring patches to
Unikraft internals. That last line is also the abandon criterion:
config and build-system fixes leave "Unikraft" meaning Unikraft, and
a core patch would make the row describe our fork. Nothing in this
section is quantitative, and nothing in it shares a table with a
measured number.

**The pin** (recorded 2026-08-22 from live GitHub state):
unikraft/unikraft PR #1698 at head
`e9b1d5496bd9d0678b035dde2986171bf4398c56` (zzSunil/unikraft
`staging`, committed 2026-06-15; base `be744898`); the application
is catalog-core `c-http` at `7196610a`, a make-driven build over
lib-lwip `ec55ae17` and nolibc, built with Unikraft's own Makefile
(`UK_DEFCONFIG`) and launched through `scripts/qemu-args.sh`, so
kraftkit is on record but off the critical path; kraftkit is pinned
at prerelease `v0.12.15-11-g5019204e`, because the latest stable
release (v0.12.15) lacks riscv64 and the support (kraftkit#2900) had
merged to `staging` on 2026-08-09 without shipping. The PR head had
not moved between the spike's registration (2026-08-16) and the pin,
so the analysis describes the port's only riscv64 state to date.
**The analysis is source-level at that pin: nothing was built or
run.** The go criteria were evaluated against the source; what that
leaves unverified is listed below.

**The trace.** Two no-go criteria fired independently (the riscv64
network path is nonfunctional, and the fix requires a patch to
Unikraft internals), and the abandon line held: no patch was
written. Each step names a file a reader can check.

1. `c-http` selects `LIBLWIP` → `LIBUKNETDEV` → `LIBVIRTIO_NET` →
   `LIBVIRTIO_BUS` (`drivers/virtio/bus/Config.uk`), which implies
   `LIBVIRTIO_PCI if HAVE_PCI` and `LIBVIRTIO_MMIO if HAVE_MMIO`;
   `KVM_VMM_QEMU` (`plat/kvm/Config.uk`) selects both `HAVE_PCI` and
   `HAVE_MMIO` with no architecture condition.

2. On the MMIO transport (Whimbrel's topology, `virtio-net-device`),
   `LIBVIRTIO_MMIO` is not architecture-gated, and
   `LIBVIRTIO_MMIO_FDT` defaults on whenever `LIBFDT && LIBUKOFW`,
   which the PR selects for riscv64. The platform bus
   (`drivers/ukbus/platform/platform_bus.c`, `pf_probe_fdt`, near
   line 144) walks every device-tree node whose compatible string is
   in `pf_device_compatible_list` (`virtio,mmio`,
   `pci-host-ecam-generic`, `arm,pl031`) and calls the driver's
   `probe` before `add_dev`. `virtio_mmio_probe_fdt`
   (`drivers/virtio/mmio/virtio_mmio.c`, near line 423) calls
   `uk_intctlr_irq_fdt_xlat(dtb, offs, 0, &irq)` unconditionally.

3. The generic interrupt layer (`lib/ukintctlr/ukintctlr.c`, lines
   212–225) asserts `uk_intctlr->ops->fdt_xlat` and then calls
   through it. The PR's PLIC driver
   (`drivers/ukintctlr/plic/ukintctlr.c`) registers `plic_ops` with
   `.fdt_xlat = __NULL` and a `configure_irq` that returns 0 without
   reading the IRQ. With asserts on, that is `UK_CRASH`; with
   asserts off, an indirect call to address 0, a fetch fault, and an
   unhandled trap.

4. QEMU's `virt` machine always presents eight `virtio,mmio`
   transports in the device tree whether or not a device is
   attached, and the magic-number / dummy-ID check that would skip
   an empty transport lives in `virtio_mmio_add_dev`, which runs
   after `probe`. The crash therefore fires on the first transport,
   during bus probing, before `main`, in any riscv64 build with
   `LIBVIRTIO_MMIO=y`. The boot criterion fails together with the
   answer-the-client criterion; only a network-less build can boot.

5. The fix is a `plic_fdt_xlat` that reads the one-cell `interrupts`
   property (the PLIC's `#interrupt-cells = <1>`) plus a real
   `configure_irq`: new code in a Unikraft driver, which the
   no-core-patches line forbids.

**Closed escape routes**, each with why it is closed. *PCI
transport:* `drivers/ukbus/pci/Config.uk` has
`LIBUKBUS_PCI depends on (ARCH_X86_64 || ARCH_ARM_64)`, untouched by
the PR, so the `virtio-net-pci` device kraftkit emits for every
architecture (`machine/qemu/v1alpha1.go`) attaches a NIC Unikraft
cannot enumerate on riscv64; flipping that one line drags in the
ECAM driver, whose device-tree interrupt parsing has its own open
fix (unikraft#804) and which needs the same `fdt_xlat` regardless.
*Command-line devices:* `VIRTIO_MMIO_LINUX_COMPAT_CMDLINE` /
`virtio_mmio.device=` exists in `drivers/virtio/mmio/Config.uk`, but
`virtio_mmio.c` in this tree has no libparam references and
`virtio_mmio_probe` has only the FDT branch: a Kconfig orphan.
*Disabling FDT probing:* `LIBVIRTIO_MMIO_FDT` is a promptless `bool`
with `default y if (LIBFDT && LIBUKOFW)`, so it cannot be switched
off from `.config`. *Stripping the `virtio,mmio` nodes:* that is a
hand-edited machine description passed via `-dtb`, not a flag delta,
and it would also remove the transport the NIC needs.

**A regression, not an absence.** The original port, unikraft#461
(2022), described PCI and MMIO probing as "virtually identical" to
the ARM implementation and reported Redis, NGINX, SQLite and Python
running, all of which need the network. The `uk_intctlr` driver-ops
interface (`fdt_xlat`, `configure_irq`) postdates that port; the
2026 rebase that is #1698 stubbed it (`plic.c` carries a "leave it
alone at the moment, seems like just not used anymore" on
`plic_ack_irq`), and the PR's own checklist lists no application and
a QEMU 10.0.3 test, consistent with a hello-world port. This rebase
has not reconnected the interrupt path to device discovery.

**What looked right in the port**, read but not run: trap dispatch
(`plat/kvm/riscv/traps.c`, `_trap_handler`: `SUPERVISOR_EXT` to
`plic_handle_irq` with a claim/complete loop; the timer via SBI with
`sbi_set_timer(-1)` as the acknowledge); PLIC enable and priority 1
on unmask (`plic_clear_irq`) with threshold 0 at init; `fence`-based
`mb`/`rmb`/`wmb` for the virtio ring
(`arch/riscv/riscv64/include/uk/asm/lcpu.h`); MMIO mapping through
`uk_bus_pf_devmap` with plain read-write attributes, sufficient
under Sv39 on TCG; lib-lwip and nolibc carry no architecture gating,
and the PR adds the riscv64 nolibc pieces `c-http` needs;
`virtio_mmio.c` accepts device versions 1 and 2, so the harness's
`-global virtio-mmio.force-legacy=false` (`scripts/qemu-args.sh`) is
compatible; OpenSBI's residency at `0x80000000` is special-cased in
`plat/common/bootinfo_fdt.c`.

**What could not be verified** without a build and a boot: TLS and
context-switch correctness (`arch/riscv/ctx.c`, `tls.c`); the timer
under load; whether riscv64 nolibc is complete enough for lwip's
build; and whether the port boots at all on the pinned QEMU 10.2.1,
the author having tested 10.0.3. The trace above is a source-level
argument, checkable file by file, that the networked configuration
cannot boot at this pin; the list of what looked right carries no
such weight.

**The cross-ISA build, available and not run.** Fallback (2), a
Unikraft number on qemu/x86_64 or qemu/arm64, where `c-http` is a
catalog example and the build was available at the pin, was declined
deliberately (D-0063, 2026-08-23). By the spike's own rule such a
number never shares a table with riscv64 numbers, so it would cost a
build, a campaign, and an exhibit to produce a figure the reader is
then told not to compare with anything else in this report. The
discipline that makes the Linux ratios meaningful (same host, same
pinned QEMU, the emulation penalty applied to both arms) is what a
cross-ISA row cannot have. Everything of (2) that survives that
scrutiny is the source-level analysis above; fallback (3) keeps it
and drops only the incomparable number. The one route back to a
three-way that does not cross the no-core-patches line is the
`fdt_xlat` stub being fixed in the PR branch itself, followed by a
re-pin to that head; it is noted, not planned (Future work). ---

## Threats to validity

Each item is mitigated-and-measured or stated. Seed: T4.0 list as
maintained in [threats-to-validity.md](threats-to-validity.md).

1. **TCG is not hardware.** Compute-dense phases (free-list walk,
   page-table build) and MMIO-dense phases (virtio) are taxed
   differently than on silicon. Every claim carries "under QEMU TCG".
2. **slirp is the TCP peer**, not a wire. E3w−E3g prices virtio+slirp.
   True hostfwd delivery plus client recv is sub-millisecond on
   every measured row: `D_fin` 63–155 µs across the Whimbrel D-0070
   campaigns ([exhibits/d0070-pcap.md](exhibits/d0070-pcap.md)) and
   ≤ ~0.3 ms on every T4.8c arm
   ([exhibits/cross-system-t48c.md](exhibits/cross-system-t48c.md)).
   The former "E3w→E4" is retired: QEMU startup (D-0071) plus the
   accepted connection waiting for the guest to boot (D-0070),
   mislabeled by E3w's anchoring construction.
3. **Client retry granularity is 1.000 ms measured** (persistent
   process; see machine-spec `client_granularity_ns`). That cadence
   does not apply after `connect()`. Fork-per-attempt curl was
   5–15 ms (finding 32) and is not in this dataset.
4. **Boost-off costs ~17% peak clock** (4.2 vs 5.05 GHz on this
   7800X3D). Absolute numbers are larger; boost-state and thermal
   variance are removed, which is what the stability criterion
   measures. All systems measured identically; only the absolute
   floor moves (D-0055).
5. **The pre-M4 harness was fail-open on build failure** (finding 31).
   A failed `cargo build` left the previous ELF in place and printed
   PASS. **No report number derives from that harness.** T4.0b closed
   it; this baseline is `scripts/bench.py` on the fail-closed tree.
6. **Single hart and fixed RAM.** The floor is for this machine shape.
7. **Debug-era history is not evidence.** Regeneration from CSV;
   appendix [appendix-regenerate.md](appendix-regenerate.md).
8. **Linux-tuning fairness** (D-0062) — measured: trimmed beats
   stock by 659.96 ms
   ([exhibits/cross-system-current.md](exhibits/cross-system-current.md)),
   so the trim removed real work. Config published:
   `bench/linux/linux-trimmed.fragment`. A Linux boot-time
   specialist could likely do better; we claim *a* minimal Linux,
   not *the* minimal Linux. On the T4.8 Image, `FTRACE` is a
   recorded miss: it defaults y from `DEBUG_KERNEL`, the fragment
   never unsets it, and `trace_eval_sync` is 68% of the 327 ms
   hole. D-0073 acts on that miss (new Image, T4.8b campaign);
   the T4.8 numbers still include it. The miss is not left as
   "we ran out of patience."

   **Non-reversing select.** Kconfig `select` does not unset the
   target when the selector goes. A helper or transport that
   `select` pulled in stays `=y` whenever it has its own prompt,
   a default, or another selector under a menu the trim did not
   touch. That is a property of trimming a kernel by subsystem,
   not a quirk of this fragment; it cost three `linux-build`
   iterations to see. Seven symbols on this Image were that
   shape: `NET_9P`, `DNS_RESOLVER`, `NLS`, `MTD`, `DAX`,
   `IP_PNP`, `EXPORTFS`. The fourth pass walked remaining `=y`
   against live `select` edges in one go (`FHANDLE` and overlay
   were still selecting `EXPORTFS`; unsetting the helper alone
   would have left it `=m`) rather than catching the next
   orphan after another rebuild.

   Walked and kept, with the reason, so the bound is analysis
   rather than patience: `CRC32` (`MACB` still selects it);
   `NVMEM` (`NVMEM_SUNXI_SID` still y); `SHMEM` (anonymous
   memory, not a DRM leftover); `EVENTFD` (`default y` syscall;
   `MEMCG`'s select was extra); `FW_LOADER` (`default y`
   firmware facility); `FILE_LOCKING` (`default y`); `MACB` /
   `PHYLIB` / `MICREL_PHY` (sibling NIC to virtio-net, still a
   live ethernet driver); `NETFILTER` (defconfig y, own prompt);
   `INET_DIAG` (`default y` for `ss`; not a dropped consumer);
   `AUTOFS_FS`, `POSIX_MQUEUE`, `SYSVIPC` (defconfig y, own
   prompts); `VIRTIO_CONSOLE` / `BALLOON` / `INPUT` (defconfig y
   extra virtio); `XFRM` (`XFRM_USER=m` still a consumer);
   `FAILOVER` / `NET_FAILOVER` (`VIRTIO_NET` selects them);
   `DEBUG_FS`, `FB`, `VT`, `PINCTRL`, `I2C`, `SPI`, `THERMAL`,
   `CPU_IDLE` (named deferred: no-boot risk or idle path).
9. **Unikraft pin** (D-0063) — stated. No Unikraft row exists or
   will: the spike ended at a pre-registered no-go and the
   comparison converged in fallback (3). The pin — unikraft/unikraft
   PR #1698 head `e9b1d549`, kraftkit prerelease
   `v0.12.15-11-g5019204e`, catalog `c-http` at `7196610a` over
   lib-lwip `ec55ae17` — is stated in full in the Results section
   "Unikraft: boot-path analysis at the pin". That analysis is
   source-level at one commit, nothing built or run, so it describes
   the port at that head and not the PR as it may later merge.
10. **Instrumentation observer effect.** Stamp overhead is a generated
    row in [exhibits/edges.md](exhibits/edges.md) (5.5 µs on
    fast-boot). `print_after_response` is a second observer. D-0068
    moved it after a yield so DBCN is not on publish→E4. Two N-trials
    produced no E0→E4 improvement
    ([dump-placement.md](exhibits/dump-placement.md)). The yield
    stays on principle. The null was later explained: there was no
    post-publish host work for it to move (D-0070).
11. **Host variance.** Dedicated native host, performance governor,
    SMT off, boost off, steal 0 on all recorded trials of every
    published campaign — the freeze, T4.4, T4.6, both D-0068
    invocations, T4.8/T4.8b/T4.8c (300 recorded each), and T4.7
    (240 recorded) — with two interleaved batches
    that met max(2%, 200 µs). D-0068 additionally reproduced across
    two independent campaigns. The KVM pod failed the criterion and
    is not cited.
12. **E3w fidelity.** filter-dump timestamps are a QEMU realtime clock
    that does not match Python `time.time_ns()` — measured as a
    per-boot offset of −30 to −846 ms on the pod, so no absolute
    `pcap_epoch − e0_wall` quantity is usable (D-0071).
    `e0_to_e3w_ns` was first-connect plus the pcap-relative
    SYN/ACK→HTTP interval; its anchor ("first-connect ≈ SYN/ACK")
    was tested and is false under hostfwd — connect-success is the
    host kernel accepting into QEMU's listen backlog during startup,
    not the guest handshake (D-0070, confirmed). E3w-derived metrics
    are retired in favor of pcap-internal intervals on one clock
    (`W`, `D_ack`, `D_fin`). No E3w-derived column may appear in a
    cross-system table.
13. **Reservation vs working set** (D-0030).
14. **Estimate bias (D-0069).** Three-for-three, all optimistic
    (predicted too fast): finding 10, T4.4 leftover bounds (~40%),
    T4.6 both paging phases over range. We scale as if cost were
    linear in operation count; a fixed per-call cost does not scale
    down with N (~75 ns/leaf over ~32k becoming ~1.3 µs/leaf over
    ~580: 731 µs measured against a linear extrapolation of ~40 µs,
    roughly 17×). The fixed component is software-walk decode, level
    and grain asserts, and TCG trace warmup. Any rung that reduces
    an operation count will disappoint relative to linear
    projection, because the fixed component becomes the dominant
    term. Headline E2→E3g ranges that pad for this have held;
    unpadded phase ranges have not. Later projections pad beyond a
    linear remainder, or treat "over range" as the expected miss and
    keep only the falsify-if line load-bearing. The 5% eligibility
    bar uses measured shares and is unaffected.
15. **Matched TCG secondaries.** T4.4 made later phases faster (warm
    data cache after not touching ~125 MiB). T4.6 made `freeze`
    slower (cold instruction translation after the hot loop's
    removal). Same cause, opposite signs, both
    sub-instrumentation-noise. Presented together under item 16;
    named in the ladder rows; not rungs.
16. **The measurement apparatus and the measured system share
    state.** QEMU's TCG (data cache, instruction translation) and
    the main loop that pumps slirp are host state that guest work
    writes as a side effect of existing. Two illustrations. The
    matched pair in item 15 is the cache/translation surface. The
    occupancy surface is guest work after a guest-side stamp moving
    a host-observed edge. D-0068 tested the PHASE dump as that
    occupant: two N-trials, no E4 movement. The dump stays off the
    interval on principle. The Linux arms share slirp/hostfwd;
    they do not share a PHASE dump. If measured runs stopped
    printing PHASE, the decomposition and E0→E4 would come from
    different boots — that would be its own line.
17. **A derived metric double-counted guest boot under a
    host-sounding name (D-0070/D-0071).** "E3w→E4" folded QEMU
    startup (~6.8 ms) and boot-to-net-init wait (~24/~85 ms) into a
    term labeled host-side delivery. It survived a pre-registered
    audit and four measurement campaigns, and was caught only
    because it moved with kernel rungs a host-side term should not
    respond to. The honest headline (E0→E4, two direct client-clock
    stamps) was never wrong — each piece was counted once there.
    The lesson sits beside D-0069's: an unexplained constant must
    not keep a plausible-sounding name.
18. **A kernel trimmed this hard cannot be fully instrumented by
    its own debug facility** (D-0072). `initcall_debug` is on the
    T4.8 cmdline and produced zero entries: `loglevel=7` filters
    `KERN_DEBUG` (necessary and sufficient); kallsyms off affects
    names only. Stated. The decomposition is printk gaps plus
    `/init` stamps plus UART-inflated labels from one
    `ignore_loglevel` boot of the same Image
    ([linux-decomposition.md](exhibits/linux-decomposition.md)).
    Gap 1 is `trace_eval_sync` (222.6 ms UART-inflated, 68% of the
    327.24 ms cell, which those microseconds label and do not
    replace). Not a sixth comparison arm. On this Image `FTRACE`
    is a missed trim (D-0062: *a* minimal Linux, not *the*
    minimal Linux). D-0073 acts on it; T4.8b is the after.
19. **`W` fuses guest boot with egress delay; only a guest-internal
    stamp separates them** (T4.8b diagnosis, 2026-08-18). `w_ns`
    spans the guest's entire boot-to-first-TX, so an inflated `W` is
    not attributable to boot or delivery without an instrument that
    sees the boundary. The largest T4.8 excursions (+39 to +125 ms in
    E0→E4 and `W` together) were slow guest boots — `/init` announce
    stamp late by the same amount, egress lag normal — not delivery
    faults; the egress-attributed tail is ≤ 7.7 ms. Medians and the
    trimmed-vs-stock delta are unmoved (≤ 0.037 ms). The one ~1 s
    anomaly is a single T4.8b warmup trial; the SYN-grid gate fired
    and nothing published. It is not an egress fault but a guest-side
    lost ARP solicit (D-0074), measured at 25 in 550 boots on the
    bench host: the first solicit never reached the TX ring and the
    guest's own `neigh` retransmit re-sent it 1.03 s later, past
    slirp's ARP-pending drop. An earlier revision of this item offered the
    absence of comparable stalls across the recorded campaigns as
    evidence of robustness; that claim is withdrawn, not weakened —
    it was an absence of observation under a detector blind below the
    cliff, and the one quantity that separated event boots from clean
    ones (the margin between the announce and the last virtio ctrl-vq
    completion, ~12.4 ms typical against ~0.2 ms on every event boot;
    a marker, not a cause — D-0076) was never measured on the older
    images. During this diagnosis the fused metric
    briefly produced the same misattribution item 17 records — one
    step after that lesson was written down — reversed by the
    guest-stamp split; the recurrence is why the corollary is an
    instrument rule, not vigilance: a metric spanning two subsystems
    must not be attributed to either without an instrument that sees
    the boundary. D-0076 supersedes that with a wider rule after a
    fifth instance: in all five the instrument was present and the
    analysis aggregated past the grain at which the effect lived, so
    check that a summary's grain is finer than the structure being
    claimed, and join per-item data before pooling it. Two harness
    facts are recorded, not fixed: the
    SYN-grid gate tests a relative interval (blind to absolute
    first-TX time, so it catches only stalls that cross slirp's ~1 s
    ARP-pending drop) and runs only on Linux trials — coverage
    inversely matched to exposure (Whimbrel fast-boot: ~980 ms silent
    window, ungated; stock: ~103 ms, gated). And Whimbrel's
    guest-side detector (`first_rx − DRIVER_OK`, flat to 0.56 ms over
    ~400 boots) is a side effect of D-0056.3's correctness `wfi`
    removal — luck, not design; a rung re-introducing that `wfi`
    degrades it to ≥ 10 ms tick grain. That interval spans request to
    reply through Whimbrel's own stack, so it bounds guest-side loss
    as well as egress hold — where Linux's fire-and-forget `/init`
    announce observes neither (D-0074).

20. **T4.8b's Linux `/init` is not T4.8's** (D-0075/D-0076). The
    lost-solicit event is campaign-fatal, so `/init` now shortens the
    `neigh` retransmit from 1 s to 50 ms via one `RTM_SETNEIGHTBL`
    before the announce. That call is on the measured path and
    inflates the Linux baseline by a measured **2.87 ms** (`T_NEIGH`
    stamp; ~0.4% of the 659.96 ms trim delta — a smaller share than
    T4.8's ~1.5% only because the denominator grew; the 2.87 ms
    itself is unchanged) — a bias toward
    Whimbrel, applied identically to stock and trimmed so the trim
    comparison is unaffected. An earlier "sub-millisecond" estimate
    was wrong by 3x, which is why the cost is stamped rather than
    argued. The heal it installs is **unexercised**: the event has
    not recurred in any fix-bearing configuration, so the timer-wheel
    arithmetic behind the 50 ms constant is read out of the 6.18.7
    source and has never been observed. Why the events stopped is
    **not** established, and four diagnostic arms overturned two
    successive readings of it (D-0076). What per-boot analysis does
    show: the events are a distinct early announce mode at ~156.4 ms,
    which occurred on 4.73% of boots one morning and 1.67% of boots
    that afternoon on the same source — so the published 4.55% rate
    measures a host state, not the image. Two consequences: the 2.87
    ms may also be the protection, so anything making the
    pre-announce path cheaper may re-arm the race; and "no event in
    6200 boots" is really **no event in 11 informative boots**, since
    only early-mode boots can collide. Per-trial `guest_ftx_ns` /
    `guest_arp_req_n` make any recurrence countable rather than
    fatal.

21. **Serial-byte cost is a campaign-scoped host regime** (D-0078
    and its amendment;
    [exhibits/regime-witness.md](exhibits/regime-witness.md)). With
    kernel, QEMU, argv and pins byte-identical, the guest serial
    path stepped from ~5.8 to ~6.8 µs/byte between T4.8 and T4.8b.
    Every safe-profile phase grew in proportion to the bytes it
    prints (~1.0 µs/byte), `frame_init`'s tick-anchored wait
    absorbed it, and a same-day two-shell A/B exonerated the
    launcher. The recorded witness — the safe arm's per-trial
    `page_verify` — divides into two clusters at ~14 ms, and every
    recorded campaign is internally uniform: T4.8 and both D-0068
    invocations deflated, T4.8b inflated, T4.8c deflated (its
    canary columns). An earlier reading — the canary's first uses
    showing the state flipping on a minutes timescale — is refuted
    by the warmup-position join: the disagreeing canaries and the
    batch-boundary first safe warmups land in one structural
    deflated cluster (11.78–12.11 ms), lane-independent, host-side
    of the polled UART — a position effect, not a mid-run flip.
    The same evidence demotes the canary from certificate to
    component: it disagreed with the recorded witness twice (t47b,
    t47c), so a campaign's regime is the canary joined with the
    recorded witness within one kernel family, never the canary
    alone. Exposed: safe-profile deltas and its `W`/E0→E4
    (+15.8 ms between the T4.8 and T4.8b tables — the campaign's
    serial regime, not a regression), the instrumented−trimmed
    observer cost (day-scoped per campaign), and pooling safe
    numbers across campaigns whose regimes differ — T4.8b and
    T4.8c's canaries disagree, so per D-0078 those safe rows do
    not compare. Not exposed: the headline — `release-fast-boot`
    prints nothing in its window (52.28 → 51.87 → 51.95 ms across
    the three campaigns), and Linux quiet rows print ~6 bytes.
    `stock` was the parity control at the T4.8→T4.8b seam
    (948.11 → 948.10 ms); at the T4.8c seam it moves by design
    (D-0081), and drift control passes to `release-fast-boot` plus
    the campaign canary. The stability gate cannot catch this: it
    compares within a campaign, and the regime is uniform within
    each; a mid-campaign flip would remain visible at trial grain
    in the safe arm's own witness, and none has been observed.

---

## Future work

`virtq_init`, the first virtqueue program-and-verify pass that the
device reset in `net::init` wipes, stays eligible under D-0058:
842 µs, 13% of the after-ladder E2→E3g
([exhibits/phase-decomposition.md](exhibits/phase-decomposition.md)),
above the 5% bar. The ladder closed with it declined as a stopping
decision (D-0083): its ceiling gain of 0.84 ms is 1.6% of the
51.95 ms fast-boot E0→E4 the comparison rests on, so landing it
would not move the comparison claim. A reader who takes the rung
measures against the T4.8c pin and adds a row.

D-0010 asked for a syscall-latency exhibit: a `gettime`-bracketed
hot loop on Whimbrel against Linux's trap path and its vDSO, the
vDSO standing in for what a single-privilege unikernel gets (PLAN
T4.10). D-0083 descoped it, together with QEMU maximum RSS and
guest-reported free memory, since no published claim depends on
them. The per-crossing price of the U/S boundary is therefore
unmeasured (Architecture), D-0010's consequence that M4 report
syscall latency as trap-based is not met, and Threats item 13 states
the reservation without a working set. It is the first measurement
to take if the boundary's cost becomes the question.

The one route back to a three-way comparison that keeps the
no-core-patches line is the `fdt_xlat` stub fixed upstream in the PR
branch itself, then a re-pin to that head and the spike's go
criteria run again (D-0063). It is noted, not planned.

On the shim lane, S differs between profiles: the shim-safe arm's S
sits below the shim-fast arm's, where the OpenSBI lane's two
profiles agree (D-0079). It gates nothing and no published number
reads it; the T4.7 claims use the fast pair. Explaining it takes a
mechanism check of D-0071's kind on that lane's captures. It is an
open D-0079 item with no consumer.

D-0080 registered a characterization of E0-side drift, the
batch-to-batch movement of first-connect that aborted t47b, and a
decision on what D-0055's stability criterion does about it. Its
first execution, on 2026-08-20, was an invalid run: the runner had
no pacing, so the probe sampled at roughly 1000× its registered
cadence and the session took about 30 s against a registered 35 to
40 minutes, and its selftest could not fail on that. A redesign that
enforces the cadence from recorded timestamps and refuses compressed
timestamps in its selftest is drafted and not implemented; the run
has not been repeated, and the question the entry was registered to
answer is open (Threats).

D-0083 added one column to the cross-system table without a
campaign: image bytes, the bytes QEMU loads from the `-kernel` file
(the sum of `PT_LOAD` sizes for Whimbrel's ELF, the file length for
a Linux `Image`), from a committed record that measures each pinned
artifact and verifies its sha256, with the generator failing closed
on a missing size or a hash mismatch. At this draft it has not
landed: the record, its script, and the column do not exist yet. It
is the remaining bench-host task before sign-off, a measurement of
files rather than a boot, and it puts a number beside the D-0082
bracket for the image-size component of S.

---

## Appendices

- [Numbers that must be regenerated, and Pins](appendix-regenerate.md)
  (audit findings 16–23; the pin behind every exhibit column).
- [Phase decomposition exhibit](exhibits/phase-decomposition.md)
- [Ladder exhibit](exhibits/ladder.md)
- [Edges exhibit](exhibits/edges.md)
- [T4.4 bump exhibit](exhibits/t44-bump.md)
- [Dump placement exhibit](exhibits/dump-placement.md)
- [Cross-system exhibit](exhibits/cross-system.md)
- [Cross-system T4.8b exhibit](exhibits/cross-system-t48b.md)
- [Cross-system T4.8c exhibit](exhibits/cross-system-t48c.md)
- [Current comparison](exhibits/cross-system-current.md) — alias
  following `CURRENT_COMPARISON`; campaign exhibits stay frozen
- [T4.7 firmware-removal exhibit](exhibits/t47-firmware.md)
- [Regime-witness exhibit](exhibits/regime-witness.md)
- [Linux boot decomposition](exhibits/linux-decomposition.md)
- [D-0070 pcap pass exhibit](exhibits/d0070-pcap.md) (generated on
  the bench host; committed from there)
- [Machine-spec block](exhibits/machine-spec.md)
