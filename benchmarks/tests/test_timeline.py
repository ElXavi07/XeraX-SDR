import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from xerax_bench.timeline import analyze_timeline, validate_event


def event(kind, ident, samples, sequence=0, **changes):
    annotation = kind == "signal_onset"
    value = {"schema": 1, "event_id": ident, "kind": kind, "stream_id": "iq0",
             "epoch": 0, "signal_id": "burst0", "producer": "truth" if annotation else "receiver",
             "sequence": sequence, "dropped_before": 0, "source_sha256": "a" * 64,
             "sample_rate_hz": 48000, "sample_domain": "source_complex_samples",
             "source_samples": samples,
             "provenance": {"kind": "independent_annotation" if annotation else "receiver_mapping",
                            "reference": "controlled-vector-v1" if annotation else "sample-map-v1"}}
    if annotation:
        value.update(purpose="acquisition", recovery_from=None)
    if kind == "discontinuity":
        value.update(signal_id=None, reason="controlled sample gap")
    value.update(changes)
    return value


def standard():
    return [event("signal_onset", "onset", [100, 100]),
            event("sync", "sync", [340, 340]),
            event("valid_frame", "valid", [580, 580], 1),
            event("pcm", "pcm", [1060, 1060], 2)]


class TimelineTests(unittest.TestCase):
    def stages(self, events):
        return analyze_timeline(events)["measurements"][0]["stages"]

    def test_exact_source_sample_delays(self):
        stages = self.stages(standard())
        for name, samples in (("sync", 240), ("valid_frame", 480), ("pcm", 960)):
            self.assertEqual(stages[name]["delay_samples"], [samples, samples])
            self.assertEqual(stages[name]["delay_seconds"], [samples / 48000] * 2)

    def test_interval_bounds_propagate_uncertainty(self):
        result = self.stages([event("signal_onset", "onset", [100, 104]),
                              event("sync", "sync", [340, 350])])["sync"]
        self.assertEqual(result["delay_samples"], [236, 250])
        self.assertEqual(result["delay_seconds"], [236 / 48000, 250 / 48000])

    def test_exact_same_sample_can_have_zero_source_delay(self):
        result = self.stages([event("signal_onset", "onset", [100, 100]),
                              event("sync", "sync", [100, 100])])["sync"]
        self.assertEqual(result["delay_samples"], [0, 0])

    def test_missing_stages_are_null_not_zero(self):
        result = self.stages([event("signal_onset", "onset", [100, 100])])
        self.assertTrue(all(x["delay_seconds"] is None for x in result.values()))

    def test_missing_onset_cannot_be_inferred(self):
        result = self.stages([event("sync", "sync", [100, 100])])["sync"]
        self.assertEqual(result["reason"], "missing_independent_onset")

    def test_decoder_generated_onset_is_invalid(self):
        events = standard()
        events[0]["provenance"]["kind"] = "receiver_mapping"
        result = analyze_timeline(events)
        self.assertEqual(result["status"], "invalid")
        self.assertIsNone(result["measurements"][0]["stages"]["sync"]["delay_samples"])

    def test_distinct_onset_producer_is_required(self):
        onset = event("signal_onset", "onset", [100, 100], producer="receiver")
        sync = event("sync", "sync", [200, 200], 1)
        self.assertEqual(self.stages([onset, sync])["sync"]["reason"], "ambiguous_or_nonindependent_producer")

    def test_unproven_mapping_is_unavailable(self):
        events = standard()
        events[1].update(source_samples=None, provenance={"kind": "unavailable", "reference": "no lineage"})
        self.assertEqual(self.stages(events)["sync"]["reason"], "stage_mapping_unavailable")
        self.assertEqual(self.stages(events)["valid_frame"]["reason"], "prior_stage_order_unproven")
        self.assertIsNone(self.stages(events)["pcm"]["delay_samples"])

    def test_unproven_mapping_cannot_smuggle_sample_count(self):
        item = event("sync", "sync", [1, 1])
        item["provenance"]["kind"] = "unavailable"
        with self.assertRaisesRegex(ValueError, "Unproven"):
            validate_event(item)

    def test_onset_mapping_unavailable(self):
        events = standard()
        events[0].update(source_samples=None, provenance={"kind": "unavailable", "reference": "no independent marker"})
        self.assertEqual(self.stages(events)["sync"]["reason"], "onset_mapping_unavailable")

    def test_wrong_sample_domain_is_rejected(self):
        for domain in ("demod_samples", "pcm_samples", "wall_clock", "symbol_count"):
            with self.subTest(domain=domain):
                with self.assertRaisesRegex(ValueError, "sample domain"):
                    validate_event(event("sync", "sync", [2, 2], sample_domain=domain))

    def test_unknown_timestamp_field_is_not_used(self):
        events = standard()
        events[1]["log_time_seconds"] = 0.0
        self.assertEqual(analyze_timeline(events)["status"], "invalid")

    def test_rate_change_requires_epoch_change(self):
        events = standard()
        events[1]["sample_rate_hz"] = 24000
        self.assertEqual(self.stages(events)["sync"]["reason"], "incompatible_source_or_rate_within_epoch")

    def test_different_capture_hash_rejected_in_same_epoch(self):
        events = standard()
        events[1]["source_sha256"] = "b" * 64
        self.assertEqual(self.stages(events)["sync"]["reason"], "incompatible_source_or_rate_within_epoch")

    def test_streams_do_not_share_onsets(self):
        events = standard()[:2]
        events[1]["stream_id"] = "iq1"
        result = analyze_timeline(events)["measurements"]
        self.assertEqual(len(result), 2)
        self.assertTrue(all(x["stages"]["sync"]["delay_samples"] is None for x in result))

    def test_epochs_do_not_share_onsets(self):
        events = standard()[:2]
        events[1]["epoch"] = 1
        self.assertTrue(all(x["stages"]["sync"]["delay_samples"] is None
                            for x in analyze_timeline(events)["measurements"]))

    def test_signal_ids_prevent_wrong_burst_association(self):
        events = standard()[:2]
        events[1]["signal_id"] = "another-burst"
        self.assertTrue(all(x["stages"]["sync"]["delay_samples"] is None
                            for x in analyze_timeline(events)["measurements"]))

    def test_ambiguous_duplicate_onset(self):
        events = standard()
        events.insert(1, event("signal_onset", "other-onset", [110, 110], 1))
        self.assertEqual(self.stages(events)["sync"]["reason"], "ambiguous_onset")

    def test_multiple_receiver_producers_are_ambiguous(self):
        events = standard()[:2] + [event("valid_frame", "frame", [400, 400], producer="other-receiver")]
        self.assertEqual(self.stages(events)["sync"]["reason"], "ambiguous_or_nonindependent_producer")

    def test_duplicate_event_id_invalidates_log(self):
        events = standard()
        events[2]["event_id"] = events[1]["event_id"]
        self.assertEqual(analyze_timeline(events)["status"], "invalid")

    def test_out_of_order_sequence_is_not_sorted_away(self):
        events = standard()
        events[2], events[3] = events[3], events[2]
        result = analyze_timeline(events)
        self.assertEqual(result["status"], "invalid")
        self.assertTrue(any("Out-of-order" in x["reason"] for x in result["errors"]))

    def test_stale_epoch_is_invalid(self):
        events = standard()
        events[1]["epoch"] = 1
        self.assertEqual(analyze_timeline(events)["status"], "invalid")

    def test_out_of_order_samples_after_unknown_mapping(self):
        events = standard()
        events[2].update(source_samples=None, provenance={"kind": "unavailable", "reference": "not mapped"})
        events[3]["source_samples"] = [300, 300]
        self.assertEqual(analyze_timeline(events)["status"], "invalid")

    def test_reported_drop_counts_and_no_first_event_claim(self):
        events = standard()
        events[1].update(sequence=2, dropped_before=2)
        events[2]["sequence"] = 3
        events[3]["sequence"] = 4
        result = analyze_timeline(events)
        self.assertEqual((result["reported_dropped_events"], result["observed_sequence_gaps"],
                          result["unreported_missing_events"]), (2, 2, 0))
        self.assertEqual(result["measurements"][0]["stages"]["sync"]["reason"], "event_loss_first_observation_unproven")

    def test_unreported_sequence_gap_is_exposed(self):
        events = standard()
        events[3]["sequence"] = 3
        result = analyze_timeline(events)
        self.assertEqual(result["unreported_missing_events"], 1)
        self.assertIsNone(result["measurements"][0]["stages"]["sync"]["delay_samples"])

    def test_drop_count_cannot_exceed_sequence_gap(self):
        events = standard()
        events[1]["dropped_before"] = 1
        self.assertEqual(analyze_timeline(events)["status"], "invalid")

    def test_telemetry_loss_in_other_stream_does_not_taint_measurement(self):
        events = standard()
        events.append(event("sync", "other-stream", [200, 200], 1, dropped_before=1, stream_id="iq1"))
        self.assertEqual(self.stages(events)["sync"]["status"], "available")

    def test_overlapping_onset_interval_cannot_claim_causal_order(self):
        events = [event("signal_onset", "onset", [100, 200]), event("sync", "sync", [190, 220])]
        self.assertEqual(self.stages(events)["sync"]["reason"], "ambiguous_or_reversed_causal_order")

    def test_overlapping_first_stage_intervals_are_ambiguous(self):
        events = [event("signal_onset", "onset", [100, 100]), event("sync", "sync1", [200, 220]),
                  event("sync", "sync2", [210, 240], 1)]
        self.assertEqual(self.stages(events)["sync"]["reason"], "ambiguous_first_event_interval")

    def test_first_repeated_stage_is_selected(self):
        events = standard()[:2] + [event("sync", "second-sync", [360, 360], 1)]
        self.assertEqual(self.stages(events)["sync"]["event_id"], "sync")

    def test_recovery_needs_new_epoch_and_independent_onset(self):
        events = [event("discontinuity", "gap", [400, 410]),
                  event("signal_onset", "return", [500, 504], epoch=1, purpose="recovery", recovery_from="gap",
                        sample_rate_hz=96000),
                  event("sync", "relock", [600, 610], 1, epoch=1, sample_rate_hz=96000)]
        result = self.stages(events)["sync"]
        self.assertEqual(result["delay_samples"], [96, 110])
        self.assertEqual(result["delay_seconds"], [96 / 96000, 110 / 96000])

    def test_recovery_with_unmapped_gap_is_unavailable(self):
        events = [event("discontinuity", "gap", None, provenance={"kind": "unavailable", "reference": "unknown loss size"}),
                  event("signal_onset", "return", [500, 500], epoch=1, purpose="recovery", recovery_from="gap"),
                  event("sync", "relock", [600, 600], 1, epoch=1)]
        self.assertEqual(self.stages(events)["sync"]["reason"], "recovery_boundary_mapping_unavailable")

    def test_recovery_with_future_gap_is_unavailable(self):
        events = [event("discontinuity", "gap", [700, 700], producer="source"),
                  event("signal_onset", "return", [500, 500], epoch=1, purpose="recovery", recovery_from="gap"),
                  event("sync", "relock", [600, 600], epoch=1)]
        self.assertEqual(self.stages(events)["sync"]["reason"], "ambiguous_or_reversed_recovery_boundary")

    def test_recovery_with_overlapping_gap_is_unavailable(self):
        events = [event("discontinuity", "gap", [400, 502], producer="source"),
                  event("signal_onset", "return", [500, 504], epoch=1, purpose="recovery", recovery_from="gap"),
                  event("sync", "relock", [600, 600], epoch=1)]
        self.assertEqual(self.stages(events)["sync"]["reason"], "ambiguous_or_reversed_recovery_boundary")

    def test_epoch_change_does_not_reset_absolute_source_position(self):
        events = [event("discontinuity", "gap", [400, 400]),
                  event("signal_onset", "return", [500, 500], epoch=1, purpose="recovery", recovery_from="gap"),
                  event("sync", "relock", [100, 100], 1, epoch=1)]
        self.assertEqual(analyze_timeline(events)["status"], "invalid")

    def test_missing_sync_cannot_produce_first_pcm_timing(self):
        events = [event("signal_onset", "onset", [100, 100]),
                  event("valid_frame", "valid", [200, 200]),
                  event("pcm", "pcm", [300, 300], 1)]
        self.assertEqual(self.stages(events)["pcm"]["reason"], "prior_stage_order_unproven")

    def test_ambiguous_sync_cannot_produce_first_pcm_timing(self):
        events = [event("signal_onset", "onset", [100, 100]),
                  event("sync", "sync1", [200, 250]), event("sync", "sync2", [240, 260], 1),
                  event("valid_frame", "valid", [300, 300], 2), event("pcm", "pcm", [400, 400], 3)]
        self.assertEqual(self.stages(events)["pcm"]["reason"], "prior_stage_order_unproven")

    def test_recovery_boundary_must_exist(self):
        events = standard()
        events[0].update(purpose="recovery", recovery_from="missing")
        self.assertEqual(self.stages(events)["sync"]["reason"], "missing_or_incompatible_recovery_boundary")

    def test_stale_recovery_boundary_rejected(self):
        events = [event("discontinuity", "old-gap", [100, 100]),
                  event("discontinuity", "new-gap", [200, 200], 1, epoch=1),
                  event("signal_onset", "onset", [300, 300], epoch=2, purpose="recovery", recovery_from="old-gap"),
                  event("sync", "sync", [400, 400], 2, epoch=2)]
        self.assertEqual(self.stages(events)["sync"]["reason"], "stale_recovery_boundary")

    def test_receiver_cannot_reuse_closed_epoch(self):
        events = [event("discontinuity", "gap", [100, 100]), event("sync", "sync", [200, 200], 1)]
        self.assertEqual(analyze_timeline(events)["status"], "invalid")

    def test_other_producer_discontinuity_still_invalidates_crossing_delay(self):
        events = standard()[:2]
        events.append(event("discontinuity", "gap", [200, 200], producer="source"))
        self.assertEqual(self.stages(events)["sync"]["reason"], "discontinuity_inside_measurement")

    def test_malformed_numbers_and_intervals_rejected(self):
        for field, value in (("sample_rate_hz", 0), ("sample_rate_hz", float("nan")), ("sample_rate_hz", True),
                             ("epoch", -1), ("sequence", 1.5), ("dropped_before", True),
                             ("source_samples", [2, 1]), ("source_samples", [0, True]),
                             ("source_samples", [0]), ("source_sha256", "missing"), ("schema", 1.0)):
            with self.subTest(field=field, value=value):
                item = event("sync", "sync", [1, 1])
                item[field] = value
                with self.assertRaises(ValueError):
                    validate_event(item)

    def test_missing_provenance_never_becomes_zero_delay(self):
        events = standard()
        del events[1]["provenance"]
        result = analyze_timeline(events)
        self.assertEqual(result["status"], "invalid")
        self.assertTrue(all(x["delay_samples"] is None for x in result["measurements"][0]["stages"].values()))

    def test_empty_and_nonobject_events(self):
        self.assertEqual(analyze_timeline([])["measurements"], [])
        self.assertEqual(analyze_timeline([None])["status"], "invalid")
        with self.assertRaises(ValueError):
            analyze_timeline({})

    def test_analysis_does_not_mutate_input(self):
        events = standard()
        original = copy.deepcopy(events)
        analyze_timeline(events)
        self.assertEqual(events, original)


if __name__ == "__main__":
    unittest.main()
