cmake_minimum_required(VERSION 3.20)
project(XeraXChecks LANGUAGES C CXX)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
enable_testing()
add_executable(nxdn_search nxdn_search.cpp ../upstream/dsd-neo/src/platform/nxdn_search.cpp)
target_compile_options(nxdn_search PRIVATE -O2)
add_test(NAME NXDN_EXPERIMENTAL_SEED_RECOVERY COMMAND nxdn_search)
add_executable(site_capture site_capture.cpp ../upstream/dsd-neo/src/platform/channel_bank.cpp)
add_executable(rtl_tcp_header rtl_tcp_header.cpp)
add_test(NAME RTL_TCP_HEADER_AND_FRAGMENTATION COMMAND rtl_tcp_header)
if(NOT XERAX_EXPAT_SOURCE)
    message(FATAL_ERROR "The expansion checks require -DXERAX_EXPAT_SOURCE=<libexpat source>/expat; see docs/BUILD.md")
endif()
get_filename_component(DSD "${CMAKE_CURRENT_LIST_DIR}/../upstream/dsd-neo" ABSOLUTE)
include_directories("${DSD}/include" "${DSD}/tests/test_support" "${DSD}/src/third_party")

add_library(fec STATIC "${DSD}/src/fec/fec.c" "${DSD}/src/fec/bptc.c"
    "${DSD}/src/fec/rs-12-9.c" "${DSD}/src/fec/ez.cpp")
foreach(test block_codes bptc_rs)
    add_executable(fec_${test} "${DSD}/tests/fec/test_fec_${test}.c")
    target_link_libraries(fec_${test} PRIVATE fec)
    add_test(NAME FEC_${test} COMMAND fec_${test})
endforeach()
add_executable(p25_bch "${DSD}/tests/fec/test_fec_bch_63_16_unit.cpp")
target_link_libraries(p25_bch PRIVATE fec)
add_test(NAME P25_BCH COMMAND p25_bch)
foreach(test convolution lfsr)
    add_executable(nxdn_${test} "${DSD}/tests/protocol/nxdn/test_nxdn_${test}.c"
        "${DSD}/src/protocol/nxdn/nxdn_${test}.c")
    add_test(NAME NXDN_${test} COMMAND nxdn_${test})
endforeach()

find_package(Qt6 6.11 REQUIRED COMPONENTS Core Gui Qml Quick)
add_library(session_models STATIC
    "${DSD}/src/ui/qt/site_groups.cpp" "${DSD}/src/ui/qt/saved_systems_model.cpp"
    "${DSD}/src/ui/qt/json_store.cpp" "${DSD}/src/ui/qt/app_prefs.cpp"
    "${DSD}/src/ui/qt/call_library.cpp"
    "${DSD}/src/ui/qt/session_args.cpp" "${DSD}/src/ui/qt/decoder_host.cpp"
    "${DSD}/src/ui/qt/scan_lists_model.cpp" "${DSD}/src/ui/qt/scan_list_targets.cpp"
    "${DSD}/src/runtime/log.cpp" "${DSD}/src/runtime/unicode.cpp")
