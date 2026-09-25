# First canonical NXDN48 synchronization experiment

This is an isolated acquisition candidate, not an application option or a
released decoder change. Read the [registered hypothesis and gates](../../docs/research/NXDN-FIRST-SYNC-PREREGISTRATION-2026-09-25.md).

The candidate allows one unconfirmed canonical positive NXDN48 sign match to
enter the existing real LICH/channel/CRC validator immediately. The baseline
waits for its existing second matching sync. All existing protection and
validation code remains in the path. Neither a sync match nor historical
confirmation is counted as a correctly decoded current frame.

Build separately with `cmake -S experiments/nxdn_first_sync -B <new build>` and
the normal dsd-neo dependencies/platform flags. Build these targets:

```text
xerax_nxdn_frame_observer
xerax_nxdn_first_sync_candidate
```

The first executable lives under the build's `frames` directory. The second is
at its root. Only `xerax_first_sync_candidate_dsp` receives the candidate macro;
the ordinary and baseline archives do not. Per-source SIMD options are copied
from the baseline target. The exact schema2 observer and independent input
generator/validator are reused unchanged.

Run a single preserved pair with:

```text
python experiments/nxdn_first_sync/run_pair.py <baseline exe> <candidate exe> <NEW evidence directory> --frozen-baseline-dir <previous schema2 evidence directory>
```

The frozen schema2 directory is included in the prior committed raw archive. The
CI workflow verifies its archive SHA-256 before extracting just that directory.
Its Windows source/binary paths remain historical provenance when read on Linux.

The paired runner freezes inputs, runs baseline before candidate once each,
stops on an invalid baseline, and preserves failed experiments. Inspect evidence
validity and `promotion_pass` separately. Exit success from the research workflow
does not approve an app release; it can report a valid negative experiment.

Reproduction checks run the old frame tests plus this directory's comparison and
runner tests, normally and under `python -O`. Linux CI builds release and
ASan/UBSan variants, preserves both executables and raw evidence, and checks
candidate-only symbol isolation. Source/binary hashes and link audit are not a
hermetic build proof.

The domain remains generated discriminator samples. No CPU throughput, original
IQ, noise/fading/interference, voice/audio, NXDN96, encryption or physical-device
claim follows. The harness still bypasses full dispatcher/profile feedback and
uses the documented counted and uncounted side-effect sinks. Even a positive
result needs held-out recovery/noise and application tests before integration.
