// SPDX-License-Identifier: GPL-3.0-or-later
// Controlled code-block experiment, not complete over-air NXDN frames.
// Independent polynomial encoder; puncturing follows nxdn_deperm.c's SACCH
// 12/5 and FACCH 16/9 reconstruction maps. No RF/SNR model or parameter tuning.
#include <dsd-neo/protocol/nxdn/nxdn_convolution.h>

#include <array>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace {
using Bytes = std::vector<uint8_t>;
struct Random {
    uint32_t state;
    uint32_t next() { state = state * 1664525U + 1013904223U; return state; }
    size_t index(size_t count) { return (next() >> 8U) % count; }
};
constexpr std::array<uint32_t, 2> seeds{{0x77AACE01U, 0x123F9917U}};
constexpr unsigned blocks_per_seed = 64;

struct Profile {
    const char* name;
    unsigned payload_bits;
    unsigned erased_remainder;
    unsigned period;
};
constexpr std::array<Profile, 2> profiles{{
    {"SACCH_code_block", 32, 5, 6},
    {"FACCH_code_block", 92, 1, 4},
}};

enum class Condition { Clean, Punctured, TwoUniform, TwoLow, BurstUniform, BurstLow, ExtraErasures };
constexpr std::array<const char*, 7> condition_names{{
    "clean_unpunctured", "clean_punctured", "punctured_two_flips_uniform",
    "punctured_two_flips_low_confidence", "punctured_four_transmitted_bit_burst_uniform",
    "punctured_four_transmitted_bit_burst_low_confidence", "punctured_four_extra_erasures"
}};

Bytes encode(const Bytes& payload) {
    Bytes encoded;
    unsigned history = 0;
    for (size_t i = 0; i < payload.size() + 4U; ++i) {
        const unsigned d = i < payload.size() ? payload[i] : 0U;
        const unsigned d1 = history & 1U, d2 = (history >> 1U) & 1U;
        const unsigned d3 = (history >> 2U) & 1U, d4 = (history >> 3U) & 1U;
        encoded.push_back(static_cast<uint8_t>(2U * (d ^ d3 ^ d4)));
        encoded.push_back(static_cast<uint8_t>(2U * (d ^ d1 ^ d2 ^ d4)));
        history = ((history << 1U) | d) & 15U;
    }
    return encoded;
}

Bytes decode(const Bytes& received, const Bytes& reliability, unsigned payload_bits) {
    // Reset every vector to isolate branch arithmetic from the separately
    // tested previous-block-state defect in nxdn_convolution_reference.cpp.
    CNXDNConvolution_init();
    CNXDNConvolution_start();
    for (size_t i = 0; i < received.size(); i += 2U) {
        CNXDNConvolution_decode_soft(received[i], received[i + 1U], reliability[i], reliability[i + 1U]);
    }
    Bytes packed((payload_bits + 7U) / 8U, 0);
    CNXDNConvolution_chainback(packed.data(), payload_bits);
    Bytes decoded(payload_bits);
    for (unsigned i = 0; i < payload_bits; ++i) decoded[i] = (packed[i / 8U] >> (7U - (i % 8U))) & 1U;
    return decoded;
}

std::string hex(const Bytes& bits) {
    static constexpr char digits[] = "0123456789abcdef";
    std::string out;
    for (size_t i = 0; i < bits.size(); i += 4U) {
        unsigned value = 0;
        for (size_t j = 0; j < 4U; ++j) value = (value << 1U) | (i + j < bits.size() ? bits[i + j] : 0U);
        out += digits[value];
    }
    return out;
}

