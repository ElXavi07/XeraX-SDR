// Registered clear conventional air-frame reference, not a receiver.
// Real encoding routines: MMDVM-Host 590c531391dfd3146073afbc3956f70d42c62a46.
// SACCH/FACCH audit copies contain only the five preregistered safety changes.
#include "NXDNAudio.h"
#include "NXDNFACCH1.h"
#include "NXDNLICH.h"
#include "NXDNSACCH.h"
#include "Sync.h"
#include "primary_whitening.h"

#include <algorithm>
#include <array>
#include <cstddef>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>

namespace {
constexpr std::size_t kRecords = 9;
constexpr std::size_t kRecordBytes = 41;
constexpr std::size_t kInputBytes = kRecords * kRecordBytes;
constexpr std::size_t kOutputBytes = kRecords * 96;
constexpr std::array<unsigned char, 9> kLich{{0x83, 0xAE, 0xAE, 0xAE, 0xAE,
                                           0xAE, 0xA6, 0xAA, 0x83}};
constexpr std::array<unsigned char, 10> kVcall{{0x01, 0x00, 0x20, 0x03, 0x85,
                                              0x04, 0xB1, 0x00, 0x00, 0x00}};

bool read_bit(const unsigned char* data, std::size_t bit) {
    return (data[bit / 8] & (0x80U >> (bit % 8))) != 0U;
}

void validate(const std::array<unsigned char, kInputBytes>& input) {
    for (std::size_t record = 0; record < kRecords; ++record) {
        const auto* row = input.data() + record * kRecordBytes;
        const bool full_control = record == 0 || record == 8;
        const bool pure_voice = record >= 1 && record <= 5;
        if (row[0] != kLich[record]) {
            throw std::runtime_error("registered LICH/profile order mismatch");
        }
        std::array<unsigned char, 4> sacch{};
        if (full_control) {
            sacch[0] = 1;  // Structure zero; RAN one.
            sacch[1] = 0x10;  // First eighteen bits of SACCH_IDLE.
        } else {
            const std::size_t fragment = (record - 1) % 4;
            sacch[0] = static_cast<unsigned char>(((3 - fragment) << 6) | 1);
            for (std::size_t bit = 0; bit < 18; ++bit) {
                if (read_bit(kVcall.data(), fragment * 18 + bit)) {
                    sacch[1 + bit / 8] |= static_cast<unsigned char>(0x80U >> (bit % 8));
                }
            }
        }
        if (!std::equal(sacch.begin(), sacch.end(), row + 1)) {
            throw std::runtime_error("registered SACCH/RAN/fragment/padding mismatch");
        }
        auto facch = kVcall;
        if (record == 8) {
            facch[0] = 0x08;
        }
        if (pure_voice) {
            facch.fill(0);
        }
        if (!std::equal(facch.begin(), facch.end(), row + 5)) {
            throw std::runtime_error("registered FACCH/control/placeholder mismatch");
        }
        if ((row[27] & 0x3FU) != 0U || (row[40] & 0x3FU) != 0U) {
            throw std::runtime_error("voice pair has nonzero six-bit padding");
        }
        if (full_control && !std::all_of(row + 15, row + 41,
                                        [](unsigned char v) { return v == 0; })) {
            throw std::runtime_error("control frame voice placeholders must be zero");
        }
        if (record == 6 || record == 7) {
            const auto* original = input.data() + (record - 5) * kRecordBytes + 15;
            if (!std::equal(row + 15, row + 41, original)) {
                throw std::runtime_error("half-steal source quartet does not match registered repeat");
            }
        }
    }
    // The independent corpus/checker additionally establishes the first twenty
    // source words against the frozen original asset. This wrapper does not
    // substitute channel output or a receiver result for source-word identity.
}

void run(const std::filesystem::path& input_path, const std::filesystem::path& output_path) {
    if (!std::filesystem::is_regular_file(input_path)
        || std::filesystem::file_size(input_path) != kInputBytes) {
        throw std::runtime_error("input must contain exactly nine 41-byte records");
    }
    if (std::filesystem::absolute(input_path).lexically_normal()
        == std::filesystem::absolute(output_path).lexically_normal()) {
        throw std::runtime_error("input and output must be distinct");
    }
    // The runner reserves a new private directory. This check rejects dangling
    // symlinks too, but is not an atomic multi-process output reservation.
    if (std::filesystem::symlink_status(output_path).type()
        != std::filesystem::file_type::not_found) {
        throw std::runtime_error("refusing an existing output entry");
    }
    std::array<unsigned char, kInputBytes> input{};
    std::ifstream source(input_path, std::ios::binary);
    if (!source) {
        throw std::runtime_error("cannot open input");
    }
    source.read(reinterpret_cast<char*>(input.data()), static_cast<std::streamsize>(input.size()));
    if (!source || source.gcount() != static_cast<std::streamsize>(input.size())) {
        throw std::runtime_error("short or failed input read");
    }
    char extra = 0;
    source.read(&extra, 1);
    if (source.gcount() != 0 || !source.eof() || source.bad()) {
        throw std::runtime_error("input changed size or read failed");
    }
    source.clear();
    source.close();
    if (source.fail()) {
        throw std::runtime_error("input close failed");
    }
    validate(input);

    std::ofstream destination(output_path, std::ios::binary | std::ios::out);
    if (!destination) {
        throw std::runtime_error("cannot create output");
    }
    std::size_t sacch_calls = 0;
    std::size_t facch_calls = 0;
    std::size_t voice_pair_calls = 0;
    CNXDNAudio audio;
    for (std::size_t record = 0; record < kRecords; ++record) {
        const auto* row = input.data() + record * kRecordBytes;
        std::array<unsigned char, 48> raw{};
        CSync::addNXDNSync(raw.data());
        CNXDNLICH lich;
        lich.setRaw(0);
        lich.setRFCT(static_cast<unsigned char>(row[0] >> 6));
        lich.setFCT(static_cast<unsigned char>((row[0] >> 4) & 3U));
        lich.setOption(static_cast<unsigned char>((row[0] >> 2) & 3U));
        lich.setDirection(static_cast<unsigned char>((row[0] >> 1) & 1U));
        lich.encode(raw.data());
        if (lich.getRaw() != row[0]) {
            throw std::runtime_error("primary LICH parity disagrees with registered profile");
        }
        CNXDNSACCH sacch;
        sacch.setRaw(row + 1);
        sacch.encode(raw.data());
        ++sacch_calls;
        CNXDNFACCH1 facch;
        facch.setData(row + 5);
        const bool full_control = record == 0 || record == 8;
        if (full_control || record == 6) {
            facch.encode(raw.data(), 96U);
            ++facch_calls;
        } else {
            audio.encode(row + 15, raw.data() + 12);
            ++voice_pair_calls;
        }
        if (full_control || record == 7) {
            facch.encode(raw.data(), 240U);
            ++facch_calls;
        } else {
            audio.encode(row + 28, raw.data() + 30);
            ++voice_pair_calls;
        }
        std::array<unsigned char, 48> air{};
        for (std::size_t byte = 0; byte < air.size(); ++byte) {
            air[byte] = static_cast<unsigned char>(raw[byte] ^ xerax_primary::kWhitening[byte]);
        }
        destination.write(reinterpret_cast<const char*>(raw.data()),
                          static_cast<std::streamsize>(raw.size()));
        destination.write(reinterpret_cast<const char*>(air.data()),
                          static_cast<std::streamsize>(air.size()));
        if (!destination) {
            throw std::runtime_error("output write failed; partial evidence retained");
        }
    }
    destination.flush();
    if (!destination) {
        throw std::runtime_error("output flush failed");
    }
    destination.close();
    if (destination.fail() || std::filesystem::file_size(output_path) != kOutputBytes) {
        throw std::runtime_error("output close or final size check failed");
    }
    if (sacch_calls != 9 || facch_calls != 6 || voice_pair_calls != 12) {
        throw std::runtime_error("unexpected actual encoder call counts");
    }
    std::cout << "{\"schema\":1,\"kind\":\"nxdn_air_primary\",\"frames\":9,"
                 "\"input_bytes\":369,\"output_bytes\":864,\"sacch_calls\":"
              << sacch_calls << ",\"facch_calls\":" << facch_calls
              << ",\"voice_pair_calls\":" << voice_pair_calls << "}\n";
    std::cout.flush();
    if (!std::cout) {
        throw std::runtime_error("summary write failed");
    }
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 3) {
            throw std::runtime_error("usage: primary_encoder input41stream output96stream");
        }
        run(argv[1], argv[2]);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "primary_encoder: " << error.what() << '\n';
        return 1;
    } catch (...) {
        std::cerr << "primary_encoder: unknown failure\n";
        return 1;
    }
}
