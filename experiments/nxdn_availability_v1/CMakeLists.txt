cmake_minimum_required(VERSION 3.20)
project(XeraXNxdnAvailabilityV1 LANGUAGES C CXX)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON CACHE BOOL "Preserve candidate build identity" FORCE)
include(CTest)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
get_filename_component(XERAX_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
set(XERAX_DSD "${XERAX_ROOT}/upstream/dsd-neo")
set(CANDIDATE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/candidate")
list(APPEND CMAKE_MODULE_PATH "${XERAX_DSD}/cmake")
find_package(LibSndFile REQUIRED)
find_package(mbe-neo CONFIG REQUIRED)
execute_process(COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/prepare_build.py"
    "${CMAKE_CURRENT_BINARY_DIR}/generated" COMMAND_ERROR_IS_FATAL ANY)

# Import definitions, never an old generator/matrix. Replace only this build's
# private DSP test archive; shipped targets and the original tree stay intact.
add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../nxdn_frames" "${CMAKE_CURRENT_BINARY_DIR}/frames")
get_target_property(DSP_SOURCES dsd-neo_dsp_private_test_support SOURCES)
list(FILTER DSP_SOURCES EXCLUDE REGEX "(^|/)dsd_symbol\\.c$")
list(APPEND DSP_SOURCES "${CANDIDATE_DIR}/src/dsp/dsd_symbol.c")
set_property(TARGET dsd-neo_dsp_private_test_support PROPERTY SOURCES ${DSP_SOURCES})
target_include_directories(dsd-neo_dsp_private_test_support BEFORE PRIVATE
    "${CANDIDATE_DIR}/include" "${XERAX_DSD}/src/dsp")

get_target_property(FRAME_SOURCES xerax_nxdn_frame_private SOURCES)
list(FILTER FRAME_SOURCES EXCLUDE REGEX "/nxdn_(frame|deperm)\\.c$")
add_library(xerax_availability_protocol STATIC ${FRAME_SOURCES}
    "${CMAKE_CURRENT_BINARY_DIR}/generated/nxdn_frame_observed.c"
    "${CMAKE_CURRENT_BINARY_DIR}/generated/nxdn_deperm_observed.c"
    "${CANDIDATE_DIR}/src/protocol/nxdn/nxdn_voice.c")
foreach(property IN ITEMS INCLUDE_DIRECTORIES INTERFACE_INCLUDE_DIRECTORIES COMPILE_DEFINITIONS COMPILE_OPTIONS COMPILE_FEATURES LINK_LIBRARIES)
    get_target_property(value xerax_nxdn_frame_private ${property})
    if(value)
        set_property(TARGET xerax_availability_protocol PROPERTY ${property} "${value}")
    endif()
endforeach()
get_target_property(DSD_DIR xerax_nxdn_frame_observer SOURCE_DIR)
get_directory_property(DSD_DEFS DIRECTORY "${DSD_DIR}" COMPILE_DEFINITIONS)
target_compile_definitions(xerax_availability_protocol PRIVATE ${DSD_DEFS})
target_include_directories(xerax_availability_protocol BEFORE PRIVATE
    "${CANDIDATE_DIR}/include" "${CMAKE_CURRENT_BINARY_DIR}/generated")
get_target_property(ENGINE_DIR dsd-neo_engine SOURCE_DIR)
get_directory_property(ENGINE_DEFS DIRECTORY "${ENGINE_DIR}" COMPILE_DEFINITIONS)
get_target_property(ENGINE_INCLUDES dsd-neo_engine INCLUDE_DIRECTORIES)
get_target_property(CLI_LINKS dsd-neo LINK_LIBRARIES)
add_executable(xerax_nxdn_availability_v1
    "${CMAKE_CURRENT_BINARY_DIR}/generated/dispatch_observed.c"
    "${CMAKE_CURRENT_BINARY_DIR}/generated/observer.c"
    "${CMAKE_CURRENT_BINARY_DIR}/generated/engine_observed.c"
    "${CANDIDATE_DIR}/src/core/frames/dsd_dibit.c")
target_include_directories(xerax_nxdn_availability_v1 BEFORE PRIVATE
    "${CANDIDATE_DIR}/include" "${CMAKE_CURRENT_BINARY_DIR}/generated"
    "${XERAX_DSD}/src/engine" "${XERAX_DSD}/src/engine/dispatch" "${XERAX_DSD}/src/dsp"
    "${XERAX_DSD}/src/protocol/nxdn" ${ENGINE_INCLUDES})
target_compile_definitions(xerax_nxdn_availability_v1 PRIVATE ${ENGINE_DEFS}
    DSD_NEO_TEST_HOOKS XERAX_ACQUISITION_RESEARCH XERAX_NXDN_FRAME_RESEARCH)
target_link_libraries(xerax_nxdn_availability_v1 PRIVATE "-Wl,--start-group" xerax_availability_protocol
    dsd-neo_dsp_private_test_support dsd-neo_engine "-Wl,--end-group"
    dsd-neo_warnings dsd-neo_feature_radio dsd-neo_feature_lz ${CLI_LINKS})
target_link_options(xerax_nxdn_availability_v1 PRIVATE "-Wl,-Map=${CMAKE_CURRENT_BINARY_DIR}/availability.map")
foreach(function IN ITEMS dsd_get_dibit_soft_checked nxdn_voice_masked processMbeFrameSoft processMbeFrame processAudio
    mbe_decodeAmbe3600x2450Frame mbe_decodeAmbe3600x2450SoftFrame mbe_processAmbe2450Dataf
    rtl_stream_start rtl_stream_tune rtl_stream_tune_tagged rtl_stream_output_rate rtl_stream_request_fsk_reacquire)
    target_link_options(xerax_nxdn_availability_v1 PRIVATE "-Wl,--wrap=${function}")
endforeach()
get_directory_property(DSD_HAS_RADIO DIRECTORY "${XERAX_DSD}" DEFINITION DSD_HAS_RADIO)
include("${CMAKE_CURRENT_SOURCE_DIR}/tests/acquisition.cmake")
include("${CMAKE_CURRENT_SOURCE_DIR}/tests/frame_voice.cmake")
find_package(Threads REQUIRED)
foreach(unit IN ITEMS xerax_nxdn_voice_available xerax_nxdn_frame_available
    xerax_availability_symbol_replay xerax_availability_symbol_replay_no_radio
    xerax_availability_symbol_wav xerax_availability_symbol_wav_no_radio
    xerax_availability_symbol_live xerax_availability_dibit)
    if(TARGET ${unit})
        target_link_libraries(${unit} PRIVATE Threads::Threads)
        target_link_options(${unit} PRIVATE "-Wl,-Map=${CMAKE_CURRENT_BINARY_DIR}/${unit}.map")
    endif()
endforeach()
