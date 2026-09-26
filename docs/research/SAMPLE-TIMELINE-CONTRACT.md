# Proposed source-sample timeline contract

**Status:** benchmark-only foundation implemented in [`timeline.py`](../../benchmarks/xerax_bench/timeline.py). It validates supplied event records and calculates bounded source-domain delays. No receiver emits this contract yet. It is not connected to the benchmark runner or the APK/EXE, and no new acquisition-speed result is claimed.

## What the measurement means

An event carries an inclusive interval `[lo, hi]` in **absolute original source complex samples**. This bounds the source position at which that event became causally available to its receiver stage. One complex sample is one I/Q pair, not one byte, scalar float, symbol, demodulated audio sample or PCM sample. Positions do not reset at an epoch boundary within the same source capture. A stream has one capture hash throughout its lifetime. Start a distinct stream when changing captures or replaying a capture from its beginning. The interval must describe event availability, not merely the input window containing the decoded payload.

An independently annotated signal onset has interval `[a, b]`; a compatible stage event has interval `[c, d]`. When `c >= b`, the supported source-delay interval is `[c-b, d-a]` samples, or those endpoints divided by the declared source sample rate. For example, onset `[100,104]` and sync `[340,350]` at 48 kHz yield `[236,250]` samples. Uncertainty is preserved instead of silently choosing a midpoint. Overlapping onset/event intervals cannot establish causal order and remain unavailable. Equal exact sample positions can legitimately yield zero *source-domain* delay.

This is not wall-clock processing latency or user-perceived audio delay. Queuing and computation can take time without advancing the consumed source position. Measuring those delays requires a separate monotonic-clock contract with independently specified origins and queue stages. Never use a text-log timestamp, emitted-demodulation count, read-ahead counter or process elapsed time as a substitute for source-sample lineage.

## Event schema 1

Every record contains exactly these common fields; unexpected fields are rejected:

| Field | Contract |
| --- | --- |
| `schema` | Integer `1` |
| `event_id` | Unique bounded identifier within the submitted timeline |
| `kind` | `signal_onset`, `sync`, `valid_frame`, `pcm` or `discontinuity` |
| `stream_id` | Distinct source-stream identity; never share it across simultaneous receiver inputs, captures or replay restarts |
| `epoch` | Nonnegative generation; increase after a discontinuity, retune or source-rate change |
| `signal_id` | Independently associated burst/call identity; null only for discontinuity |
| `producer` | Identity of the event producer; annotation and receiver producers must differ |
| `sequence` | Nonnegative event sequence, beginning at zero per `(stream_id, producer)` and continuing across epochs |
| `dropped_before` | Producer-reported number of lost event records since its previous recorded sequence |
| `source_sha256` | Lowercase SHA-256 of the source capture; fixed per stream, and verified against the actual capture separately by adapters |
| `sample_rate_hz` | Integer original complex-sample rate, not a downstream resampler rate |
| `sample_domain` | Literal `source_complex_samples` |
| `source_samples` | Inclusive two-integer source interval, or null when mapping is unavailable |
| `provenance` | Exactly `kind` and nonempty `reference`, as described below |

`signal_onset` additionally requires `purpose` (`acquisition` or `recovery`) and `recovery_from` (null for acquisition, the discontinuity event ID for recovery). `discontinuity` additionally requires a nonempty `reason`. These identifiers contain letters, digits and the separators `_ . : -`; the first character must be alphanumeric.

Provenance for onset must be `{"kind":"independent_annotation","reference":"..."}`. It should identify a separate transmitter/test-vector marker or reviewed recording annotation. Receiver events use `receiver_mapping`, identifying the actual source-position mapping and its error bound. The reader checks declarations and compatibility; it cannot prove that an asserted annotation is independent or that a mapping derivation is correct. Those are producer/experiment responsibilities.

If source lineage is absent, provide `{"kind":"unavailable","reference":"reason"}` and `source_samples: null`. An unavailable mapping carrying a numeric position is rejected. Missing provenance, estimated positions falsely labelled as proven, or a downstream sample domain cannot produce a timing result. The current contract is capture-oriented; live streams need a verifiable recording/segment identity before exporting source-hash evidence.

Example independent onset and sync records:

