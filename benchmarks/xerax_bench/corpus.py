"""Deterministic, local-only impairment generation; originals are never modified."""
import array
import cmath
import copy
import math
import random
import shutil
import sys
import wave
from pathlib import Path
from .model import digest, load_corpus, read_json, write_json

FIXTURES = [
    ("p25p1_c4fm_cc", "p25_c4fm", "NAC/CC: 140", "derived_off_air_iq"),
    ("p25p1_cqpsk_cc", "p25_cqpsk", "WACN: 92065; SYS: 0D5", "derived_off_air_iq"),
    ("p25p2_cc", "p25p2", "P25p2 SACCH", "remodulated_discriminator"),
    ("dmr_voice", "dmr", r"Color Code[=: ]+0?2", "remodulated_discriminator"),
    ("nxdn48", "nxdn48", r"Src=\s*0*901\b", "derived_off_air_iq"),
    ("nxdn96", "nxdn96", r"RAN\s+0+\b", "derived_off_air_iq"),
]
SCENARIOS = {
    "clean": {},
    "awgn20": {"snr_db": 20},
    "awgn10": {"snr_db": 10},
    "awgn0": {"snr_db": 0},
    "offset": {"frequency_offset_hz": 300},
    "echo": {"echo_amplitude": 0.55, "echo_delay_samples": 3, "echo_phase_rad": 0.7},
    "clock": {"clock_ppm": 100},
    "dropout": {"gap_start_fraction": 0.4, "gap_duration_s": 0.04},
    "adjacent": {"interferer_offset_hz": 12500, "interferer_amplitude": 0.8},
    "cochannel": {"interferer_offset_hz": 0, "interferer_amplitude": 0.8},
    "traffic": {"repeat": 4},
}
TRANSMISSION = r"(FRAME (?:AMBE|IMBE)|Src=\s*\d+|NAC/CC:|WACN:|Color Code[=:]|P25p2 SACCH)"


