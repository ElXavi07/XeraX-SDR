"""Independent fixed NXDN control-frame encoder for a bounded receiver test.

Usage: python generate_vectors.py <new output directory>
The .dibits files contain one numeric dibit (0..3) per byte, not ASCII or IQ.
No production decoder, CRC helper, lookup/permutation table, or radio is used.
This builds one RDCH/SACCH-nonsuperframe profile, not general NXDN certification.
"""
import argparse
import hashlib
import json
from pathlib import Path


PRIMARY_COMMIT = "590c531391dfd3146073afbc3956f70d42c62a46"
PRIMARY_REPOSITORY = "https://github.com/g4klx/MMDVM-Host"
PRIMARY_HASHES = {
    "NXDNCRC.cpp": "68cca2da00fd1048d2ad0c27b6230de6bf2933ac4448b98e1eb365719c4979bc",
    "NXDNConvolution.cpp": "79a765cc9311391f48746be994e84e32cf0224f10524f87684c509e38006ed2f",
    "NXDNSACCH.cpp": "ba6d07d66c6214a726ddf554e184ec417af9910a75ac57bb57c8c8f262351706",
    "NXDNFACCH1.cpp": "5a71c39552de8cf2fe17b75007fa2e373816223f70ad5995d24f51341cd7b1f7",
    "NXDNLICH.cpp": "d69a3a756b99b757d9f51c0dadb46f9482fbeaa14090b415e983a8ca48af3565",
    "NXDNDefines.h": "f56abd2fbcc07d09052c9752532c3f482ff99fef3fe82a4834909bebf4191239",
    "NXDNControl.cpp": "f52eb28581885be4dfc7500867dd43458385bad564ea45f6326f75133f2cb1a4",
}
VARIANTS = ("valid", "wrong_all_crc", "wrong_lich")
FSW = 0xCDF59
FSW_SIGN = "3131331131"
LEVELS = (8000, 24000, -8000, -24000)


def bits(value, width):
    if type(value) is not int or type(width) is not int or width < 1 or not 0 <= value < (1 << width):
        raise ValueError("Integer must fit a positive bit width")
    return tuple((value >> shift) & 1 for shift in range(width - 1, -1, -1))


def checked_bits(data):
    values = tuple(data)
    if any(type(value) is not int or value not in (0, 1) for value in values):
        raise ValueError("Bits must be integers zero or one")
    return values


def bit_string(data):
    return "".join(str(value) for value in checked_bits(data))


def crc(data, width, polynomial):
    """Non-reflected, all-ones initial state, no appended zeros/final XOR."""
    if (width, polynomial) not in ((6, 0x27), (12, 0x80F)):
        raise ValueError("Only the two declared channel CRCs are supported")
    register = (1 << width) - 1
    for value in checked_bits(data):
        feedback = value ^ (register >> (width - 1))
        register = (register << 1) & ((1 << width) - 1)
        if feedback:
            register ^= polynomial
    return register


def crc6(data):
    return crc(data, 6, 0x27)


def crc12(data):
    return crc(data, 12, 0x80F)


def convolution(data):
    """K=5, rate 1/2, zero history; caller explicitly supplies tail bits."""
    history = [0, 0, 0, 0]
    encoded = []
    for value in checked_bits(data):
        d1, d2, d3, d4 = history
        encoded.extend((value ^ d3 ^ d4, value ^ d1 ^ d2 ^ d4))
        history = [value, d1, d2, d3]
    return tuple(encoded)


def puncture(data, period, removed_residue):
    values = checked_bits(data)
    if type(period) is not int or type(removed_residue) is not int or period < 2 or not 0 <= removed_residue < period:
        raise ValueError("Invalid puncturing rule")
    return tuple(value for index, value in enumerate(values) if index % period != removed_residue)


