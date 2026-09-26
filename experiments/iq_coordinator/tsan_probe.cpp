// Deliberately racy instrumentation control. Never link into any receiver.
// A supported ThreadSanitizer run MUST diagnose this race before its clean
// coordinator run can be described as evidence of working instrumentation.
#include <atomic>
#include <thread>

namespace {
std::atomic<int> ready{0};
volatile int intentionally_shared = 0;
constexpr unsigned writes_per_thread = 1U << 20U;
void write_value(int value) {
    ready.fetch_add(1, std::memory_order_relaxed);
    while (ready.load(std::memory_order_relaxed) != 2) std::this_thread::yield();
    // A fixed exposure window replaces the former single store. Volatile keeps
    // these actual stores visible to instrumentation; it does NOT make them
    // atomic or establish synchronization. The relaxed start gate also does
    // not order one writer's non-atomic stores before the other writer's stores.
    // Periodic yields offer the other writer execution opportunities without
    // introducing a mutex, condition-variable handshake or result-based retry.
    // This intentionally undefined program is only a detector control, never a
    // correctness/performance workload, and no finite loop guarantees a report.
    for (unsigned i = 0; i < writes_per_thread; ++i) {
        intentionally_shared = value + static_cast<int>(i & 1U);
        if ((i & 255U) == 255U) std::this_thread::yield();
    }
}
}

int main() {
    std::thread first(write_value, 1);
    std::thread second(write_value, 2);
    first.join();
    second.join();
    return intentionally_shared == 0 ? 1 : 0;
}
