// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "../nxdn_engine_gap/observer_api.h"
#include <stdint.h>
void xerax_v2_lich(const dsd_state* state, const char* reason, int result,
    int full, int lich, int received, int computed, int voice, int scch,
    int pich_tch, int idas, int sacch, int facch);
void xerax_v2_scch(const dsd_state* state, const uint8_t* bits, unsigned computed,
    unsigned received, int soft_pass, int direction);