def impair(data, rate, params, seed):
    if not params:
        return data, {"clipped_components": 0, "transform": "identity"}
    x = [complex(data[i] - 127.5, data[i + 1] - 127.5) for i in range(0, len(data), 2)]
    power = sum(abs(v) ** 2 for v in x) / len(x)
    rng = random.Random(seed)
    sigma = math.sqrt(power / (2 * 10 ** (params["snr_db"] / 10))) if "snr_db" in params else 0
    scale = 1 + params.get("echo_amplitude", 0) + params.get("interferer_amplitude", 0)
    phase_step = cmath.exp(2j * math.pi * params.get("frequency_offset_hz", 0) / rate)
    int_step = cmath.exp(2j * math.pi * params.get("interferer_offset_hz", 0) / rate)
    phase = int_phase = 1 + 0j
    echo = params.get("echo_amplitude", 0) * cmath.exp(1j * params.get("echo_phase_rad", 0))
    delay = params.get("echo_delay_samples", 0)
    clock_ratio = 1 + params.get("clock_ppm", 0) / 1e6
    start = int(len(x) * params.get("gap_start_fraction", 2))
    stop = start + int(rate * params.get("gap_duration_s", 0))
    result = bytearray()
    clipped = 0
    for n in range(len(x)):
        pos = n * clock_ratio
        index = min(int(pos), len(x) - 1)
        frac = pos - int(pos)
        value = x[index] * (1 - frac) + x[min(index + 1, len(x) - 1)] * frac
        if n >= delay:
            value += echo * x[n - delay]
        if "interferer_amplitude" in params:
            # A delayed independent segment of the same recording: interference
            # stress, not ground truth for two independently identified calls.
            value += params["interferer_amplitude"] * x[(n + len(x) // 3) % len(x)] * int_phase
        value *= phase
        if sigma:
            value += complex(rng.gauss(0, sigma), rng.gauss(0, sigma))
        value /= scale
        if start <= n < stop:
            value = 0j  # erasure preserving sample time, not a hardware drop claim
        for component in (value.real, value.imag):
            quantized = round(component + 127.5)
            clipped += int(quantized < 0 or quantized > 255)
            result.append(max(0, min(255, quantized)))
        phase *= phase_step
        int_phase *= int_step
        if n % 4096 == 4095:
            phase /= abs(phase)
            int_phase /= abs(int_phase)
    result *= params.get("repeat", 1)
    return bytes(result), {"clipped_components": clipped * params.get("repeat", 1),
                           "snr_reference": "source total sample power, including original noise",
                           "seed": seed, **params}


def synthetic(rate, seconds, seed, mode):
    rng = random.Random(seed)
    result = bytearray()
    phase = 0.0
    symbol = 0
    for n in range(int(rate * seconds)):
        if mode == "noise":
            sample = complex(rng.gauss(0, 12), rng.gauss(0, 12))
        else:
            if n % (rate // 4800) == 0:
                symbol = rng.choice((-3, -1, 1, 3))
            phase += 2 * math.pi * symbol * 600 / rate
            sample = 50 * cmath.exp(1j * phase)
        result.extend(max(0, min(255, round(v + 127.5))) for v in (sample.real, sample.imag))
    return bytes(result)


def add_iq(out, ident, data, meta, protocol, truth, provenance, transformation, source_hash=None):
    path = out / (ident + ".iq")
    path.write_bytes(data)
    meta = copy.deepcopy(meta)
    meta.update(data_file=path.name, data_bytes=len(data), source_args="benchmark offline fixture")
    sidecar = path.with_suffix(".iq.json")
    write_json(sidecar, meta)
    # Interoperable export; source RF center and transform history remain in manifest.
    write_json(out / (ident + ".sigmf-meta"), {
        "global": {"core:datatype": "cu8", "core:sample_rate": meta["sample_rate_hz"],
                   "core:version": "1.2.6", "core:dataset": path.name,
                   "core:description": "XeraX benchmark; provenance and transforms in manifest.json"},
        "captures": [{"core:sample_start": 0, "core:frequency": meta["capture_center_frequency_hz"]}],
        "annotations": []})
    return {"id": ident, "protocol": protocol, "input": {
        "stage": "iq", "format": "cu8", "path": path.name, "sha256": digest(path),
        "metadata": sidecar.name, "metadata_sha256": digest(sidecar),
        "sample_rate_hz": meta["sample_rate_hz"], "samples": len(data) // 2},
        "truth": truth, "provenance": provenance, "transformation": transformation,
        "source_sha256": source_hash, "hardware_acceptance": False,
        "expected_payload_bits": None}


def generate(repo, out, scenarios, seed=20260924):
    repo, out = Path(repo), Path(out)
    if not scenarios or any(s not in SCENARIOS for s in scenarios) or len(set(scenarios)) != len(scenarios):
        raise ValueError("Choose unique supported scenarios")
    assets = repo / "upstream/dsd-neo/android/package/assets/iq-lab"
    manifest = read_json(assets / "manifest.json")
    # Validate all requested source bytes before creating any output.
    for stem, *_ in FIXTURES:
        for suffix in (".iq", ".iq.json"):
            if digest(assets / (stem + suffix)) != manifest["sha256"][stem + suffix]:
                raise ValueError("Upstream fixture hash mismatch: " + stem + suffix)
    out.mkdir(parents=True, exist_ok=False)
    cases = []
    for stem, protocol, expected, origin in FIXTURES:
        data = (assets / (stem + ".iq")).read_bytes()
        meta = read_json(assets / (stem + ".iq.json"))
        for scenario in scenarios:
            transformed, details = impair(data, meta["sample_rate_hz"], SCENARIOS[scenario], seed)
            truth = {"kind": "known_fields", "required": [expected], "forbidden": [],
                     "release_gate": scenario == "clean", "scope": "field recognition, not BER or intelligibility"}
            cases.append(add_iq(out, stem + "-" + scenario, transformed, meta, protocol, truth,
                {"kind": origin, "source_revision": manifest["revision"],
                 "source_fixture": stem, "license": "See upstream/dsd-neo/THIRD_PARTY.md; not a blanket GPL grant",
                 "hardware": None}, details, manifest["sha256"][stem + ".iq"]))
    meta = read_json(assets / "nxdn48.iq.json")
    for name in ("noise", "random4fsk"):
        data = synthetic(48000, 2, seed, name)
        for protocol in ("nxdn48", "nxdn96", "dmr", "p25_c4fm", "auto"):
            cases.append(add_iq(out, "synthetic-" + name + "-" + protocol, data, meta, protocol,
                {"kind": "no_protocol", "required": [], "forbidden": [TRANSMISSION], "release_gate": True},
                {"kind": "synthetic_nonprotocol", "license": "project-generated", "hardware": None},
                {"seed": seed, "generator": name}))
    doc = {"schema": 1, "seed": seed, "generator_sha256": digest(__file__), "cases": cases,
           "limitations": ["No known transmitted bitstream for off-air fixtures; BER unavailable",
                          "Remodulated audio does not preserve original RF impairments",
                          "Traffic repetition is load testing, not realistic call/grant generation",
                          "No physical hardware acceptance or encryption-key recovery"]}
    write_json(out / "manifest.json", doc)
    load_corpus(out / "manifest.json")
    return doc


def discriminator_suite(source, out):
    doc = load_corpus(source)
    root, out = Path(source).resolve().parent, Path(out)
    out.mkdir(parents=True, exist_ok=False)
    cases = []
    for original in doc["cases"]:
        if original["input"]["stage"] != "iq" or original["protocol"] in ("p25_cqpsk", "p25p2", "auto"):
            continue
        data = (root / original["input"]["path"]).read_bytes()
        samples = array.array("h", [0])
        previous = complex(data[0] - 127.5, data[1] - 127.5)
        for i in range(2, len(data), 2):
            sample = complex(data[i] - 127.5, data[i + 1] - 127.5)
            phase = cmath.phase(sample * previous.conjugate())
            samples.append(max(-32768, min(32767, round(phase * 16384 / math.pi))))
            previous = sample
        if sys.byteorder != "little":
            samples.byteswap()
        path = out / (original["id"] + ".wav")
        rate = original["input"]["sample_rate_hz"]
        with wave.open(str(path), "wb") as wav:
            wav.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            wav.writeframes(samples.tobytes())
        case = copy.deepcopy(original)
        case["input"] = {"stage": "discriminator", "format": "pcm16le_wav",
                         "path": path.name, "sha256": digest(path), "samples": len(samples),
                         "sample_rate_hz": rate}
        case["provenance"]["derived_from_iq_sha256"] = original["input"]["sha256"]
        case["transformation"]["shared_discriminator"] = "arg(x[n]*conj(x[n-1])) * 16384/pi; no filtering"
        cases.append(case)
    if not cases:
        raise ValueError("No compatible FSK cases for a discriminator comparison")
    write_json(out / "manifest.json", {"schema": 1, "cases": cases,
        "limitations": ["Shared-discriminator comparison excludes each application's RF front end",
                       "No CQPSK/P25 Phase 2 equivalence is assumed"]})
    return load_corpus(out / "manifest.json")


def register_capture(sidecar, out, protocol, kind, description, expected=None, hardware=None):
    """Import a declared capture without asserting its provenance has been verified."""
    from .model import MODES
    if protocol not in MODES or kind not in ("off_air_iq", "synthetic_protocol", "remodulated_discriminator"):
        raise ValueError("Invalid capture classification")
    if not description.strip():
        raise ValueError("A provenance description is required")
    sidecar, out = Path(sidecar).resolve(), Path(out)
    meta = read_json(sidecar)
    if meta.get("sample_format") != "cu8" or meta.get("format") != "dsd-neo-iq":
        raise ValueError("Initial import supports dsd-neo CU8 sidecars only")
    from .model import contained
    source = contained(sidecar.parent, meta["data_file"])
    if source.stat().st_size != meta["data_bytes"] or source.stat().st_size % 2:
        raise ValueError("Capture byte count does not match sidecar")
    out.mkdir(parents=True, exist_ok=False)
    data = out / "capture.iq"
    shutil.copyfile(source, data)
    meta["data_file"] = data.name
    meta["source_args"] = "user-registered offline capture"
    destination = out / "capture.iq.json"
    write_json(destination, meta)
    case = {"id": "registered-capture", "protocol": protocol, "input": {
        "stage": "iq", "format": "cu8", "path": data.name, "sha256": digest(data),
        "metadata": destination.name, "metadata_sha256": digest(destination),
        "sample_rate_hz": meta["sample_rate_hz"], "samples": data.stat().st_size // 2},
        "truth": {"kind": "known_fields" if expected else "unknown", "required": expected or [],
                  "forbidden": [], "release_gate": False},
        "provenance": {"kind": kind, "description": description, "hardware": hardware,
                       "declaration": "operator supplied, not independently verified"},
        "hardware_acceptance": False, "transformation": {"import": "byte-exact"},
        "expected_payload_bits": None}
    write_json(out / "manifest.json", {"schema": 1, "cases": [case]})
    return load_corpus(out / "manifest.json")


def mix(source, left_id, right_id, out, offset_hz=12500, sir_db=0):
    """Compose two identified captures at the same rate; score only the wanted channel."""
    from .model import contained
    doc = load_corpus(source)
    by_id = {c["id"]: c for c in doc["cases"]}
    left, right = by_id[left_id], by_id[right_id]
    a, b = left["input"], right["input"]
    if a["stage"] != "iq" or b["stage"] != "iq" or a["sample_rate_hz"] != b["sample_rate_hz"]:
        raise ValueError("Mix requires CU8 captures at identical sample rates")
    rate = a["sample_rate_hz"]
    if not math.isfinite(sir_db) or not -60 <= sir_db <= 60 or not math.isfinite(offset_hz) or abs(offset_hz) >= rate / 2:
        raise ValueError("Invalid mixing parameters")
    root, out = Path(source).resolve().parent, Path(out)
    ad = contained(root, a["path"]).read_bytes()
    bd = contained(root, b["path"]).read_bytes()
    x = [complex(ad[i] - 127.5, ad[i + 1] - 127.5) for i in range(0, len(ad), 2)]
    y = [complex(bd[i] - 127.5, bd[i + 1] - 127.5) for i in range(0, len(bd), 2)]
    px, py = sum(abs(v)**2 for v in x) / len(x), sum(abs(v)**2 for v in y) / len(y)
    if px == 0 or py == 0:
        raise ValueError("Cannot define power ratio for zero-power input")
    gain = math.sqrt(px / py / 10**(sir_db / 10))
    step, phase = cmath.exp(2j * math.pi * offset_hz / rate), 1 + 0j
    mixed, clipped = bytearray(), 0
    for i, sample in enumerate(x):
        value = (sample + gain * y[i % len(y)] * phase) / (1 + gain)
        for component in (value.real, value.imag):
            q = round(component + 127.5)
            clipped += int(q < 0 or q > 255)
            mixed.append(max(0, min(255, q)))
        phase *= step
        if i % 4096 == 4095:
            phase /= abs(phase)
    out.mkdir(parents=True, exist_ok=False)
    truth = copy.deepcopy(left["truth"])
    truth["release_gate"] = False
    case = add_iq(out, "mixed-capture", mixed, read_json(contained(root, a["metadata"])),
        left["protocol"], truth, {"kind": "composite", "hardware": None,
            "components": [{"case": left_id, "sha256": a["sha256"], "offset_hz": 0},
                           {"case": right_id, "sha256": b["sha256"], "offset_hz": offset_hz}]},
        {"sir_db_relative_to_source_total_power": sir_db, "clipped_components": clipped,
         "interferer_looped": len(y) < len(x), "score_scope": "wanted channel only"})
    write_json(out / "manifest.json", {"schema": 1, "cases": [case],
        "limitations": ["Composite tests software interference handling; not physical tuner overload",
                       "Two independently supplied recordings; no simultaneous-call reception claim"]})
    return load_corpus(out / "manifest.json")
