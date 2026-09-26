/* Runtime-setting qualification: exact frozen observer and inputs, ordinary
 * DSP test-support library, no compile-time first-canonical candidate flag. */
#include <dsd-neo/core/opts.h>
#include <dsd-neo/dsp/frame_sync.h>
static int
runtime_fast_sync(dsd_opts* opts, dsd_state* state) {
    opts->nxdn_fast_acquisition = 1;
    return getFrameSync(opts, state);
}
#define getFrameSync runtime_fast_sync
#include "../nxdn_frames/observer.c"
