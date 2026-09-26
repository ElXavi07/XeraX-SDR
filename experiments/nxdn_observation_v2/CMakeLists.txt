cmake_minimum_required(VERSION 3.20)
project(XeraXNxdnObservationV2 LANGUAGES C CXX)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON CACHE BOOL "Preserve observation build identity" FORCE)
include(CTest)
find_package(Python3 REQUIRED COMPONENTS Interpreter)
get_filename_component(XERAX_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
set(XERAX_DSD "${XERAX_ROOT}/upstream/dsd-neo")
list(APPEND CMAKE_MODULE_PATH "${XERAX_DSD}/cmake")
find_package(LibSndFile REQUIRED)
find_package(mbe-neo CONFIG REQUIRED)
execute_process(COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/prepare_build.py"
    "${CMAKE_CURRENT_BINARY_DIR}/generated" COMMAND_ERROR_IS_FATAL ANY)
# This parent defines private protocol/DSP libraries without running an old matrix
# or invoking historical source-patching preparers.
add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../nxdn_frames" "${CMAKE_CURRENT_BINARY_DIR}/frames")
get_target_property(FRAME_SOURCES xerax_nxdn_frame_private SOURCES)
list(FILTER FRAME_SOURCES EXCLUDE REGEX "/nxdn_(frame|deperm)\\.c$")
add_library(xerax_observation_protocol STATIC ${FRAME_SOURCES}
    "${CMAKE_CURRENT_BINARY_DIR}/generated/nxdn_frame_observed.c"
    "${CMAKE_CURRENT_BINARY_DIR}/generated/nxdn_deperm_observed.c")
foreach(property IN ITEMS INCLUDE_DIRECTORIES INTERFACE_INCLUDE_DIRECTORIES COMPILE_DEFINITIONS COMPILE_OPTIONS COMPILE_FEATURES LINK_LIBRARIES)
    get_target_property(value xerax_nxdn_frame_private ${property})
    if(value)
        set_property(TARGET xerax_observation_protocol PROPERTY ${property} "${value}")
    endif()
endforeach()
get_target_property(DSD_DIR xerax_nxdn_frame_observer SOURCE_DIR)
get_directory_property(DSD_DEFS DIRECTORY "${DSD_DIR}" COMPILE_DEFINITIONS)
target_compile_definitions(xerax_observation_protocol PRIVATE ${DSD_DEFS})
target_include_directories(xerax_observation_protocol PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
get_target_property(ENGINE_DIR dsd-neo_engine SOURCE_DIR)
get_directory_property(ENGINE_DEFS DIRECTORY "${ENGINE_DIR}" COMPILE_DEFINITIONS)
get_target_property(ENGINE_INCLUDES dsd-neo_engine INCLUDE_DIRECTORIES)
get_target_property(CLI_LINKS dsd-neo LINK_LIBRARIES)
add_executable(xerax_nxdn_observation_v2 dispatch_observed.c
    "${CMAKE_CURRENT_BINARY_DIR}/generated/observer.c" "${CMAKE_CURRENT_BINARY_DIR}/generated/engine_observed.c")
target_include_directories(xerax_nxdn_observation_v2 PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}"
    "${XERAX_DSD}/src/engine" "${XERAX_DSD}/src/dsp" "${XERAX_DSD}/src/protocol/nxdn" ${ENGINE_INCLUDES})
target_compile_definitions(xerax_nxdn_observation_v2 PRIVATE ${ENGINE_DEFS} DSD_NEO_TEST_HOOKS XERAX_ACQUISITION_RESEARCH XERAX_NXDN_FRAME_RESEARCH)
target_link_libraries(xerax_nxdn_observation_v2 PRIVATE "-Wl,--start-group" xerax_observation_protocol
    dsd-neo_dsp_private_test_support dsd-neo_engine "-Wl,--end-group"
    dsd-neo_warnings dsd-neo_feature_radio dsd-neo_feature_lz ${CLI_LINKS})
target_link_options(xerax_nxdn_observation_v2 PRIVATE "-Wl,-Map=${CMAKE_CURRENT_BINARY_DIR}/observation.map")
foreach(function IN ITEMS getDibitSoft nxdn_voice processMbeFrameSoft processAudio rtl_stream_start rtl_stream_tune
    rtl_stream_tune_tagged rtl_stream_output_rate rtl_stream_request_fsk_reacquire)
    target_link_options(xerax_nxdn_observation_v2 PRIVATE "-Wl,--wrap=${function}")
endforeach()
