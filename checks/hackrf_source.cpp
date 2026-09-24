// Actual adapter and anti-alias filter; only the physical USB library is mocked.
#include "hackrf_source.h"
#include <hackrf.h>
#include <libusb.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr,"line %d: %s\n",__LINE__,#x); std::exit(1); } } while(0)
static int initRc=0, openRc=0, rateRc=0, stops=0, starts=0, exits=0, closes=0, amp=-1, antenna=-1;
static bool streaming=false;
static double physicalRate=0;
static uint32_t lna=0,vga=0;
static hackrf_sample_block_cb_fn receiveFn=nullptr;
static void* receiveContext=nullptr;
extern "C" {
int LIBUSB_CALLV libusb_set_option(libusb_context*,libusb_option,...) { return 0; }
int ADDCALL hackrf_init() { return initRc; }
int ADDCALL hackrf_exit() { ++exits; return 0; }
int hackrf_open_fd(int fd,hackrf_device** d) { CHECK(fd==71); *d=reinterpret_cast<hackrf_device*>(1); return openRc; }
int ADDCALL hackrf_close(hackrf_device*) { ++closes; return 0; }
int ADDCALL hackrf_start_rx(hackrf_device*,hackrf_sample_block_cb_fn cb,void* ctx) { ++starts; receiveFn=cb;receiveContext=ctx;streaming=true;return 0; }
int ADDCALL hackrf_stop_rx(hackrf_device*) { ++stops;streaming=false;return 0; }
int ADDCALL hackrf_is_streaming(hackrf_device*) { return streaming?HACKRF_TRUE:HACKRF_SUCCESS; }
int ADDCALL hackrf_set_freq(hackrf_device*,uint64_t) { return 0; }
int ADDCALL hackrf_set_sample_rate(hackrf_device*,double rate) { physicalRate=rate;return rateRc; }
int ADDCALL hackrf_set_baseband_filter_bandwidth(hackrf_device*,uint32_t bw) { CHECK(bw>=1750000);return 0; }
uint32_t ADDCALL hackrf_compute_baseband_filter_bw_round_down_lt(uint32_t bw) { return bw; }
int ADDCALL hackrf_set_lna_gain(hackrf_device*,uint32_t gain) { lna=gain;return 0; }
int ADDCALL hackrf_set_vga_gain(hackrf_device*,uint32_t gain) { vga=gain;return 0; }
int ADDCALL hackrf_set_amp_enable(hackrf_device*,uint8_t value) { amp=value;return 0; }
int ADDCALL hackrf_set_antenna_enable(hackrf_device*,uint8_t value) { antenna=value;return 0; }
}
static std::vector<unsigned char> output;
static void collect(unsigned char* data,uint32_t size,void*) { output.insert(output.end(),data,data+size); }
static double tone(double hz) {
    std::vector<unsigned char> input(262144);
    output.clear();
    for(size_t j=0;j<input.size()/2;++j) {
        double phase=6.283185307179586*hz*j/physicalRate;
        input[2*j]=static_cast<unsigned char>(static_cast<signed char>(std::lround(60*std::cos(phase))));
        input[2*j+1]=static_cast<unsigned char>(static_cast<signed char>(std::lround(60*std::sin(phase))));
    }
    hackrf_transfer t{};t.buffer=input.data();t.buffer_length=t.valid_length=int(input.size());t.rx_ctx=receiveContext;
    CHECK(receiveFn(&t)==0);CHECK(output.size()==input.size()/16);
    double power=0;size_t count=0;
    for(size_t i=512;i<output.size();++i) { const double x=double(output[i])-128;power+=x*x;++count; }
    t.valid_length=3;CHECK(receiveFn(&t)!=0);
    t.valid_length=262146;CHECK(receiveFn(&t)!=0);
    return std::sqrt(power/count);
}
int main() {
    CHECK(!xerax_hackrf_open(collect,nullptr));xerax_hackrf_set_fd(71);
    initRc=-1;CHECK(!xerax_hackrf_open(collect,nullptr));CHECK(!xerax_hackrf_fd_in_use());initRc=0;
    openRc=-1;CHECK(!xerax_hackrf_open(collect,nullptr));CHECK(exits==1);CHECK(!xerax_hackrf_fd_in_use());openRc=0;
    auto* s=xerax_hackrf_open(collect,nullptr);CHECK(s);CHECK(amp==0&&antenna==0);
    CHECK(xerax_hackrf_fd_in_use());CHECK(!xerax_hackrf_open(collect,nullptr));
    CHECK(xerax_hackrf_start(s)!=0);CHECK(xerax_hackrf_rate(s,1)!=0);
    CHECK(xerax_hackrf_rate(s,768000)==0);CHECK(physicalRate==12288000);
    CHECK(xerax_hackrf_start(s)==0);CHECK(xerax_hackrf_running(s));
    const auto pass=tone(50000),stop=tone(1000000);
    CHECK(pass>35&&pass<48);CHECK(stop<2); // Real signed IQ and multi-stage alias rejection.
    CHECK(xerax_hackrf_gain(s,-1)==320);CHECK(lna==32&&vga==0);
    CHECK(xerax_hackrf_gain(s,490)==480);CHECK(lna==40&&vga==8);
    CHECK(xerax_hackrf_frequency(s,451100000)==0);CHECK(xerax_hackrf_frequency(s,2100000000U)!=0);
    CHECK(xerax_hackrf_rate(s,1024000)==0);CHECK(physicalRate==8192000);CHECK(starts==2&&stops==1);
    rateRc=-1;CHECK(xerax_hackrf_rate(s,1536000)!=0);CHECK(!xerax_hackrf_running(s));rateRc=0;
    CHECK(xerax_hackrf_rate(s,1536000)==0);CHECK(xerax_hackrf_start(s)==0);
    xerax_hackrf_set_fd(-1);CHECK(xerax_hackrf_fd_in_use());
    xerax_hackrf_close(s);CHECK(!xerax_hackrf_fd_in_use());CHECK(antenna==0&&closes==1&&exits==2);
    std::printf("HackRF lifecycle, gain, rate, signed IQ and anti-alias tests passed (pass %.2f, stop %.2f). Physical USB is mocked.\n",pass,stop);
}
