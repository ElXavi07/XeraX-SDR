// SPDX-License-Identifier: GPL-3.0-or-later
// Untimed source-allocation calibration. Never linked into xerax_iq_screen.
#include "credit_history.h"
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <new>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef _WIN32
#include <malloc.h>
#endif
#if defined(__has_feature)
#if __has_feature(thread_sanitizer)
#define XERAX_SCREEN_CALIBRATION_UNAVAILABLE 1
#endif
#endif
#if defined(__SANITIZE_THREAD__)
#define XERAX_SCREEN_CALIBRATION_UNAVAILABLE 1
#endif

namespace probe {
struct Entry {void* pointer=nullptr;std::size_t bytes=0;};
std::array<Entry,64> entries{};
bool enabled=false,overflow=false;
std::size_t allocations=0,deallocations=0,live=0,peak=0,total=0;
void record(void* pointer,std::size_t bytes) {
    if(!enabled)return;
    for(auto& e:entries)if(!e.pointer){e={pointer,bytes};++allocations;live+=bytes;total+=bytes;if(live>peak)peak=live;return;}
    overflow=true;throw std::bad_alloc();
}
void release(void* pointer) noexcept {
    for(auto& e:entries)if(e.pointer==pointer&&pointer){live-=e.bytes;++deallocations;e={};return;}
}
}
#if !defined(XERAX_SCREEN_CALIBRATION_UNAVAILABLE)
#if defined(_MSC_VER)
#define PROBE_NOINLINE __declspec(noinline)
#elif defined(__GNUC__)
#define PROBE_NOINLINE __attribute__((noinline))
#else
#define PROBE_NOINLINE
#endif
PROBE_NOINLINE void* operator new(std::size_t bytes) {
    void* p=std::malloc(bytes?bytes:1);if(!p)throw std::bad_alloc();
    try{probe::record(p,bytes);}catch(...){std::free(p);throw;}return p;
}
PROBE_NOINLINE void* operator new[](std::size_t bytes){return ::operator new(bytes);}
PROBE_NOINLINE void operator delete(void* p) noexcept {probe::release(p);std::free(p);}
PROBE_NOINLINE void operator delete[](void* p) noexcept {::operator delete(p);}
PROBE_NOINLINE void operator delete(void* p,std::size_t) noexcept {::operator delete(p);}
PROBE_NOINLINE void operator delete[](void* p,std::size_t) noexcept {::operator delete(p);}
PROBE_NOINLINE void* operator new(std::size_t bytes,std::align_val_t align) {
    void* p=nullptr;
#ifdef _WIN32
    p=_aligned_malloc(bytes?bytes:1,static_cast<std::size_t>(align));
#else
    if(posix_memalign(&p,static_cast<std::size_t>(align),bytes?bytes:1)!=0)p=nullptr;
#endif
    if(!p)throw std::bad_alloc();
    try{probe::record(p,bytes);}catch(...){
#ifdef _WIN32
        _aligned_free(p);
#else
        std::free(p);
#endif
        throw;
    }return p;
}
PROBE_NOINLINE void* operator new[](std::size_t bytes,std::align_val_t a){return ::operator new(bytes,a);}
PROBE_NOINLINE void operator delete(void* p,std::align_val_t) noexcept {probe::release(p);
#ifdef _WIN32
    _aligned_free(p);
#else
    std::free(p);
#endif
}
PROBE_NOINLINE void operator delete[](void* p,std::align_val_t a) noexcept {::operator delete(p,a);}
PROBE_NOINLINE void operator delete(void* p,std::size_t,std::align_val_t a) noexcept {::operator delete(p,a);}
PROBE_NOINLINE void operator delete[](void* p,std::size_t,std::align_val_t a) noexcept {::operator delete(p,a);}
#undef PROBE_NOINLINE
#endif

