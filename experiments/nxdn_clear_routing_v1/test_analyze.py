import copy
import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest

_spec = importlib.util.spec_from_file_location("clear_routing_analyze", Path(__file__).with_name("analyze.py"))
analyze = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(analyze)


def process_result(flags=3):
    return {"c0_errors": 0, "protected_errors": 0, "c4_errors": 0, "total_errors": 0, "flags": flags}


def call_snapshot(phase=1):
    return {"present": 1, "epoch": 1, "phase": phase, "protocol": 28, "kind": 2, "source": 901,
            "target": 1201, "policy_target": 1201, "crypto": 1, "algid": 0, "kid": 0,
            "audio_permitted": int(phase == 1), "media_active": int(phase == 1), "end_reason": 3 if phase == 2 else 0}


def route_fixture(slot=0, frame_id=0, rid=0, channel="0"*72, word="0"*49):
    matrix, reliability = analyze.matrix_for(channel, [255]*36)
    basic = {"frame": frame_id, "route_id": rid, "confirmed": 1, "call": call_snapshot()}
    fec = {"call_id": rid, "parent_call_id": None, "depth": 1, "outer": 1, "mode": "soft"}
    rows = [{**basic, "kind": "route_begin", "slot": slot, "voice": 3, "mode": "soft", "fec_outer": 0, "syntheses": 0},
            {**basic, **fec, "kind": "fec_input", "matrix96": matrix, "reliability": reliability,
             "channel72": channel, "channel_dibits": "".join(str(int(channel[i:i+2], 2)) for i in range(0,72,2)), "channel_reliability": [255]*36},
            {**basic, **fec, "kind": "fec", "status": 0, "bits49": word, "result": process_result(), "input_unchanged": 1},
            {**basic, "kind": "synthesis", "call_id": rid, "input49": word, "result_before": process_result(),
             "status": 0, "result_after": process_result(), "input_unchanged": 1},
            {**basic, "kind": "route_end", "slot": slot, "voice": 3, "mode": "soft", "fec_outer": 1, "syntheses": 1}]
    for seq, row in enumerate(rows): row["seq"] = seq
    return rows


def frame_fixture():
    raw_body = "".join(str((int(b)<<1)|1) for b in format(0xae, "08b")) + "0"*174
    body = analyze.dewhiten(raw_body, 228)
    source = {"ordinal": 0, "source_frame": 1, "kind": "voice0", "start": 640, "end": 4480,
              "vector": "r1.dibits", "scored": True}
    truth = {"full_lich": 0xae, "lich": 0x57, "sacch": {"information_bits": "0"*26,
             "computed_crc": analyze.crc("0"*26, 6), "transmitted_crc": analyze.crc("0"*26, 6)},
             "facch": None, "transmitted_voice": [{"slot": i, "source_id": i} for i in range(4)]}
    calls = [{"before": 840+i*20, "after": 860+i*20, "eof_before": 0, "eof_after": 0,
              "symbol_before": 42+i, "symbol_after": 43+i} for i in range(182)]
    end = {"body": body, "body_count": 182, "body_calls": calls, "body_positions": [c["after"] for c in calls],
           "value": 2, "confirmed": 1, "ran": 1, "call": call_snapshot(), "eof": 0}
    lich = {"full_lich": 0xae, "lich": 0x57, "voice": 3, "scch": 0, "pich_tch": 0, "idas": 0,
            "sacch": 1, "facch": 0, "result": 1, "reason": "accepted", "parity_received": 0,
            "parity_computed": 0, "symbolcnt": 50, "frontier": 1000}
    event = {"kind": "crc", "channel": 1, "part": 0, "bits": "0"*26, "computed": analyze.crc("0"*26,6),
             "received": analyze.crc("0"*26,6), "soft_pass": 1, "fallback": 0}
    frame = {"begin": {"frame": 0, "sync": 28, "pn95": 228}, "end": end, "classes": ["complete"]*182,
             "lich_source": source, "source": source, "fully_sampled": True, "lich": [lich], "crcs": [event], "scch": [], "events": []}
    for slot in range(4): frame["events"] += route_fixture(slot, rid=slot)
    for seq, row in enumerate(frame["events"]): row["seq"] = seq
    analyze.inspect_routes(frame, 1)
    wave = {"samples": 5000, "frames": [source]}
    oracle = {"words": ["0"*49]*20, "channels": ["0"*72]*20, "vectors": {"r1.dibits": truth},
              "dibits": {"r1.dibits": bytes(10)+bytes(map(int,body))}}
    return frame, wave, oracle


