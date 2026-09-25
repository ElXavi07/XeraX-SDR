# XeraX SDR 4.2.0 — optional AI receiver investigations

This release adds user-configured OpenAI and DeepSeek connections. Radio acquisition,
demodulation, decoding, playback and the available receiver experiments run on the phone.
The selected provider runs the language model remotely; an API key does not download a
model to the phone. No computer or XeraX backend is required. AI is off by default and
radio reception continues with AI disabled, disconnected or out of quota.

## Setup

Open **Tools → AI receiver · OpenAI / DeepSeek** (also available through Receiver tools).
Enable optional AI, choose a provider, enter that provider's personal API key, and tap
**Connect and load models**. This calls the provider's authenticated model-list endpoint.
Select a returned model and tap **Check model (uses API)**. The check asks for a harmless
function call; listing a model does not prove it supports receiver tools or has usable quota.
Each provider retains its own key and selected model. Switching providers or models cancels
the current run, clears its conversation, and requires a fresh compatibility check.
Model lists are refreshed explicitly after reopening the app; a new key loads its list immediately.

On **Investigate**, describe the reception problem in English or Spanish and start a run.
The UI explains what text is sent. Receiver experiments are separately enabled for that run.
Choose a saved capture if you want it compared. The capture indexes follow Receiver tools → Clips.

## Real tools in this version

* Current numeric receiver diagnostics and recent measurement/comparison results.
* A 30-second fixed-channel reception measurement, without changing settings.
* A bounded local gain comparison using the existing receiver assistant. Active calls,
  scanner/trunking ownership, other workers, thermal limits, unsupported hardware and
  insufficient frame/SNR evidence can prevent it. Worse or inconclusive trial settings
  restore the original gain. At most two measurement/experiment actions run per investigation.
* Reprocessing the explicitly selected local native I/Q recording with P25 Phase 1/2,
  DMR, NXDN48/96, NFM or AM settings. The existing lab compares frequency offsets and
  filters; P25 additionally compares C4FM/CQPSK and the experimental equalizer. Samples stay local.

Provider function calls pass an application allowlist, strict argument validation and
runtime receiver checks. No arbitrary code, file reads, network tools, retuning, key access
or model-defined commands are exposed. Experiments carry ownership identifiers so stopping
an AI run cannot cancel a newer manual experiment. Backgrounding the app cancels the AI run.
Cancellation stops its local tools and network connection; a provider may already have processed
an in-flight billable request.

The AI gets sanitized numeric evidence. Imported labels, file paths, raw worker logs, radio
keys, RadioReference credentials, GPS, audio and I/Q data are not included. Questions typed by
the user are transmitted as entered. Answers are rendered as plain text and remain in process
memory until cleared or the app closes. AI conclusions still need comparison with measurements.

## Limits and scope

This is a language-model controller for implemented DSP tools. It does not add a trained RF
classifier, neural demodulator, universal decoder or encryption-key finder. Frequency-range
scanning was subsequently implemented separately in [4.3.0](RANGE-SCANNER-4.3.0.md) and does
not require AI. Existing receiver/decoder functionality remains available.

Control-frame metrics primarily cover P25; absent counters cannot establish DMR/NXDN voice
quality. Lab reports are exploratory comparisons, not guaranteed speech recovery. Null-output
replays may have no player PCM. Sequential live gain measurements can also be affected by a
changing RF channel, so a higher score does not establish a laboratory sensitivity gain.

Investigations use up to five provider requests with 4,096 output-token limits per request;
model checks allow 2,048 output tokens.
The default daily request limit is 25 per phone, adjustable from 1 to 200. Model checks count;
model listing does not. There are no automatic retries or periodic paid monitoring. Reported
token usage excludes responses the app could not receive or parse. Request limits are not dollar
budgets and cannot cover usage outside this app; check provider billing separately.

All discovered model IDs are shown without assuming capabilities from names. Unsupported models,
invalid/restricted keys, quota limits, redirects, incomplete responses and timeouts have explicit
errors. OpenAI uses stateless Responses requests with store:false and reasoning items carried
forward where supplied. DeepSeek uses Chat Completions with default model reasoning for investigations
and thinking disabled for the forced compatibility check; returned assistant/reasoning/tool messages
are preserved. HTTP redirects are refused, endpoints are fixed HTTPS provider
origins, and Android's TLS/certificate validation is used.

## Keys and privacy

Users supply their own provider keys. There is no developer AI key in the APK. On Android,
keys are stored separately per provider using AES-256-GCM and an Android Keystore key;
ciphertext is under noBackupFilesDir. App backups do not contain them. The key field is
masked and cleared after submission, and keys are not placed in QSettings or diagnostics.
If secure storage fails, the key remains session-only and the app reports that failure.
This is a direct personal-key mobile client: a compromised/rooted device can still expose
a key in use. Provider retention and account policies apply to transmitted requests.

## Verification

Offline C++ tests exercise both provider formats and the actual controller: dynamic model
discovery, tool compatibility, independent credentials, privacy allowlists, measurement results,
gain completion/cancellation, capture selection boundaries, stale replies, malformed responses,
authentication/rate-limit errors and request limits. QML tests check disabled defaults, masked
input, English/Spanish controls and 320-pixel layouts with 130% text. The full existing host
regression suite is included in verification. Android builds compile the actual JNI transport,
TLS client and Keystore code for ARM64 and ARMv7.

No live provider key was supplied for this release's testing. Account-specific model access,
live end-to-end provider calls, physical-phone Keystore persistence, battery/thermal behavior
and reception improvements remain phone acceptance tests, not verified release claims.

## Protocol references

* [OpenAI model listing](https://developers.openai.com/api/reference/resources/models/methods/list)
* [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)
* [DeepSeek model listing](https://api-docs.deepseek.com/api/list-models/)
* [DeepSeek tool calls](https://api-docs.deepseek.com/guides/tool_calls/)
* [DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)