namespace {
[[maybe_unused]] std::uint8_t pattern(std::uint64_t byte){byte^=byte>>13U;byte*=UINT64_C(0x9e3779b97f4a7c15);return static_cast<std::uint8_t>((byte>>48U)^(byte>>24U)^byte);}
void require(bool value,const char* message){if(!value)throw std::runtime_error(message);}
}
int main(int argc,char** argv) {
    try {
        const std::string format=argc==3&&std::string(argv[1])=="--format"?argv[2]:"";
        require(format=="cu8"||format=="cf32","Use --format cu8|cf32");
#if defined(XERAX_SCREEN_CALIBRATION_UNAVAILABLE)
        std::cout<<"{\"schema_version\":1,\"kind\":\"whole_source_allocation_calibration\",\"available\":false,\"complete\":false,\"reason\":\"TSan replacement allocation operators unavailable\"}\n";return 2;
#else
        namespace iq=xerax::experiment;
        constexpr std::size_t mib=1024U*1024U,payload=15U*mib;
        const std::uint32_t width=format=="cu8"?2U:8U;
        const iq::Stream stream{1,1,3072000,451100000,width};
        std::vector<std::uint8_t> input(30720U*width); // Explicitly outside source scope.
        probe::enabled=true;
        auto source=std::make_unique<iq::CreditHistory>(iq::CreditConfig{8U*mib,7U*mib,1U,payload});
        const auto construction_allocations=probe::allocations,captured=probe::live;
        require(source->begin_epoch(stream)==iq::Status::Ok,"Calibration epoch rejected");
        std::uint64_t first=0;
        for(unsigned block=0;block<140U;++block){for(std::size_t i=0;i<input.size();++i)input[i]=pattern(first*width+i);
            require(source->append(stream,first,input.data(),input.size())==iq::Status::Ok,"Calibration append rejected");first+=30720;}
        const auto state=source->state();require(state.retained_bytes==8U*mib,"Calibration retention not full");
        auto lease=source->snapshot(stream,first-768000U,768000U);require(static_cast<bool>(lease),"Calibration grant rejected");
        require(lease.size()==768000U*width,"Calibration byte count mismatch");
        for(std::size_t i=0;i<lease.size();++i)require(lease.data()[i]==pattern((first-768000U)*width+i),"Calibration source bytes mismatch");
        const auto verified=lease.size();
        const auto operational=probe::allocations-construction_allocations;
        require(!probe::overflow&&operational==0&&captured>=payload,"Unexpected source allocation profile");
        source.reset();const auto retired=probe::live;
        require(retired>0,"Held snapshot lost source ownership");
        lease.reset();const auto final_live=probe::live;
        probe::enabled=false;
        const auto metadata=captured-payload;
        const bool complete=final_live==0&&probe::allocations==probe::deallocations&&metadata+sizeof(iq::SnapshotLease)<=128U*1024U;
        std::cout<<"{\"schema_version\":1,\"kind\":\"whole_source_allocation_calibration\",\"available\":true,\"format\":\""<<format<<"\",\"width\":"<<width
            <<",\"payload_bytes\":"<<payload<<",\"allocation_count\":"<<probe::allocations<<",\"deallocation_count\":"<<probe::deallocations
            <<",\"captured_allocation_bytes\":"<<captured<<",\"metadata_allocation_bytes_including_facade\":"<<metadata
            <<",\"metadata_reservation_bytes\":"<<metadata+sizeof(iq::SnapshotLease)<<",\"peak_live_bytes\":"<<probe::peak
            <<",\"live_bytes_after_history_destroy\":"<<retired<<",\"live_bytes_after_destroy\":"<<final_live
            <<",\"operational_allocations\":"<<operational<<",\"verified_bytes\":"<<verified<<",\"retained_bytes\":"<<state.retained_bytes
            <<",\"credit_history_bytes\":"<<sizeof(iq::CreditHistory)<<",\"snapshot_lease_bytes\":"<<sizeof(iq::SnapshotLease)
            <<",\"pointer_bytes\":"<<sizeof(void*)<<",\"complete\":"<<(complete?"true":"false")<<"}\n";
        return complete?0:2;
#endif
    }catch(const std::exception& e){probe::enabled=false;std::cerr<<"Calibration failure: "<<e.what()<<'\n';return 1;}
}
