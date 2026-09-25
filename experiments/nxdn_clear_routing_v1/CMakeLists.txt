cmake_minimum_required(VERSION 3.20)
project(XeraXClearNxdnRoutingV1 LANGUAGES C CXX)
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

# Import library definitions only. No historical source generator or matrix runs.
add_subdirectory("${CMAKE_CURRENT_SOURCE_DIR}/../nxdn_frames" "${CMAKE_CURRENT_BINARY_DIR}/frames")
get_target_property(FRAME_SOURCES xerax_nxdn_frame_private SOURCES)
list(FILTER FRAME_SOURCES EXCLUDE REGEX "/nxdn_(frame|deperm)\\.c$")
add_library(xerax_clear_routing_protocol STATIC ${FRAME_SOURCES}
    "${CMAKE_CURRENT_BINARY_DIR}/generated/nxdn_frame_observed.c"
    "${CMAKE_CURRENT_BINARY_DIR}/generated/nxdn_deperm_observed.c")
foreach(property IN ITEMS INCLUDE_DIRECTORIES INTERFACE_INCLUDE_DIRECTORIES COMPILE_DEFINITIONS COMPILE_OPTIONS COMPILE_FEATURES LINK_LIBRARIES)
    get_target_property(value xerax_nxdn_frame_private ${property})
    if(value)
        set_property(TARGET xerax_clear_routing_protocol PROPERTY ${property} "${value}")
    endif()
endforeach()
get_target_property(DSD_DIR xerax_nxdn_frame_observer SOURCE_DIR)
get_directory_property(DSD_DEFS DIRECTORY "${DSD_DIR}" COMPILE_DEFINITIONS)
target_compile_definitions(xerax_clear_routing_protocol PRIVATE ${DSD_DEFS})
target_include_directories(xerax_clear_routing_protocol PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/generated")
get_target_property(ENGINE_DIR dsd-neo_engine SOURCE_DIR)
get_directory_property(ENGINE_DEFS DIRECTORY "${ENGINE_DIR}" COMPILE_DEFINITIONS)
get_target_property(ENGINE_INCLUDES dsd-neo_engine INCLUDE_DIRECTORIES)
get_target_property(CLI_LINKS dsd-neo LINK_LIBRARIES)

add_executable(xerax_nxdn_clear_routing_v1
    "${CMAKE_CURRENT_BINARY_DIR}/generated/dispatch_observed.c"
    "${CMAKE_CURRENT_BINARY_DIR}/generated/observer.c"
    "${CMAKE_CURRENT_BINARY_DIR}/generated/engine_observed.c")
target_include_directories(xerax_nxdn_clear_routing_v1 PRIVATE
    "${CMAKE_CURRENT_BINARY_DIR}/generated" "${CMAKE_CURRENT_SOURCE_DIR}"
    "${XERAX_DSD}/src/engine" "${XERAX_DSD}/src/engine/dispatch" "${XERAX_DSD}/src/dsp" "${XERAX_DSD}/src/protocol/nxdn" ${ENGINE_INCLUDES})
target_compile_definitions(xerax_nxdn_clear_routing_v1 PRIVATE ${ENGINE_DEFS}
    DSD_NEO_TEST_HOOKS XERAX_ACQUISITION_RESEARCH XERAX_NXDN_FRAME_RESEARCH)
target_link_libraries(xerax_nxdn_clear_routing_v1 PRIVATE "-Wl,--start-group" xerax_clear_routing_protocol
    dsd-neo_dsp_private_test_support dsd-neo_engine "-Wl,--end-group"
    dsd-neo_warnings dsd-neo_feature_radio dsd-neo_feature_lz ${CLI_LINKS})
target_link_options(xerax_nxdn_clear_routing_v1 PRIVATE "-Wl,-Map=${CMAKE_CURRENT_BINARY_DIR}/clear-routing.map")
foreach(function IN ITEMS getDibitSoft nxdn_voice processMbeFrameSoft processMbeFrame processAudio
    mbe_decodeAmbe3600x2450Frame mbe_decodeAmbe3600x2450SoftFrame mbe_processAmbe2450Dataf
    rtl_stream_start rtl_stream_tune rtl_stream_tune_tagged rtl_stream_output_rate rtl_stream_request_fsk_reacquire)
    target_link_options(xerax_nxdn_clear_routing_v1 PRIVATE "-Wl,--wrap=${function}")
endforeach()

# The registered policy is the actual product plus the public option only.
foreach(definitions IN ITEMS CMAKE_C_FLAGS CMAKE_CXX_FLAGS DSD_DEFS ENGINE_DEFS)
    if("${${definitions}}" MATCHES "XERAX_FIRST_CANONICAL_NXDN48|XERAX_NXDN_BOUNDARY")
        message(FATAL_ERROR "Private first-sync/boundary policy is forbidden in clear routing")
    endif()
endforeach()
