"""Registered active-boundary evidence gates; no receiver or encoder execution."""
import collections
import hashlib
from pathlib import Path
import types

ROOT = Path(__file__).resolve().parents[2]
BASE_PATH = ROOT / "experiments/nxdn_clear_routing_v1/analyze.py"
BASE_SHA = "6241cd1596f2a5b1ef87ce017e3083283cc12af43af2fed10bbcd5e5b7fe0009"
_base_bytes = BASE_PATH.read_bytes()
if hashlib.sha256(_base_bytes).hexdigest() != BASE_SHA:
    raise ValueError("Frozen common receiver evidence checker changed")
base = types.ModuleType("active_frozen_clear_evidence"); base.__file__ = str(BASE_PATH)
exec(compile(_base_bytes,str(BASE_PATH),"exec"),base.__dict__)
require = base.require
TRUTH_PATH = Path(__file__).with_name("source_truth.py")
_truth_bytes = TRUTH_PATH.read_bytes()
truth = types.ModuleType("active_boundary_truth"); truth.__file__ = str(TRUTH_PATH)
exec(compile(_truth_bytes,str(TRUTH_PATH),"exec"),truth.__dict__)
SCENARIOS = truth.NAMES
FLAGS = {"ERASURE":32,"REPEAT":64,"MUTE":128}


def good_call(call):
    return call is not None and ((call["phase"],call["protocol"],call["kind"],call["source"],call["target"],
        call["policy_target"],call["crypto"],call["algid"],call["kid"],call["audio_permitted"])
        == (1,28,2,901,1201,1201,1,0,0,1))


def exact_crcs(frame, oracle, source):
    """Final channel fields, not the callback's pre-note confirmation state."""
    expected = oracle["vectors"][source["vector"]]
    seen = [(r["channel"],r["part"]) for r in frame["crcs"]]
    if seen != [(1,0),(2,1),(2,2)]: return False
    for row in frame["crcs"]:
        control = expected["sacch" if row["channel"] == 1 else "facch"]
        if control is None or (row["bits"],row["computed"],row["received"]) != (
                control["information_bits"],control["computed_crc"],control["transmitted_crc"]): return False
    return True