set_target_properties(session_models PROPERTIES AUTOMOC ON)
target_compile_definitions(session_models PUBLIC QT_NO_KEYWORDS)
target_include_directories(session_models PUBLIC "${DSD}/src/ui/qt")
target_link_libraries(session_models PUBLIC Qt6::Gui gdi32)
add_executable(session_args "${DSD}/tests/ui/test_ui_qt_session_args.cpp")
target_link_libraries(session_args PRIVATE session_models)
add_test(NAME SESSION_ARGUMENTS_AND_KEYS COMMAND session_args)
add_executable(privacy_editor privacy_editor.cpp)
target_link_libraries(privacy_editor PRIVATE session_models Qt6::Quick)
target_compile_definitions(privacy_editor PRIVATE XERAX_QML_DIR="${DSD}/src/ui/qt/qml")
add_test(NAME PRIVACY_EDITOR_QML COMMAND privacy_editor)
set_tests_properties(PRIVACY_EDITOR_QML PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen;QT_QUICK_BACKEND=software")

add_executable(scan_policy scan_policy.cpp)
target_link_libraries(scan_policy PRIVATE session_models)
add_test(NAME SCANNER_POLICY_AND_PERSISTENCE COMMAND scan_policy)
add_executable(scan_targets "${DSD}/tests/ui/test_ui_qt_scan_list_targets.cpp")
target_link_libraries(scan_targets PRIVATE session_models)
add_test(NAME SCANNER_TARGET_REGRESSION COMMAND scan_targets)

find_package(Qt6 REQUIRED COMPONENTS QuickTest)
add_executable(scanner_qml scanner_qml.cpp scanner_context.h radio_fixture.h rr_fixture.h)
target_sources(scanner_qml PRIVATE
    "${DSD}/src/ui/qt/spectrum_model.cpp" "${DSD}/src/ui/qt/spectrum_view_item.cpp"
    "${DSD}/tests/ui/qml_spectrum_stub.cpp"
    "${DSD}/src/runtime/decode_mode.c" "${DSD}/src/runtime/rtl_stream_metrics_hooks.c")
set_target_properties(scanner_qml PROPERTIES AUTOMOC ON)
target_link_libraries(scanner_qml PRIVATE session_models Qt6::QuickTest Qt6::Quick)
target_compile_definitions(scanner_qml PRIVATE QUICK_TEST_SOURCE_DIR="${CMAKE_CURRENT_LIST_DIR}/qml"
    XERAX_QML_DIR="${DSD}/src/ui/qt/qml")
add_test(NAME SCANNER_AND_RECEPTION_QML COMMAND scanner_qml)
set_tests_properties(SCANNER_AND_RECEPTION_QML PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen;QT_QUICK_BACKEND=software")

add_executable(decode_modes "${DSD}/tests/runtime/test_runtime_decode_mode.c"
    "${DSD}/src/runtime/decode_mode.c" "${DSD}/src/runtime/rtl_stream_metrics_hooks.c")
add_test(NAME ANALOG_AND_DIGITAL_MODE_PRESETS COMMAND decode_modes)

add_executable(aaudio_backend "${DSD}/tests/platform/test_platform_audio_aaudio.c")
target_sources(aaudio_backend PRIVATE "${DSD}/src/platform/audio_replay.cpp")
target_include_directories(aaudio_backend PRIVATE "${DSD}/tests/platform/aaudio_stub")
add_test(NAME ANDROID_AUDIO_ROUTING_AND_BACKEND COMMAND aaudio_backend)

if(XERAX_EXPAT_SOURCE)
    add_subdirectory(radioreference)
endif()

add_executable(expansion expansion.cpp
    "${DSD}/src/platform/channel_bank.cpp"
    "${DSD}/src/ui/qt/receiver_tools.cpp" "${DSD}/src/ui/qt/receiver_backup.cpp"
    "${DSD}/src/platform/audio_replay.cpp" "${DSD}/src/platform/analog_tones.cpp")
set_target_properties(expansion PROPERTIES AUTOMOC ON)
target_link_libraries(expansion PRIVATE session_models rr_runtime)
target_link_options(expansion PRIVATE -flto -Wl,--gc-sections)
add_test(NAME REPLAY_TONES_PRIORITY_BACKUP COMMAND expansion)
add_executable(analog_dsp analog_dsp.cpp "${DSD}/src/dsp/demod_pipeline.cpp")
target_compile_options(analog_dsp PRIVATE -O2 -flto -ffunction-sections -fdata-sections)
target_link_options(analog_dsp PRIVATE -flto -Wl,--gc-sections)
add_test(NAME AM_NFM_WFM_DISCRIMINATORS COMMAND analog_dsp)

target_sources(scanner_qml PRIVATE "${DSD}/src/ui/qt/receiver_tools.cpp" "${DSD}/src/ui/qt/receiver_backup.cpp"
    "${DSD}/src/platform/audio_replay.cpp" "${DSD}/src/platform/analog_tones.cpp" frontend_stub.cpp)
target_link_libraries(scanner_qml PRIVATE rr_runtime)
target_link_options(scanner_qml PRIVATE -flto -Wl,--gc-sections)

add_library(receiver_assistance STATIC
    "${DSD}/src/platform/nxdn_search.cpp"
    "${DSD}/src/ui/qt/receiver_assistant.cpp" "${DSD}/src/ui/qt/app_language.cpp"
    "${DSD}/src/platform/receiver_filter.cpp"
    "${DSD}/src/platform/audio_replay.cpp" "${DSD}/src/platform/analog_tones.cpp")
set_target_properties(receiver_assistance PROPERTIES AUTOMOC ON)
target_link_libraries(receiver_assistance PUBLIC session_models Qt6::Qml)
target_link_libraries(scanner_qml PRIVATE receiver_assistance)
target_sources(scanner_qml PRIVATE "${DSD}/src/ui/qt/decryption_profiles_model.cpp")
add_executable(receiver_assistant receiver_assistant.cpp)
target_link_libraries(receiver_assistant PRIVATE receiver_assistance)
target_compile_definitions(receiver_assistant PRIVATE XERAX_QML_DIR="${DSD}/src/ui/qt/qml")
add_test(NAME RECEIVER_ASSISTANT_POLICIES_AND_FILTERS COMMAND receiver_assistant)

set_target_properties(receiver_assistant PROPERTIES AUTOMOC ON)

add_executable(adp_rc4 "${DSD}/tests/crypto/test_rc4.c" "${DSD}/src/crypto/crypt-rc4.c")
target_compile_options(adp_rc4 PRIVATE -ffunction-sections -fdata-sections)
target_link_options(adp_rc4 PRIVATE -Wl,--gc-sections)
add_test(NAME ADP_ARC4_KNOWN_VECTORS COMMAND adp_rc4)
add_executable(decryption_profiles "${DSD}/tests/ui/test_ui_qt_decryption_profiles.cpp"
    "${DSD}/src/ui/qt/decryption_profiles_model.cpp")
set_target_properties(decryption_profiles PROPERTIES AUTOMOC ON)
target_link_libraries(decryption_profiles PRIVATE rr_runtime session_models)
target_link_options(decryption_profiles PRIVATE -flto -Wl,--gc-sections)
add_test(NAME ADP_PROFILES_AND_KEY_PERSISTENCE COMMAND decryption_profiles)

add_executable(key_selection key_selection.c "${DSD}/src/dsp/frame_sync_profile.c")
target_link_libraries(key_selection PRIVATE rr_runtime session_models)
target_compile_options(key_selection PRIVATE -O2 -flto -ffunction-sections -fdata-sections)
target_link_options(key_selection PRIVATE -flto -Wl,--gc-sections)
add_test(NAME NATIVE_KEY_SELECTION_AND_NXDN_MISSING_KEYS COMMAND key_selection)

find_path(XERAX_CODEC_HEADERS mbelib-neo/mbelib.h
    HINTS "$ENV{LOCALAPPDATA}/XeraXSDR-build/installed/arm64-android-static/include" REQUIRED)
add_executable(native_voice_privacy native_voice_privacy.c
    "${DSD}/src/crypto/crypt-rc4.c" "${DSD}/src/core/file/dsd_file.c")
target_include_directories(native_voice_privacy PRIVATE "${XERAX_CODEC_HEADERS}")
target_link_libraries(native_voice_privacy PRIVATE rr_runtime session_models)
target_compile_options(native_voice_privacy PRIVATE -O2 -flto -ffunction-sections -fdata-sections)
target_link_options(native_voice_privacy PRIVATE -flto -Wl,--gc-sections)
add_test(NAME NATIVE_P25_DMR_ADP_AND_NXDN_VOICE_PAYLOADS COMMAND native_voice_privacy)

target_sources(receiver_assistance PRIVATE "${DSD}/src/ui/qt/receiver_expansion.cpp" "${DSD}/src/platform/channel_bank.cpp" "${DSD}/src/platform/analog_signaling.cpp" "${DSD}/src/platform/receiver_lab.cpp")
target_sources(analog_dsp PRIVATE "${DSD}/src/platform/receiver_lab.cpp")

add_executable(advanced_receiver advanced_receiver.cpp "${DSD}/src/platform/analog_recording.cpp")
target_link_libraries(advanced_receiver PRIVATE receiver_assistance)
add_test(NAME ADVANCED_RECEIVER_DSP_SIGNALING_LIBRARY COMMAND advanced_receiver)

add_executable(p25_supplied_keys p25_supplied_keys.c
    "${DSD}/src/crypto/crypt-aes.c" "${DSD}/src/crypto/crypt-des.c"
    "${DSD}/src/crypto/crypt-kirisun.c" "${DSD}/src/crypto/crypt-rc4.c"
    "${DSD}/src/crypto/md2ii.c" "${DSD}/src/crypto/crypt-pc4.c"
    "${DSD}/src/protocol/p25/p25_lfsr.c" "${DSD}/src/core/audio/dsd_audio_gate.c")
target_include_directories(p25_supplied_keys PRIVATE "${XERAX_CODEC_HEADERS}")
target_link_libraries(p25_supplied_keys PRIVATE rr_runtime session_models)
target_compile_options(p25_supplied_keys PRIVATE -O2 -flto -ffunction-sections -fdata-sections)
target_link_options(p25_supplied_keys PRIVATE -flto -Wl,--gc-sections)
add_test(NAME P25_AES_DES_SUPPLIED_KEY_REFERENCE_PAYLOADS COMMAND p25_supplied_keys)

add_executable(channel_capture channel_capture.cpp "${DSD}/src/platform/channel_bank.cpp")
target_include_directories(channel_capture PRIVATE "${DSD}/include")
target_compile_options(channel_capture PRIVATE -O2)
add_executable(hackrf_source hackrf_source.cpp "${DSD}/src/io/radio/hackrf_source.cpp" "${DSD}/src/platform/channel_bank.cpp")
target_include_directories(hackrf_source PRIVATE "${DSD}/src/io/radio" "${DSD}/android/third_party/libhackrf" "${DSD}/android/third_party/libusb/libusb")
target_compile_definitions(hackrf_source PRIVATE DSD_HAVE_HACKRF libhackrf_EXPORTS)
target_compile_options(hackrf_source PRIVATE -O2)
add_test(NAME HACKRF_ADAPTER_FILTER_AND_LIFECYCLE COMMAND hackrf_source)

add_library(ai_receiver_runtime STATIC "${DSD}/src/ui/qt/ai_protocol.cpp" "${DSD}/src/ui/qt/ai_transport.cpp" "${DSD}/src/ui/qt/ai_receiver.cpp")
set_target_properties(ai_receiver_runtime PROPERTIES AUTOMOC ON)
target_compile_definitions(ai_receiver_runtime PUBLIC QT_NO_KEYWORDS)
target_include_directories(ai_receiver_runtime PUBLIC "${DSD}/src/ui/qt")
target_link_libraries(ai_receiver_runtime PUBLIC Qt6::Gui)
target_link_libraries(scanner_qml PRIVATE ai_receiver_runtime)
add_executable(ai_receiver ai_receiver.cpp)
set_target_properties(ai_receiver PROPERTIES AUTOMOC ON)
target_link_libraries(ai_receiver PRIVATE ai_receiver_runtime Qt6::Qml)
add_test(NAME AI_PROVIDERS_TOOLS_PRIVACY_AND_CANCELLATION COMMAND ai_receiver)

add_library(range_scanner_runtime STATIC "${DSD}/src/ui/qt/range_scanner.cpp")
set_target_properties(range_scanner_runtime PROPERTIES AUTOMOC ON)
target_link_libraries(range_scanner_runtime PUBLIC session_models)
target_link_libraries(scanner_qml PRIVATE range_scanner_runtime)
add_executable(range_scanner range_scanner.cpp "${DSD}/src/runtime/decode_mode.c" "${DSD}/src/runtime/rtl_stream_metrics_hooks.c"
    "${DSD}/src/platform/audio_replay.cpp")
set_target_properties(range_scanner PROPERTIES AUTOMOC ON)
target_compile_options(range_scanner PRIVATE -ffunction-sections -fdata-sections)
target_link_options(range_scanner PRIVATE -Wl,--gc-sections)
target_link_libraries(range_scanner PRIVATE range_scanner_runtime)
add_test(NAME RANGE_SCANNER_DETECTION_TUNING_AUDIO_AND_RESUME COMMAND range_scanner)
