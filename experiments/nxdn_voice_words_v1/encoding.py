"""Independent arithmetic for the registered NXDN 49-to-72 channel-word study.

This is a channel encoder, not a speech encoder or a receiver oracle. It imports
no production decoder, encoder, or lookup table. Protocol conventions are bound
to MMDVM-Host 590c531391dfd3146073afbc3956f70d42c62a46: NXDNAudio.cpp,
Golay24128.cpp. The A-dependent recurrence is checked separately against the
pinned primary encoder; sharing protocol knowledge is not formal independence.

All strings and byte records are MSB first. Public inputs require the exact
documented built-in type; bools, implicit conversions and mutable buffers are
not accepted. Upstream source-record padding is opaque on extraction, whereas
pack_words always normalizes the final six bits of each 13-byte record to zero.
"""

from __future__ import annotations


def _checked_word(word: str) -> str:
    if type(word) is not str:
        raise TypeError("A voice word must be a binary str")
    if len(word) != 49 or any(bit not in "01" for bit in word):
        raise ValueError("A voice word must contain exactly 49 binary characters")
    return word


def _checked_information(value: int) -> int:
    if type(value) is not int:
        raise TypeError("Golay information must be an int")
    if not 0 <= value < (1 << 12):
        raise ValueError("Golay information must fit 12 bits")
    return value


def _golay23(information: int) -> int:
    """Systematic degree-11 polynomial code, information in its high 12 bits.

    g(x) = x^11 + x^10 + x^6 + x^5 + x^4 + x^2 + 1 = 0xC75.
    This returns the actual 23-bit word; the primary C++ function named
    encode23127 instead stores it shifted left by one.
    """
    information = _checked_information(information)
    systematic = information << 11
    remainder = systematic
    for degree in range(22, 10, -1):
        if remainder & (1 << degree):
            remainder ^= 0xC75 << (degree - 11)
    return systematic | remainder


def _golay24(information: int) -> int:
    code = _golay23(information)
    return (code << 1) | (code.bit_count() & 1)


def _mask23(a_information: int) -> int:
    """Generate B's 23-bit mask from A's original 12 information bits.

    Seed x0=16*A. Each emitted MSB uses the UPDATED 16-bit LCG state, not x0:
    x=(173*x+13849) mod 65536. The 23 emitted bits correspond to the primary
    NXDNAudio.cpp PRNG_TABLE[A] >> 1; no table is embedded or read here.
    This channel mask is neither air-frame PN9 whitening nor encryption.
    """
    state = _checked_information(a_information) << 4
    mask = 0
    for _ in range(23):
        state = (173 * state + 13849) & 0xFFFF
        mask = (mask << 1) | (state >> 15)
    return mask


def channel_layout() -> tuple[tuple[str, int], ...]:
    """Map each transmitted index to (field, MSB-first CHANNEL field index).

    A indices 0..23 and B indices 0..22 refer to protected channel bits, not
    information bits. C indices 0..24 map directly to source indices 24..48.
    The inverse of p(k)=4*(k mod 18)+floor(k/18) avoids copied tables.
    """
    layout = []
    for transmitted in range(72):
        linear = 18 * (transmitted % 4) + transmitted // 4
        if linear < 24:
            layout.append(("A", linear))
        elif linear < 47:
            layout.append(("B", linear - 24))
        else:
            layout.append(("C", linear - 47))
    return tuple(layout)


def encode_word(bits49: str) -> bytes:
    """Encode one exact binary source word into nine packed channel bytes."""
    word = _checked_word(bits49)
    a_information = int(word[:12], 2)
    b_information = int(word[12:24], 2)
    a = _golay24(a_information)
    b = _golay23(b_information) ^ _mask23(a_information)
    channel_fields = f"{a:024b}{b:023b}{word[24:]}"
    packed = 0
    for linear, bit in enumerate(channel_fields):
        transmitted = 4 * (linear % 18) + linear // 18
        packed |= (ord(bit) - ord("0")) << (71 - transmitted)
    return packed.to_bytes(9, "big")


def unpack_units(raw13multiple: bytes) -> list[str]:
    """Extract the two source words at offsets 0 and 49 of each 13-byte unit.

    The six trailing bits are original source padding, not part of either word.
    They may be nonzero (the registered upstream linked asset uses 0b111110).
    Callers must preserve original bytes/padding in provenance before packing a
    normalized copy. Empty bytes represent zero records and yield an empty list.
    """
    if type(raw13multiple) is not bytes:
        raise TypeError("Packed source units must be immutable bytes")
    if len(raw13multiple) % 13:
        raise ValueError("Packed source length must be a multiple of 13 bytes")
    words = []
    for offset in range(0, len(raw13multiple), 13):
        unit = int.from_bytes(raw13multiple[offset:offset + 13], "big") >> 6
        words.append(f"{unit >> 49:049b}")
        words.append(f"{unit & ((1 << 49) - 1):049b}")
    return words


def pack_words(words: list[str]) -> bytes:
    """Pack an even list of words into 13-byte pairs with six zero pad bits."""
    if type(words) is not list:
        raise TypeError("Source words must be supplied as a list")
    if len(words) % 2:
        raise ValueError("The paired source format requires an even word count")
    for word in words:
        _checked_word(word)
    packed = bytearray()
    for offset in range(0, len(words), 2):
        unit = ((int(words[offset], 2) << 49) | int(words[offset + 1], 2)) << 6
        packed.extend(unit.to_bytes(13, "big"))
    return bytes(packed)
