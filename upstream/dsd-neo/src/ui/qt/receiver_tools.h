// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QTimer>
#include <QVariant>
#include <QVariantList>
#include <QVariantMap>
namespace dsd_qt {
class AppPrefs;
class SavedSystemsModel;
class ScanListsModel;
class DecoderHost;
class ReceiverTools : public QObject {
    Q_OBJECT
    Q_PROPERTY(double replaySeconds READ replaySeconds NOTIFY changed)
    Q_PROPERTY(QVariantMap health READ health NOTIFY changed)
    Q_PROPERTY(QVariantList profiles READ profiles NOTIFY changed)
  public:
    ReceiverTools(AppPrefs*, SavedSystemsModel*, ScanListsModel*, DecoderHost*, QObject* parent = nullptr);
    double replaySeconds() const;
    QVariantMap health() const { return m_health; }
    QVariantList profiles() const;
    Q_INVOKABLE QString saveReplay(const QString& url, int seconds);
    Q_INVOKABLE QString playReplay(int seconds);
    Q_INVOKABLE void clearReplay();
    Q_INVOKABLE void stopPlayback();
    Q_INVOKABLE void restoreAudio();
    Q_INVOKABLE void testAudio();
    Q_INVOKABLE bool saveProfile(const QString& name, int gain, int ppm, int bandwidth, bool biasTee);
    Q_INVOKABLE bool applyProfile(int index);
    Q_INVOKABLE bool removeProfile(int index);
    Q_INVOKABLE QVariantList sites(double latitude, double longitude) const;
    Q_INVOKABLE QString alertRules() const;
    Q_INVOKABLE bool setAlertRules(const QString&);
    Q_INVOKABLE QString backup(const QString& url);
    Q_INVOKABLE QString restore(const QString& url);
  Q_SIGNALS:
    void changed();
  private:
    AppPrefs* m_prefs;
    SavedSystemsModel* m_systems;
    ScanListsModel* m_lists;
    DecoderHost* m_host;
    QVariantMap m_health;
    QTimer m_timer;
    quint64 m_audioFrames = 0, m_nonzeroFrames = 0, m_outputFrames = 0;
};
}
