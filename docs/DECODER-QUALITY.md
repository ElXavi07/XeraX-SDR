# Decoder quality, supplied keys and GPU research

Windows preview 3, September 24, 2026. This is an engineering assessment of
XeraX's pinned DSD-neo engine, not a ranking against every receiver.

## What changed

- Fixed the Windows queued-audio drain using a device handle as if it were the
  enclosing stream. It now uses the same output gate, accounting and device-error
  handling as ordinary playback. A deterministic device-boundary regression
  failed before the fix and passed after it.
- Fixed digital automatic gain repeatedly measuring the first 20 samples of a
  160-sample frame. It now follows each current sub-block independently for both
  slots. A late speech-onset regression failed before the fix and passed after it.
- Saturated loud PCM16 analog samples before conversion, avoiding polarity
  wraparound when manual gain exceeds the available headroom.
- Added actual CPU acceleration and Windows graphics-adapter reporting under
  **Tools → Receiver tools → Quality**, in English and Spanish. Graphics inventory
  is taken at startup; restart after connecting an external adapter.

These changes do not restore information lost to interference, a weak signal,
incorrect channel settings, missing encryption material or unsupported formats.

## Supplied-key evidence

| Path | Current software evidence |
| --- | --- |
| P25 Phase 1/2 ADP/ARC4 | Independent reference payloads, both TDMA slots, wrong-key negatives |
| P25 Phase 1/2 DES, AES-128 and AES-256 | Independent reference payloads, two message indicators, successive frames, wrong/missing material and slot isolation |
| DMR ADP/ARC4 | Independent payload reference, both slots, wrong-key negative |
| DMR DES, AES-128 and AES-256 | Independent OFB payload references with established IVs, successive frames and both slots |
| NXDN 15-bit scrambler | Native payload reference, wrong-key negative, received-ID/destination selection, supplied zero, stale-key clearing |
| NXDN DES and AES-256 | Independent PyCryptodome references, two established IVs per cipher, all 32 contiguous voice frames per period, wrong-key negatives |

The new DMR/NXDN OFB tests exercise production payload transformations. They do
not test over-the-air IV acquisition, vocoder intelligibility, every vendor
variant, or RF/phone reception. The fixture keys and voice bits are public
synthetic data. The generators are checked in; ordinary builds need no Python
crypto package. Other inherited vendor modes remain documented in the
[profile reference](../upstream/dsd-neo/docs/decryption-profiles.md); this release
does not certify all of them.

Profiles retain supplied material and can be assigned to saved systems or scan
targets. Received identifiers select entries; they are not proof of a correct
key. Selection must be reevaluated on a changed call, algorithm or key context.
Keeping the old key across an unrelated call would reduce correctness. Clear
audio can help a human assess a supplied key but is not cryptographic
authentication. The existing experimental NXDN candidate feature remains
experimental; it is not relabeled as verified or saved as an authenticated key.

There is no universal unknown-key recovery for DMR, NXDN or P25. RAS handling is
also distinct from voice encryption; relaxing validation indiscriminately can
admit incorrect signaling.

## CPU measurements and GPU decision

Measured on this Windows computer: Intel Core i5-1038NG7 (4 cores / 8 logical
threads), Intel Iris Plus Graphics, production Release compiler settings, active
AVX2 FIR implementation. Each synthetic case used 3,000 iterations and five
repeats. No before/after speedup is claimed: the DSP algorithms were unchanged.

| Demodulation benchmark | Median time for 512 symbols |
| --- | ---: |
| FSK, 24 kHz, channel filter enabled | 0.0450 ms |
| C4FM monitor, 24 kHz, channel filter enabled | 0.0651 ms |
| CQPSK, P25 Phase 1 | 0.2292 ms |
| CQPSK, P25 Phase 2 | 0.4103 ms |

The separate P25 rate-1/2 trellis benchmark took 28.6–33.7 microseconds per
49-symbol decode across its three synthetic cases. These are isolated stage
measurements, not complete receiver latency, RF sensitivity, scan speed or a
count of simultaneous channels supported by the app. They show substantial
headroom in these stages on this machine; they do not identify a GPU bottleneck.

CPU SIMD dispatch already chooses AVX2/FMA, SSE2 or a scalar fallback on Windows
according to CPU and OS support. The shared ARM64 path includes NEON. Do not ship
a universal binary compiled solely for the developer's CPU.

**GPU radio decoding is not implemented in this release.** Detecting integrated,
discrete or external graphics does not offload the DSP. Cloud AI requests also
do not accelerate frame decoding or validate cryptographic keys.

NVIDIA's guidance calls for profiling realistic workloads, exposing sufficient
parallel work and counting transfers and launch overhead. Based on that guidance
and the local measurements, a future GPU prototype should target batched FFTs or
many-channel filtering first, with a CPU fallback. It must demonstrate a measured
end-to-end improvement and numerical agreement before being offered as a faster
decoder. GPU hardware cannot supply a missing AES key.

## Primary references

- [NVIDIA CUDA Best Practices: profiling, parallel work and transfer costs](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html).
- [DSD-neo decryption profiles](https://github.com/arancormonk/dsd-neo/blob/main/docs/decryption-profiles.md): supplied material, profile scopes, vendor modes and the distinction between availability and verified decryption.
- [DSD-neo DSP benchmarking](../upstream/dsd-neo/docs/dsp-benchmarking.md): benchmark workload definitions and interpretation.
- [DSD-FME release history](https://github.com/lwvmobile/dsd-fme/releases): ongoing FEC and protocol work; its change list is not evidence that swapping engines automatically improves XeraX.

Physical SDR testing, independent computers, real known-key radio recordings,
weak-signal comparisons and human listening remain necessary before broader
reception or clarity claims.
