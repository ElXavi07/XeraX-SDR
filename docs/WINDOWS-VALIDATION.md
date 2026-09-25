# Windows preview validation — 4.3.0-windows.2

Software validation on Windows x64. The release verification JSON records the
exact application hash and source commit.

| Check | Result |
|---|---|
| Shared host suite, including protocol fixtures, scanner policy, AI and QML | 34 groups passed |
| Actual desktop application with a clean runtime path | 28 checks passed |
| Navigation | Home, receiver setup, direct range setup, Scan, Calls, Tools, receiver lab and AI entry checked |
| Mouse/keyboard and modal isolation | Desktop sidebar tests passed |
| Layout | English, Spanish, light/dark and compact views rendered and reviewed |
| Translations | 957 catalog placeholder checks passed |
| Native audio | Synthetic NFM, AM and WFM I/Q produced PCM and reached the real PortAudio output |
| Scanner output gate | Audio paused while decoding continued, then resumed |
| WAV replay / test tones | Playback lifecycle and exclusion of diagnostic tones from radio counters passed |
| RTL-TCP failures | Refused, invalid-header and stalled-header sessions reported failures |
| AI protocol | OpenAI Responses and DeepSeek Chat Completions tested with deterministic fixtures |
| AI safety and accuracy boundaries | Tool allowlists, capture scope, gain rollback, request limits, stale responses, cancellation and the corrected analog mode mapping tested |
| Windows AI transport | HTTPS endpoints, redirect refusal, response limit, cancellation, partial failure and DPAPI encrypted key storage tested |
| Provider reachability | Both official providers rejected deliberately invalid fixture keys over verified HTTPS; no paid model call made |
| Packaging | Installer payload under a separate validation identity, portable package and native Windows startup verified against staged file hashes |
| Windows icon | Multi-resolution icon embedded in the app and installer; window icon present |

The 28 application cases exercise the real host, decoder and PortAudio backend.
Synthetic I/Q is input to the production RTL-TCP path. Device-accepted output is
not a human listening or intelligibility test. The screenshot gallery contains
actual application renders with a separate test profile and no invented traffic.

The initial Windows preview also passed 31 selected I/Q/atomic-tuning tests,
analog tone-fidelity tests and additional bounded TCP failure tests. Those
historical results remain with [preview 1](https://github.com/ElXavi07/XeraX-SDR/releases/tag/v4.3.0-windows.1);
they are not counted as new preview 2 test executions.

Physical SDR/antenna acceptance, weak-signal performance, field scan speed,
independent community computers and a paid AI investigation with a user's key
remain unverified. AI can be wrong and does not speed up the DSP decoder. The
feature limits in [WINDOWS.md](WINDOWS.md) still apply; no zero-bug guarantee is
made.

To repeat application checks, run `scripts/check_windows.py` against the staged
or installed EXE. Build `checks` and run CTest for the host suite. The additional
`ai_windows_transport --live-tls` check uses invalid test credentials solely to
verify HTTPS reachability and rejection, without a real account.

The explicit `--smoke-seconds` developer mode uses separate test settings and
bounded exit. Ordinary launches do not start a source, tones or AI requests.

[Screenshot gallery](WINDOWS-SCREENSHOTS.md) · [Windows setup](WINDOWS.md)
