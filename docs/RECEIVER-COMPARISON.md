# Reproducible receiver comparison

There is no SDS100 or attached phone in this build session. Physical results are pending.

## Software evidence

Run `scripts/build_iq_lab.ps1` to build the same native decoder for host replay and run the bundled fixtures. Run `scripts/benchmark_reception.py build/iq-lab-clang/tests/dsd-neo_test_receiver_lab.exe build/checks/channel_capture.exe` for shared-channel parity and impaired simulcast comparisons. The reports include fixture hashes, source revision, impairment parameters, expected decoded evidence and P25 FEC counts. Preserve both successful and failed cases. A fixed random seed makes comparisons repeatable, not representative of every RF environment.

Run `scripts/generate_privacy_vectors.py` with PyCryptodome 3.23.0 available to regenerate the public synthetic AES/DES reference payloads. The actual production P25 routines are exercised by the `P25_AES_DES_SUPPLIED_KEY_REFERENCE_PAYLOADS` host test. This is separate from speech intelligibility and I/Q demodulation testing.

## Phone and antenna optimization

1. Start a known active fixed control channel. Choose the correct mode and check frequency correction, signal level and clipping. Use the existing gain trial tool for an initial setting; higher gain is not automatically better.
2. Open **Tools → Receiver lab → Reception**. Label the antenna, location and gain, then measure for 30 seconds. Export the report.
3. Change one factor, repeat at least five times per setup, and alternate A/B order. Keep mode, bandwidth and frequency fixed. Compare control-frame counts, rejection counts and valid SNR readings together.
4. A retune, stopped receiver or counter reset invalidates the timed measurement. Zero frames is insufficient digital evidence. The SNR average includes only valid readings. For analog reception, listen to repeated known speech as well.
5. Verify actual speaker output, USB stability and 30-minute background operation using PHONE-ACCEPTANCE.md. Record phone/Android version, dongle, antenna, hub, gain, PPM and temperature.

## Paired SDS100 procedure, when one is available

Use the same programmed frequencies, talkgroups, service types, holds and comparable squelch. Use a suitable splitter and shared antenna with appropriate attenuation, or swap antennas/positions between runs. Document splitter loss, receiver settings, firmware and paid protocol options. Different antennas cannot isolate decoder performance.

For each independently known transmission, record whether each receiver produced intelligible voice and whether it captured the opening word. Record both-missed events too when the reference establishes that a call occurred. Do not use encrypted calls with unavailable keys to score sensitivity. Separate analog, P25 C4FM, P25 simulcast, Phase 2, DMR and NXDN observations; do not combine them into an unsupported universal ranking.

Use `scripts/compare_receivers.py observations.csv --template` to create an empty form, then `scripts/compare_receivers.py observations.csv --output comparison.json` to summarize it. Enter only observed trials. The script checks paired 0/1 scores, IDs and consistency and explicitly reports pending for an empty sheet. A tally by itself is not a controlled statistical claim of superiority. Keep audio/reference evidence and the setup notes alongside it.
