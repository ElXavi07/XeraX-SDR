# Host checks use a real Expat parser and injected SOAP responses. Production
# Android still requires both libcurl and Expat; this target performs no network.
set(EXPAT_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(EXPAT_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(EXPAT_BUILD_TOOLS OFF CACHE BOOL "" FORCE)
set(EXPAT_BUILD_DOCS OFF CACHE BOOL "" FORCE)
set(EXPAT_SHARED_LIBS OFF CACHE BOOL "" FORCE)
add_subdirectory("${XERAX_EXPAT_SOURCE}" "${CMAKE_CURRENT_BINARY_DIR}/expat" EXCLUDE_FROM_ALL)

set(DSD_RR_APP_KEY "XERAX_TEST_APPLICATION_KEY")
configure_file("${DSD}/src/runtime/radioreference/rr_app_key.c.in" "rr_app_key.c" @ONLY)
set(RR "${DSD}/src/runtime/radioreference")
add_library(rr_runtime STATIC
    "${RR}/rr_types.c" "${RR}/rr_soap.c" "${RR}/rr_client.c"
    "${RR}/rr_generate.c" "${RR}/rr_import.c" "${RR}/rr_provenance.c"
    "${CMAKE_CURRENT_BINARY_DIR}/rr_app_key.c"
    "${DSD}/src/engine/trunk_scan.c"
    "${DSD}/src/app_control/trunk_scan_validate.c"
    "${DSD}/src/app_control/trunk_scan_document.cpp"
    "${DSD}/src/runtime/scan_options.c" "${DSD}/src/runtime/scan_mode.c"
    "${DSD}/src/runtime/path_policy.c" "${DSD}/src/runtime/config_expand.c"
    "${DSD}/src/platform/file_compat_win32.c"
    "${DSD}/src/platform/posix_compat_win32.c"
    "${DSD}/src/platform/threading_win32.c" "${DSD}/src/platform/timing_win32.c"
    "${DSD}/src/core/util/key_set.c" "${DSD}/src/core/util/scan_profile.c"
    "${DSD}/src/core/file/dsd_import.c" "${DSD}/src/core/file/source_alias_csv.c"
    "${DSD}/src/core/file/p25_bandplan_csv.c"
    "${DSD}/src/core/util/talkgroup_policy.c" "${DSD}/src/core/util/dsd_state_trunk_lcn.c"
    "${DSD}/src/core/util/bit_packing.c" "${DSD}/src/runtime/state_ext.c"
    "${DSD}/src/core/util/source_alias.c" "${DSD}/src/crypto/crypt-etc.c"
    "${DSD}/src/core/vocoder/keyring.c" "${DSD}/src/core/vocoder/keyring_dmr_tg_map.c"
    "${DSD}/src/protocol/nxdn/nxdn_lfsr.c")
target_include_directories(rr_runtime PUBLIC "${RR}")
target_compile_definitions(rr_runtime PUBLIC USE_EXPAT XML_STATIC)
target_compile_options(rr_runtime PRIVATE -O2 -flto -ffunction-sections -fdata-sections)
target_link_libraries(rr_runtime PUBLIC expat)
target_sources(rr_runtime PRIVATE "${DSD}/src/runtime/decode_mode.c"
    "${DSD}/src/runtime/rtl_stream_metrics_hooks.c" "${DSD}/src/runtime/config_user.cpp")
add_executable(scan_modes "${DSD}/tests/runtime/test_runtime_scan_mode.c")
target_link_libraries(scan_modes PRIVATE rr_runtime session_models)
target_link_options(scan_modes PRIVATE -flto -Wl,--gc-sections)
add_test(NAME MIXED_ANALOG_DIGITAL_SCOPED_MODES COMMAND scan_modes)
set_target_properties(rr_runtime PROPERTIES INTERPROCEDURAL_OPTIMIZATION TRUE)

add_executable(rr_model "${DSD}/tests/ui/test_ui_qt_radio_reference_model.cpp"
    "${DSD}/src/ui/qt/radio_reference_model.cpp"
    "${DSD}/src/ui/qt/imported_files_model.cpp" "${DSD}/src/ui/qt/csv_bundle_import.cpp")
set_target_properties(rr_model PROPERTIES AUTOMOC ON)
if(WIN32)
    # Qt stores paths as UTF-8. Match narrow CRT filesystem APIs to that encoding
    # for upstream fixtures with non-ASCII names, just as Android does natively.
    enable_language(RC)
    configure_file(utf8.rc.in utf8.rc @ONLY)
    target_sources(rr_model PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/utf8.rc")
endif()
target_link_libraries(rr_model PRIVATE rr_runtime session_models Qt6::Quick)
target_compile_options(rr_model PRIVATE -O2 -flto -ffunction-sections -fdata-sections)
target_link_options(rr_model PRIVATE -flto -Wl,--gc-sections)
target_compile_definitions(rr_model PRIVATE DSD_QML_UI_DIR="${DSD}/src/ui/qt/qml"
    DSD_NEO_TEST_RR_FIXTURE_DIR="${DSD}/tests/fixtures/radioreference")
add_test(NAME RADIOREFERENCE_ACCOUNT_MODEL_AND_IMPORT COMMAND rr_model)
set_tests_properties(RADIOREFERENCE_ACCOUNT_MODEL_AND_IMPORT PROPERTIES
    ENVIRONMENT "QT_QPA_PLATFORM=offscreen;QT_QUICK_BACKEND=software")

foreach(test soap client generate import)
    add_executable(rr_${test} "${DSD}/tests/runtime/test_runtime_rr_${test}.c")
    target_link_libraries(rr_${test} PRIVATE rr_runtime session_models)
    target_link_options(rr_${test} PRIVATE -flto -Wl,--gc-sections)
    target_compile_options(rr_${test} PRIVATE -O2 -flto -include dsd-neo/core/safe_api.h)
    target_compile_definitions(rr_${test} PRIVATE
        DSD_NEO_TEST_RR_FIXTURE_DIR="${DSD}/tests/fixtures/radioreference")
    add_test(NAME RADIOREFERENCE_${test} COMMAND rr_${test})
endforeach()

add_executable(rr_conventional conventional.c)
target_link_libraries(rr_conventional PRIVATE rr_runtime session_models)
target_link_options(rr_conventional PRIVATE -flto -Wl,--gc-sections)
add_test(NAME RADIOREFERENCE_CONVENTIONAL_SHAPES COMMAND rr_conventional)
