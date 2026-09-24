// SPDX-License-Identifier: GPL-3.0-or-later
#include <dsd-neo/app_control/commands.h>
#include <dsd-neo/app_control/frontend_runtime.h>
#include <dsd-neo/core/init.h>
#include <dsd-neo/core/opts.h>
#include <dsd-neo/core/state.h>
#include <dsd-neo/platform/receiver_lab.h>
#include <stdio.h>
#include <string.h>
#include "../../src/app_control/commands_internal.h"
static int expect_u64(const char* label,uint64_t actual,uint64_t expected) {
    if(actual==expected) return 0;
    fprintf(stderr,"%s: got %llu expected %llu\n",label,(unsigned long long)actual,(unsigned long long)expected); return 1;
}
static int expect_int(const char* label,int actual,int expected) { return expect_u64(label,actual,expected); }
static void init_test_context(dsd_opts* opts,dsd_state* state) {
    memset(opts,0,sizeof(*opts)); memset(state,0,sizeof(*state));
    initOpts(opts); initState(state); state->cli_argc_effective=0; state->cli_argv=NULL;
    dsd_app_frontend_runtime_start(opts,state);
}
static int
test_atomic_p25_voice_tune(void) {
    int rc=0;
    static dsd_opts opts;
    static dsd_state state;
    init_test_context(&opts,&state);
    opts.audio_in_type=AUDIO_IN_RTL;
    opts.frame_p25p1=1; opts.frame_p25p2=0;
    opts.trunk_enable=0; opts.trunk_scan_enabled=0; opts.scanner_mode=0;
    dsd_voice_tune tune={{4101,851375000,0x92065,0x0D5,0x140,123,456,1,1,0},0};
    uint64_t sequence=0;
    opts.scanner_mode=1;
    dsd_app_command_submit(DSD_APP_CMD_P25_VOICE_TUNE,&tune,sizeof tune);
    dsd_app_drain_cmds(&opts,&state);
    rc|=expect_int("voice tune rejects scanning receiver",dsd_voice_tune_status(&sequence),-1);
    rc|=expect_u64("rejection sequence",sequence,4101);
    rc|=expect_int("rejected tune preserves phase",opts.frame_p25p1,1);
    opts.scanner_mode=0; tune.grant.sequence++;
    // No live USB handle is available. The command must establish all context
    // together, then report the tune failure instead of claiming RF success.
    dsd_app_command_submit(DSD_APP_CMD_P25_VOICE_TUNE,&tune,sizeof tune);
    dsd_app_drain_cmds(&opts,&state);
    rc|=expect_int("voice phase two context",opts.frame_p25p2,1);
    rc|=expect_int("voice phase two uses CQPSK",opts.mod_qpsk,1);
    rc|=expect_u64("voice WACN",state.p2_wacn,0x92065);
    rc|=expect_u64("voice SYSID",state.p2_sysid,0x0D5);
    rc|=expect_u64("voice NAC",state.p2_cc,0x140);
    rc|=expect_int("slot two unmutes",opts.slot2_on,1);
    rc|=expect_int("other slot stays muted",opts.slot1_on,0);
    rc|=expect_int("no tuner cannot acknowledge success",dsd_voice_tune_status(&sequence),-1);
    rc|=expect_u64("applied context sequence",sequence,4102);
    tune.grant.sequence++; tune.grant.tdma=0;
    dsd_app_command_submit(DSD_APP_CMD_P25_VOICE_TUNE,&tune,sizeof tune);
    dsd_app_drain_cmds(&opts,&state);
    rc|=expect_int("returns to phase one",opts.frame_p25p1,1);
    rc|=expect_int("phase one uses requested C4FM",opts.mod_c4fm,1);
    rc|=expect_int("phase one restores left slot",opts.slot1_on,1);
    freeState(&state);
    return rc;
}

int main(void) { return test_atomic_p25_voice_tune(); }