```json
[
  {
    "schema": 1, "event_id": "onset-1", "kind": "signal_onset",
    "stream_id": "iq0", "epoch": 0, "signal_id": "burst-1", "producer": "truth",
    "sequence": 0, "dropped_before": 0,
    "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "sample_rate_hz": 48000, "sample_domain": "source_complex_samples", "source_samples": [100,104],
    "provenance": {"kind":"independent_annotation","reference":"controlled-onsets-v1"},
    "purpose": "acquisition", "recovery_from": null
  },
  {
    "schema": 1, "event_id": "sync-1", "kind": "sync",
    "stream_id": "iq0", "epoch": 0, "signal_id": "burst-1", "producer": "receiver",
    "sequence": 0, "dropped_before": 0,
    "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "sample_rate_hz": 48000, "sample_domain": "source_complex_samples", "source_samples": [340,350],
    "provenance": {"kind":"receiver_mapping","reference":"verified-sample-map-v1"}
  }
]
```

The repeated `a` hash is an illustrative placeholder, not a recorded test capture. The validator checks hash syntax; the future adapter must compare it to the real input.

## Validation and failure behavior

Call `validate_event(record)` for strict syntax/provenance validation, or `analyze_timeline(records)` to obtain stage results and validation diagnostics. The analysis does not mutate records, read files, infer positions, reorder malformed producer logs or contact a receiver.

Grouping requires identical stream, epoch and signal identity. Source hash and rate must agree throughout the epoch, and the hash must also remain identical across epochs of a stream. There must be exactly one independently annotated onset and one receiver producer for a measured group. Duplicate event IDs, malformed fields and producer-order violations invalidate measurements across the submitted log because their causal destination cannot be trusted.

**Input interleaving is producer-only, not a global causal order.** Each producer's sequence, epoch and mapped sample bounds must progress in supplied order, including across an intervening record with unavailable mapping. Cross-producer arrival order imposes no such chronology. For example, receiver sync at sample 150, source discontinuity at sample 200, then an independent annotation for onset at sample 100 is valid: the annotation arrived later, but its source position is proven earlier. The analyzer does not reject an old epoch merely because some other producer has already submitted a newer one. Delayed records within one producer still must respect that producer's causal sequence.

Discontinuities close a **whole stream epoch**, across every producer and signal group. A boundary `[lo,hi]` bounds the transition position; it is not an inferred number of lost samples. All ordinary records in the closing epoch must have proven intervals ending strictly before `lo`. All records in the next observed epoch must begin at or after `hi`, including that next epoch's own eventual closure. A record touching or straddling a closing boundary cannot be assigned to the old epoch. An exact new-epoch position at `hi` is allowed. Every record is checked, not only the first stage selected for measurement. A stale later sync therefore cannot hide behind an earlier valid-looking first sync.

These boundary checks run after collecting the producer logs, using absolute intervals and epoch numbers rather than cross-producer arrival order. The first observed epoch may have any nonnegative generation. Between observed epochs, an explicit closure of the preceding observed epoch is required even for a new acquisition or a different receiver producer. Epoch numbers need only increase; numeric gaps do not supply missing boundary evidence. Source-rate changes require a new epoch with the same proven boundary rules; no delay is calculated across different rates. A source-capture change requires a new stream, because positions from different captures are not comparable.

Schema 1 permits one authoritative discontinuity record per closing epoch. Multiple records, even with matching intervals from different producers, are ambiguous because the schema has no identity linking duplicate reports of one physical boundary. Missing, unmapped, ambiguous or chronologically reversed boundaries cannot establish a later epoch's start. A later mapped boundary also cannot repair a boundary chain whose own position in that chain is unproven. Producers must provide a verified chain, or begin a separately identified stream with independently established provenance.

The report's `epoch_issues` lists all detected stream/epoch boundary and identity reasons, including epochs containing only discontinuities. Semantic boundary issues leave timing unavailable for the affected epoch; an unproven boundary chain also affects dependent later epochs, and a capture-hash change affects all epochs of that stream. A stale ordinary record invalidates measurements throughout its epoch, but does not by itself invalidate an otherwise independently proven closing boundary and subsequent epoch. Unrelated streams remain measurable. When multiple epoch issues apply, the stage reason uses the first reason in sorted order unless an earlier validation check already supplies a reason; inspect `epoch_issues` for the complete set.

For each stage, the first compatible event is selected in producer sequence order. If repeated stage intervals overlap enough to leave first-event timing ambiguous, that stage remains unavailable. An available later stage must not precede the available earlier stage. The causal chain is strict: onset → sync → valid frame → PCM. A missing, ambiguous or unproven earlier stage also leaves later-stage measurements unavailable. All numeric delays remain onset-relative; the strict chain prevents a first-PCM claim when preceding stage order is unproven.