def assess(audit, wave, oracle, enabled, scenario):
    """Additional source-position gates on already structurally checked events."""
    frames = audit["frames"]; exposure=[]; retention=[]; negative=[]
    def issue(target,reason,**extra): target.append({"reason":reason,**extra})
    def mapped(frame, ordinal, complete=False):
        source = frame["source"] if complete else frame["lich_source"]
        return source is not None and source["ordinal"] == ordinal and (not complete or frame["fully_sampled"])
    headers = [f for f in frames if mapped(f,0,True)]
    header = headers[0] if len(headers)==1 else None
    header_ok = header is not None and header.get("source_body_exact") is True and (
        header["end"]["value"],header["end"]["confirmed"],header["end"]["evidence"],header["end"]["proved"]
        ) == (2,1,2,1) and good_call(header["end"].get("call"))
    if enabled and header is not None:
        header_ok = header_ok and exact_crcs(header,oracle,header["source"])
        header_ok = header_ok and len(header["lich"])==1 and header["lich"][0]["result"]==1
    if not header_ok: issue(exposure,"complete_strong_clear_header_not_exposed")
    targets = [f for f in frames if mapped(f,1)]
    target = targets[0] if len(targets)==1 else None
    if target is None: issue(exposure,"unique_source_V0_LICH_not_exposed")
    elif header is None or header["end"]["seq"] >= target["begin"]["seq"]:
        issue(exposure,"source_V0_not_after_header")
    prior = header["end"].get("call") if header is not None else None
    expected = []
    if scenario.startswith("active_prefix_"):
        if target is not None:
            if (len(target["classes"]) != 182 or not any(c != "complete" for c in target["classes"])
                    or target.get("source_body_exact") is not True):
                issue(exposure,"source_V0_incomplete_body_not_exposed")
            if enabled and (len(target["lich"])!=1 or target["lich"][0]["reason"]!="accepted"
                            or target["lich"][0]["result"]!=1 or target["lich"][0]["full_lich"]!=0xae):
                issue(exposure,"source_V0_accepted_profile_not_exposed")
            for item in oracle["vectors"][target["lich_source"]["vector"]]["transmitted_voice"]:
                indices=list(range(38+36*item["slot"],74+36*item["slot"]))
                source=base.source_at(target,wave,list(range(8))+indices)
                if source is not None:
                    expected.append((source["ordinal"],item["slot"],item["source_id"]))
            if target["end"]["ran"] != 1: issue(retention,"eligible_V0_SACCH_RAN_not_one")
        else: issue(retention,"complete_slot_eligibility_unobserved")
    elif scenario=="active_bad_lich":
        if target is not None:
            rejected = len(target["classes"])==8 and target.get("source_body_exact") is True
            if enabled:
                rejected = rejected and len(target["lich"])==1 and (
                    target["lich"][0]["full_lich"],target["lich"][0]["reason"],target["lich"][0]["result"]
                    ) == (0xaf,"parity_reject",0)
            if not rejected: issue(exposure,"source_V0_parity_rejection_not_exposed")
            # Sticky confirmation and return 1 are explicitly permitted here.
            if target["end"]["value"]==2 or target["end"]["evidence"]!=0 or target["end"]["proved"]!=0:
                issue(negative,"rejected_V0_claims_current_proof")
            if target["routes"] or target["crcs"] or any(r["kind"] in ("voice_begin","mbe_begin","fec","synthesis") for r in target["events"]):
                issue(negative,"rejected_V0_processes_control_or_voice")
        else: issue(negative,"parity_restriction_unexposed")
        expected=[(s["ordinal"],v["slot"],v["source_id"]) for s in wave["frames"] if s["ordinal"]!=1
                  for v in oracle["vectors"][s["vector"]]["transmitted_voice"]]
        require(len(expected)==20,"Independent survivor oracle is not twenty occurrences")
        trailers=[f for f in frames if mapped(f,8,True)]
        trailer=trailers[0] if len(trailers)==1 else None
        final=trailer["end"].get("call") if trailer else None
        if (final is None or prior is None or trailer.get("source_body_exact") is not True or
                (final["epoch"],final["phase"],final["end_reason"],final["media_active"],final["audio_permitted"],
                 final["source"],final["target"],final["crypto"],final["algid"],final["kid"]) !=
                (prior["epoch"],2,3,0,0,901,1201,1,0,0)):
            issue(retention,"same_known_clear_epoch_not_terminated_by_source_trailer")
        if trailer is None or trailer["end"]["value"]!=2 or (enabled and not exact_crcs(trailer,oracle,trailer["source"])):
            issue(retention,"source_trailer_control_not_proved")
    else: raise ValueError("Unregistered active scenario")
    actual=[(o["ordinal"],o["slot"],o["source_id"]) for o in audit["source_occurrences"]]
    if actual!=expected or not all(o["exact"] for o in audit["source_occurrences"]):
        issue(retention,"complete_source_occurrence_retention_differs",expected=[list(v) for v in expected],actual=[list(v) for v in actual])
    for frame in frames:
        for route in frame["routes"]:
            if route.get("source") is None: continue
            call=route["begin"].get("call")
            if not good_call(call) or prior is None or call["epoch"]!=prior["epoch"]:
                issue(retention,"source_owned_route_lost_known_clear_epoch",frame=frame["begin"]["frame"],slot=route["begin"]["slot"])
    flags=collections.Counter()
    for frame in frames:
        for route in frame["routes"]:
            for row in route["synthesis"]:
                if row["result_after"] is not None: flags[row["result_after"]["flags"]]+=1
    return {"exposure_pass":not exposure,"retention_pass":not retention,"negative_pass":not negative,
            "exposure_issues":exposure,"retention_issues":retention,"negative_issues":negative,
            "expected_complete_occurrences":[list(v) for v in expected],
            "synthesis_flags":{str(value):count for value,count in sorted(flags.items())},"substitution_counts":{name:sum(n for value,n in flags.items() if value&mask) for name,mask in FLAGS.items()},
            "scope":"finite discriminator source ownership and exact FEC/synthesis input; status/flags do not certify intelligible speech or playback"}


