"""Independent finite-input reconstruction; no generator or receiver imports."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import types

ROOT = Path(__file__).resolve().parents[2]
PARENT_SHA = "6ca26a31598d8bb9d701bb9f6eba19d783de7e00a3e0730be2ccd3f0b20b12eb"
REPORT_SHA = "50a7dbb4b33200e203e102f58195110abedf6159ce02b66b551ebb2c65b74ab0"
INDEX_SHA = "6d9c5b08482f37e30d15893f3a2c517c36f280a9ce6dcae6e11749505416236a"
COLD_SHA = "187ec959f1d3fb81b7fa4f35df7a118eab7a50dca9677ef6bdacae06aa9657c8"
TRUTH_SHA = "28f92b0a021a971d355085fd3876d25e5e055e7bdf31dee714b562cd385d47ea"
NAMES = ("active_prefix_6159", "active_prefix_6160", "active_prefix_6161", "active_bad_lich")


def need(ok, message):
    if not ok: raise ValueError(message)


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, "Duplicate JSON key")
            out[key] = value
        return out
    def invalid(value): raise ValueError("Nonfinite JSON number: " + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def read_file(root, name, digest=None):
    root = Path(root).resolve(); path = (root / name).resolve()
    need(path.is_relative_to(root) and path.is_file(), "Missing/escaped input: " + name)
    raw = path.read_bytes()
    if digest is not None: need(hashlib.sha256(raw).hexdigest() == digest, "Input identity changed: " + name)
    return raw


def parent_truth(inputs, base):
    path = ROOT / "experiments/nxdn_clear_routing_v1/source_truth.py"
    raw = path.read_bytes(); need(hashlib.sha256(raw).hexdigest() == TRUTH_SHA, "Frozen parent truth changed")
    helper = types.ModuleType("active_frozen_parent_truth"); helper.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), helper.__dict__)
    manifest = strict_json(read_file(inputs, "parent/manifest.json", PARENT_SHA))
    return manifest, helper.verify(Path(inputs) / "parent", manifest, base.crc)


def shape_dibits(frames):
    """Prefix-sum reconstruction, separately expressed from the new preparer."""
    level = {0: 8000, 1: 24000, 2: -8000, 3: -24000}
    symbols = list((1, 3) * 16)
    for frame in frames:
        need(len(frame) == 192 and all(d in level for d in frame), "Bad independent frame dimensions")
        symbols.extend(frame)
    raw = [level[d] for d in symbols for _ in range(20)] + [8000] * 1280
    padded = [raw[0]] * 4 + raw + [raw[-1]] * 3
    sums = [0]
    for value in padded: sums.append(sums[-1] + value)
    return b"".join(struct.pack("<f", (sums[i+8] - sums[i]) / 8) for i in range(len(raw)))


def expected_cases():
    return [{"id": f"{name}-c{chunk}", "configuration": name, "waveform": name, "chunk": chunk, "fast": 1}
            for name in NAMES for chunk in (37, 512)]


def verify(inputs, manifest, base, verify_anchors=True):
    inputs = Path(inputs)
    need((manifest["schema"], manifest["kind"], manifest["domain"], manifest["rate_hz"], manifest["samples_per_symbol"])
         == (1, "nxdn_active_boundaries_v1", "discriminator_samples", 48000, 20), "Registered domain changed")
    need(manifest["registration_commit"] == "b3a8cee4608db93ba3bc446281ed1ded954a6270"
         and manifest["source_baseline"] == "acb52828842050986ab95e4ab25b270d227561e1"
         and manifest["receiver_sha256"] == "6682f833c9c9a9ec23b596af2c8fe3f176de28134a90f3f487e8ab996b464704",
         "Registered identity changed")
    need(manifest["cases"] == expected_cases() and set(manifest["waveforms"]) == set(NAMES), "Registered grid changed")
    old, oracle = parent_truth(inputs, base)
    report = strict_json(read_file(inputs, "parent-report.json", REPORT_SHA))
    read_file(inputs, "parent-publication.json", INDEX_SHA)
    need(report["measurement_pass"] is True and report["preservation_pass"] is True
         and report["progression_pass"] is False, "Prior failed outcome changed")
    reference_hashes = {"parent-report.json": REPORT_SHA, "parent-publication.json": INDEX_SHA}
    for source, digest in report["files"].items():
        source = source.replace("\\", "/")
        if source.startswith("inputs/"): reference_hashes["parent/" + source[7:]] = digest
        elif any(source.startswith(f"runs/cold_fast-c{chunk}/{detail}/") for chunk in (37,512) for detail in (0,1)):
            reference_hashes["anchors/" + source[5:]] = digest
    need(set(manifest["reference_files"]) == set(reference_hashes), "Copied reference inventory changed")
    for name, digest in reference_hashes.items():
        raw = read_file(inputs, name, digest)
        need(manifest["reference_files"][name] == {"bytes": len(raw), "sha256": digest}, "Reference metadata changed")
    cold = read_file(inputs, "parent/cold.f32le", COLD_SHA)
    bad = [oracle["dibits"][f"r{i}.dibits"] for i in range(9)]
    changed = bytearray(bad[1]); changed[17] ^= 2
    need(bytes(changed) == oracle["dibits"]["r1_bad_lich.dibits"], "Parity vector changed more than bit 34")
    bad[1] = bytes(changed)
    waves = {f"active_prefix_{cut}": cold[:cut*4] for cut in (6159,6160,6161)}
    waves["active_bad_lich"] = shape_dibits(bad)
    for name, expected in waves.items():
        wave = manifest["waveforms"][name]; count = len(expected)//4
        need(wave["file"] == name+".f32le" and wave["samples"] == count and wave["scenario"] == name, "Wave identity changed")
        need(read_file(inputs, wave["file"], wave["sha256"]) == expected, "Independent waveform reconstruction differs")
        need(wave["lineage_file"] == name+".origin.u32le" and wave["occurrence_file"] == name+".occurrence.u32le", "Lineage filename changed")
        need(read_file(inputs, wave["lineage_file"], wave["lineage_sha256"]) == b"".join(struct.pack("<I",i) for i in range(count)), "Source lineage changed")
        need(read_file(inputs, wave["occurrence_file"], wave["occurrence_sha256"]) == bytes(count*4), "Source occurrence changed")
        need((wave["original_file"],wave["original_sha256"],wave["original_samples"]) == ("parent/cold.f32le",COLD_SHA,36480), "Parent identity changed")
        frames = copy.deepcopy(old["waveforms"]["cold"]["frames"])
        if name == "active_bad_lich":
            frames[1].update(vector="r1_bad_lich.dibits",sha256=oracle["vectors"]["r1_bad_lich.dibits"]["sha256"])
        need(wave["frames"] == frames, "Canonical full parent oracle changed")
        edit = {"kind":"lich_parity_before_shaping","frame_ordinal":1,"full_frame_bit":34} if name == "active_bad_lich" else {"kind":"prefix","cut":count}
        need(wave["edit"] == edit, "Registered transformation changed")
    if verify_anchors:
        anchors = {}
        for chunk in (37,512):
            anchors[chunk] = {}
            for detail in (0,1):
                stem = f"anchors/cold_fast-c{chunk}/{detail}/"
                need(strict_json(read_file(inputs,stem+"process.json"))["exit_code"] == 0, "Archived anchor did not exit successfully")
                rows = [strict_json(line) for line in read_file(inputs,stem+"events.jsonl").splitlines()]
                case = next(c for c in old["cases"] if c["id"] == f"cold_fast-c{chunk}")
                a = base.inspect_evidence(rows,read_file(inputs,stem+"pops.u32le"),case,old["waveforms"]["cold"],oracle,detail)
                wanted = [(s["ordinal"],v["slot"],v["source_id"]) for s in old["waveforms"]["cold"]["frames"] for v in oracle["vectors"][s["vector"]]["transmitted_voice"]]
                actual = [(o["ordinal"],o["slot"],o["source_id"]) for o in a["source_occurrences"]]
                need(a["measurement_pass"] and a["routing_pass"] and a["finite_voice_safety_pass"] and actual == wanted and len(actual) == 24, "Archived 24-word anchor changed")
                anchors[chunk][detail] = a
            need(anchors[chunk][0]["semantic"] == anchors[chunk][1]["semantic"], "Archived callback neutrality changed")
        for detail in (0,1):
            need(anchors[37][detail]["chunk_semantic"] == anchors[512][detail]["chunk_semantic"]
                 and anchors[37][detail]["trace_sha256"] == anchors[512][detail]["trace_sha256"], "Archived chunk neutrality changed")
    return oracle
