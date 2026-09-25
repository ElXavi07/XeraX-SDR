// Deliberately racy instrumentation control. Never link into any receiver.
// A supported ThreadSanitizer run MUST diagnose this race before its clean
// coordinator run can be described as evidence of working instrumentation.
#include <atomic>
#include <thread>

namespace {
std::atomic<int> ready{0};
volatile int intentionally_shared = 0;
void write_value(int value) {
    ready.fetch_add(1, std::memory_order_relaxed);
    while (ready.load(std::memory_order_relaxed) != 2) std::this_thread::yield();
    intentionally_shared = value;
}
}

int main() {
    std::thread first(write_value, 1);
    std::thread second(write_value, 2);
    first.join();
    second.join();
    return intentionally_shared == 0 ? 1 : 0;
}
