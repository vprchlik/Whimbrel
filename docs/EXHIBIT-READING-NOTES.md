# Reading the historical Whimbrel exhibits

The campaign exhibits remain historical records. Their measurements, pins and original wording are preserved. These notes clarify how to read them alongside the [current comparison](../report/exhibits/cross-system-current.md).

## Cross-system ratios

The ratios printed in the frozen [T4.8](../report/exhibits/cross-system.md), [T4.8b](../report/exhibits/cross-system-t48b.md) and [T4.8c](../report/exhibits/cross-system-t48c.md) exhibits divide the Linux median by the Whimbrel `release-fast-boot` median. Their original bullet labels put the operands in the opposite order. Read the values as follows:

| Campaign | `trimmed` / `release-fast-boot` | `stock` / `release-fast-boot` |
|---|---:|---:|
| T4.8 | 14.5× | 18.1× |
| T4.8b | 5.5× | 18.3× |
| T4.8c | 5.1× | 17.8× |

These are comparisons within the recorded QEMU TCG campaigns. Running both systems under emulation does not establish that they incur equal emulation overhead, or that the ratios transfer to KVM or other hosts. The current comparison exhibit now uses the corrected labels and this narrower interpretation.

## Controls and causal explanations

The T4.8b `stock` control changed little between campaigns. That supports stability for that arm and measurement; it does not, by itself, exclude all host drift or establish that serial-byte cost is the sole cause of another arm's movement. The stated serial explanation should be read with its supporting D-0078 evidence and campaign limits.

The regime-witness exhibit reports overlapping idle-gap ranges for dipped boots and their neighbors. Those ranges do not distinguish the groups in that summary. Overlap alone cannot rule out timing effects or establish a causal mechanism. Likewise, observations in both firmware lanes support investigating a shared cause but do not uniquely locate it.

## Diagnostic intervals

The Linux decomposition distinguishes the original T4.8 log from a separate, more heavily instrumented diagnostic boot. Its 222.6 ms `trace_eval_sync` duration is 68.0% of the original 327.24 ms gap as a numerical comparison; it is not a measured partition of that gap. The phrase “essentially the whole anonymous region” should not be read as a complete attribution. The exhibit itself says the diagnostic durations label the gap rather than replace its measurement.

The `/init` table places `listen` at 627.03 ms on `CLOCK_MONOTONIC`. Calling that entire prefix “kernel boot before userspace” is too broad: listening occurs in userspace after program startup. The same exhibit separately reports `Run /init` at 617.58 ms and an exec-to-listen interval of 9.45 ms. Keep those event boundaries distinct.

## Outcomes and historical metrics

The D-0070 pcap exhibit's “CONFIRMED” verdict applies to its stated D_fin checks. Its original reconstruction prediction failed as written, and the exhibit records the later S-term explanation. Do not summarize the whole set of original predictions as having passed.

The edge exhibit retains retired E3w-derived quantities as evidence of an earlier labeling problem. The dump-placement exhibit also uses those historical quantities. They should not be presented as current cross-system metrics. The optimization ladder records both landed and declined steps; closing it does not prove that no further improvement is possible.

## Startup remainder and the FIN tail

The historical S discussion in the [results schema record](../results/README.md)
calls the mixed-clock remainder S plus the FIN-after-E4 tail. The formula in
that record and the [harness](../scripts/bench.py) subtracts that tail.

To see the sign, put the events on a common idealized timeline: C is the
first-connect timestamp, A the first slirp ARP, F the client FIN and E4
the client's first-byte receipt. Then
`(E4 − C) − (F − A) = (A − C) − (F − E4)`.
A positive FIN-after-receipt tail therefore makes the remainder smaller
than the ARP-minus-first-connect interval, not larger.

This is an algebraic clarification. The recorded calculation combines a
client-monotonic duration with a pcap duration; clock-rate differences and
timestamp placement still limit its interpretation. It does not directly
measure listener-up or main-loop entry. The historical formula, records
and reported values are unchanged.

## Firmware decomposition sign convention

The [T4.7 exhibit](../report/exhibits/t47-firmware.md) expresses its boot-time and guest-work changes as shim minus OpenSBI. It defines ΔS in the opposite direction, S(OpenSBI) minus S(shim), then subtracts ΔS in the residual formula. The [generator](../scripts/report-exhibits.py) reproduces that inconsistency.

With the exhibit's existing definition of ΔS, the consistently signed residual is `ΔE0→E4 − ΔE2→E3g + ΔS`. Equivalently, define every change as shim minus OpenSBI and subtract that version of ΔS. Recalculation from the exhibit's pinned CSVs confirms the sign issue. It does not change the directly measured E0→E4 or E2→E3g differences.

That residual combines differences of medians and a campaign-level S estimate. It is not an independently measured guest-firmware duration or proof that every remaining change comes from firmware execution. The historical exhibit and its calculations remain unchanged; use the consistent formula if deriving a new decomposition.

These notes are a wording and internal-consistency review, not a new benchmark run, a reproduction of every diagnostic, or an independent audit of all causal claims.
