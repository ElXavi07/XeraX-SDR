# XeraX SDR 1.3.0: speaker and audio-output selection

The previous build let Android choose the media output and displayed its reported route. It had no control for choosing the internal speaker when Android selected an earbud, earpiece or another output. This release adds that control. The user's physical audio problem has not been reproduced here because neither phone is connected.

## Implemented

- **Phone speaker** is the initial preference, explicitly resolving Android's built-in loudspeaker device rather than the separate earpiece.
- **Radio → Audio output** and **Settings → Listening → Audio output** offer the same device selector and **Use phone speaker** button. Choices include **System default** and outputs currently exposed by Android.
- **Reported output** comes from the native audio stream, independently of the selection. A mismatch stays visible when Android grants a different route. Selecting an output again retries it.
- A route change is consumed on the existing audio writer's next buffer. The writer closes and reopens its stream; it does not restart the SDR receiver or close a stream concurrently from the UI thread. A brief audio gap is expected.
- The audio backend retains its sample-rate fallback, resampling, buffering and failure backoff. Route requests survive fallback attempts. Input streams are unaffected.
- Device callbacks remain registered in the application process while the foreground receiver service runs. Removing a selected external output requests the speaker. Stable speaker/default preferences persist; transient external device IDs are not restored after a process restart.
- Analog NFM and digital decoded audio use the same output preference. Media volume controls from 1.2 remain available.

## Android API research

Android's [AAudio guide](https://developer.android.com/ndk/guides/audio/aaudio/aaudio) directs apps to Java's audio APIs to enumerate devices. The router uses [AudioManager.getDevices](https://developer.android.com/reference/android/media/AudioManager#getDevices(int)) to enumerate output sinks.

The [AAudio API reference](https://developer.android.com/ndk/reference/group/audio) documents `AAudioStreamBuilder_setDeviceId` as a device request and `AAudioStream_getDeviceId` as the stream's actual device. A requested device may not be granted. The implementation therefore displays both the requested choice and reported output, preserves media usage, and avoids assuming that a successful selection means audible speaker playback.

## Validation and limits

The ARM64 Android release build, vital lint, signature verification, ZIP/dependency checks and 16 KB library/alignment checks passed. All twelve host check groups passed; the production-QML test executable reports 40 passed, zero failed. Audio backend tests compile the real C implementation against a fake Android API and cover initial selection, deferred reopening, explicit retries, default routing, actual/requested mismatch, sample-rate fallback, failed-open backoff and input-stream isolation. UI checks exercise selection and speaker actions, mismatches, errors and compact layouts.

These tests do not run Android's actual audio policy or Bluetooth stack. Speaker/headphone playback, device removal during playback, background routing, and simultaneous SDR USB reception still need physical testing on the Galaxy S25 and Pixel 9 Pro. A device being listed does not guarantee Android permits media routing to it. No changes to protocol coverage or unknown-key handling are included in this release.
