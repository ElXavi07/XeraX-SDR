cmake_minimum_required(VERSION 3.20)
project(XeraXNxdnFrameResearch LANGUAGES C CXX)
include(CTest)
set(XERAX_ACQUISITION_RESEARCH ON CACHE BOOL "Private discriminator observer" FORCE)
set(BUILD_TESTING ON CACHE BOOL "Required research test support" FORCE)
get_filename_component(XERAX_REPO "${CMAKE_CURRENT_SOURCE_DIR}/../.." ABSOLUTE)
set(XERAX_DSD "${XERAX_REPO}/upstream/dsd-neo")
list(APPEND CMAKE_MODULE_PATH "${XERAX_DSD}/cmake")
find_package(LibSndFile REQUIRED)
add_subdirectory("${XERAX_DSD}" "${CMAKE_CURRENT_BINARY_DIR}/dsd")

# Direct real frame/channel objects isolate the only new protocol seam. The
# ordinary installed protocol archive never receives either test definition.
add_library(xerax_nxdn_frame_private STATIC
    "${XERAX_DSD}/src/protocol/nxdn/nxdn_frame.c"
    "${XERAX_DSD}/src/protocol/nxdn/nxdn_deperm.c"
    "${XERAX_DSD}/src/protocol/nxdn/nxdn_convolution.c"
    "${XERAX_DSD}/src/protocol/nxdn/nxdn_confirm.c"
    "${XERAX_DSD}/src/protocol/nxdn/nxdn_descramble.c"
    "${XERAX_DSD}/src/protocol/nxdn/nxdn_crc.c"
    "${XERAX_DSD}/src/protocol/nxdn/nxdn_dcr_utils.c"
    "${XERAX_DSD}/src/protocol/nxdn/nxdn_enc_class.c")
target_include_directories(xerax_nxdn_frame_private PUBLIC
    "${XERAX_DSD}/include" "${XERAX_DSD}/src/protocol/nxdn")
target_compile_definitions(xerax_nxdn_frame_private PRIVATE DSD_NEO_TEST_HOOKS XERAX_NXDN_FRAME_RESEARCH)
target_link_libraries(xerax_nxdn_frame_private PUBLIC dsd-neo_runtime dsd-neo_feature_radio)

add_executable(xerax_nxdn_frame_observer observer.c side_effect_sinks.c dsp_side_effect_sinks.c
    "${XERAX_DSD}/src/core/frames/dsd_dibit.c"
    "${XERAX_DSD}/src/core/util/dsd_misc.c"
    "${XERAX_DSD}/src/core/util/bit_packing.c")
target_include_directories(xerax_nxdn_frame_observer PRIVATE "${XERAX_DSD}/src/dsp")
target_compile_definitions(xerax_nxdn_frame_observer PRIVATE
    DSD_NEO_TEST_HOOKS XERAX_ACQUISITION_RESEARCH XERAX_NXDN_FRAME_RESEARCH)
target_link_libraries(xerax_nxdn_frame_observer PRIVATE
    xerax_nxdn_frame_private dsd-neo_dsp_private_test_support
    dsd-neo_test_call_state_support dsd-neo_test_support
    ${LIBSNDFILE_LIBRARIES}
    $<$<NOT:$<PLATFORM_ID:Windows>>:m>)
