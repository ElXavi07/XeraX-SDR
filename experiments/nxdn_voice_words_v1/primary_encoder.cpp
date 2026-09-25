// Registered clear-word corpus wrapper. The channel encoder is the untouched
// MMDVM-Host implementation at 590c531391dfd3146073afbc3956f70d42c62a46.
// This program performs no decoding, synthesis, radio I/O or privacy operation.
#include "NXDNAudio.h"

#include <array>
#include <cstddef>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
constexpr std::size_t kRecords = 4133;
constexpr std::size_t kInputRecordBytes = 13;
constexpr std::size_t kOutputRecordBytes = 18;
constexpr std::size_t kInputBytes = kRecords * kInputRecordBytes;
constexpr std::size_t kOutputBytes = kRecords * kOutputRecordBytes;

void run(const std::filesystem::path& input_path,
         const std::filesystem::path& output_path) {
    if (!std::filesystem::is_regular_file(input_path)) {
        throw std::runtime_error("input must be a regular file");
    }
    if (std::filesystem::file_size(input_path) != kInputBytes) {
        throw std::runtime_error("input must contain exactly 4133 records of 13 bytes");
    }
    if (std::filesystem::absolute(input_path).lexically_normal()
        == std::filesystem::absolute(output_path).lexically_normal()) {
        throw std::runtime_error("input and output must be distinct");
    }
    // Inspect the entry itself so a dangling output symlink is also rejected.
    // The runner owns a fresh output directory; this check is not an atomic
    // multi-process file reservation.
    if (std::filesystem::symlink_status(output_path).type()
        != std::filesystem::file_type::not_found) {
        throw std::runtime_error("refusing an existing output entry");
    }

    std::array<unsigned char, kInputBytes> input{};
    std::ifstream source(input_path, std::ios::binary);
    if (!source) {
        throw std::runtime_error("cannot open input");
    }
    source.read(reinterpret_cast<char*>(input.data()),
                static_cast<std::streamsize>(input.size()));
    if (!source || source.gcount() != static_cast<std::streamsize>(input.size())) {
        throw std::runtime_error("short or failed input read");
    }
    char extra = 0;
    source.read(&extra, 1);
    if (source.gcount() != 0 || !source.eof() || source.bad()) {
        throw std::runtime_error("input size changed or read failed");
    }
    source.clear();
    source.close();
    if (source.fail()) {
        throw std::runtime_error("input close failed");
    }
    for (std::size_t record = 0; record < kRecords; ++record) {
        if ((input[record * kInputRecordBytes + 12] & 0x3FU) != 0U) {
            throw std::runtime_error("nonzero six-bit input padding");
        }
    }

    // Open only after validating the complete finite input. A failed write
    // leaves its partial output for the outer evidence-preserving runner.
    std::ofstream destination(output_path, std::ios::binary | std::ios::out);
    if (!destination) {
        throw std::runtime_error("cannot create output");
    }
    CNXDNAudio audio;
    for (std::size_t record = 0; record < kRecords; ++record) {
        std::array<unsigned char, kOutputRecordBytes> output{};
        audio.encode(input.data() + record * kInputRecordBytes, output.data());
        destination.write(reinterpret_cast<const char*>(output.data()),
                          static_cast<std::streamsize>(output.size()));
        if (!destination) {
            throw std::runtime_error("output write failed");
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
    std::cout << "{\"schema\":1,\"kind\":\"primary_voice_encoder\","
                 "\"records\":" << kRecords
              << ",\"words\":" << kRecords * 2
              << ",\"input_bytes\":" << kInputBytes
              << ",\"output_bytes\":" << kOutputBytes
              << ",\"encode_calls\":" << kRecords << "}\n";
    std::cout.flush();
    if (!std::cout) {
        throw std::runtime_error("summary write failed");
    }
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 3) {
            throw std::runtime_error("usage: primary_encoder input13stream output18stream");
        }
        run(std::filesystem::path(argv[1]), std::filesystem::path(argv[2]));
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "primary_encoder: " << error.what() << '\n';
        return 1;
    } catch (...) {
        std::cerr << "primary_encoder: unknown failure\n";
        return 1;
    }
}
