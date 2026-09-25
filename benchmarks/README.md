# XeraX reproducible receiver experiments

This is the first milestone of the [engineering roadmap](../docs/research/ENGINEERING-ROADMAP.md). Python 3.11+ and the standard library are sufficient. Receiver binaries are optional, explicitly configured dependencies. The framework never downloads/runs a receiver automatically, opens a live SDR, or loads personal decoder settings.

## Quick start

Run from the repository root. Output directories must be new; use a different suffix for each experiment.

```text
python -m unittest discover -s benchmarks/tests -v
python benchmarks/bench.py generate --out build/bench-corpus --scenarios clean awgn20 awgn10 awgn0 offset echo clock dropout adjacent cochannel traffic
python benchmarks/bench.py validate build/bench-corpus/manifest.json
```

The full selection generates 76 cases: six protocol fixtures times eleven conditions, plus ten synthetic negative cases. Source bytes and metadata must match the existing fixture manifest. Generation records hashes, transformations, seeds, clipping counts and provenance, and emits native CU8 replay metadata plus SigMF metadata. Keep original recordings untouched.

Copy [xerax.example.json](adapters/xerax.example.json) to an ignored local file, fill in the real executable path and exact build identity, and give every variant a unique name. A missing executable produces `unavailable`; it does not pass or receive a zero time. `xerax-lab` is the native `dsd-neo_test_receiver_lab` runner with the documented baseline/equalizer prefix. `xerax-cli` requires a compatible DSD-neo CLI. These adapters are not the graphical Windows EXE.

```text
python benchmarks/bench.py run build/bench-corpus/manifest.json --profile build/baseline.json --out build/baseline-run --repeats 3 --warmups 1
python benchmarks/bench.py run build/bench-corpus/manifest.json --profile build/baseline.json --profile build/candidate.json --out build/paired-run --repeats 5 --warmups 1 --measure speed
python benchmarks/bench.py compare build/paired-run/report.json --baseline baseline --candidate candidate --out build/paired-comparison.json
```

`diagnostics` writes decoder output, engine events, vocoder frames and WAV audio where the adapter supports them. `speed` omits that added instrumentation; it still includes ordinary application logging and process startup/shutdown. Times are **whole-process replay times**, not time to sync or first speech. Variants rotate execution order, warmups are excluded, and reports include median/p95 observations. Small samples do not justify precise tail-latency claims. Run timed comparisons sequentially on an otherwise quiet machine; pin power settings and document background work for formal results.

The exit code is 1 for a missing/unsupported/failed process or failed required assertion. Exploratory impairment misses remain visible but do not fail the required clean/negative gates. Exit code 0 is not proof of intelligible audio, correct payload bits, sensitivity or hardware support. A paired report never automatically promotes a candidate based on field recognition and elapsed time.

## Independent reference applications

The current reference adapter is DSD-FME using a legitimately obtained, identified executable and [dsd-fme.example.json](adapters/dsd-fme.example.json). It accepts 48 kHz mono PCM16 discriminator WAV files, not raw CU8 I/Q.

```text
python benchmarks/bench.py discriminator build/bench-corpus/manifest.json --out build/discriminator-corpus
python benchmarks/bench.py run build/discriminator-corpus/manifest.json --profile build/baseline.json --profile build/dsd-fme.json --out build/reference-run --only '.*-clean$' --repeats 3
```

Both programs receive the identical converted WAV bytes. This comparison excludes their RF front ends. First require each application's clean-input qualification for each protocol; an unqualified adapter/input combination is a diagnostic finding, not evidence that one program is the better decoder. In the initial experiments, NXDN qualification was incomplete. CQPSK/P25 Phase 2 are intentionally excluded from this discriminator conversion comparison. OP25, SDRTrunk, SDRangel and SDR++ integration remain listed as pending in [coverage.json](coverage.json).

## Captures, interference, load and inspection

Register an actual CU8 capture plus DSD-neo sidecar. Use `--expected` once per known field pattern, or omit it to keep truth unknown. Supply an actual hardware declaration using [hardware.example.json](hardware.example.json); this declaration is not hardware certification. Keep personal recordings and receiver/antenna details in ignored local folders unless publication is authorized and licensed.

```text
python benchmarks/bench.py register build/my-capture.iq.json --out build/imported --protocol dmr --kind off_air_iq --description "Cabled lab test, transmitter settings recorded separately" --hardware build/hardware.json
python benchmarks/bench.py mix build/bench-corpus/manifest.json --left nxdn48-clean --right dmr_voice-clean --offset-hz 12500 --sir-db 0 --out build/mixed
python benchmarks/bench.py stress build/bench-corpus/manifest.json --profile build/baseline.json --out build/load --workers 4 --iterations 2 --only '.*-clean$'
python benchmarks/bench.py inspect build/baseline-run/nxdn48-clean--baseline--0/frames.log --out build/frames.jsonl
```

Mixing places two identified recordings into one input, preserves component hashes and scores the wanted channel only. It does not prove simultaneous decoding. Load testing runs independent receiver processes; it does not measure a shared channelizer, live device bandwidth, long-term thermal limits or bounded streaming queues. The inspector currently understands native AMBE/IMBE vocoder-frame records; full protocol packet parsing is a future milestone. Timestamps in text logs are not converted into fabricated sample positions.

## Evidence limits

- Existing P25 Phase 1 and NXDN fixtures derive from off-air I/Q. Existing DMR voice and P25 Phase 2 control fixtures were reconstructed from discriminator audio. The latter cannot establish original RF sensitivity. Review `upstream/dsd-neo/THIRD_PARTY.md`; some source material has no explicit content license. This work adds no new recordings to the repository.
- Clean means the unmodified source fixture, not noise-free RF. Added-noise levels reference total original sample power, including existing noise. Clipping, quantization and linear clock resampling are declared transformations, not a calibrated RF channel model.
- Synthetic noise and random 4FSK are **negative cases**, not valid generated DMR/NXDN/P25 waveforms. Known-bit, valid protocol transmitters remain pending.
- Repetition is workload, not realistic new calls, grants or a statistically independent dataset. Split future data by radio/site/session before adding impairments; never use sibling transformations as independent training/holdout samples.
- Known-field regexes, engine FEC counters and vocoder payload hashes are useful regression evidence. They are not BER, independent frame truth, key authentication or speech-intelligibility scores. Missing metrics remain null.
- The child environment removes `DSD_*` settings and native runs disable configuration loading. No candidate-key search arguments are added. Runtime dependencies/firmware, power state and compiler/build identity must accompany formal results.

The GitHub workflow runs framework tests and corpus generation/validation on Windows/Linux and Python 3.11/3.13. It does **not** claim to build every reference receiver or exercise physical hardware. See [initial observations](../docs/research/INITIAL-RESULTS.md) for what was actually run.
