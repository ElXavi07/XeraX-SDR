// SPDX-License-Identifier: GPL-3.0-or-later
#include "desktop_host.h"
#include "desktop_media.h"
#include <QMetaObject>
#include <QVector>
#include <QDesktopServices>
#include <QUrl>
#include <cstdlib>
#include <dsd-neo/core/init.h>
#include <dsd-neo/core/opts.h>
#include <dsd-neo/core/state.h>
#include <dsd-neo/engine/engine.h>
#include <dsd-neo/runtime/bootstrap.h>
#include <dsd-neo/runtime/exitflag.h>
#include <dsd-neo/runtime/shutdown.h>
#include <dsd-neo/app_control/frontend_runtime.h>
#include <dsd-neo/platform/audio.h>
#include <dsd-neo/dsp/simd_fir.h>
#include <dxgi1_2.h>

DesktopHost::DesktopHost(QObject* parent):DecoderHost(parent) {
    QStringList adapters;
    IDXGIFactory1* factory = nullptr;
    if (SUCCEEDED(CreateDXGIFactory1(__uuidof(IDXGIFactory1), reinterpret_cast<void**>(&factory)))) {
        IDXGIAdapter1* adapter = nullptr;
        for (UINT index = 0; factory->EnumAdapters1(index, &adapter) == S_OK; ++index) {
            DXGI_ADAPTER_DESC1 desc{};
            if (SUCCEEDED(adapter->GetDesc1(&desc)) && !(desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE))
                adapters << QString::fromWCharArray(desc.Description);
            adapter->Release();
        }
        factory->Release();
    }
    adapters.removeDuplicates();
    m_hardware = {{"backend", "CPU"}, {"simd", QString::fromLatin1(simd_fir_get_impl_name()).toUpper()},
                  {"logicalThreads", QThread::idealThreadCount()}, {"graphicsAdapters", adapters},
                  {"gpuDecoding", false}};
}
DesktopHost::~DesktopHost() {
    stop();
    if(m_thread) { m_thread->wait(); delete m_thread; m_thread=nullptr; }
}
QString DesktopHost::statusText() const {
    switch(m_state) {
    case Starting:return tr("Starting receiver");
    case Running:return tr("Listening");
    case Stopping:return tr("Stopping receiver");
    case Failed:return m_error;
    default:return tr("Ready");
    }
}
void DesktopHost::changeState(SessionState state) {
    m_state=state;
    Q_EMIT runningChanged(); Q_EMIT sessionStateChanged(); Q_EMIT statusTextChanged();
}
QString DesktopHost::audioRoute() const { return tr("Windows default output (PortAudio)"); }
QVariantMap DesktopHost::audioOutput() const {
    return {{"choices",QVariantList{QVariantMap{{"key","default"},{"label",tr("Windows default output")}},
                                   QVariantMap{{"key","settings"},{"label",tr("Open Windows sound settings")}}}},
            {"selected","default"},{"note",tr("Choose speakers or headphones in Windows sound settings. Stop and restart reception after changing the default output.")}};
}
bool DesktopHost::selectAudioOutput(const QString& key) {
    if(key=="settings") return QDesktopServices::openUrl(QUrl("ms-settings:sound"));
    return key=="default";
}
bool DesktopHost::start(const QStringList& args) {
    if(m_thread || sessionActive() || dsd_qt::desktop_audio_testing()) return false;
    if(args.contains("--xerax-site-capture")) {
        m_error=tr("Extra receiver workers are unavailable in the Windows preview.");
        changeState(Failed); return false;
    }
    m_error.clear(); m_result.begin(m_result.session_id+1);
    m_stop.store(false); dsd_exitflag_store(0);
    changeState(Starting);
    m_thread=QThread::create([this,args] {
        dsd_android::RunStatus result;
        auto* opts=static_cast<dsd_opts*>(calloc(1,sizeof(dsd_opts)));
        auto* state=static_cast<dsd_state*>(calloc(1,sizeof(dsd_state)));
        int rc=1;
        if(opts && state) {
            initOpts(opts); initState(state);
#ifdef USE_RADIO
            rtl_device_clear_open_error();
#endif
            QVector<QByteArray> owned; owned.reserve(args.size()+1);
            owned.append("XeraX-SDR");
            for(const auto& arg:args) owned.append(arg.toUtf8());
            QVector<char*> argv; argv.reserve(owned.size()+1);
            for(auto& arg:owned) argv.append(arg.data());
            argv.append(nullptr);
            int bootstrap=dsd_runtime_bootstrap(owned.size(),argv.data(),opts,state,nullptr,&rc);
            // argv is compacted by bootstrap; owned retains every allocation.
            for(auto& arg:owned) arg.fill('\0');
            if(bootstrap==DSD_BOOTSTRAP_CONTINUE && !m_stop.load()) {
                dsd_app_frontend_runtime_start(opts,state);
                dsd_engine_lifecycle_hooks hooks{};
                hooks.context=this;
                hooks.start=[](dsd_opts* o,dsd_state* s,void* context) {
                    auto* self=static_cast<DesktopHost*>(context);
                    if(self->m_stop.load()) dsd_request_shutdown(o,s);
                    else QMetaObject::invokeMethod(self,[self] {
                        if(!self->m_stop.load()) { self->changeState(Running); Q_EMIT self->sessionInitialized(); }
                    },Qt::QueuedConnection);
                    return 0;
                };
                rc=dsd_engine_run_with_lifecycle(opts,state,&hooks);
                dsd_app_frontend_runtime_stop();
            }
            dsd_android::collect_run_result(result,rc,m_stop.load());
            // Stream exhaustion can return zero while retaining a terminal I/O
            // failure. Present that as a failure, rather than a successful stop.
            if(!m_stop.load() && result.input_failure.kind!=DSD_INPUT_FAILURE_NONE) {
                result.reason=dsd_android::kRunFailed;
                if(result.run_code==0) result.run_code=1;
            }
            freeState(state);
        } else result.finish(1,false,0);
        free(opts); free(state);
        QThread::currentThread()->setProperty("resultCode",result.run_code);
        QThread::currentThread()->setProperty("reason",int(result.reason));
        QThread::currentThread()->setProperty("failureKind",result.input_failure.kind);
        QThread::currentThread()->setProperty("failureCode",result.input_failure.native_code);
        QThread::currentThread()->setProperty("deviceError",result.device_error);
    });
    connect(m_thread,&QThread::finished,this,[this] {
        auto* done=m_thread; m_thread=nullptr;
        m_result.run_code=done->property("resultCode").toInt();
        m_result.reason=static_cast<dsd_android::RunReason>(done->property("reason").toInt());
        m_result.input_failure.kind=done->property("failureKind").toInt();
        m_result.input_failure.native_code=done->property("failureCode").toInt();
        m_result.device_error=done->property("deviceError").toInt();
        if(m_result.reason==dsd_android::kRunFailed) {
            switch(m_result.input_failure.kind) {
            case DSD_INPUT_FAILURE_REFUSED:m_error=tr("Connection refused. Check the server address, port and whether another client is connected.");break;
            case DSD_INPUT_FAILURE_TIMEOUT:m_error=tr("The receiver timed out without a usable signal stream. Check the server and network.");break;
            case DSD_INPUT_FAILURE_RESOLVE:m_error=tr("The server address could not be resolved.");break;
            case DSD_INPUT_FAILURE_NETWORK:m_error=tr("The network signal stream failed. Check the server and connection.");break;
            default:m_error=tr("Receiver failed (code %1). Check the input, Windows USB driver and whether another app is using the SDR.").arg(m_result.run_code);break;
            }
        }
        done->deleteLater();
        Q_EMIT runResultChanged();
        changeState(m_result.reason==dsd_android::kRunFailed?Failed:Idle);
    });
    m_thread->start();
    return true;
}
void DesktopHost::stop() {
    if(!m_thread) return;
    m_stop.store(true); dsd_request_shutdown(nullptr,nullptr);
    if(m_state!=Stopping) changeState(Stopping);
}
