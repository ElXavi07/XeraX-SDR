# NXDN observation contract v2

This standalone research target changes observation only. The preceding
**216-invocation recovery study remains failed and frozen**.
This separately registered contract has 36 invocations, one unchanged decoder
policy, no hardware startup and disabled audio/file output.

The new recorder distinguishes completed, partial and empty per-dibit calls at
finite EOF. Private generated source records actual LICH decisions and final
SCCH CRC7 after fallback. Wrappers forward real voice, soft-vocoder and audio
staging calls once. Internal buffer statistics do not prove valid speech,
successful synthesis or playback. The detailed-off mode still has common
wrappers/counters but installs neither optional sample nor CRC callback.

See `docs/research/NXDN-OBSERVATION-V2-PREREGISTRATION-2026-09-25.md`. Nine fixed
waveforms run with chunks 37/512 and detailed observation off/on; fast acquisition
is off. Two synthetic SCCH controls have independently verified information and
checkwords but no independently established voice truth. Four exact prefixes
exercise partially delivered symbols and EOF without padding.

```
python -m unittest discover -s experiments/nxdn_observation_v2 -v
python -O -m unittest discover -s experiments/nxdn_observation_v2 -v
python experiments/nxdn_observation_v2/prepare.py <frozen-recovery-inputs> <new-input-directory>
cmake -S experiments/nxdn_observation_v2 -B <build> <receiver-dependency-options> -DDSD_AUDIO_BACKEND=none -DDSD_ENABLE_QT_UI=OFF -DDSD_ENABLE_TERMINAL_UI=OFF -DDSD_FORCE_RADIO_PIPELINE=ON
cmake --build <build> --target xerax_nxdn_observation_v2
python experiments/nxdn_observation_v2/run.py <build> <frozen-recovery-result-directory> <new-input-directory> <new-result-directory>
```

The checked runner targets the registered Windows executable. Other platforms
require a separately recorded build/validation and cannot inherit Windows native
results. All dependencies are the normal receiver dependencies; no substitute
protocol, reset, voice or audio stubs are linked. Inspect the link map and generated
source before executing the fixed matrix. The generator verifies pinned original
source bytes before inserting private hooks; installed product code is untouched.

Existing input/result directories are refused. Every native attempt, failure,
trace, source/build identity and legacy projection is retained. Old raw outcomes
are compared without re-executing the old engine. A successful observer contract
would establish measurement validity and neutrality within these cases only;
it is not improved recovery, an application release or a changed default.
