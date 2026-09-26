"""Synthetic checker controls only: no receiver or generator execution."""
import collections
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import types
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("active_boundary_analyze",HERE/"analyze.py")
a=importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
OLD_TEST_PATH=HERE.parent/"nxdn_clear_routing_v1/test_analyze.py"
old_bytes=OLD_TEST_PATH.read_bytes()
if hashlib.sha256(old_bytes).hexdigest()!="ceab4c4e85ea11b5775a77a7e07add8552dc0803e9afb54d6a8a3b99cc44196d":
    raise ValueError("Frozen synthetic fixture source changed")
fixtures=types.ModuleType("frozen_clear_synthetic_fixtures"); fixtures.__file__=str(OLD_TEST_PATH)
exec(compile(old_bytes,str(OLD_TEST_PATH),"exec"),fixtures.__dict__)


def prepared_frames():
    """Synthetic named-field fixtures, not claims of independently encoded FEC."""
    frames,wave,oracle=fixtures.primed_quality_fixture()
    for n,frame in enumerate(frames):
        source=frame["lich_source"]
        source["ordinal"]-=1; source["start"]-=3840; source["end"]-=3840
        frame["end"]["body_positions"]=[p-3840 for p in frame["end"]["body_positions"]]
        frame["begin"]["seq"]=500*n
        frame["end"].update(seq=500*n+400,evidence=2,proved=1,confirmed=1)
        frame["lich"][0].update(reason="accepted",result=1)
        if n in (0,8):
            info="0"*80; crc=a.base.crc(info,12)
            oracle["vectors"][source["vector"]]["facch"]={"information_bits":info,"computed_crc":crc,"transmitted_crc":crc}
            frame["crcs"] += [{"kind":"crc","channel":2,"part":part,"bits":info,"computed":crc,"received":crc} for part in (1,2)]
    wave["samples"]=36480
    return frames,wave,oracle


def prefix_fixture(cut=6160):
    frames,wave,oracle=prepared_frames(); frames=frames[:2]; wave["samples"]=cut
    frame=frames[1]; committed=(cut-4680)//20; partial=(cut-4680)%20
    frame["classes"]=["complete"]*committed+(["partial_eof"] if partial else [])
    frame["classes"] += ["empty_after_eof"]*(182-len(frame["classes"]))
    frame["fully_sampled"]=False; frame["source"]=None
    frame["end"].update(eof=1,evidence=1,proved=1)
    for i in range(committed,182): frame["end"]["body_positions"][i]=0
    for i,call in enumerate(frame["end"]["body_calls"]):
        call.update(before=min(cut,4680+20*i),after=min(cut,4700+20*i),
                    eof_before=int(4680+20*i>=cut),eof_after=int(i>=committed),
                    symbol_before=234+min(i,committed),symbol_after=234+min(i+1,committed))
    # This safe synthetic observation only routes slots with complete input.
    frame["routes"]=[r for r in frame["routes"] if 74+36*r["begin"]["slot"]<=committed]
    for route in frame["routes"]:
        route["begin"]["eof"]=1
    return frames,wave,oracle


def bad_fixture():
    frames,wave,oracle=prepared_frames(); frame=frames[1]; source=frame["lich_source"]
    original=source["vector"]; changed="r1_bad_lich.dibits"
    oracle["vectors"][changed]={**copy.deepcopy(oracle["vectors"][original]),"full_lich":0xaf,"parity_valid":False}
    vector=bytearray(oracle["dibits"][original]); vector[17]^=2; oracle["dibits"][changed]=bytes(vector)
    source["vector"]=changed
    frame["end"].update(body="".join(map(str,vector[10:18])),body_count=8,
                        body_positions=frame["end"]["body_positions"][:8],body_calls=frame["end"]["body_calls"][:8],
                        value=1,evidence=0,proved=0,confirmed=1)
    frame["classes"]=["complete"]*8; frame["fully_sampled"]=False
    frame["lich"][0].update(full_lich=0xaf,reason="parity_reject",result=0)
    frame["routes"]=[]; frame["crcs"]=[]; frame["events"]=[]
    return frames,wave,oracle


def quality(values,scenario):
    frames,wave,oracle=values
    audit={"frames":frames,**a.base.assess_frames(frames,wave,oracle,1,scenario)}
    return {**audit,**a.assess(audit,wave,oracle,1,scenario)}


