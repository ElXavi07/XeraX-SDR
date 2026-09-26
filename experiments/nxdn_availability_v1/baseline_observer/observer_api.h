// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <dsd-neo/core/opts_fwd.h>
#include <dsd-neo/core/state_fwd.h>
#include <dsd-neo/dsp/frame_sync.h>
#include <dsd-neo/engine/frame_processing.h>
void xerax_run_live_loop(dsd_opts* opts, dsd_state* state);
void xerax_real_noCarrier(dsd_opts* opts, dsd_state* state);
int xerax_record_sync(dsd_opts* opts, dsd_state* state);
void xerax_record_dispatch(dsd_opts* opts, dsd_state* state);
int xerax_record_frame(dsd_opts* opts, dsd_state* state);

// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stdint.h>
void xerax_v2_lich(const dsd_state* state, const char* reason, int result,
    int full, int lich, int received, int computed, int voice, int scch,
    int pich_tch, int idas, int sacch, int facch);
void xerax_v2_scch(const dsd_state* state, const uint8_t* bits, unsigned computed,
    unsigned received, int soft_pass, int direction);
