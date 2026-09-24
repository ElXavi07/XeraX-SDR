# Physical-phone acceptance: S25 and Pixel 9 Pro

Run this separately on each phone with its Android version noted. No physical run is recorded yet. Use a known active channel and an appropriate antenna; a database entry alone is not proof of an active signal.

1. Install 4.3.0 over the old official APK. Confirm systems/lists survive. Allow USB and notification access. Record ARM64/ARMv7, receiver model and connection type.
2. Explore → Analog NFM. Select a known VHF/UHF two-way frequency, choose Phone speaker in the audio output picker, raise media volume and temporarily disable squelch. Confirm audible noise and intelligible received voice. Compare requested and actual output in diagnostics.
3. Attach wired/USB or Bluetooth audio, select it, then explicitly choose Phone speaker again. Disconnect the external output and verify the router reports its speaker fallback. Record any requested-versus-actual mismatch.
4. Let the app buffer audio. Save WAV while listening; replay 30 seconds without stopping reception. Verify voice and output route, continued scan/call updates and continued configured recordings. At clip completion, verify live audio resumes. Tap Replay twice rapidly and confirm the earlier clip is not corrupted. Export the clip for a separate WAV player. Clear the buffer and verify replay reports no audio.
5. Test a mixed NFM/P25/DMR/NXDN list with channels actually available locally. Check mode changes, audibility, activity hold, mute behavior, Next and Hold. Mark one priority; verify ordinary channels still rotate. Compare a finite visit limit with Finish active calls.
6. Test AM and WFM against known transmissions. WFM should be mono; neither mode should display an NFM tone identity. Move back to NFM and confirm the prior wideband setting did not leak into the new session.
7. Lock the phone for 30 minutes. Exercise expanded notification Hold/Next/Mute/Speaker/Stop. Note audio gaps, thermal status, battery change and whether Android suspends reception. Record any OEM-specific restrictions rather than claiming a universal fix.
8. Receive a phone call while listening, end it, and check audio-focus recovery. Disconnect/reconnect the SDR; confirm a clean error/stop and successful reopen, without stale USB permissions or a stuck service. Repeat while the screen is off.
9. Sign into RadioReference in the app. Fetch Riverside agencies/categories, open actual frequency rows, import NFM/digital and individual AM/WFM channels. Confirm source/mode, frequency and any displayed tone against the API page.
10. Save a backup and restore it on the other phone while stopped. Verify relocated labels, site names, entry priorities and tuning. Re-enter account credentials and any radio keys independently. Keep the original backup until the restored lists have been exercised.
11. Add an alert for a known talkgroup/radio ID and observe a real matching call. Check notification permission and the 30-second repeat limit. Remove the rule and confirm no new matching alerts.
12. Switch English/Español while listening. Visit all four Receiver tools tabs at normal and larger font sizes, edit the last filter field with the keyboard open, and check notification actions. Note any untranslated or clipped text.
13. Compare Quality counters on a known control channel, an analog channel and a silent frequency. Enable automatic gain only on a steady RTL channel; record the baseline/trial/result and verify rollback for a worse trial. Start a call during a trial, then change gain manually; automation must not overwrite the manual choice.
14. Enable automatic site selection with two imported sites from the same system. Verify a call or Hold prevents switching, a weak candidate returns to the original site, a failed source rolls back, and the cooldown prevents rapid oscillation. Disable selection and confirm no further trial is started.
15. Capture I/Q from a single-channel session and verify return after about 20 running seconds with the app open and after locking/recreating the activity. The Android service now owns the deadline. Export while stopped, extract the TAR, and verify both files and the 64 MB bound. Force-stop/reboot recovery is not promised.
16. Apply a known CTCSS or DCS filter to an NFM channel. Check matching voice, mismatched/no tone muting, inversion and at least three seconds of scan dwell. Test DMR color code, both slot choices and talkgroup filters with known traffic; clear each filter and verify unrestricted reception.
17. Enable the notebook, receive a known digital signal and a signal without recognized digital sync. Verify confirmed versus unconfirmed labels, timestamps, saved preset frequency and full JSON export.
18. Use controlled transmissions/recordings with supplied keys: P25 Phase 1 ADP, both P25 Phase 2 slots, and both DMR Enhanced Privacy slots. Assign automatic profiles, change the transmitted key ID, remove one matching saved entry, and compare intelligibility to a reference receiver. Verify no other slot or previous call's key is reused on a missing entry. A matched key ID alone is not a pass.
19. Test NXDN48 supplied scrambler values and automatic key IDs, plus NXDN96 destination mappings and direct supplied values. Include zero and 32767 when supported by the test source, a changed key, and a missing mapping. Confirm intelligible voice against known clear reference audio; do not infer success from sync or a key-available label.

