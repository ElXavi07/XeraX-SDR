// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QString>
#include <QVariantMap>
namespace dsd_qt {
QString desktop_play(const QString& file, bool temporary=false);
void desktop_stop_playback();
void desktop_test_audio();
QVariantMap desktop_media_health();
bool desktop_audio_testing();
}