void impair(const Profile& profile, Condition condition, uint32_t case_seed, Bytes& observed, Bytes& reliability) {
    if (condition == Condition::Clean) return;
    std::vector<size_t> transmitted;
    for (size_t i = 0; i < observed.size(); ++i) {
        if ((i % profile.period) == profile.erased_remainder) {
            observed[i] = 0;
            reliability[i] = 0;
        } else transmitted.push_back(i);
    }
    if (condition == Condition::Punctured) return;
    Random random{case_seed ^ 0xCAFEBABEU};
    std::vector<size_t> changed;
    if (condition == Condition::TwoUniform || condition == Condition::TwoLow) {
        while (changed.size() < 2U) {
            const size_t bit = transmitted[random.index(transmitted.size())];
            if (changed.empty() || bit != changed[0]) changed.push_back(bit);
        }
    } else {
        const size_t start = random.index(transmitted.size() - 3U);
        for (size_t i = 0; i < 4U; ++i) changed.push_back(transmitted[start + i]);
    }
    for (const size_t bit : changed) {
        if (condition == Condition::ExtraErasures) {
            observed[bit] = 0;
            reliability[bit] = 0;
        } else {
            observed[bit] ^= 2U;
            if (condition == Condition::TwoLow || condition == Condition::BurstLow) reliability[bit] = 16;
        }
    }
}
}

int main() {
    bool clean_passed = true;
    for (const auto& profile : profiles) {
        for (size_t ci = 0; ci < condition_names.size(); ++ci) {
            const Condition condition = static_cast<Condition>(ci);
            unsigned correct = 0, wrong_bits = 0;
            unsigned first_bad_block = 0;
            uint32_t first_bad_seed = 0;
            std::string first_expected, first_decoded;
            for (uint32_t seed : seeds) {
                for (unsigned block = 0; block < blocks_per_seed; ++block) {
                    const uint32_t case_seed = seed ^ (profile.payload_bits * 2654435761U) ^ (block * 2246822519U);
                    Random random{case_seed};
                    Bytes payload(profile.payload_bits);
                    for (auto& bit : payload) bit = static_cast<uint8_t>((random.next() >> 24U) & 1U);
                    Bytes observed = encode(payload);
                    Bytes reliability(observed.size(), 255);
                    impair(profile, condition, case_seed, observed, reliability);
                    const Bytes decoded = decode(observed, reliability, profile.payload_bits);
                    unsigned errors = 0;
                    for (size_t i = 0; i < payload.size(); ++i) errors += payload[i] == decoded[i] ? 0U : 1U;
                    correct += errors == 0U ? 1U : 0U;
                    wrong_bits += errors;
                    if (errors != 0U && first_expected.empty()) {
                        first_bad_seed = seed;
                        first_bad_block = block;
                        first_expected = hex(payload);
                        first_decoded = hex(decoded);
                    }
                }
            }
            const unsigned blocks = blocks_per_seed * static_cast<unsigned>(seeds.size());
            const unsigned code_bits = 2U * (profile.payload_bits + 4U);
            const unsigned punctures = condition == Condition::Clean ? 0U : code_bits / profile.period;
            if (condition == Condition::Clean || condition == Condition::Punctured) clean_passed &= correct == blocks;
            std::printf("{\"schema\":1,\"generator\":\"xerax-nxdn-codeblocks-v1\",\"profile\":\"%s\","
                        "\"condition\":\"%s\",\"seeds\":[%u,%u],\"blocks_per_seed\":%u,"
                        "\"payload_bits_per_block\":%u,\"coded_bits_per_block\":%u,\"punctures_per_block\":%u,"
                        "\"blocks\":%u,\"correct_blocks\":%u,\"incorrect_blocks\":%u,\"incorrect_payload_bits\":%u,"
                        "\"scored_payload_bits\":%u,\"first_failure\":",
                        profile.name, condition_names[ci], seeds[0], seeds[1], blocks_per_seed,
                        profile.payload_bits, code_bits, punctures, blocks, correct, blocks - correct,
                        wrong_bits, blocks * profile.payload_bits);
            if (first_expected.empty()) std::printf("null}\n");
            else std::printf("{\"seed\":%u,\"block\":%u,\"expected_hex\":\"%s\",\"decoded_hex\":\"%s\"}}\n",
                             first_bad_seed, first_bad_block, first_expected.c_str(), first_decoded.c_str());
        }
    }
    return clean_passed ? 0 : 1;
}
