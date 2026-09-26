// SPDX-License-Identifier: GPL-3.0-or-later
// Independent encoder/codeword oracle for the NXDN convolutional decoder.
// Encoder equations cross-checked against G4KLX MMDVMHost NXDNConvolution.cpp.
#include <dsd-neo/protocol/nxdn/nxdn_convolution.h>

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <vector>

namespace {
using Bytes = std::vector<uint8_t>;
uint32_t random_state = 0x584e5844U;
uint32_t next_random() {
    random_state = random_state * 1664525U + 1013904223U;
    return random_state;
}

// Constraint length five, generators 1+D^3+D^4 and 1+D+D^2+D^4.
// This computes polynomial parity directly; it does not use decoder branch tables.
Bytes encode_byte(uint8_t payload, unsigned initial_history = 0) {
    Bytes symbols;
    unsigned history = initial_history;
    for (int position = 0; position < 12; ++position) {
        const unsigned bit = position < 8 ? (payload >> (7 - position)) & 1U : 0U;
        const unsigned d1 = history & 1U;
        const unsigned d2 = (history >> 1U) & 1U;
        const unsigned d3 = (history >> 2U) & 1U;
        const unsigned d4 = (history >> 3U) & 1U;
        symbols.push_back(static_cast<uint8_t>(2U * (bit ^ d3 ^ d4)));
        symbols.push_back(static_cast<uint8_t>(2U * (bit ^ d1 ^ d2 ^ d4)));
        history = ((history << 1U) | bit) & 15U;
    }
    return symbols;
}

Bytes decode(const Bytes& observations, const Bytes& reliability, bool soft, bool reset = true) {
    if (reset) CNXDNConvolution_init();
    CNXDNConvolution_start();
    const unsigned pairs = static_cast<unsigned>(observations.size() / 2U);
    for (unsigned i = 0; i < pairs; ++i) {
        if (soft) {
            CNXDNConvolution_decode_soft(observations[2U * i], observations[2U * i + 1U],
                                        reliability[2U * i], reliability[2U * i + 1U]);
        } else {
            CNXDNConvolution_decode(observations[2U * i], observations[2U * i + 1U]);
        }
    }
    const unsigned payload_bits = pairs - 4U;
    Bytes output((payload_bits + 7U) / 8U, 0);
    CNXDNConvolution_chainback(output.data(), payload_bits);
    return output;
}

uint32_t codeword_cost(const Bytes& observed, const Bytes& reliability, const Bytes& encoded) {
    uint32_t cost = 0;
    for (size_t i = 0; i < observed.size(); ++i) {
        const int difference = static_cast<int>(observed[i]) - static_cast<int>(encoded[i]);
        cost += static_cast<uint32_t>(difference < 0 ? -difference : difference) * reliability[i];
    }
    return cost;
}

// Production start() permits every initial state. Enumerate all 16 histories,
// all 256 payloads and a terminated four-bit tail; ties may return any minimizer.
uint32_t best_cost_for_payload(uint8_t payload, const Bytes& observed, const Bytes& reliability) {
    uint32_t best = std::numeric_limits<uint32_t>::max();
    for (unsigned initial = 0; initial < 16; ++initial) {
        best = std::min(best, codeword_cost(observed, reliability, encode_byte(payload, initial)));
    }
    return best;
}

struct Result {
    const char* name;
    unsigned cases = 0;
    unsigned failures = 0;
    void record(bool passed) { ++cases; failures += passed ? 0U : 1U; }
    int print() const {
        std::printf("%s: %u/%u passed\n", name, cases - failures, cases);
        return failures != 0U;
    }
};
}

