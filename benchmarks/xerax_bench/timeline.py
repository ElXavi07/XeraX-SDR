"""Proposed source-sample event contract; no live receiver instrumentation.

Intervals describe when an event became causally available in the original
complex-sample domain. They are not payload support windows or host timestamps.
Provenance is a required declaration, not something this module can establish.
"""
import re

SCHEMA = 1
KINDS = {"signal_onset", "sync", "valid_frame", "pcm", "discontinuity"}
STAGES = ("sync", "valid_frame", "pcm")
IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMON = {"schema", "event_id", "kind", "stream_id", "epoch", "signal_id",
          "producer", "sequence", "dropped_before", "source_sha256", "sample_rate_hz",
          "sample_domain", "source_samples", "provenance"}


def _integer(value, label, minimum=0, maximum=(1 << 63) - 1):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError("Invalid " + label)


def _identifier(value, label):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("Invalid " + label)


def validate_event(event):
    """Reject malformed events; unavailable mappings are valid but unmeasurable."""
    if not isinstance(event, dict):
        raise ValueError("Event must be an object")
    kind = event.get("kind")
    if not isinstance(kind, str) or kind not in KINDS:
        raise ValueError("Unknown event kind")
    allowed = COMMON | ({"purpose", "recovery_from"} if kind == "signal_onset" else set())
    allowed |= {"reason"} if kind == "discontinuity" else set()
    if set(event) != allowed:
        raise ValueError("Missing or unknown event fields")
    if type(event["schema"]) is not int or event["schema"] != SCHEMA:
        raise ValueError("Unsupported event schema")
    for key in ("event_id", "stream_id", "producer"):
        _identifier(event[key], key)
    for key in ("epoch", "sequence", "dropped_before"):
        _integer(event[key], key)
    _integer(event["sample_rate_hz"], "sample rate", 1, 1000000000)
    if not isinstance(event["source_sha256"], str) or not SHA256.fullmatch(event["source_sha256"]):
        raise ValueError("Missing source capture SHA-256")
    if event["sample_domain"] != "source_complex_samples":
        raise ValueError("Unsupported sample domain; no inferred conversion")
    if kind == "discontinuity":
        if event["signal_id"] is not None or not isinstance(event["reason"], str) or not event["reason"].strip():
            raise ValueError("Discontinuity needs a reason and no signal ID")
    else:
        _identifier(event["signal_id"], "signal_id")
    provenance = event["provenance"]
    if not isinstance(provenance, dict) or set(provenance) != {"kind", "reference"}:
        raise ValueError("Missing mapping provenance")
    reference = provenance["reference"]
    if not isinstance(reference, str) or not reference.strip() or len(reference) > 1024:
        raise ValueError("Missing provenance reference")
    expected = "independent_annotation" if kind == "signal_onset" else "receiver_mapping"
    if provenance["kind"] not in (expected, "unavailable"):
        raise ValueError("Wrong provenance kind")
    interval = event["source_samples"]
    if provenance["kind"] == "unavailable":
        if interval is not None:
            raise ValueError("Unproven mapping cannot carry sample positions")
    else:
        if not isinstance(interval, list) or len(interval) != 2:
            raise ValueError("Sample interval needs inclusive lower and upper bounds")
        for value in interval:
            _integer(value, "sample interval")
        if interval[0] > interval[1]:
            raise ValueError("Reversed sample interval")
    if kind == "signal_onset":
        if event["purpose"] not in ("acquisition", "recovery"):
            raise ValueError("Unknown onset purpose")
        if event["purpose"] == "recovery":
            _identifier(event["recovery_from"], "recovery discontinuity")
        elif event["recovery_from"] is not None:
            raise ValueError("Acquisition onset cannot reference a discontinuity")
    return event


def _unavailable(reason):
    return {"status": "unavailable", "reason": reason, "event_id": None,
            "delay_samples": None, "delay_seconds": None}


