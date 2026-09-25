find_package(Qt6 6.11 REQUIRED COMPONENTS Core Gui Qml Quick QuickControls2 QuickDialogs2 Network)
enable_language(RC)
qt_add_executable(xerax-sdr WIN32 main.cpp desktop_host.cpp desktop_host.h app.rc)
set_target_properties(xerax-sdr PROPERTIES AUTOMOC ON OUTPUT_NAME "XeraX-SDR")
target_include_directories(xerax-sdr PRIVATE "${PROJECT_SOURCE_DIR}/include" "${PROJECT_SOURCE_DIR}/android")
target_include_directories(xerax-sdr SYSTEM PRIVATE ${_PUBLIC_INCLUDES})
target_link_libraries(xerax-sdr PRIVATE dsd-neo_ui_qt dsd-neo_engine
    dsd-neo_feature_rtlsdr dsd-neo_feature_codec2 shell32 dxgi ${LIBS})
install(TARGETS xerax-sdr RUNTIME DESTINATION .)
