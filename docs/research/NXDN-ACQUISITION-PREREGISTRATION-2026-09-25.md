# NXDN48 discriminator acquisition observer: fixed correctness screen

Registered before the first native observer run on 2026-09-25. Baseline source
is `4b0dd222c3bb6abb80c50729058471313bbcb5ce`; the preserved source archive
SHA-256 is `35806211ab30ce11d7f2422b751f07dd062fa0998a0083ef67d090f02e529dfc`.
This is a measurement qualification experiment, not a decoder optimization.

## Question and domain

Can a research-only observer identify the exact exclusive frontier of samples
successfully delivered from the RTL symbol cache, without changing the real
NXDN48 synchronization and dibit results? Is acquisition invariant to provider
read chunk size on the fixed vectors?

The domain is **48,000 supplied discriminator samples per second**, not original
complex I/Q. Source read-ahead is explicitly separate. The nominal FSW boundaries
are generated symbol landmarks, not RF-energy onset. Original-IQ acquisition,
CRC/FEC-validated frame latency, PCM latency and whole-app speed remain null.

## Fixed matrix and oracle

Reuse the existing independently specified phase-regression signal: 32 alternating
outer preamble dibits, followed by 16 units of the NXDN FSW `3131331131` and 182
uncoded payload dibits cycling `0132230110322301`, rotated by unit number.
Dibit levels are +8000, +24000, -8000, -24000 at 20 samples/dibit. Centered
boxcar shaping uses widths 8 and 14; its future support is 3 and 6 samples.
Each complete generated vector has 62,080 samples. The first nominal FSW starts
at sample 640 and successive boundaries are 3,840 samples apart.

For both shapes and each initial offset 0–19, run read chunks 1, 37 and 512:
120 fixed cases, each with observer disabled then enabled. Decode two sequential
sync-plus-payload observations per run through the actual getFrameSync,
getSymbol and getDibitSoft path. No matched filter, channel coding, voice codec,
encrypted traffic or original-IQ frontend is exercised. Frame selection uses
the measured consumed frontier and fixed generated boundaries, never a search
over payload alignments. Preserve complete payloads and successful-pop indices.

## Controls and gates

Direct cache controls cover a successful delivery, cleared/disabled observer,
empty/null input, nonzero cache position, a generation mismatch before delivery
and a generation change during delivery. Rejected deliveries must not notify.
These are mapping controls, not noise-only RF false-positive tests.

The correctness gate requires all 120 cases, two correct 182-dibit payloads per
run, exact observer-disabled/enabled parity, no lineage errors, increasing pop
indices in bounds, and agreement between pop records and cache accounting.
The independent validator reconstructs expected payloads and reconciles all
recorded frontiers. The separate invariance gate requires identical consumed
sync frontiers and payloads across all three chunk sizes in all 40 shape/offset
groups. Neither gate is a performance or RF-reliability claim.

Any failed case or gate remains in the evidence. Infrastructure/compiler fixes
may be made with the original failure preserved; do not alter the waveform,
oracle or gates in response to native results. Keep instrumentation in a private
test archive, behind an OFF-by-default research option; verify the normal DSP
archive does not export it. Run existing phase regression and independent
validator negative mutations. Production apps and release artifacts stay intact.

## Follow-up gates (not measured here)

Original-IQ lineage must survive filtering, rate changes, asynchronous buffers,
loop/reset boundaries and block-dependent operations before reporting original
sample acquisition. Protocol-valid frames need independently encoded test
vectors and explicit current-frame CRC/FEC evidence. Impaired I/Q, nonprotocol
negative controls, dropped frames and real hardware remain subsequent work.