def interleave(data, rows, columns):
    """Read a column-major source rectangle in row-major transmitted order."""
    values = checked_bits(data)
    if type(rows) is not int or type(columns) is not int or rows < 1 or columns < 1 or len(values) != rows * columns:
        raise ValueError("Interleave dimensions do not match input")
    return tuple(values[(index % columns) * rows + index // columns] for index in range(len(values)))


def to_dibits(data):
    values = checked_bits(data)
    if len(values) % 2:
        raise ValueError("Dibits require an even number of bits")
    return bytes((values[index] << 1) | values[index + 1] for index in range(0, len(values), 2))


def checked_dibits(data):
    values = tuple(data)
    if any(type(value) is not int or not 0 <= value <= 3 for value in values):
        raise ValueError("Dibits must be integers zero through three")
    return values


def whiten(data, seed=228):
    """PN95 channel whitening. This is not encryption or a privacy key."""
    if type(seed) is not int or not 1 <= seed <= 511:
        raise ValueError("An explicit nonzero nine-bit whitening seed is required")
    register = seed
    result = []
    for dibit in checked_dibits(data):
        result.append(dibit ^ ((register & 1) << 1))
        feedback = ((register >> 4) ^ register) & 1
        register = (register >> 1) | (feedback << 8)
    return bytes(result)


def sign_candidates(data):
    signs = "".join("1" if LEVELS[value] > 0 else "3" for value in checked_dibits(data))
    inverted = FSW_SIGN.translate(str.maketrans("13", "31"))
    return {"positive": [index for index in range(len(signs) - 9) if signs[index:index + 10] == FSW_SIGN],
            "negative": [index for index in range(len(signs) - 9) if signs[index:index + 10] == inverted]}


def channel(information, width, wrong_check):
    information = checked_bits(information)
    if (len(information), width) not in ((26, 6), (80, 12)):
        raise ValueError("Unsupported control-channel dimensions")
    computed = crc6(information) if width == 6 else crc12(information)
    transmitted = computed ^ ((1 << (width - 1)) if wrong_check else 0)
    check = bits(transmitted, width)
    raw = information + check + (0, 0, 0, 0)
    coded = convolution(raw)
    punctured = puncture(coded, 6, 5) if width == 6 else puncture(coded, 4, 1)
    encoded = interleave(punctured, 12, 5) if width == 6 else interleave(punctured, 16, 9)
    return encoded, {"information_bits": bit_string(information), "crc_width": width,
                     "computed_crc": computed, "transmitted_crc": transmitted,
                     "check_bits": bit_string(check), "crc_expected_pass": computed == transmitted,
                     "convolution_input_bits": bit_string(raw), "coded_bits": bit_string(coded),
                     "punctured_bits": bit_string(punctured), "channel_bits": bit_string(encoded),
                     "flipped_check_bit_index": 0 if wrong_check else None}


def build_frame(variant="valid"):
    """Return (immutable numeric-dibit bytes, independent expected metadata)."""
    if variant not in VARIANTS:
        raise ValueError("Unknown fixed vector variant")
    # This parity equation is deliberately qualified for the chosen 0x41
    # profile. MMDVM's limited parity lookup is not a general LICH oracle.
    seven = 0x41
    full_without_parity = seven << 1
    parity = sum(bits(full_without_parity >> 4, 4)) % 2
    full = full_without_parity | (parity ^ (variant == "wrong_lich"))
    lich = tuple(component for value in bits(full, 8) for component in (value, 1))
    sacch_info = bits(0, 2) + bits(23, 6) + bits(0x10, 8) + (0,) * 10
    facch_info = bits(0x10, 8) + (0,) * 72
    sacch, sacch_meta = channel(sacch_info, 6, variant == "wrong_all_crc")
    facch, facch_meta = channel(facch_info, 12, variant == "wrong_all_crc")
    fsw = to_dibits(bits(FSW, 20))
    unwhitened = fsw + to_dibits(lich + sacch + facch + facch)
    air = fsw + whiten(unwhitened[10:])
    if len(air) != 192:
        raise RuntimeError("Internal frame length invariant failed")
    meta = {"variant": variant, "frame_bits": 384, "frame_dibits": 192,
            "fsw_bits": bit_string(bits(FSW, 20)), "fsw_dibits": "".join(map(str, fsw)),
            "lich_seven_bit": seven, "lich_full_byte": full, "lich_expected_pass": variant != "wrong_lich",
            "lich_channel_bits": bit_string(lich), "ran": 23, "structure": 0,
            "sacch": sacch_meta, "facch_a": facch_meta, "facch_b": dict(facch_meta),
            "expected_channel_callbacks": 0 if variant == "wrong_lich" else 3,
            "expected_current_frame_proof": variant == "valid",
            "unwhitened_dibits": list(unwhitened), "air_dibits": list(air),
            "sha256": hashlib.sha256(air).hexdigest(),
            "channel_frame_dibit_intervals": {"fsw": [0, 10], "lich": [10, 18], "sacch": [18, 48],
                                               "facch_a": [48, 120], "facch_b": [120, 192]},
            "whitening": {"seed": 228, "applied_frame_dibit_interval": [10, 192], "resets_each_frame": True},
            "single_frame_sign_candidates": sign_candidates(air)}
    return air, meta


def generate(output_directory):
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=False)
    frames = {}
    for variant in VARIANTS:
        data, meta = build_frame(variant)
        filename = variant + ".dibits"
        (directory / filename).write_bytes(data)
        meta["file"] = filename
        frames[variant] = meta
    sequences = {}
    for name, variants in (("four_valid", ("valid",) * 4),
                           ("four_wrong_all_crc", ("wrong_all_crc",) * 4),
                           ("four_wrong_lich", ("wrong_lich",) * 4),
                           ("valid_then_invalid", ("valid", "valid", "wrong_all_crc", "wrong_lich"))):
        stream = bytes((1, 3) * 16) + b"".join(bytes(frames[variant]["air_dibits"]) for variant in variants)
        sequences[name] = {"variants": list(variants), "preamble_dibits": 32, "total_dibits": len(stream),
                           "sha256": hashlib.sha256(stream).hexdigest(),
                           "nominal_fsw_starts_dibits": [32 + 192 * index for index in range(4)],
                           "sign_candidates": sign_candidates(stream)}
    manifest = {"schema": 1, "kind": "independent_nxdn_control_vectors", "byte_encoding": "one numeric dibit per byte, 0..3",
                "bit_order": "MSB first", "profile": "RDCH outbound, SACCH single, both FACCH1 halves, IDLE",
                "primary_source": {"repository": PRIMARY_REPOSITORY, "commit": PRIMARY_COMMIT, "sha256": PRIMARY_HASHES,
                                   "qualification": "Compiled primary CRC/convolution/SACCH/LICH plus FACCH audit copy with terminal puncture sentinel 192; original source retained in audit."},
                "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "frames": frames, "sequences": sequences,
                "suggested_discriminator_profile": {"rate_hz": 48000, "symbol_rate": 2400, "samples_per_symbol": 20,
                                                     "levels_by_dibit": list(LEVELS)},
                "original_iq_samples": None, "pcm_truth": None,
                "limits": ["Generated encoded control frames, not an off-air recording or voice test.",
                           "FSW candidates are exact symbol-sign windows; they are not measured decoder accepts.",
                           "Nominal landmarks do not account for waveform shaping or receiver group delay.",
                           "CRC expectations describe original channel bits; receiver observations must be measured separately."]}
    with (directory / "vectors.json").open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, allow_nan=False)
        handle.write("\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("new_output_directory", type=Path)
    args = parser.parse_args(argv)
    manifest = generate(args.new_output_directory)
    print(json.dumps({"frames": {name: row["sha256"] for name, row in manifest["frames"].items()}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
