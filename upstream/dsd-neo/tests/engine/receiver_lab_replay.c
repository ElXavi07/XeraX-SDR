// SPDX-License-Identifier: GPL-3.0-or-later
// Host parity runner for the Android worker's actual equalizer and trial DSP.
#include <dsd-neo/core/init.h>
#include <dsd-neo/core/opts.h>
#include <dsd-neo/core/state.h>
#include <dsd-neo/engine/engine.h>
#include <dsd-neo/platform/receiver_lab.h>
#include <dsd-neo/runtime/bootstrap.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
int main(int argc,char** argv) {
    if(argc<5) return 2;
    dsd_equalizer_enable(atoi(argv[1]));
    dsd_trial_configure(atof(argv[2]),atoi(argv[3]));
    argv[3]=argv[0]; argv+=3; argc-=3;
    for(int i=1;i<argc;++i) if(strcmp(argv[i],"--xerax-ras")==0) {
        dsd_dmr_ras_enable(1); for(int j=i;j<argc;++j) argv[j]=argv[j+1]; --argc; --i;
    }
    dsd_opts* opts=calloc(1,sizeof(*opts));
    dsd_state* state=calloc(1,sizeof(*state));
    if(!opts || !state) { free(opts); free(state); return 2; }
    initOpts(opts); initState(state);
    int rc=1;
    if(dsd_runtime_bootstrap(argc,argv,opts,state,NULL,&rc)==DSD_BOOTSTRAP_CONTINUE)
        rc=dsd_engine_run_with_lifecycle(opts,state,NULL);
    dsd_dmr_evidence dmr; dsd_dmr_evidence_get(&dmr);
    fprintf(stderr,"XeraX DMR evidence: checked=%llu suspected_ras=%llu rejected=%llu\n",
        (unsigned long long)(dmr.checked[0]+dmr.checked[1]),
        (unsigned long long)(dmr.suspected_ras[0]+dmr.suspected_ras[1]),
        (unsigned long long)(dmr.rejected[0]+dmr.rejected[1]));
    freeState(state); free(state); free(opts);
    return rc;
}
