# Included by the registered isolated candidate build, never the product build.
add_executable(xerax_nxdn_voice_available
    ${CMAKE_CURRENT_LIST_DIR}/test_nxdn_voice_available.c
    ${CANDIDATE_DIR}/src/protocol/nxdn/nxdn_voice.c)
add_executable(xerax_nxdn_frame_available
    ${CMAKE_CURRENT_LIST_DIR}/test_nxdn_frame_available.c
    ${CANDIDATE_DIR}/src/protocol/nxdn/nxdn_frame.c
    ${XERAX_DSD}/src/core/util/bit_packing.c
    ${XERAX_DSD}/src/protocol/nxdn/nxdn_confirm.c)
foreach(target xerax_nxdn_voice_available xerax_nxdn_frame_available)
    target_include_directories(${target} BEFORE PRIVATE
        ${CANDIDATE_DIR}/include ${XERAX_DSD}/include ${XERAX_DSD}/src/protocol/nxdn)
    target_compile_features(${target} PRIVATE c_std_11)
    target_compile_definitions(${target} PRIVATE NDEBUG)
    if(MSVC)
        target_compile_options(${target} PRIVATE /W4 /WX)
    else()
        target_compile_options(${target} PRIVATE -Wall -Wextra -Werror)
    endif()
endforeach()
add_test(NAME NXDN_AVAILABILITY_VOICE COMMAND xerax_nxdn_voice_available)
add_test(NAME NXDN_AVAILABILITY_FRAME COMMAND xerax_nxdn_frame_available)