def comparison_fixture():
    cases=a.truth.expected_cases(); pairs={}
    for case in cases:
        pairs[case["id"]]={detail:{"case":case,"summary":{"observed":detail},"measurement_pass":True,
            "semantic":[{"common":1}],"chunk_semantic":[{"common":1}],"trace_sha256":str(detail),
            "routing_pass":True,"exposure_pass":True,"retention_pass":True,"negative_pass":True,
            "finite_voice_safety_pass":True,"routing_issues":[],"exposure_issues":[],"retention_issues":[],
            "negative_issues":[],"unsafe_synthesis":[]} for detail in (0,1)}
    return pairs,{"cases":cases}


class ActiveBoundaryChecker(unittest.TestCase):
    def test_frozen_common_source_identities(self):
        self.assertEqual(hashlib.sha256(a._base_bytes).hexdigest(),a.BASE_SHA)
        self.assertEqual(hashlib.sha256(a.base._finite_bytes).hexdigest(),a.base.FINITE_SHA)

    def test_frozen_structural_checks_still_run(self):
        rows,trace,case,wave,oracle=fixtures.full_fixture()
        self.assertTrue(a.base.inspect_evidence(rows,trace,case,wave,oracle,1)["measurement_pass"])
        rows[-1]["synthesis_calls"]+=1
        with self.assertRaises(ValueError): a.base.inspect_evidence(rows,trace,case,wave,oracle,1)

    def test_three_active_prefix_controls(self):
        for cut,count in ((6159,0),(6160,1),(6161,1)):
            result=quality(prefix_fixture(cut),f"active_prefix_{cut}")
            with self.subTest(cut=cut):
                for key in ("routing_pass","exposure_pass","retention_pass","negative_pass","finite_voice_safety_pass"):
                    self.assertTrue(result[key],(key,result))
                self.assertEqual(len(result["source_occurrences"]),count)

    def test_complete_early_slot_survives_later_eof(self):
        values=prefix_fixture(); self.assertEqual(values[0][1]["end"]["eof"],1)
        result=quality(values,"active_prefix_6160")
        self.assertEqual(result["expected_complete_occurrences"],[[1,0,0]])
        self.assertTrue(result["retention_pass"] and result["finite_voice_safety_pass"])

    def test_all_frame_abort_loses_complete_early_slot(self):
        values=prefix_fixture(); values[0][1]["routes"]=[]
        result=quality(values,"active_prefix_6160")
        self.assertFalse(result["retention_pass"]); self.assertTrue(result["finite_voice_safety_pass"])

    def test_partial_or_empty_synthesis_is_unsafe_despite_returned_bits(self):
        for cut,slot in ((6159,0),(6160,1),(6161,1)):
            values=prefix_fixture(cut); complete=prepared_frames()[0][1]
            values[0][1]["routes"].append(copy.deepcopy(complete["routes"][slot]))
            result=quality(values,f"active_prefix_{cut}")
            self.assertFalse(result["finite_voice_safety_pass"])
            self.assertTrue(any(r["slot"]==slot for r in result["unsafe_synthesis"]))

    def test_returned_positions_cannot_supply_missing_samples(self):
        values=prefix_fixture(6159); frame=values[0][1]
        frame["end"]["body_positions"][73]=6160
        self.assertIsNone(a.base.source_at(frame,values[1],list(range(38,74))))

    def test_missing_header_or_V0_exposure_is_not_success(self):
        for remove in (0,1):
            values=prefix_fixture(); values[0].pop(remove)
            self.assertFalse(quality(values,"active_prefix_6160")["exposure_pass"])

    def test_strong_clear_header_is_required(self):
        for field,value in (("value",1),("evidence",1),("proved",0),("confirmed",0)):
            values=prefix_fixture(); values[0][0]["end"][field]=value
            self.assertFalse(quality(values,"active_prefix_6160")["exposure_pass"])
        values=prefix_fixture(); values[0][0]["end"]["call"]["source"]=902
        self.assertFalse(quality(values,"active_prefix_6160")["exposure_pass"])

    def test_header_CRC_and_actual_order_are_required(self):
        values=prefix_fixture(); values[0][0]["crcs"][1]["computed"]^=1
        self.assertFalse(quality(values,"active_prefix_6160")["exposure_pass"])
        values=prefix_fixture(); values[0][1]["begin"]["seq"]=0
        self.assertFalse(quality(values,"active_prefix_6160")["exposure_pass"])

    def test_frame_wide_full_input_is_not_an_active_EOF_control(self):
        frames,wave,oracle=prepared_frames()
        self.assertFalse(quality((frames[:2],wave,oracle),"active_prefix_6160")["exposure_pass"])

    def test_sticky_rejected_return_one_is_allowed_without_fresh_proof(self):
        result=quality(bad_fixture(),"active_bad_lich")
        for key in ("routing_pass","exposure_pass","retention_pass","negative_pass","finite_voice_safety_pass"):
            self.assertTrue(result[key],(key,result))
        self.assertEqual(len(result["source_occurrences"]),20)

    def test_rejected_current_proof_or_voice_fails(self):
        for mutation in ("proof","voice"):
            values=bad_fixture(); target=values[0][1]
            if mutation=="proof": target["end"].update(value=2,evidence=1,proved=1)
            else: target["routes"]=[copy.deepcopy(prepared_frames()[0][1]["routes"][0])]
            self.assertFalse(quality(values,"active_bad_lich")["negative_pass"])

    def test_unexposed_parity_rejection_is_failure(self):
        values=bad_fixture(); values[0][1]["lich_source"]=None
        result=quality(values,"active_bad_lich")
        self.assertFalse(result["exposure_pass"]); self.assertFalse(result["negative_pass"])

    def test_subsequent_clean_loss_and_epoch_change_fail(self):
        for change in ("loss","epoch","trailer","ran"):
            values=bad_fixture()
            if change=="loss": values[0][2]["routes"].pop()
            elif change=="epoch": values[0][2]["routes"][0]["begin"]["call"]["epoch"]=2
            elif change=="trailer": values[0][-1]["end"]["call"]["end_reason"]=0
            else:
                values=prefix_fixture(); values[0][1]["end"]["ran"]=0
            self.assertFalse(quality(values,"active_prefix_6160" if change=="ran" else "active_bad_lich")["retention_pass"])

    def test_trailer_requires_actual_control_proof_not_only_call_fields(self):
        for change in ("proof","missing_crc","wrong_crc"):
            values=bad_fixture(); trailer=values[0][-1]
            if change=="proof": trailer["end"]["value"]=1
            elif change=="missing_crc": trailer["crcs"].pop()
            else: trailer["crcs"][-1]["received"]^=1
            self.assertFalse(quality(values,"active_bad_lich")["retention_pass"])

    def test_common_mode_exposure_uses_real_body_not_absent_detail(self):
        for scenario,values in (("active_prefix_6160",prefix_fixture()),("active_bad_lich",bad_fixture())):
            frames,wave,oracle=values
            for frame in frames:
                frame["lich"]=[]; frame["crcs"]=[]
            audit={"frames":frames,**a.base.assess_frames(frames,wave,oracle,0,scenario)}
            result=a.assess(audit,wave,oracle,0,scenario)
            self.assertTrue(result["exposure_pass"] and result["retention_pass"] and result["negative_pass"])

    def test_new_diagnostics_are_json_round_trip_stable(self):
        values=prefix_fixture(); values[0][1]["routes"]*=2
        frames,wave,oracle=values
        audit={"frames":frames,**a.base.assess_frames(frames,wave,oracle,1,"active_prefix_6160")}
        result=a.assess(audit,wave,oracle,1,"active_prefix_6160")
        self.assertEqual(result,json.loads(json.dumps(result,allow_nan=False)))

    def test_equal_bit_duplicates_cannot_replace_missing_occurrence(self):
        values=bad_fixture(); values[0][2]["routes"][1]=copy.deepcopy(values[0][2]["routes"][0])
        result=quality(values,"active_bad_lich")
        self.assertFalse(result["routing_pass"]); self.assertFalse(result["retention_pass"])

    def test_changed_FEC_or_synthesis_bits_cannot_reidentify_source(self):
        for key in ("fec","synthesis"):
            values=prefix_fixture(); route=values[0][1]["routes"][0]
            route[key][0]["bits49" if key=="fec" else "input49"]="1"+"0"*48
            result=quality(values,"active_prefix_6160")
            self.assertFalse(result["routing_pass"]); self.assertFalse(result["retention_pass"])

    def test_actual_substitution_masks_are_reported_not_speech_acceptance(self):
        self.assertEqual(a.FLAGS,{"ERASURE":32,"REPEAT":64,"MUTE":128})
        for flag in (3,35,67,131,227):
            values=prefix_fixture(); values[0][1]["routes"][0]["synthesis"][0]["result_after"]["flags"]=flag
            result=quality(values,"active_prefix_6160")
            self.assertTrue(result["retention_pass"])
            self.assertEqual(result["substitution_counts"],{name:int(bool(flag&mask)) for name,mask in a.FLAGS.items()})
            self.assertNotIn("speech_pass",result); self.assertIn("do not certify intelligible speech",result["scope"])

    def test_flags_do_not_repair_missing_source_or_incorrect_bits(self):
        for flag in (32,64,128):
            values=prefix_fixture(6159); route=copy.deepcopy(prepared_frames()[0][1]["routes"][0])
            route["synthesis"][0]["result_after"]["flags"]=flag; values[0][1]["routes"]=[route]
            self.assertFalse(quality(values,"active_prefix_6159")["finite_voice_safety_pass"])

    def test_strict_source_phase_and_ambiguous_identity(self):
        for delta in (-20,20):
            values=prefix_fixture(); frame=values[0][1]
            frame["end"]["body_positions"]=[p+delta if p else p for p in frame["end"]["body_positions"]]
            self.assertIsNone(a.base.source_at(frame,values[1],list(range(8))))
        values=prefix_fixture(); values[1]["frames"].append(copy.deepcopy(values[1]["frames"][1]))
        with self.assertRaisesRegex(ValueError,"Ambiguous"): a.base.source_at(values[0][1],values[1],list(range(8)))

    def test_fixed_grid_and_no_product_promotion(self):
        pairs,manifest=comparison_fixture(); result=a.compare(pairs,manifest)
        self.assertTrue(result["measurement_pass"] and result["progression_pass"])
        self.assertEqual(result["audited_invocations"],16); self.assertFalse(result["product_promotion"])

    def test_grid_and_neutrality_corruption_fail_measurement(self):
        for mutation in ("missing","duplicate","detail","common","chunk","trace"):
            pairs,manifest=comparison_fixture(); cid=manifest["cases"][0]["id"]; audit=pairs[cid][1]
            if mutation=="missing": pairs.pop(cid)
            elif mutation=="duplicate": manifest["cases"]=manifest["cases"]+[manifest["cases"][0]]
            elif mutation=="detail": pairs[cid].pop(0)
            elif mutation=="common": audit["semantic"]=[]
            elif mutation=="chunk": audit["chunk_semantic"]=[]
            else: audit["trace_sha256"]="changed"
            result=a.compare(pairs,manifest)
            self.assertFalse(result["measurement_pass"]); self.assertFalse(result["progression_pass"])

    def test_receiver_failure_is_valid_measurement(self):
        for key in ("exposure_pass","retention_pass","negative_pass","finite_voice_safety_pass","routing_pass"):
            pairs,manifest=comparison_fixture(); pairs[manifest["cases"][0]["id"]][1][key]=False
            result=a.compare(pairs,manifest)
            self.assertTrue(result["measurement_pass"]); self.assertFalse(result["progression_pass"])

    def test_json_rejects_ambiguous_or_nonfinite_input(self):
        for raw in ('{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}'):
            with self.assertRaises(ValueError): a.truth.strict_json(raw)

    def test_independent_shaping_edges_and_length(self):
        data=a.truth.shape_dibits([bytes(192)]); values=[v[0] for v in struct.iter_unpack("<f",data)]
        self.assertEqual(len(values),5760)
        self.assertEqual([values[i] for i in (0,19,20,-1)],[24000,6000,0,8000])

    def test_parity_bit_changes_only_declared_pre_shaping_dibit(self):
        frames=[bytes(192) for _ in range(9)]
        changed=bytearray(frames[1]); changed[17]^=2
        self.assertEqual([i for i,(old,new) in enumerate(zip(frames[1],changed)) if old!=new],[17])
        altered=frames[:]; altered[1]=bytes(changed)
        before=a.truth.shape_dibits(frames); after=a.truth.shape_dibits(altered)
        old=[v[0] for v in struct.iter_unpack("<f",before)]; new=[v[0] for v in struct.iter_unpack("<f",after)]
        affected=[i for i,(x,y) in enumerate(zip(old,new)) if x!=y]
        start=4480+17*20
        self.assertEqual(affected,list(range(start-3,start+24)))

    def test_source_reader_rejects_escape_missing_and_bad_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/"inputs"; root.mkdir(); (root/"sample").write_bytes(b"fixed")
            digest=hashlib.sha256(b"fixed").hexdigest()
            self.assertEqual(a.truth.read_file(root,"sample",digest),b"fixed")
            for name,pin in (("../sample",None),("missing",None),("sample","0"*64)):
                with self.assertRaises(ValueError): a.truth.read_file(root,name,pin)


if __name__=="__main__": unittest.main()
