// SPDX-License-Identifier: GPL-3.0-or-later
#include "hackrf_source.h"
#ifdef DSD_HAVE_HACKRF
#include <hackrf.h>
#include <libusb.h>
#include <dsd-neo/platform/channel_bank.h>
#include <algorithm>
#include <atomic>
#include <cstdio>
#include <mutex>
#include <new>
#include <vector>
extern "C" int hackrf_open_fd(int fd, hackrf_device** device);
namespace {
std::atomic<int> input_fd{-1}, fd_users{0};
}
struct xerax_hackrf {
    hackrf_device* device = nullptr;
    xerax_hackrf_callback callback = nullptr;
    void* context = nullptr;
    void* filter = nullptr;
    uint32_t rate = 0;
    std::mutex control;
    std::atomic<bool> starting{false};
    std::vector<unsigned char> converted, output;
};
int xerax_hackrf_set_fd(int fd) { input_fd.store(fd); return 0; }
int xerax_hackrf_fd_set() { return input_fd.load() >= 0; }
int xerax_hackrf_fd_in_use() { return fd_users.load(); }
static int receive(hackrf_transfer* transfer) {
    auto* s = static_cast<xerax_hackrf*>(transfer->rx_ctx);
    if (!s || transfer->valid_length <= 0 || (transfer->valid_length & 1) || !s->filter) return -1;
    const auto count = static_cast<size_t>(transfer->valid_length);
    if (count > 262144) return -1;
    // HackRF sends signed complex 8-bit samples; the shared decoder expects CU8.
    for (size_t i=0; i<count; ++i) s->converted[i] = transfer->buffer[i] ^ 0x80U;
    const auto written = dsd_channel_filter_process(s->filter, s->converted.data(), count, s->output.data());
    if (written) s->callback(s->output.data(), static_cast<uint32_t>(written), s->context);
    return 0;
}
xerax_hackrf* xerax_hackrf_open(xerax_hackrf_callback callback, void* context) {
    const int fd = input_fd.load();
    int expected = 0;
    if (fd < 0 || !callback || !fd_users.compare_exchange_strong(expected, 1)) return nullptr;
    auto* s = new (std::nothrow) xerax_hackrf;
    if (!s) { fd_users=0; return nullptr; }
    s->callback=callback; s->context=context;
    try { s->converted.resize(262144); s->output.resize(262144); }
    catch (const std::bad_alloc&) { delete s; fd_users=0; return nullptr; }
    // Android USB permission provides access; global discovery cannot read usbfs.
    libusb_set_option(nullptr, LIBUSB_OPTION_NO_DEVICE_DISCOVERY);
    if (hackrf_init() != HACKRF_SUCCESS) { delete s; fd_users=0; return nullptr; }
    if (hackrf_open_fd(fd, &s->device) != HACKRF_SUCCESS) {
        hackrf_exit(); delete s; fd_users=0; return nullptr;
    }
    if (hackrf_set_amp_enable(s->device, 0) != HACKRF_SUCCESS
        || hackrf_set_antenna_enable(s->device, 0) != HACKRF_SUCCESS) {
        xerax_hackrf_close(s); return nullptr;
    }
    std::fprintf(stderr, "HackRF One USB receiver opened; RF amplifier and antenna power off.\n");
    return s;
}
int xerax_hackrf_frequency(xerax_hackrf* s, uint32_t hz) {
    if (!s || hz < 1000000 || hz > 2000000000U) {
        std::fprintf(stderr, "HackRF: this decoder supports 1 MHz through 2 GHz.\n"); return -1;
    }
    std::lock_guard<std::mutex> guard(s->control);
    return hackrf_set_freq(s->device, hz);
}
int xerax_hackrf_rate(xerax_hackrf* s, uint32_t rate) {
    if (!s || rate < 225000 || rate > 3200000) return -1;
    std::lock_guard<std::mutex> guard(s->control);
    if (rate == s->rate) return 0;
    // Keep ADC operation at >= 8 MS/s, then apply anti-alias halfband stages.
    uint32_t physical=rate;
    while (physical < 8000000) physical *= 2;
    if (physical > 20000000) return -1;
    void* next=dsd_channel_filter_create(physical, rate, 0);
    if (!next) return -1;
    const bool was_running=hackrf_is_streaming(s->device)==HACKRF_TRUE;
    s->starting=true;
    if (was_running && hackrf_stop_rx(s->device)!=HACKRF_SUCCESS) {
        dsd_channel_filter_destroy(next); s->starting=false; return -1;
    }
    int rc=hackrf_set_sample_rate(s->device, physical);
    if (!rc) rc=hackrf_set_baseband_filter_bandwidth(s->device,
        hackrf_compute_baseband_filter_bw_round_down_lt(std::max(1750000U, rate)));
    if (!rc) {
        dsd_channel_filter_destroy(s->filter); s->filter=next; s->rate=rate;
        std::fprintf(stderr,"HackRF capture %u S/s -> filtered %u S/s.\n",physical,rate);
        if (was_running) rc=hackrf_start_rx(s->device,receive,s);
    } else dsd_channel_filter_destroy(next);
    s->starting=false;
    return rc;
}
int xerax_hackrf_gain(xerax_hackrf* s, int tenth_db) {
    if (!s) return -1;
    std::lock_guard<std::mutex> guard(s->control);
    // No hardware AGC: use a moderate manual default for an automatic request.
    const int db=std::max(0,std::min(102,tenth_db < 0 ? 32 : tenth_db/10));
    const int lna=std::min(40,(db/8)*8), vga=std::min(62,((db-lna)/2)*2);
    if (hackrf_set_lna_gain(s->device,static_cast<uint32_t>(lna)) ||
        hackrf_set_vga_gain(s->device,static_cast<uint32_t>(vga))) return -1;
    return (lna+vga)*10;
}
int xerax_hackrf_bias(xerax_hackrf* s,int enabled) {
    if (!s) return -1;
    std::lock_guard<std::mutex> guard(s->control);
    return hackrf_set_antenna_enable(s->device,enabled?1:0);
}
int xerax_hackrf_start(xerax_hackrf* s) {
    if (!s || !s->filter) return -1;
    std::lock_guard<std::mutex> guard(s->control);
    s->starting=true;
    int rc=hackrf_start_rx(s->device,receive,s);
    s->starting=false;
    return rc;
}
int xerax_hackrf_stop(xerax_hackrf* s) {
    if (!s) return -1;
    std::lock_guard<std::mutex> guard(s->control);
    return hackrf_stop_rx(s->device);
}
int xerax_hackrf_running(xerax_hackrf* s) {
    return s && (s->starting || hackrf_is_streaming(s->device)==HACKRF_TRUE);
}
void xerax_hackrf_close(xerax_hackrf* s) {
    if (!s) return;
    xerax_hackrf_stop(s);
    hackrf_set_antenna_enable(s->device,0);
    hackrf_close(s->device);
    hackrf_exit();
    dsd_channel_filter_destroy(s->filter);
    delete s; fd_users=0;
}
#else
int xerax_hackrf_set_fd(int) { return -1; }
int xerax_hackrf_fd_set() { return 0; }
int xerax_hackrf_fd_in_use() { return 0; }
xerax_hackrf* xerax_hackrf_open(xerax_hackrf_callback, void*) { return nullptr; }
void xerax_hackrf_close(xerax_hackrf*) {}
int xerax_hackrf_start(xerax_hackrf*) { return -1; }
int xerax_hackrf_stop(xerax_hackrf*) { return -1; }
int xerax_hackrf_running(xerax_hackrf*) { return 0; }
int xerax_hackrf_frequency(xerax_hackrf*, uint32_t) { return -1; }
int xerax_hackrf_rate(xerax_hackrf*, uint32_t) { return -1; }
int xerax_hackrf_gain(xerax_hackrf*, int) { return -1; }
int xerax_hackrf_bias(xerax_hackrf*, int) { return -1; }
#endif
