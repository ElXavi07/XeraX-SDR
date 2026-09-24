# Pinned for reproducible Windows/vcpkg builds. See docs/supply-chain-guardrails.md
# for the refresh process.
vcpkg_from_github(
    OUT_SOURCE_PATH SOURCE_PATH
    REPO arancormonk/mbelib-neo
    REF be5992dab7589aec6f3a45fa1881139c0caa2a97
    SHA512 9675428bd2d7d87cc77a4b3feed65312622ffa15618ff87399f264e8feca288552aae0bbaa16c79cde97fcef57d4fbb89928df0eca3830668afa8a5871748446
)

# NDK Clang accepts the probe but ignores this flag on ARMv7; the library's
# warnings-as-errors then reject it. Keep stack-protector-strong enabled.
set(architecture_options)
if(VCPKG_TARGET_IS_ANDROID AND VCPKG_TARGET_ARCHITECTURE STREQUAL "arm")
    list(APPEND architecture_options -DMBELIB_C_HAS_STACK_CLASH_PROTECTION=FALSE)
endif()
vcpkg_cmake_configure(
    SOURCE_PATH "${SOURCE_PATH}"
    OPTIONS
        ${architecture_options}
        -DMBELIB_BUILD_TESTS=OFF
        -DMBELIB_BUILD_EXAMPLES=OFF
        -DMBELIB_BUILD_DOCS=OFF
)

vcpkg_cmake_install()

vcpkg_cmake_config_fixup(
    PACKAGE_NAME mbe-neo
    CONFIG_PATH lib/cmake/mbe-neo
)

vcpkg_fixup_pkgconfig()

file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/include")
file(REMOVE_RECURSE "${CURRENT_PACKAGES_DIR}/debug/share")

vcpkg_install_copyright(FILE_LIST "${SOURCE_PATH}/LICENSE")
