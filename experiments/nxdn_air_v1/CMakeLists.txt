cmake_minimum_required(VERSION 3.20)
project(XeraXIndependentNXDNAir LANGUAGES CXX)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON CACHE BOOL "Preserve build identity" FORCE)
find_package(Python3 3.9 REQUIRED COMPONENTS Interpreter)
set(XERAX_AIR_PRIMARY_DIR "" CACHE PATH "Verified private source directory from prepare_build.py")
if(NOT XERAX_AIR_PRIMARY_DIR)
    message(FATAL_ERROR "Set XERAX_AIR_PRIMARY_DIR to the new verified prepared source directory")
endif()
execute_process(
    COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/prepare_build.py"
            --verify "${XERAX_AIR_PRIMARY_DIR}"
    RESULT_VARIABLE verify_result OUTPUT_VARIABLE verify_output ERROR_VARIABLE verify_error)
if(NOT verify_result EQUAL 0)
    message(FATAL_ERROR "Prepared primary source verification failed: ${verify_error}")
endif()
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/primary-source-verification.json" "${verify_output}")
set(MMDVM "${XERAX_AIR_PRIMARY_DIR}/originals/MMDVM-Host")
set(GENERATED "${XERAX_AIR_PRIMARY_DIR}/generated")
add_executable(xerax_air_primary primary_encoder.cpp
    "${XERAX_AIR_PRIMARY_DIR}/support/primary_support.cpp"
    "${MMDVM}/NXDNLICH.cpp"
    "${GENERATED}/NXDNSACCH.cpp"
    "${GENERATED}/NXDNFACCH1.cpp"
    "${MMDVM}/NXDNConvolution.cpp"
    "${MMDVM}/NXDNCRC.cpp"
    "${MMDVM}/NXDNAudio.cpp"
    "${MMDVM}/Golay24128.cpp"
    "${MMDVM}/Sync.cpp")
target_include_directories(xerax_air_primary PRIVATE "${MMDVM}" "${GENERATED}")
target_compile_features(xerax_air_primary PRIVATE cxx_std_17)
set_target_properties(xerax_air_primary PROPERTIES CXX_EXTENSIONS OFF)
if(MSVC)
    target_compile_options(xerax_air_primary PRIVATE /W4 /WX)
    target_link_options(xerax_air_primary PRIVATE "/MAP:${CMAKE_CURRENT_BINARY_DIR}/xerax_air_primary.map")
else()
    target_compile_options(xerax_air_primary PRIVATE -Wall -Wextra -Wpedantic -Werror)
    target_link_options(xerax_air_primary PRIVATE "-Wl,-Map=${CMAKE_CURRENT_BINARY_DIR}/xerax_air_primary.map")
endif()