def full_fixture(enabled=1):
    frame, wave, oracle = frame_fixture(); rows = []
    def add(kind, frontier, **extra):
        row = {"seq": len(rows), "kind": kind, "provided": frontier, "frontier": frontier if enabled else 0,
               "pops": frontier if enabled else 0, "eof": int(frontier == 5000), "frame": 0,
               "cache_pos": 0, "cache_len": 0, "read_start": frontier, "symbolcnt": frontier//20,
               "sync": 28, "last_sync": 28, "confirmed": 1, "streak": 0, "evidence": 2, "proved": 1,
               "verdict": 0, "profile_valid": 1, "profile_idx": 0, "profile_symbol": 224,
               "hunt_idx": 0, "hunt_counter": 0, "hunt_mark": 0, "hunt_entry": 0,
               "pn95": 228, "carrier": 1, "rf_mod": 2, "sps": 20, "center": 10, "search_part_valid": 0,
               "ran": 1, "sacch_non_superframe": 0, "audio_indices": [0]*4, "part_of_frame": 0,
               "cipher": 0, "search_ready": 0, "search_applied": 0, "manual_key": 0, "forced_cipher": 0,
               "keyloader": 0, "call": call_snapshot(), "value": 0}
        row.update(extra); row["seq"] = len(rows); rows.append(row)
    add("configuration", 0, **analyze.finite.CONFIG, routing_schema=1, search_enabled=0, initial_manual_key=0,
        initial_forced_cipher=0, initial_cipher=0, initial_keyloader=0, initial_aes_key_loaded=0)
    add("initialized", 0); add("reset_begin", 0); add("reset_end", 0)
    add("search_begin", 0); add("search_end", 840, value=28)
    add("dispatch_begin", 840); add("frame_begin", 840)
    if enabled:
        add("lich", 1000, **{k:v for k,v in frame["lich"][0].items() if k != "frontier"})
        event = frame["crcs"][0]; add("crc", 4480, **{k:v for k,v in event.items() if k != "kind"})
        add("voice_begin", 4480, value=3)
    for slot in range(4):
        for event in route_fixture(slot, rid=slot):
            kind = event["kind"]
            if kind == "fec_input" and not enabled: continue
            if kind == "fec_input": add("mbe_begin", 4480)
            add(kind, 4480, **{k:v for k,v in event.items() if k not in ("kind", "seq")})
            if kind == "synthesis" and enabled: add("mbe_end", 4480)
    if enabled: add("voice_end", 4480, value=3)
    add("frame_end", 4480, **frame["end"]); add("dispatch_end", 4480)
    add("search_begin", 4480); add("search_end", 5000, value=-1)
    add("completed", 5000)
    add("summary", 5000, observed=enabled, fast=0, chunk=37, samples=5000, errors=0, starts=0, tunes=0,
        skipped=0, frames=1, dispatches=1, resets=1, crcs=enabled, rate_calls=0, reacquire_calls=0,
        v2_lich_events=1, v2_scch_events=0, v2_voice_calls=1, v2_mbe_calls=4, v2_audio_calls=0,
        route_words=4, fec_hard_calls=0, fec_soft_calls=4, fec_outer_calls=4, fec_nested_calls=0, synthesis_calls=4)
    trace = b"".join(struct.pack("<I", i) for i in range(5000)) if enabled else b""
    case = {"id": "cold_default-c37", "configuration": "cold_default", "waveform": "cold", "chunk": 37, "fast": 0}
    return rows, trace, case, wave, oracle


def quality(frame, wave, oracle, scenario="cold_default"):
    return analyze.assess_frames([frame], wave, oracle, 1, scenario)


