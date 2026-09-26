"""Create the registered voice-word corpus once, before native execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import encoding

ROOT = Path(__file__).resolve().parents[2]
PINS = {"MMDVM-Host": "590c531391dfd3146073afbc3956f70d42c62a46",
        "NXDNClients": "8950677e9876e577fb87b955cfa93bacd059209d"}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def verify_primary(primary):
    primary = Path(primary).resolve()
    manifest = json.loads((primary / "manifest.json").read_text(encoding="utf-8"))
    need(manifest["repositories"] == PINS, "Primary repository pins changed")
    hashes = {}
    for f in manifest["files"]:
        p = (primary / f["path"]).resolve()
        need(p.is_relative_to(primary), "Primary path escaped closure")
        raw = p.read_bytes()
        need(len(raw) == f["bytes"] and hashlib.sha256(raw).hexdigest() == f["sha256"], "Primary file changed: " + f["path"])
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        need(blob == f["git_blob_sha1"], "Primary Git blob changed: " + f["path"])
        hashes[f["path"]] = f["sha256"]
    return hashes


def generate(primary, output):
    need(not output.exists(), "Never overwrite an existing corpus")
    hashes = verify_primary(primary)
    voice_path = "NXDNClients/NXDNGateway/Voice.cpp"
    asset_path = "NXDNClients/NXDNGateway/Audio/en_GB.nxdn"
    index_path = "NXDNClients/NXDNGateway/Audio/en_GB.indx"
    need(hashes[voice_path] == "340764309fb8995372e58c8dd29a9c08406537605f660c3be59ba3b490509d1a", "Voice construction source changed")
    need(hashes[asset_path] == "7d1cb388fd91edae4f9b68de1cc54fae01b461357a3cf148a0ba6c85b3f732fc", "Announcement asset changed")
    index_rows = [line.split() for line in (primary / index_path).read_text(encoding="utf-8").splitlines()]
    need([row for row in index_rows if row and row[0] == "linked"] == [["linked", "652", "10"]], "Announcement source index changed")
    linked = (primary / asset_path).read_bytes()[8476:8606]
    need(hashlib.sha256(linked).hexdigest() == "8f4116e67a4c950a524c8568caf17d550e9b0b0bbdac3f9e3761ce76c0056e41", "Announcement slice changed")
    declarations = re.findall(r"const unsigned char SILENCE\[\]\s*=\s*\{([^}]+)\}", (primary / voice_path).read_text(encoding="utf-8"))
    need(len(declarations) == 1, "Silence declaration is not unique")
    silence = bytes(int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{2})U", declarations[0]))
    need(len(silence) == 13 and silence.hex() == "f0000000000078000000000000", "Silence source bytes changed")
    rows = []
    def add(kind, index, value):
        rows.append({"id": len(rows), "kind": kind, "source_index": index, "bits": value})
    for i, value in enumerate(encoding.unpack_units(linked)): add("announcement", i, value)
    for i, value in enumerate(encoding.unpack_units(silence)): add("upstream_silence", i, value)
    add("zero", 0, "0" * 49); add("ones", 0, "1" * 49)
    for i in range(49): add("onehot", i, "0" * i + "1" + "0" * (48 - i))
    need(len(rows) == 73, "Base word count changed")
    for i in range(4096): add("sweep_a", i, format(i, "012b") + "0" * 37)
    for i in range(4096): add("sweep_b", i, "0" * 12 + format(i, "012b") + "0" * 25)
    add("pair_padding", 0, "0" * 49)
    need(len(rows) == 8266, "Registered word count changed")
    values = [row["bits"] for row in rows]
    packed = encoding.pack_words(values)
    expected = b"".join(encoding.encode_word(value) for value in values)
    need(len(packed) == 53729 and len(expected) == 74394, "Packed dimensions changed")
    need(all(packed[i + 12] & 63 == 0 for i in range(0, len(packed), 13)), "Normalized packing contains nonzero padding")
    output.mkdir(parents=True, exist_ok=False)
    (output / "input.pairs13").write_bytes(packed)
    (output / "expected.channels9").write_bytes(expected)
    (output / "linked-source.bin").write_bytes(linked)
    (output / "silence-source.bin").write_bytes(silence)
    (output / "primary-manifest.json").write_bytes((primary / "manifest.json").read_bytes())
    save(output / "words.json", rows)
    save(output / "manifest.json", {"schema": 1, "kind": "nxdn_voice_words_v1", "words": 8266, "base_words": 73,
        "pairs": 4133, "probe_calls": 27044, "primary_pins": PINS, "primary_files": hashes,
        "primary_manifest_sha256": sha(primary / "manifest.json"),
        "linked_original_padding": [linked[i + 12] & 63 for i in range(0, 130, 13)],
        "silence_original_padding": silence[12] & 63,
        "files": {p.name: {"bytes": p.stat().st_size, "sha256": sha(p)} for p in output.iterdir()},
        "generation_sources": {p.name: sha(p) for p in (Path(__file__), Path(encoding.__file__))},
        "scope": "clear source/channel words only; no synthesis, receiver, key search or RF"})
    return {"words": len(rows), "manifest_sha256": sha(output / "manifest.json")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("primary", type=Path); parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.primary.resolve(), args.output.resolve())))
