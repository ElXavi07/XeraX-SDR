# XeraX SDR privacy information

Updated September 23, 2026. This describes the independent XeraX SDR Android derivative,
package `com.xerax.sdr`, version 4.2.0. It does not describe the separately distributed
upstream DSD-neo application.

## Local radio processing

Radio demodulation, decoding and playback run on the phone. Recordings, receiver settings
and diagnostic logs are stored locally. Android app backup is disabled. Uninstalling the
app removes its private data; recordings exported to shared storage remain there.

## Connections selected by the user

- RTL-TCP receives radio samples from the configured receiver server.
- RadioReference requests database information using the configured account and application key.
- Configured rigctl, UDP output and rdio-scanner integrations communicate with the selected servers;
  audio export integrations can transmit decoded audio when enabled.
- Optional OpenAI or DeepSeek AI sends the user's typed question, frequency and a limited set of
  numeric receiver measurements and experiment results directly to the selected provider. Model
  listing and compatibility checks also contact that provider. These requests use the user's
  personal API key and may incur charges. Providers apply their own account and retention policies.

AI is off by default. Enabling it alone does not start an investigation; the user explicitly
connects, checks a model or starts a run. The AI feature does not upload audio, I/Q recordings,
radio decryption keys, GPS coordinates, RadioReference credentials, imported labels or file paths.
Local capture experiments send their numeric results. Typed questions are transmitted as entered.
AI conversations are held in process memory and can be cleared in the AI screen. No XeraX AI
backend, advertising or analytics service is used by this feature.

## Personal API keys

The APK contains no shared OpenAI or DeepSeek credential. Keys entered by users are encrypted
separately per provider using Android Keystore AES-GCM and stored in the app's non-backup directory.
They are sent as HTTPS authorization credentials only to that provider's fixed API origin.
Redirects are refused. Keys are not included in diagnostics or portable app backups. Users can
remove each provider's saved key in the AI screen. Secure storage failure is reported, with
session-only use as a fallback. A compromised device may expose credentials while in use.

## Permissions

Internet supports the configured network services. USB host access connects compatible SDR
hardware. Foreground service/notification and wake-lock permissions support ongoing reception.
Approximate foreground location is used when the user requests nearby-site selection;
the AI diagnostics do not include those coordinates.

For questions about this derivative, contact the distributor who supplied XeraX SDR. Upstream
DSD-neo's maintainers do not operate this app's optional AI integration.
