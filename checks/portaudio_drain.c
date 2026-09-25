// SPDX-License-Identifier: GPL-3.0-or-later
// Exercise the production drain/write path with a deterministic device boundary.
#define DSD_USE_PORTAUDIO 1
#include "../upstream/dsd-neo/src/platform/audio_portaudio.c"
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "Audio drain failure at %d: %s\n", __LINE__, #x); return 1; } } while (0)
static dsd_audio_stream fake_device;
static int writes, suppressed, sleeps, noted, broadcasts;
static PaError write_result;
static int16_t received[32];
static size_t received_count;
PaError Pa_WriteStream(PaStream* device, const void* data, unsigned long frames) {
    if (device != &fake_device || received_count + frames > 32) return paBadStreamPtr;
    memcpy(received + received_count, data, frames * sizeof(int16_t));
    received_count += frames; ++writes; return write_result;
}
const char* Pa_GetErrorText(PaError error) { (void)error; return "fixture device error"; }
int dsd_audio_live_suppressed(void) { return suppressed; }
void dsd_audio_note_output(size_t frames, int rate) { (void)rate; noted += (int)frames; }
void dsd_sleep_ms(unsigned int ms) { (void)ms; ++sleeps; }
int dsd_mutex_lock(dsd_mutex_t* m) { (void)m; return 0; }
int dsd_mutex_init(dsd_mutex_t* m) { (void)m; return 0; }
void dsd_thread_yield(void) {}
int dsd_mutex_unlock(dsd_mutex_t* m) { (void)m; return 0; }
int dsd_cond_broadcast(dsd_cond_t* c) { (void)c; ++broadcasts; return 0; }
int main(void) {
    int16_t ring[8] = {1,2,3,4,5,6,7,8}, chunk[4] = {0};
    dsd_audio_stream s = {0};
    s.handle = &fake_device; s.channels = 1; s.sample_rate = 8000;
    s.ring = ring; s.ring_samples_capacity = 8; s.chunk = chunk; s.chunk_samples = 4;
    s.ring_samples_count = 8;
    CHECK(portaudio_flush_drain_locked(&s) == 0);
    CHECK(writes == 2 && noted == 8 && received_count == 8 && s.ring_samples_count == 0);
    CHECK(memcmp(received, ring, sizeof ring) == 0);
    // Scanner/replay suppression also applies while flushing queued live audio.
    suppressed = 1; s.ring_samples_count = 4;
    CHECK(portaudio_flush_drain_locked(&s) == 0 && writes == 2 && noted == 8 && sleeps == 1);
    // Diagnostic tones are deliberately allowed through the live gate.
    s.diagnostic_output = 1;
    CHECK(portaudio_write_frames(&s, chunk, 4) == 0 && writes == 3 && noted == 8);
    suppressed = 0; s.diagnostic_output = 0; write_result = paOutputUnderflowed;
    CHECK(portaudio_write_frames(&s, chunk, 4) == 0 && noted == 12);
    // An actual device error stops the pump and wakes the draining caller.
    write_result = paUnanticipatedHostError; s.ring_samples_count = 4;
    CHECK(portaudio_flush_drain_locked(&s) == -1 && s.stop && broadcasts == 1);
    puts("Queued audio drains through the correct device, gate and failure handling");
    return 0;
}