Results carry `status`, an explicit `reason`, `event_id`, `delay_samples` and `delay_seconds` per stage. Unavailable results contain null delay fields, never zero substitutes. The report-level `status` describes syntax/producer-order validation and record availability, not a blanket claim that every stage or epoch is valid or measured; consumers must inspect `errors`, `epoch_issues` and each stage's status.

Telemetry losses are not RF sample gaps. For every producer, observed sequence gaps are counted, declared `dropped_before` values are totaled, and undeclared portions appear as `unreported_missing_events`. A reported drop count exceeding its sequence gap is invalid. Any detected telemetry loss conservatively invalidates first-event claims for that stream throughout this submitted log; unrelated valid streams can still produce results. This intentionally avoids selecting a fast-looking surviving event after the actual first event was lost. The counters cover loss bounded by observed records; schema 1 has no terminal producer footer and cannot establish how many records were lost after the last observed record.

Recovery requires a separately annotated post-gap onset in a newer epoch, linked to a discontinuity in the same stream/source. The boundary itself must have proven absolute source bounds, and its latest possible position must not be after the onset's earliest possible position. Missing, overlapping or future boundary mappings leave recovery timing unavailable. An intervening newer discontinuity makes an older recovery reference stale. Recovery delay is measured from the independent post-gap onset, **not from an assumed gap duration**. Recovery and acquisition both obey the stream-wide boundary checks above.

### Reproduced cross-producer failures and regression results

The original analyzer checked closure in a producer's own event sequence and guarded only the selected first stage against its own epoch's boundary. Three controlled counterexamples were reproduced before the stream-wide validation change:

| Submitted source positions | Previous result | Corrected result |
| --- | --- | --- |
| Source producer closes epoch 0 at `[400,410]`; another producer supplies epoch-1 acquisition onset 100 and sync 200 | Available 100-sample delay despite occurring before the gap | Unavailable: `record_precedes_epoch_start` |
| Epoch-0 onset 100 and sync 150; source producer closes at 200; receiver later emits another epoch-0 sync 250 | Available 50-sample first-sync delay despite a stale later record | Entire epoch unavailable: `record_outside_closed_epoch` |
| Separate producers supply onset/sync in epoch 0 and then epoch 1, with no discontinuity | Both epoch measurements available | Unavailable: missing closure evidence for both adjacent epochs |

A positive control submits sync 150 and source gap 200 **before** the independent onset-100 annotation. It retains the correct 50-sample delay regardless of their cross-producer interleaving. Regression cases also cover a delayed old receiver record arriving after a new receiver's new-epoch record, uncertain boundaries, unmapped positions, stale workers, source/rate changes, duplicate closure reports and invalid boundary chains. These are artificial event-contract checks, not RF or acquisition-speed measurements.

## What live instrumentation must eventually provide

1. A unique stream identity, verified source capture identity, independent signal-onset annotations, and explicit tune/rate/continuity epochs.
2. Original source-complex-sample lineage through input buffering, filters, resampling, symbol decisions, framing and vocoder queues. Track both group delay and fractional/interpolation uncertainty; read-ahead alone is not consumed-sample provenance.
3. Explicit event semantics: sync candidate/acceptance policy; the check that makes a frame valid; the PCM handoff stage. A sync event never substitutes for an independently validated frame, and PCM generation never proves actual speaker playback or intelligibility.
4. A causal event sequence per producer, assigned before attempted publication so dropped telemetry leaves observable gaps, plus a reliable final loss summary in a future extension.
5. Per-channel/burst identity so simultaneous signals, slots or worker reuse cannot attach to another signal's onset. Reject uncertain associations rather than guessing.
6. A bounded-cost exporter with its own loss counters and independent tests of mapping through rate changes, transport discontinuities, retunes, replay and queue saturation.

Only after those producer guarantees are independently tested should the runner ingest this contract and publish real acquisition/recovery results. The tests here use declared artificial source positions to exercise the measurement rules; they do not benchmark decoder speed.

## Deterministic checks

Run `python -m unittest discover -s benchmarks/tests -p test_timeline.py -v`. The 69 tests cover exact/uncertain intervals, missing data, explicit unavailable lineage, source/rate/epoch mismatches, independent producer/onset requirements, duplicate and stale events, sequence drops, out-of-order records, discontinuity crossing, recovery boundaries, producer interleaving, whole-stream epoch membership and input immutability. All fixtures are small standard-library objects; no SDR device, decoder executable or network is used.
