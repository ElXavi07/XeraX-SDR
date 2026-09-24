# XeraX SDR 1.2.0: analog listening and fine tuning

The reported silent channel was VHF/UHF narrow FM. The previous picker exposed digital modes only, although the pinned engine already implements analog FM monitoring. Digital auto detection does not turn analog transmissions into speaker audio. That is a source-level explanation consistent with the report; the phone and RF signal were not available to confirm the complete cause.

## Implemented

- **Analog FM (NFM)** in Explore setup and the saved-system mode catalog; **NFM** in the live Radio panel. Explore remembers its analog/digital choice.
- Switching between analog and digital from Radio uses a stop, confirmed Idle, and new start at the current frequency. This initializes the front-end output kind, de-emphasis and audio stream together. The existing live decode-preset command alone does not do all three. Mode changes are unavailable while a scan/trunk controller owns tuning; use Explore or edit the saved source.
- Android hardware volume keys select the media stream. The Radio panel displays the existing audio-route readout, and the reception check explains analog audio without demanding digital frame sync.
- Spectrum **Fine** mode previews frequency while swiping and sends one tuning command on release. A full-width drag spans no more than 24 selected channel steps. Drag left to increase frequency and right to decrease it. Steps are relative to the starting frequency, preserving its offset.
- Tap the step button to cycle **6.25 / 12.5 / 25 kHz**. The adjacent minus/plus buttons move one step. Tap a spectrum peak to snap nearby, pinch to zoom, or change **Fine** to **Pan** to move the displayed window without retuning.
- Canceled gestures, pinch zoom and a controller taking ownership do not issue a fine-swipe tune. A refused request returns to the receiver readout; an unconfirmed swipe preview expires after two seconds.
- The mode catalog now exposes dPMR, X2-TDMA, ProVoice, EDACS variants and alternate single-slot DMR. dPMR privacy-profile detection now correctly recognizes `-fm`; `-fp` is ProVoice. [Full protocol coverage](PROTOCOLS.md).

## Source findings and research

The pinned engine's [decode presets](https://github.com/arancormonk/dsd-neo/blob/8c9c120389401fc2db3ef52869e13d555712e5fb/src/runtime/decode_mode.c), [radio demodulator configuration](https://github.com/arancormonk/dsd-neo/blob/8c9c120389401fc2db3ef52869e13d555712e5fb/src/io/radio/rtl_demod_config.cpp), [audio stream opening](https://github.com/arancormonk/dsd-neo/blob/8c9c120389401fc2db3ef52869e13d555712e5fb/src/core/audio/dsd_audio.c), and [live profile publisher](https://github.com/arancormonk/dsd-neo/blob/8c9c120389401fc2db3ef52869e13d555712e5fb/src/app_control/symbol_profile.c) were inspected locally. Analog requires the audio-monitor output path; a digital demodulator may instead produce discriminator or symbol output. Restarting avoids assuming those pipelines can be interchanged by changing frame flags alone.

Android documents separate volume streams and recommends matching hardware volume controls to media playback. The activity now selects `STREAM_MUSIC`; it does not force a device-wide volume level. See [Android audio output guidance](https://developer.android.com/media/platform/output).

The spectrum tests use the production QML and C++ spectrum model, with a generated RF frame and a command recorder at the hardware boundary. Pointer and two-finger events exercise the real handlers. Qt documents [DragHandler cancellation and grabs](https://doc.qt.io/qt-6/qml-qtquick-draghandler.html) and [Qt Quick Test input synthesis](https://doc.qt.io/qt-6/qml-qttest-testcase.html).

## Limits

This release exposes the existing narrow FM monitoring path. It does not add AM, broadcast stereo FM, CTCSS/DCS decoding, automatic analog/digital classification, or unknown-key recovery. The digital spectrum sweep still stops on digital frame sync and is unavailable in analog mode; analog reception uses manual tuning and peak selection. This is separate from the existing digital channel/system scanner.

All device audio, USB reception, RF sensitivity, adjacent-channel performance, analog/digital restart behavior on Android, and background routing still require physical testing. No phone was attached. The screenshots in this folder are desktop renders using synthetic receiver data, not RF reception evidence.
