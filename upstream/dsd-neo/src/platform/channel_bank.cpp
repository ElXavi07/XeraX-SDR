// SPDX-License-Identifier: GPL-3.0-or-later
#include <dsd-neo/platform/channel_bank.h>
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstring>
#include <deque>
#include <mutex>
#include <thread>
#include <vector>
#include <array>
#include <complex>
#include <memory>
#include <chrono>
#if defined(__ANDROID__) || defined(__linux__)
#include <arpa/inet.h>
#include <fcntl.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>
#endif
namespace {
constexpr double pi = 3.14159265358979323846;
constexpr size_t queueLimit = 1024 * 1024;
struct Block { std::shared_ptr<const std::vector<unsigned char>> data; uint32_t hz, rate; };
struct Lane {
    std::mutex mutex;
    std::deque<Block> queue;
    size_t queued = 0;
    std::atomic<bool> active{false}, stop{false};
    std::atomic<uint64_t> missed{0};
    std::thread thread;
    dsd_channel_info info{};
    ~Lane() { stop = true; if (thread.joinable()) thread.join(); }
};
Lane lanes[DSD_CHANNEL_LANES];
std::atomic<uint32_t> sourceHz{0}, sourceRate{0};
std::atomic<uint64_t> sourceBytes{0}, sourceAt{0};
uint64_t nowMs() { return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
std::atomic<uint32_t> workerRate{0};
struct HalfBand {
    std::array<std::complex<float>,47> history{};
    unsigned cursor=0, phase=0;
};
struct ChannelFilter {
    std::vector<HalfBand> stages;
    std::array<float,47> taps{};
    std::complex<double> oscillator{1,0}, step{1,0};
    uint64_t samples=0;
    bool decimate(size_t stage, std::complex<float>& value) {
        if(stage==stages.size()) return true;
        auto& s=stages[stage]; s.history[s.cursor]=value;
        const auto head=s.cursor; s.cursor=(s.cursor+1)%47;
        if(++s.phase!=2) return false;
        s.phase=0; value={0,0};
        for(unsigned k=0;k<47;++k) if(k==23 || !(k&1U)) value+=taps[k]*s.history[(head+47-k)%47];
        return decimate(stage+1,value);
    }
};
}
void dsd_channel_worker_rate_set(uint32_t rate) { workerRate=rate==192000?rate:0; }
uint32_t dsd_channel_worker_rate() { return workerRate.load(); }
void* dsd_channel_filter_create(uint32_t input,uint32_t output,double delta) {
    if(!output || input<output || input%output || !std::isfinite(delta)) return nullptr;
    unsigned ratio=input/output;
    if((ratio&(ratio-1)) || ratio>64) return nullptr;
    auto f=std::make_unique<ChannelFilter>();
    while(ratio>1) { f->stages.emplace_back(); ratio/=2; }
    f->step=std::polar(1.0,2*pi*delta/input);
    double sum=0;
    for(int k=0;k<47;++k) {
        const int x=k-23;
        const double sinc=x==0?0.5:(x%2?std::sin(pi*x/2)/(pi*x):0);
        f->taps[size_t(k)]=float(sinc*(0.42-0.5*std::cos(2*pi*k/46)+0.08*std::cos(4*pi*k/46)));
        sum+=f->taps[size_t(k)];
    }
    for(auto& tap:f->taps) tap/=float(sum);
    return f.release();
}
size_t dsd_channel_filter_process(void* handle,const unsigned char* in,size_t n,unsigned char* out) {
    if(!handle || !in || !out || (n&1U)) return 0;
    auto& f=*static_cast<ChannelFilter*>(handle); size_t written=0;
    for(size_t j=0;j<n;j+=2) {
        auto sample=std::complex<float>(float(in[j])-127.5F,float(in[j+1])-127.5F)*std::complex<float>(f.oscillator);
        f.oscillator*=f.step;
        if((++f.samples&4095U)==0) f.oscillator/=std::abs(f.oscillator);
        if(!f.decimate(0,sample)) continue;
        out[written++]=static_cast<unsigned char>(std::min(255L,std::max(0L,std::lround(127.5+sample.real()))));
        out[written++]=static_cast<unsigned char>(std::min(255L,std::max(0L,std::lround(127.5+sample.imag()))));
    }
    return written;
}
void dsd_channel_filter_destroy(void* handle) { delete static_cast<ChannelFilter*>(handle); }
void dsd_channel_translate(const unsigned char* in, unsigned char* out, size_t n, double delta, double rate, double* phase) {
    if (!in || !out || !phase || rate <= 0) return;
    const double step = 2*pi*delta/rate, cr = std::cos(step), ci = std::sin(step);
    double xr = std::cos(*phase), xi = std::sin(*phase);
    for (size_t j=0;j+1<n;j+=2) {
        const double i = in[j]-127.5, q = in[j+1]-127.5;
        out[j] = static_cast<unsigned char>(std::min(255L,std::max(0L,std::lround(127.5+i*xr-q*xi))));
        out[j+1] = static_cast<unsigned char>(std::min(255L,std::max(0L,std::lround(127.5+i*xi+q*xr))));
        const double nr=xr*cr-xi*ci; xi=xr*ci+xi*cr; xr=nr;
        if ((j&4095U)==4094U) { double norm=std::hypot(xr,xi); xr/=norm; xi/=norm; }
    }
    *phase = std::remainder(*phase + step*static_cast<double>(n/2),2*pi);
}
void dsd_channel_get(int lane, dsd_channel_info* out) {
    if (!out) return;
    *out = {};
    if (lane>=0 && lane<DSD_CHANNEL_LANES) {
        auto& l=lanes[lane]; std::lock_guard<std::mutex> g(l.mutex);
        *out=l.info; out->dropped+=l.missed;
    }
    out->source_hz=sourceHz; out->sample_rate=sourceRate; out->source_bytes=sourceBytes;
    const auto at=sourceAt.load(); out->source_age_ms=at?nowMs()-at:UINT64_MAX;
}
void dsd_channel_reset_source() {
    for(int i=0;i<DSD_CHANNEL_LANES;++i) dsd_channel_close(i);
    sourceHz=0; sourceRate=0; sourceBytes=0; sourceAt=0;
}
int dsd_channel_fits(uint32_t center,uint32_t rate,uint32_t channel) {
    // The 192 kS/s worker tunes 48 kHz above its wanted channel (Fs/4).
    return rate>=192000 && rate%192000==0 && ((rate/192000)&((rate/192000)-1))==0
        && std::abs(double(channel)+48000-center)<=rate*0.375;
}
void dsd_channel_feed_cu8(const unsigned char* p, size_t n, uint32_t hz, uint32_t rate) {
    if (!p || !n || (n&1U) || !hz || !rate) return;
    sourceHz=hz; sourceRate=rate; sourceBytes+=n; sourceAt=nowMs();
    std::shared_ptr<const std::vector<unsigned char>> shared;
    for (auto& l:lanes) {
        if (!l.active) continue;
        // Queue locks contain no socket I/O or filtering. A diagnostic reader
        // taking this short lock must not terminate a receiver.
        std::lock_guard<std::mutex> g(l.mutex);
        if (n>queueLimit || l.queued+n>queueLimit) { l.info.error=1; l.info.dropped+=n; l.stop=true; continue; }
        if(!shared) shared=std::make_shared<const std::vector<unsigned char>>(p,p+n);
        l.queue.push_back({shared,hz,rate}); l.queued+=n;
    }
}
void dsd_channel_close(int lane) {
    if (lane<0 || lane>=DSD_CHANNEL_LANES) return;
    auto& l=lanes[lane]; l.active=false; l.stop=true;
    if (l.thread.joinable()) l.thread.join();
    std::lock_guard<std::mutex> g(l.mutex); l.queue.clear(); l.queued=0; l.info.connected=0; l.info.port=0;
}
int dsd_channel_open(int lane) {
    if (lane<0 || lane>=DSD_CHANNEL_LANES || !sourceRate.load() || !sourceAt.load() || nowMs()-sourceAt.load()>2000) return -1;
    dsd_channel_close(lane);
#if defined(__ANDROID__) || defined(__linux__)
    const int server=socket(AF_INET,SOCK_STREAM,0);
    if (server<0) return -1;
    sockaddr_in addr{}; addr.sin_family=AF_INET; addr.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    socklen_t len=sizeof(addr);
    if (bind(server,reinterpret_cast<sockaddr*>(&addr),len)<0 || listen(server,1)<0
        || getsockname(server,reinterpret_cast<sockaddr*>(&addr),&len)<0) { close(server); return -1; }
    auto& l=lanes[lane]; l.stop=false; l.missed=0;
    { std::lock_guard<std::mutex> g(l.mutex); l.info={}; l.info.port=ntohs(addr.sin_port); }
    const int port=ntohs(addr.sin_port);
    l.thread=std::thread([server,&l] {
        int client=-1;
        while (!l.stop) {
            pollfd p{server,POLLIN,0}; if (poll(&p,1,100)>0) { client=accept(server,nullptr,nullptr); break; }
        }
        close(server);
        if (client<0) return;
        timeval timeout{0,200000}; setsockopt(client,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
        const unsigned char hello[12]={'R','T','L','0',0,0,0,5,0,0,0,0};
        if (send(client,hello,12,MSG_NOSIGNAL)!=12) { close(client); return; }
        uint32_t target=0, requestedRate=0, initialSource=0;
        unsigned char command[5]; size_t have=0;
        std::unique_ptr<ChannelFilter> filter;
        uint32_t filterSource=0,filterTarget=0,filterRate=0,filterOutput=0;
        { std::lock_guard<std::mutex> g(l.mutex); l.info.connected=1; }
        l.active=true;
        while (!l.stop) {
            pollfd p{client,POLLIN,0}; int pr=poll(&p,1,5);
            if (pr<0 || (p.revents&(POLLERR|POLLHUP|POLLNVAL))) break;
            if (pr>0 && (p.revents&POLLIN)) {
                const auto count=recv(client,command+have,5-have,0); if(count<=0) break;
                have+=static_cast<size_t>(count);
                if(have==5) {
                    uint32_t v=(uint32_t(command[1])<<24)|(uint32_t(command[2])<<16)|(uint32_t(command[3])<<8)|command[4];
                    if(command[0]==1) target=v;
                    if(command[0]==2) requestedRate=v;
                    have=0;
                }
                continue; // drain tuning commands before delivering the first samples
            }
            Block block;
            { std::lock_guard<std::mutex> g(l.mutex);
                if(l.queue.empty()) continue;
                block=std::move(l.queue.front()); l.queue.pop_front(); l.queued-=block.data->size();
                l.info.target_hz=target; l.info.output_rate=requestedRate;
            }
            if (!target || !requestedRate) continue;
            int error=0;
            if(requestedRate!=192000 || block.rate<requestedRate || block.rate%requestedRate
                || ((block.rate/requestedRate)&((block.rate/requestedRate)-1))) error=2;
            // Allow the worker's Fs/4 capture offset, but reserve one eighth at each edge.
            if(std::abs(double(target)-block.hz)>block.rate*0.375) error=3;
            if(initialSource && initialSource!=block.hz) error=4;
            if(error) { std::lock_guard<std::mutex> g(l.mutex); l.info.error=error; break; }
            initialSource=block.hz;
            if(!filter || filterSource!=block.hz || filterTarget!=target || filterRate!=block.rate || filterOutput!=requestedRate) {
                filter.reset(static_cast<ChannelFilter*>(dsd_channel_filter_create(block.rate,requestedRate,double(block.hz)-target)));
                filterSource=block.hz; filterTarget=target; filterRate=block.rate; filterOutput=requestedRate;
            }
            if(!filter) { std::lock_guard<std::mutex> g(l.mutex); l.info.error=2; break; }
            std::vector<unsigned char> output(block.data->size());
            output.resize(dsd_channel_filter_process(filter.get(),block.data->data(),block.data->size(),output.data()));
            size_t done=0;
            while(done<output.size() && !l.stop) {
                const auto sent=send(client,output.data()+done,output.size()-done,MSG_NOSIGNAL);
                if(sent<=0) { l.stop=true; break; } done+=static_cast<size_t>(sent);
            }
            { std::lock_guard<std::mutex> g(l.mutex); l.info.bytes+=done; }
        }
        l.active=false; close(client);
        std::lock_guard<std::mutex> g(l.mutex); l.queue.clear(); l.queued=0; l.info.connected=0;
        if(l.missed && !l.info.error) l.info.error=1;
    });
    return port;
#else
    return -1;
#endif
}