int main() {
    // Fixed cross-check for encoder bit order: payload A5 followed by four
    // zeros yields this 24-bit convolutional codeword using the cited equations.
    const char* golden = "110110111001101011101011";
    const Bytes encoded = encode_byte(0xA5U);
    for (size_t i = 0; i < encoded.size(); ++i) {
        if (encoded[i] != static_cast<uint8_t>(2 * (golden[i] - '0'))) {
            std::fprintf(stderr, "Independent encoder golden vector failed at bit %zu\n", i);
            return 1;
        }
    }
    Result clean{"NXDN_REFERENCE_CLEAN"};
    Result equivalence{"NXDN_REFERENCE_UNIFORM_RELIABILITY"};
    Result erased_value{"NXDN_REFERENCE_ERASED_VALUE_INVARIANCE"};
    Result oracle{"NXDN_REFERENCE_WEIGHTED_CODEWORD_ORACLE"};
    Result independent{"NXDN_REFERENCE_BLOCK_INDEPENDENCE"};
    Result long_blocks{"NXDN_REFERENCE_LONG_UNIFORM_BLOCKS"};
    Result midpoint{"NXDN_REFERENCE_MIDPOINT_OBSERVATIONS"};

    for (unsigned payload = 0; payload < 256; ++payload) {
        const Bytes symbols = encode_byte(static_cast<uint8_t>(payload));
        const Bytes reliability(symbols.size(), 255);
        clean.record(decode(symbols, reliability, false)[0] == payload);
        clean.record(decode(symbols, reliability, true)[0] == payload);
    }

    for (unsigned trial = 0; trial < 256; ++trial) {
        Bytes observed = encode_byte(static_cast<uint8_t>(next_random() >> 24U));
        Bytes reliability(observed.size(), 255);
        for (size_t i = 0; i < observed.size(); ++i) {
            if ((next_random() >> 24U) < 55U) observed[i] ^= 2U;
        }
        const Bytes hard = decode(observed, reliability, false);
        equivalence.record(decode(observed, reliability, true) == hard);

        // Vary both reliability values independently, including real punctures.
        static constexpr std::array<uint8_t, 5> weights{{0, 17, 63, 128, 255}};
        Bytes erased_flipped = observed;
        for (size_t i = 0; i < observed.size(); ++i) {
            reliability[i] = weights[(next_random() >> 16U) % weights.size()];
            if (reliability[i] == 0) erased_flipped[i] ^= 2U;
        }
        const Bytes decoded = decode(observed, reliability, true);
        erased_value.record(decode(erased_flipped, reliability, true) == decoded);
        uint32_t best = std::numeric_limits<uint32_t>::max();
        for (unsigned payload = 0; payload < 256; ++payload) {
            best = std::min(best, best_cost_for_payload(static_cast<uint8_t>(payload), observed, reliability));
        }
        oracle.record(best_cost_for_payload(decoded[0], observed, reliability) == best);

        // A prior unrelated block must not affect B. Exercise soft and hard
        // entry points: M17 also calls the shared hard decoder after start().
        Bytes preceding(2U * (12U + (trial % 33U)));
        Bytes preceding_reliability(preceding.size(), 255);
        for (auto& symbol : preceding) symbol = static_cast<uint8_t>(2U * ((next_random() >> 24U) & 1U));
        for (bool soft : {false, true}) {
            const Bytes fresh = decode(observed, reliability, soft);
            (void)decode(preceding, preceding_reliability, soft);
            independent.record(decode(observed, reliability, soft, false) == fresh);
        }
    }
    // The stored decision array has 2400 entries. Exercise realistic long
    // control blocks plus its capacity with unstructured observations so that
    // cumulative weighted costs can exceed 65535 before traceback.
    for (unsigned pairs : {96U, 203U, 300U, 2400U}) {
        for (unsigned trial = 0; trial < 8; ++trial) {
            Bytes observed(2U * pairs);
            Bytes reliability(observed.size(), 255);
            for (auto& symbol : observed) symbol = static_cast<uint8_t>(2U * ((next_random() >> 24U) & 1U));
            long_blocks.record(decode(observed, reliability, true) == decode(observed, reliability, false));
        }
    }
    for (unsigned trial = 0; trial < 64; ++trial) {
        Bytes observed(24U);
        Bytes reliability(observed.size(), 255);
        for (auto& symbol : observed) symbol = static_cast<uint8_t>((next_random() >> 24U) % 3U);
        midpoint.record(decode(observed, reliability, true) == decode(observed, reliability, false));
        for (auto& weight : reliability) weight = static_cast<uint8_t>(next_random() >> 24U);
        const Bytes decoded = decode(observed, reliability, true);
        uint32_t best = std::numeric_limits<uint32_t>::max();
        for (unsigned payload = 0; payload < 256; ++payload) {
            best = std::min(best, best_cost_for_payload(static_cast<uint8_t>(payload), observed, reliability));
        }
        midpoint.record(best_cost_for_payload(decoded[0], observed, reliability) == best);
    }
    return clean.print() | equivalence.print() | erased_value.print() | oracle.print() | independent.print()
           | long_blocks.print() | midpoint.print();
}