def validate_inputs(inputs):
    raw=truth.read_file(inputs,"manifest.json"); manifest=truth.strict_json(raw)
    require(hashlib.sha256(Path(__file__).with_name("prepare.py").read_bytes()).hexdigest()==manifest["generator_sha256"],"Frozen input preparer changed")
    truth.verify(inputs,manifest,base)
    return manifest


def inspect(rows,trace_path,case,manifest,inputs,enabled):
    require(case in manifest["cases"] and manifest["cases"]==truth.expected_cases(),"Unregistered invocation")
    require(enabled in (0,1),"Invalid detail role")
    _,oracle=truth.parent_truth(inputs,base)
    wave=manifest["waveforms"][case["waveform"]]
    audit=base.inspect_evidence(rows,Path(trace_path).read_bytes(),case,wave,oracle,enabled)
    audit.update(assess(audit,wave,oracle,enabled,case["configuration"]))
    return audit


def compare(pairs,manifest):
    measurement=[]; quality=[]; normalized={}
    expected_list=truth.expected_cases(); expected={c["id"]:c for c in expected_list}
    if manifest.get("cases")!=expected_list or set(pairs)!=set(expected):
        measurement.append({"reason":"incomplete_or_changed_registered_grid"})
    keys=("routing_pass","exposure_pass","retention_pass","negative_pass","finite_voice_safety_pass")
    gates={k:True for k in keys}
    for cid,case in expected.items():
        values=pairs.get(cid,{})
        if len(values)!=2 or {str(k) for k in values}!={"0","1"}:
            measurement.append({"reason":"missing_detail_pair","id":cid}); continue
        roles={int(k):v for k,v in values.items()}; normalized[cid]=roles
        for detail,audit in roles.items():
            if audit.get("case")!=case or audit.get("summary",{}).get("observed")!=detail or audit.get("measurement_pass") is not True:
                measurement.append({"reason":"audit_identity_or_integrity","id":cid})
            for key in keys: gates[key] &= audit.get(key) is True
            for name in ("routing_issues","exposure_issues","retention_issues","negative_issues"):
                quality.extend({**e,"id":cid,"observed":detail} for e in audit.get(name,[]))
            quality.extend({"reason":"unavailable_voice_interval_synthesized","id":cid,"observed":detail,**e} for e in audit.get("unsafe_synthesis",[]))
        if roles[0].get("semantic")!=roles[1].get("semantic"):
            measurement.append({"reason":"detail_changed_common_outcomes","id":cid})
    for name in SCENARIOS:
        ids=[f"{name}-c{c}" for c in (37,512)]
        if not all(cid in normalized for cid in ids):
            measurement.append({"reason":"missing_chunk_pair","configuration":name}); continue
        for detail in (0,1):
            a,b=[normalized[cid][detail] for cid in ids]
            if a.get("chunk_semantic")!=b.get("chunk_semantic") or a.get("trace_sha256")!=b.get("trace_sha256"):
                measurement.append({"reason":"chunk_outcomes_or_trace_changed","configuration":name,"observed":detail})
    measured=not measurement
    return {"measurement_pass":measured,**gates,"progression_pass":bool(measured and all(gates.values())),
            "product_promotion":False,"expected_invocations":16,"audited_invocations":sum(map(len,normalized.values())),
            "measurement_issues":measurement,"quality_issues":quality,"issues":measurement+quality,
            "scope":"registered finite-input ownership; no accepted-speech metric or product promotion"}