def comparison_fixture():
    cases, pairs = [], {}
    for scenario in analyze.SCENARIOS:
        for chunk in (37,512):
            case={"id":f"{scenario}-c{chunk}","configuration":scenario,"waveform":scenario,"chunk":chunk,
                  "fast":int(scenario in ("single_weak","cold_fast"))}
            cases.append(case); pairs[case["id"]]={}
            for enabled in (0,1):
                pairs[case["id"]][enabled]={"case":case,"summary":{"observed":enabled},"measurement_pass":True,
                    "semantic":[{"scope":"common"}],"chunk_semantic":[{"scope":"common"}],
                    "trace_sha256":f"{scenario}-{enabled}","routing_pass":True,"negative_pass":True,
                    "finite_voice_safety_pass":True,"routing_issues":[],"negative_issues":[],"unsafe_synthesis":[]}
    return pairs,{"cases":cases}


def primed_quality_fixture():
    frames=[]; oracle={"words":["0"*49]*20,"channels":["0"*72]*20,"vectors":{},"dibits":{}}
    wave={"frames":[]}; rid=0
    for identity in range(9):
        frame,_,base=frame_fixture(); source=frame["source"]
        source.update(ordinal=identity+1,source_frame=identity,start=640+(identity+1)*3840,
                      end=640+(identity+2)*3840,vector=f"r{identity}.dibits")
        frame["begin"]["frame"]=identity; frame["end"]["body_positions"]=[p+(identity+1)*3840 for p in frame["end"]["body_positions"]]
        full=0x83 if identity in (0,8) else 0xa6 if identity==6 else 0xaa if identity==7 else 0xae
        slots=[] if identity in (0,8) else [2,3] if identity==6 else [0,1] if identity==7 else [0,1,2,3]
        ids=[0,1,2,3] if identity==6 else [4,5,6,7] if identity==7 else list(range((identity-1)*4,(identity-1)*4+4))
        raw="".join(str((int(b)<<1)|1) for b in format(full,"08b"))+"0"*174
        frame["end"]["body"]=analyze.dewhiten(raw,228)
        frame["lich"][0]["full_lich"]=full
        truth=copy.deepcopy(base["vectors"]["r1.dibits"]); truth.update(full_lich=full,lich=full>>1,
            transmitted_voice=[{"slot":slot,"source_id":ids[slot]} for slot in slots])
        oracle["vectors"][source["vector"]]=truth
        oracle["dibits"][source["vector"]]=bytes(10)+bytes(map(int,frame["end"]["body"]))
        frame["events"]=[]
        for slot in slots:
            events=route_fixture(slot,frame_id=identity,rid=rid); rid+=1
            selector=2 if identity==6 else 1 if identity==7 else 3
            for event in events:
                if "voice" in event: event["voice"]=selector
            frame["events"]+=events
        for seq,row in enumerate(frame["events"]): row["seq"]=seq
        analyze.inspect_routes(frame,1)
        if identity==8: frame["end"]["call"]=call_snapshot(2)
        wave["frames"].append(source); frames.append(frame)
    return frames,wave,oracle


