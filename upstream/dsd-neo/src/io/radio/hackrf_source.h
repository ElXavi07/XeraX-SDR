// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
struct xerax_hackrf;
using xerax_hackrf_callback = void (*)(unsigned char*, uint32_t, void*);
int xerax_hackrf_set_fd(int fd);
int xerax_hackrf_fd_set();
int xerax_hackrf_fd_in_use();
xerax_hackrf* xerax_hackrf_open(xerax_hackrf_callback callback, void* context);
void xerax_hackrf_close(xerax_hackrf* source);
int xerax_hackrf_start(xerax_hackrf* source);
int xerax_hackrf_stop(xerax_hackrf* source);
int xerax_hackrf_running(xerax_hackrf* source);
int xerax_hackrf_frequency(xerax_hackrf* source, uint32_t hz);
int xerax_hackrf_rate(xerax_hackrf* source, uint32_t rate);
int xerax_hackrf_gain(xerax_hackrf* source, int tenth_db);
int xerax_hackrf_bias(xerax_hackrf* source, int enabled);
