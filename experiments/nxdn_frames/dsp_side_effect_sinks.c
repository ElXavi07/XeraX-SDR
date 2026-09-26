// SPDX-License-Identifier: GPL-3.0-or-later
/* Keep the shared fixture unchanged. This harness links real dsd_misc.c for
 * trellis_decode and therefore also its real filters/power helpers. Rename
 * the four otherwise duplicate no-op fixture definitions, never the real ones.
 */
#define lpf_f xerax_unused_stub_lpf_f
#define hpf_f xerax_unused_stub_hpf_f
#define pbf_f xerax_unused_stub_pbf_f
#define pwr_to_dB xerax_unused_stub_pwr_to_dB
#include "../../upstream/dsd-neo/tests/test_support/frame_sync_dsp_stubs.c"
