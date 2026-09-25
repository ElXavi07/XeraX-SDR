"""Strict corpus validation and portable evidence utilities."""
import hashlib
import json
import math
import re
from pathlib import Path

SCHEMA = 1
ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,95}$")
MODES = {"nxdn48": ["-fi"], "nxdn96": ["-fn"], "dmr": ["-fs"],
         "dmr_t3": ["-ft"], "p25_c4fm": ["-f1"], "p25_cqpsk": ["-f1", "-mq"],
         "p25p2": ["-f2"], "auto": ["-fa"]}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    def reject(value):
        raise ValueError("Non-finite JSON number: " + value)
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), parse_constant=reject)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                          encoding="utf-8")


def contained(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError("Corpus paths must be relative")
    result = (Path(root) / relative).resolve()
    if not result.is_relative_to(Path(root).resolve()):
        raise ValueError("Corpus path escapes its directory")
    return result


def load_corpus(path):
    path = Path(path).resolve()
    doc = read_json(path)
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA or not isinstance(doc.get("cases"), list) or not doc["cases"]:
        raise ValueError("Unsupported or empty corpus")
    seen = set()
    for case in doc["cases"]:
        ident = case.get("id", "")
        if not isinstance(ident, str) or not ID.fullmatch(ident) or ident in seen:
            raise ValueError("Invalid or duplicate case ID")
        seen.add(ident)
        if case.get("protocol") not in MODES:
            raise ValueError("Unsupported protocol selector")
        inp = case["input"]
        if inp["stage"] not in ("iq", "discriminator"):
            raise ValueError("Unsupported input stage")
        rate = inp["sample_rate_hz"]
        if isinstance(rate, bool) or not isinstance(rate, int) or not 8000 <= rate <= 20000000:
            raise ValueError("Invalid sample rate")
        samples = inp["samples"]
        if isinstance(samples, bool) or not isinstance(samples, int) or samples <= 0:
            raise ValueError("Invalid sample count")
        data = contained(path.parent, inp["path"])
        if digest(data) != inp["sha256"]:
            raise ValueError("Capture hash mismatch: " + ident)
        if inp["stage"] == "iq":
            if inp["format"] != "cu8" or data.stat().st_size != samples * 2:
                raise ValueError("CU8 size/format mismatch")
            meta_path = contained(path.parent, inp["metadata"])
            if digest(meta_path) != inp["metadata_sha256"]:
                raise ValueError("Metadata hash mismatch")
            meta = read_json(meta_path)
            if (meta.get("format") != "dsd-neo-iq" or meta.get("sample_format") != "cu8"
                    or meta.get("version") not in (1, 2)
                    or meta.get("sample_rate_hz") != rate or meta.get("data_bytes") != samples * 2
                    or contained(meta_path.parent, meta["data_file"]) != data):
                raise ValueError("Sidecar disagrees with corpus")
        else:
            import wave
            if inp["format"] != "pcm16le_wav":
                raise ValueError("Unsupported discriminator format")
            with wave.open(str(data), "rb") as wav:
                if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()) != (1, 2, rate, samples):
                    raise ValueError("Discriminator WAV format mismatch")
        truth = case["truth"]
        if truth["kind"] not in ("known_fields", "no_protocol", "unknown"):
            raise ValueError("Unknown truth level")
        if truth["kind"] == "known_fields" and not truth.get("required"):
            raise ValueError("Known-field case has no positive assertion")
        if truth["kind"] == "no_protocol" and not truth.get("forbidden"):
            raise ValueError("Negative case has no false-positive assertion")
        if not isinstance(truth.get("release_gate", False), bool):
            raise ValueError("Release gate must be boolean")
        for field in ("required", "forbidden"):
            if not isinstance(truth.get(field, []), list) or not all(isinstance(p, str) and p for p in truth.get(field, [])):
                raise ValueError("Assertions must be non-empty regular-expression strings")
        for pattern in truth.get("required", []) + truth.get("forbidden", []):
            re.compile(pattern)
        if not case.get("provenance"):
            raise ValueError("Provenance required")
    return doc


def percentile(values, fraction):
    values = sorted(values)
    if not values:
        return None
    index = (len(values) - 1) * fraction
    low = math.floor(index)
    return values[low] + (values[math.ceil(index)] - values[low]) * (index - low)