20. Run the bundled I/Q lab on each phone, stopped and during main reception. Export results. Verify baseline expectations, cancellation, timeout, nonzero voice PCM and no stale evidence between cases.
21. Start two nearby known channels in a fixed RTL capture at 48 kHz base bandwidth. Confirm independent audio/IDs/recordings, speaker selection, out-of-band errors and explicit failure when the main tuner moves. Monitor heat and dropped data.
22. Connect two different RTL dongles through a powered hub and arm P25 voice. Verify the main stays on control while voice follows Phase 1 and both Phase 2 slots with correct WACN/SYSID/NAC. Measure missed call openings. Unplug voice: dual mode must disarm and restore main audio.
23. Compare a real simulcast capture with forced CQPSK and identical offsets/filters, changing only the equalizer. Record FEC outcomes and intelligible speech against a reference. Do not attribute a demodulator change to the equalizer.
24. Feed known MDC, FleetSync, DTMF and ordered two-tone NFM audio. Compare IDs with a reference; test successive bursts, corrupt CRCs, noise and reversed tones.
25. Record overlapping digital calls on workers and an analog transmission. Check finalized WAV duration, metadata, favorites/expiry protection, playback focus/route and WAV+JSON export through an Android document-provider folder. Test duplicate filenames and cancellation.
26. Test Indio/current-location radius filtering with known coordinates, denied permission and stale/inaccurate fixes. Check 30-second rotation, call/hold protection and no rotation with extra workers. Survey a short band; stop/background the app and confirm frequency restoration.
27. Test opt-in USB recovery with the same serial, another dongle, missing permission and a disconnect exceeding one minute. Verify worker foreground notifications disappear after completion, focus loss mutes live outputs and severe heat stops extra processing.

Capture exact version, frequency, receive mode, source, requested/actual audio route, signal/sync state and exported diagnostics for a failure. Do not mark a row passed based only on a build or desktop screenshot.

## Additional 4.3 acceptance

- Scan a narrow known band first, then 440–450 or 440–460 MHz as appropriate for your location. Log actual cycle/acquisition times with USB and RTL-TCP; synthetic timing is not a measured hardware speed.
- Exercise Hold/Resume, Skip, Avoid/Clear avoids, Save frequency and Stop. Confirm saved channels match the selected discovery even as new findings arrive.
- Check NFM/AM carrier gating and digital sync without voice, active voice, tail/resume and maximum visits. Ensure scan suppression never unmutes a user-muted player.
- Change between analog/digital modes through the UI, test receiver disconnection and a stalled network, and verify clear errors and recovery without stale audio.
- Switch away from the scanner page, lock the phone, and record whether scanning/audio continue. Force-stop is not an automatic-recovery acceptance case.
- Optional AI: with your own key, fetch models and run compatibility/investigation tests for each provider. Confirm cancellation, request limits and secure key persistence on the device. Do not attach keys to a report.
- Test V4, HackRF and ARMv7 separately rather than inferring their behavior from a V3/ARM64 result. Record power/thermal conditions for multi-channel reception.

## Additional 4.1 acceptance

- Run the new RAS and strict-rejection I/Q cases, then compare the dedicated main DMR RAS switch on a known RAS source. Check that P25/M17 behavior is unchanged. Compare displayed burst counters to the exported evidence; a suspected RAS counter is not proof of valid voice.
- Repeat supplied-key tests with P25 AES-128, AES-256 and DES, including both Phase 2 slots, changed message indicators, missing mappings and wrong keys. Compare with known reference speech.
- During two-dongle operation, verify that grant changes do not reopen USB or restart the voice service. Alternate Phase 1 and both Phase 2 slots; ensure the unselected TDMA slot is inaudible. Record acknowledgment latency and first-word capture separately. Simulate a failed tune/disconnect and confirm dual mode disarms.
- Check the shared-receiver rate display: a 1.536 MS/s main capture should feed each worker at 192 kS/s. Verify nearby channels, boundary rejection, recordings, queue/drop reports and heat with two workers for 30 minutes.
- On Reception, label antenna/gain A, measure 30 seconds, change one setting and repeat as B. Export JSON. Verify that stopping or retuning during a sample marks it invalid, then repeat in Spanish with large text and the keyboard open.
- If an SDS100 becomes available, use RECEIVER-COMPARISON.md. Until paired observations exist, leave this comparison pending.
