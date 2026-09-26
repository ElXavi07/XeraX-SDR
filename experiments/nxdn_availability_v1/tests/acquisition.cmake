# Private acquisition contract tests; parent provides CANDIDATE_DIR and XERAX_DSD.
# The original regression files are included read-only by the new test sources.
set(_availability_tests "${CMAKE_CURRENT_LIST_DIR}")
function(availability_symbol_test target source no_radio)
    add_executable(${target} "${_availability_tests}/${source}")
    target_include_directories(${target} BEFORE PRIVATE
        "${CANDIDATE_DIR}/include" "${XERAX_DSD}/include"
        "${XERAX_DSD}/src/dsp" "${XERAX_DSD}/tests/test_support"
        ${LIBSNDFILE_INCLUDE_DIR})
    target_link_libraries(${target} PRIVATE dsd-neo_dsp_private_test_support
        dsd-neo_test_support ${LIBSNDFILE_LIBRARIES}
        $<$<NOT:$<PLATFORM_ID:Windows>>:m>)
    if(no_radio)
        # Resolve the public acquisition symbols from this local non-radio object;
        # the archive still supplies the unmodified DSP dependencies. The radio
        # symbol object must not be extracted (verify in the build map).
        target_sources(${target} PRIVATE "${CANDIDATE_DIR}/src/dsp/dsd_symbol.c")
        target_compile_definitions(${target} PRIVATE DSD_NEO_TEST_HOOKS)
        target_compile_options(${target} PRIVATE -UUSE_RADIO)
    endif()
    add_test(NAME ${target} COMMAND ${target})
    set_tests_properties(${target} PROPERTIES TIMEOUT 15)
endfunction()
availability_symbol_test(xerax_availability_symbol_replay test_checked_symbol_replay.c FALSE)
availability_symbol_test(xerax_availability_symbol_replay_no_radio test_checked_symbol_replay.c TRUE)
availability_symbol_test(xerax_availability_symbol_wav test_checked_symbol_wav.c FALSE)
availability_symbol_test(xerax_availability_symbol_wav_no_radio test_checked_symbol_wav.c TRUE)
get_target_property(_availability_radio_dir dsd-neo_feature_radio SOURCE_DIR)
get_directory_property(_availability_has_radio DIRECTORY "${_availability_radio_dir}" DEFINITION DSD_HAS_RADIO)
if(_availability_has_radio)
    availability_symbol_test(xerax_availability_symbol_live test_checked_symbol_live.c FALSE)
endif()
add_executable(xerax_availability_dibit
    "${_availability_tests}/test_checked_dibit.c"
    "${CANDIDATE_DIR}/src/core/frames/dsd_dibit.c"
    "${XERAX_DSD}/tests/test_support/call_state_stubs.c")
target_include_directories(xerax_availability_dibit BEFORE PRIVATE
    "${CANDIDATE_DIR}/include" "${XERAX_DSD}/include")
target_link_libraries(xerax_availability_dibit PRIVATE dsd-neo_platform
    $<$<NOT:$<PLATFORM_ID:Windows>>:m>)
add_test(NAME xerax_availability_dibit COMMAND xerax_availability_dibit)
set_tests_properties(xerax_availability_dibit PROPERTIES TIMEOUT 15)
