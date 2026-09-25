// SPDX-License-Identifier: GPL-3.0-or-later
/* Supply unrelated DSP archive references from the real implementation. This
 * experiment's input is the finite getDibitSoft provider in observer.c; no
 * symbol demodulator or sync-search call is made by this harness. */
#define getDibitSoft xerax_gap_unused_real_getDibitSoft
#include "../../upstream/dsd-neo/src/core/frames/dsd_dibit.c"