def analyze_timeline(events):
    """Validate a complete bounded event log and derive first-stage delay bounds.

    Producer sequences begin at zero and persist across epochs. Input order must
    preserve each producer's sequence. Any telemetry loss conservatively makes
    that stream's first-event measurements unavailable for the entire log.
    Malformed/order-invalid records invalidate the complete log, since their
    causal destination cannot be trusted. Other valid streams survive loss only.
    """
    if not isinstance(events, list):
        raise ValueError("Timeline must be a list of events")
    valid, errors, by_id, previous, last_samples = [], [], {}, {}, {}
    dropped, gaps, unknown_loss = 0, 0, 0
    loss_streams, groups, domains = set(), {}, {}
    for index, event in enumerate(events):
        try:
            validate_event(event)
            ident = event["event_id"]
            if ident in by_id:
                raise ValueError("Duplicate event ID")
            key = (event["stream_id"], event["producer"])
            old = previous.get(key)
            last_sequence = old["sequence"] if old else -1
            gap = event["sequence"] - last_sequence - 1
            if gap < 0:
                raise ValueError("Out-of-order producer sequence")
            if event["dropped_before"] > gap:
                raise ValueError("Dropped count exceeds sequence gap")
            if old and event["epoch"] < old["epoch"]:
                raise ValueError("Stale epoch")
            if old and event["epoch"] == old["epoch"]:
                if old["kind"] == "discontinuity":
                    raise ValueError("Event after discontinuity must start a new epoch")
            # Epoch changes do not reset absolute positions in one capture.
            sample_key = key + (event["source_sha256"],)
            before, after = last_samples.get(sample_key), event["source_samples"]
            if before is not None and after is not None and (after[0] < before[0] or after[1] < before[1]):
                raise ValueError("Out-of-order source sample interval")
            dropped += event["dropped_before"]
            gaps += gap
            unknown_loss += gap - event["dropped_before"]
            if gap:
                loss_streams.add(event["stream_id"])
            previous[key] = event
            if after is not None:
                last_samples[sample_key] = after
            by_id[ident] = event
            valid.append(event)
            epoch_key = (event["stream_id"], event["epoch"])
            domains.setdefault(epoch_key, set()).add((event["source_sha256"], event["sample_rate_hz"]))
            if event["kind"] != "discontinuity":
                group = epoch_key + (event["signal_id"],)
                groups.setdefault(group, []).append(event)
        except (ValueError, TypeError) as exc:
            errors.append({"record": index, "event_id": event.get("event_id") if isinstance(event, dict) else None,
                           "reason": str(exc)})

    measurements = []
    for (stream, epoch, signal), related in sorted(groups.items()):
        anchors = [e for e in related if e["kind"] == "signal_onset"]
        reason = "invalid_timeline" if errors else None
        if reason is None and stream in loss_streams:
            reason = "event_loss_first_observation_unproven"
        if reason is None and len(domains[(stream, epoch)]) != 1:
            reason = "incompatible_source_or_rate_within_epoch"
        if reason is None and len(anchors) != 1:
            reason = "missing_independent_onset" if not anchors else "ambiguous_onset"
        onset = anchors[0] if len(anchors) == 1 else None
        if reason is None and onset["source_samples"] is None:
            reason = "onset_mapping_unavailable"
        producers = {e["producer"] for e in related if e["kind"] in STAGES}
        if reason is None and (len(producers) > 1 or onset["producer"] in producers):
            reason = "ambiguous_or_nonindependent_producer"
        if reason is None and onset["purpose"] == "recovery":
            gap_event = by_id.get(onset["recovery_from"])
            if (gap_event is None or gap_event["kind"] != "discontinuity"
                    or gap_event["stream_id"] != stream or gap_event["epoch"] >= epoch
                    or gap_event["source_sha256"] != onset["source_sha256"]):
                reason = "missing_or_incompatible_recovery_boundary"
            elif gap_event["source_samples"] is None:
                reason = "recovery_boundary_mapping_unavailable"
            elif gap_event["source_samples"][1] > onset["source_samples"][0]:
                reason = "ambiguous_or_reversed_recovery_boundary"
            elif any(e["kind"] == "discontinuity" and e["stream_id"] == stream
                     and gap_event["epoch"] < e["epoch"] < epoch for e in valid):
                reason = "stale_recovery_boundary"
        result = {"stream_id": stream, "epoch": epoch, "signal_id": signal,
                  "purpose": onset["purpose"] if onset else None,
                  "onset_event_id": onset["event_id"] if onset else None, "stages": {}}
        prior = onset
        prior_stage_unproven = False
        boundaries = [e for e in valid if e["kind"] == "discontinuity"
                      and e["stream_id"] == stream and e["epoch"] == epoch]
        for stage in STAGES:
            if reason is not None:
                result["stages"][stage] = _unavailable(reason)
                continue
            if prior_stage_unproven:
                result["stages"][stage] = _unavailable("prior_stage_order_unproven")
                continue
            candidates = [e for e in related if e["kind"] == stage]
            if not candidates:
                result["stages"][stage] = _unavailable("missing_stage_event")
                prior_stage_unproven = True
                continue
            if any(e["source_samples"] is None for e in candidates):
                result["stages"][stage] = _unavailable("stage_mapping_unavailable")
                prior_stage_unproven = True
                continue
            candidates.sort(key=lambda e: e["sequence"])
            event = candidates[0]
            lower, upper = event["source_samples"]
            if any(e["source_samples"] is None or upper >= e["source_samples"][0] for e in boundaries):
                result["stages"][stage] = _unavailable("discontinuity_inside_measurement")
                prior_stage_unproven = True
                continue
            if lower < prior["source_samples"][1]:
                result["stages"][stage] = _unavailable("ambiguous_or_reversed_causal_order")
                prior_stage_unproven = True
                continue
            if any(other["source_samples"][0] < upper for other in candidates[1:]):
                result["stages"][stage] = _unavailable("ambiguous_first_event_interval")
                prior_stage_unproven = True
                continue
            bounds = [lower - onset["source_samples"][1], upper - onset["source_samples"][0]]
            result["stages"][stage] = {"status": "available", "reason": None, "event_id": event["event_id"],
                                       "delay_samples": bounds,
                                       "delay_seconds": [n / onset["sample_rate_hz"] for n in bounds]}
            prior = event
        measurements.append(result)
    return {"schema": SCHEMA, "scope": "proposed source-sample contract; no live instrumentation",
            "reported_dropped_events": dropped, "observed_sequence_gaps": gaps,
            "unreported_missing_events": unknown_loss, "errors": errors,
            "status": "invalid" if errors else ("complete" if measurements else "unavailable"),
            "measurements": measurements}
