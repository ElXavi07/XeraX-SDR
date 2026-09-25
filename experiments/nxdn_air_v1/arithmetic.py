"""Strict arithmetic assembly for the registered nine clear NXDN air frames.

This module imports no primary/receiver tables. Historical independent control
and voice primitives are executed only from bytes matching their fixed hashes.
Default paths are in the repository; a reproducer may set CONTROL_PATH and
VOICE_PATH to preserved copies without changing the required identities.
encode_record has no file output and performs no native/receiver execution.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
CONTROL_PATH = ROOT / "experiments/nxdn_frames/generate_vectors.py"
VOICE_PATH = ROOT / "experiments/nxdn_voice_words_v1/encoding.py"
CONTROL_SHA256 = "3e2c63b57dba137bbb35cdb9457a17deb9d0363fff8b8117e5d530e5990be9bd"
VOICE_SHA256 = "00c8adcc76302e13319e506ee6570d337e5975fca42c11ac32dd5e0eb69354df"
VCALL = bytes.fromhex("010020038504b1000000")
TX_REL = bytes.fromhex("080020038504b1000000")
IDLE_SACCH = bytes.fromhex("01100000")
PROFILES = (0x83, 0xAE, 0xA6, 0xAA)


def _load_checked(path, digest, name):
    # Hash and compile the SAME bytes; a separate import loader could reread a
    # changed file or select a cached bytecode file after verification.
    path = Path(path).resolve()
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("Historical arithmetic source identity changed: " + str(path))
    module = ModuleType(name)
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def _bits(raw):
    return tuple((byte >> shift) & 1 for byte in raw for shift in range(7, -1, -1))


def _pack(bits):
    if len(bits) % 8 or any(type(bit) is not int or bit not in (0, 1) for bit in bits):
        raise ValueError("Internal byte packing requires complete binary bytes")
    return bytes(sum(bits[start + bit] << (7 - bit) for bit in range(8))
                 for start in range(0, len(bits), 8))


def _validate(record41):
    if type(record41) is not bytes:
        raise TypeError("A frame record must be immutable bytes")
    if len(record41) != 41:
        raise ValueError("A frame record must contain exactly 41 bytes")
    lich = record41[0]
    if lich not in PROFILES:
        raise ValueError("LICH is outside the four registered RDCH outbound profiles")
    sacch, facch, voice = record41[1:5], record41[5:15], record41[15:41]
    if sacch[3] & 0x3F:
        raise ValueError("SACCH raw padding must be six zero bits")
    if voice[12] & 0x3F or voice[25] & 0x3F:
        raise ValueError("Each source voice pair must have six zero padding bits")
    if sacch[0] & 0x3F != 1:
        raise ValueError("The registered RAN is exactly one")
    if lich == 0x83:
        if sacch != IDLE_SACCH:
            raise ValueError("Full control frames require the registered single IDLE SACCH")
        if facch not in (VCALL, TX_REL):
            raise ValueError("Full control frames require clear VCALL or TX_REL information")
        if voice != bytes(26):
            raise ValueError("Full control frames require a zero voice placeholder")
    else:
        structure = sacch[0] >> 6
        fragment = 3 - structure
        if _bits(sacch)[8:26] != _bits(VCALL[:9])[fragment * 18:(fragment + 1) * 18]:
            raise ValueError("SACCH structure and registered VCALL fragment disagree")
        if lich == 0xAE:
            if facch != bytes(10):
                raise ValueError("Pure voice requires a zero FACCH placeholder")
        elif facch != VCALL:
            raise ValueError("Half-steal frames require registered clear VCALL information")
        if lich == 0xA6 and structure != 2:
            raise ValueError("First-half FACCH requires registered SACCH structure two")
        if lich == 0xAA and structure != 1:
            raise ValueError("Second-half FACCH requires registered SACCH structure one")
    return lich, sacch, facch, voice


def encode_record(record41: bytes) -> tuple[bytes, bytes]:
    """Return (unwhitened48, whitened48) for a strict registered-shape record.

    Input: LICH1 + SACCH4 + FACCH10 + two source voice pairs (13 bytes each).
    Half-steal inputs retain both source pairs; only the unstolen pair is sent.
    Source IDs/order belong to the independently checked corpus, not this API.
    """
    lich, sacch, facch, voice_input = _validate(record41)
    control = _load_checked(CONTROL_PATH, CONTROL_SHA256, "_nxdn_air_control_arithmetic")
    voice = _load_checked(VOICE_PATH, VOICE_SHA256, "_nxdn_air_voice_arithmetic")

    # This high-nibble XOR agrees with the pinned limited primary parity rule
    # ONLY for the four accepted profiles; do not extend the domain silently.
    parity = (lich >> 4).bit_count() & 1
    if (lich & 1) != parity:
        raise ValueError("Registered LICH parity is inconsistent")
    logical_lich = control.bits((lich & 0xFE) | parity, 8)
    lich_bits = tuple(bit for value in logical_lich for bit in (value, 1))
    sacch_bits, _ = control.channel(_bits(sacch)[:26], 6, False)
    facch_bits = None
    if lich != 0xAE:
        facch_bits, _ = control.channel(_bits(facch), 12, False)

    words = voice.unpack_units(voice_input)
    if lich in (0xAE, 0xAA):
        first = _bits(voice.encode_word(words[0]) + voice.encode_word(words[1]))
    else:
        first = facch_bits
    if lich in (0xAE, 0xA6):
        second = _bits(voice.encode_word(words[2]) + voice.encode_word(words[3]))
    else:
        second = facch_bits

    frame_bits = control.bits(0xCDF59, 20) + lich_bits + sacch_bits + first + second
    if len(frame_bits) != 384:
        raise ValueError("Internal complete-frame dimensions changed")
    raw = _pack(frame_bits)
    dibits = control.to_dibits(frame_bits)
    air_dibits = dibits[:10] + control.whiten(dibits[10:], seed=228)
    air = _pack(tuple(bit for dibit in air_dibits for bit in (dibit >> 1, dibit & 1)))
    if len(raw) != 48 or len(air) != 48:
        raise ValueError("Internal packed-frame dimensions changed")
    return raw, air