class ClearRoutingChecker(unittest.TestCase):
    def test_frozen_finite_dependency_identity(self):
        self.assertEqual(hashlib.sha256(analyze._finite_bytes).hexdigest(), analyze.FINITE_SHA)

    def test_crc_goldens(self):
        self.assertEqual(analyze.crc("0"*25,7),17)
        self.assertEqual(analyze.crc("00001011000100000101010101",6),59)

    def test_independent_matrix_72_unique_positions_and_reliabilities(self):
        positions = set()
        for i in range(72):
            data = "0"*i+"1"+"0"*(71-i); matrix, rel = analyze.matrix_for(data,[i%256 for i in range(36)])
            self.assertEqual(matrix.count("1"),1); positions.add(matrix.index("1"))
            self.assertEqual(rel[matrix.index("1")], i//2)
        self.assertEqual(len(positions),72)

    def test_full_common_and_detail_synthetic_measurement(self):
        audits=[]
        for enabled in (0,1):
            rows,trace,case,wave,oracle=full_fixture(enabled)
            audit=analyze.inspect_evidence(rows,trace,case,wave,oracle,enabled)
            self.assertTrue(audit["measurement_pass"]); self.assertTrue(audit["routing_pass"],audit["routing_issues"])
            self.assertEqual(len(audit["source_occurrences"]),4); audits.append(audit)
        self.assertEqual(audits[0]["semantic"],audits[1]["semantic"])

    def test_malformed_record_or_trace_fails_measurement(self):
        for mutation in ("duplicate", "missing_pop", "body_position", "profile", "frame_scope", "counter", "seq", "undefined"):
            rows,trace,case,wave,oracle=full_fixture()
            if mutation=="duplicate": next(r for r in rows if r["kind"]=="fec")["call_id"]=1
            elif mutation=="missing_pop": trace=trace[:-4]
            elif mutation=="body_position": next(r for r in rows if r["kind"]=="frame_end")["body_positions"][1]-=1
            elif mutation=="profile": next(r for r in rows if r["kind"]=="frame_begin")["sps"]=10
            elif mutation=="frame_scope": next(r for r in rows if r["kind"]=="synthesis")["frame"]=55
            elif mutation=="counter": rows[-1]["synthesis_calls"]+=1
            elif mutation=="seq": rows[3]["seq"]=99
            elif mutation=="undefined": next(r for r in rows if r["kind"]=="fec")["status"]=-1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                analyze.inspect_evidence(rows,trace,case,wave,oracle,1)

    def test_changed_synthesis_bits_are_quality_failure_not_hidden(self):
        frame,wave,oracle=frame_fixture(); frame["routes"][0]["synthesis"][0]["input49"]="1"+"0"*48
        result=quality(frame,wave,oracle)
        self.assertFalse(result["routing_pass"])
        self.assertTrue(any(x["reason"]=="clear_synthesis_input_changed_or_without_decode" for x in result["routing_issues"]))

    def test_negative_decoder_and_staged_pcm_never_certify_word(self):
        frame,wave,oracle=frame_fixture(); route=frame["routes"][0]
        route["fec"][0].update(status=-1,bits49=None,result=None); route["synthesis"]=[]
        frame["end"]["audio_indices"]=[999,999,999,999]
        self.assertFalse(quality(frame,wave,oracle)["routing_pass"])

    def test_substitution_flags_are_reported_without_speech_claim(self):
        frame,wave,oracle=frame_fixture()
        for flag in (4,8,16):
            frame["routes"][0]["synthesis"][0]["result_after"]["flags"]=flag
            result=quality(frame,wave,oracle)
            self.assertTrue(result["routing_pass"])
            self.assertIn("not intelligible speech",result["scope"])
            self.assertNotIn("speech_pass",result)

    def test_duplicate_occurrences_with_equal_bits_fail(self):
        frame,wave,oracle=frame_fixture(); frame["routes"][1]=copy.deepcopy(frame["routes"][0])
        self.assertFalse(quality(frame,wave,oracle)["routing_pass"])

    def test_half_steal_cannot_credit_swapped_or_stolen_slots(self):
        for permitted in ([2,3],[0,1]):
            frame,wave,oracle=frame_fixture()
            oracle["vectors"]["r1.dibits"]["transmitted_voice"]=[{"slot":i,"source_id":i} for i in permitted]
            self.assertFalse(quality(frame,wave,oracle)["routing_pass"])

    def test_source_position_before_bits_and_strict_phase_limit(self):
        frame,wave,oracle=frame_fixture()
        for delta in (-20,20):
            changed=copy.deepcopy(frame); changed["end"]["body_positions"]=[p+delta for p in changed["end"]["body_positions"]]
            self.assertIsNone(analyze.source_at(changed,wave,list(range(8))))
        wave["frames"].append({**wave["frames"][0],"ordinal":7})
        with self.assertRaisesRegex(ValueError,"Ambiguous"): analyze.source_at(frame,wave,list(range(8)))

    def test_partial_slot_synthesis_fails_finite_safety(self):
        frame,wave,oracle=frame_fixture()
        frame["classes"][73]="partial_eof"; frame["end"]["body_positions"][73]=0
        result=quality(frame,wave,oracle,"prefix_9999")
        self.assertFalse(result["finite_voice_safety_pass"])
        self.assertTrue(any(x["slot"]==0 for x in result["unsafe_synthesis"]))
        self.assertFalse(any(x["slot"]==0 for x in result["source_occurrences"]))

    def test_early_complete_slot_permitted_even_after_later_eof(self):
        frame,wave,oracle=frame_fixture(); frame["end"]["eof"]=1
        frame["classes"][74:]=["empty_after_eof"]*108
        frame["routes"]=frame["routes"][:1]
        result=quality(frame,wave,oracle,"prefix_10000")
        self.assertTrue(result["finite_voice_safety_pass"])
        self.assertEqual([v["slot"] for v in result["source_occurrences"]],[0])

    def test_stale_positions_cannot_override_unavailable_classes(self):
        frame,wave,oracle=frame_fixture(); frame["classes"][38]="empty_after_eof"
        self.assertIsNone(analyze.source_at(frame,wave,list(range(38,74))))

    def test_unconfirmed_route_fails_quality_even_with_final_confirmation(self):
        frame,wave,oracle=frame_fixture(); frame["routes"][0]["begin"]["confirmed"]=0
        self.assertFalse(quality(frame,wave,oracle)["routing_pass"])

    def test_source_crc_cannot_be_forged(self):
        frame,wave,oracle=frame_fixture(); frame["crcs"][0]["received"]^=1
        self.assertFalse(quality(frame,wave,oracle)["routing_pass"])

    def test_absent_single_weak_exposure_is_not_success(self):
        frame,wave,oracle=frame_fixture(); frame["source"]=None; frame["routes"]=[]; frame["events"]=[]
        self.assertFalse(quality(frame,wave,oracle,"single_weak")["negative_pass"])

    def test_single_weak_voice_is_quality_failure(self):
        frame,wave,oracle=frame_fixture(); frame["end"]["confirmed"]=0
        self.assertFalse(quality(frame,wave,oracle,"single_weak")["negative_pass"])

    def test_zero_voice_or_proof_is_quality_failure(self):
        frame,wave,oracle=frame_fixture()
        self.assertFalse(quality(frame,wave,oracle,"zero")["negative_pass"])

    def test_call_presence_honors_actual_epoch(self):
        analyze.validate_call({"call":None})
        with self.assertRaises(ValueError): analyze.validate_call({"call":{**call_snapshot(),"epoch":0}})
        with self.assertRaises(ValueError): analyze.validate_call({})

    def test_control_after_voice_is_rejected(self):
        rows,trace,case,wave,oracle=full_fixture()
        event=next(r for r in rows if r["kind"]=="crc"); rows.remove(event)
        index=next(i for i,r in enumerate(rows) if r["kind"]=="route_end")
        rows.insert(index+1,event)
        for seq,row in enumerate(rows): row["seq"]=seq
        with self.assertRaisesRegex(ValueError,"after voice"):
            analyze.inspect_evidence(rows,trace,case,wave,oracle,1)

    def test_parent_depth_and_input_order_are_verified(self):
        for change in ("parent","depth","input_order"):
            frame,_,_=frame_fixture()
            fec=next(r for r in frame["events"] if r["kind"]=="fec")
            if change=="parent": fec["parent_call_id"]=100
            elif change=="depth": fec["depth"]=2
            else: next(r for r in frame["events"] if r["kind"]=="fec_input")["seq"]=fec["seq"]+1
            with self.subTest(change=change),self.assertRaises(ValueError): analyze.inspect_routes(frame,1)

    def test_completed_nested_fallback_does_not_create_second_word(self):
        frame,_,_=frame_fixture(); original=frame["events"][:5]
        nested_input=copy.deepcopy(original[1]); nested_input.update(call_id=1,parent_call_id=0,depth=2,outer=0,mode="hard",reliability=None)
        nested_return=copy.deepcopy(original[2]); nested_return.update(call_id=1,parent_call_id=0,depth=2,outer=0,mode="hard")
        frame["events"]=original[:2]+[nested_input,nested_return]+original[2:]
        for seq,row in enumerate(frame["events"]): row["seq"]=seq
        routes=analyze.inspect_routes(frame,1)
        self.assertEqual(len(routes),1); self.assertEqual(len(routes[0]["fec"]),2)
        self.assertEqual(sum(x["outer"] for x in routes[0]["fec"]),1)

    def test_source_unknown_current_proof_is_quality_failure(self):
        frame,wave,oracle=frame_fixture(); wave["frames"]=[]; frame["source"]=frame["lich_source"]=None
        result=quality(frame,wave,oracle)
        self.assertFalse(result["routing_pass"])
        self.assertTrue(any(e["reason"]=="current_proof_without_complete_known_channel" for e in result["routing_issues"]))

    def test_primed_24_and_control_transition_quality(self):
        frames,wave,oracle=primed_quality_fixture()
        result=analyze.assess_frames(frames,wave,oracle,1,"primed")
        self.assertTrue(result["routing_pass"],result["routing_issues"])
        self.assertEqual(len(result["source_occurrences"]),24)
        self.assertEqual(len({x["source_id"] for x in result["source_occurrences"]}),20)

    def test_primed_header_exposure_trailer_and_identity_are_independent(self):
        for mutation in ("header","trailer","source","epoch","ran","missing"):
            frames,wave,oracle=primed_quality_fixture()
            if mutation=="header": frames[0]["end"]["value"]=1
            elif mutation=="trailer": frames[-1]["end"]["call"]["phase"]=1
            elif mutation=="source": frames[0]["end"]["call"]["source"]=999
            elif mutation=="epoch": frames[1]["routes"][0]["begin"]["call"]["epoch"]=2
            elif mutation=="ran": frames[1]["end"]["ran"]=0
            elif mutation=="missing": frames[1]["routes"].pop()
            with self.subTest(mutation=mutation):
                self.assertFalse(analyze.assess_frames(frames,wave,oracle,1,"primed")["routing_pass"])

    def test_complete_fixed_grid_can_pass(self):
        pairs,manifest=comparison_fixture(); result=analyze.compare(pairs,manifest)
        self.assertTrue(result["measurement_pass"]); self.assertTrue(result["progression_pass"])
        self.assertEqual(result["audited_invocations"],36); self.assertFalse(result["product_promotion"])

    def test_missing_grid_and_neutrality_fail_closed(self):
        for mutation in ("identity","role","common","chunk","trace"):
            pairs,manifest=comparison_fixture(); audit=pairs["primed-c37"][1]
            if mutation=="identity": pairs.pop("primed-c37")
            elif mutation=="role": pairs["primed-c37"].pop(0)
            elif mutation=="common": audit["semantic"]=[]
            elif mutation=="chunk": audit["chunk_semantic"]=[]
            elif mutation=="trace": audit["trace_sha256"]="wrong"
            result=analyze.compare(pairs,manifest)
            self.assertFalse(result["measurement_pass"]); self.assertFalse(result["progression_pass"])

    def test_validly_measured_quality_failure_is_not_measurement_failure(self):
        for key in ("routing_pass","negative_pass","finite_voice_safety_pass"):
            pairs,manifest=comparison_fixture(); pairs["primed-c37"][1][key]=False
            result=analyze.compare(pairs,manifest)
            self.assertTrue(result["measurement_pass"]); self.assertFalse(result["progression_pass"])

    def test_prefix_sum_shape_matches_hand_computed_edge(self):
        module=analyze._truth_module(); values=[x[0] for x in struct.iter_unpack("<f",module.shape([bytes(48)]))]
        self.assertEqual(len(values),5760)
        self.assertEqual(values[0],24000); self.assertEqual(values[19],6000); self.assertEqual(values[20],0)
        self.assertEqual(values[-1],8000)


if __name__ == "__main__": unittest.main()
