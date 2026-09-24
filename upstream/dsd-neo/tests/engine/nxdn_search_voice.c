// SPDX-License-Identifier: GPL-3.0-or-later
// Exercise the production post-FEC recovery hook and real MBElib synthesis.
#include "../../src/core/vocoder/dsd_mbe.c"
#include <dsd-neo/core/init.h>
#include <dsd-neo/fec/block_codes.h>
#include <math.h>
#include <stdlib.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"NXDN native check failed at %d\n",__LINE__); return 1; } } while(0)
static void encode(const char bits[49],char frame[4][24]) {
    unsigned char word[24],data[12];
    memset(frame,0,96);
    for(int i=0;i<12;++i) data[i]=(unsigned char)bits[i];
    Golay_24_12_encode(data,word);
    for(int i=0;i<24;++i) frame[0][23-i]=(char)word[i];
    for(int i=0;i<12;++i) data[i]=(unsigned char)bits[i+12];
    Golay_24_12_encode(data,word);
    for(int i=0;i<23;++i) frame[1][22-i]=(char)word[i];
    for(int i=0;i<11;++i) frame[2][10-i]=bits[24+i];
    for(int i=0;i<14;++i) frame[3][13-i]=bits[35+i];
    (void)mbe_demodulateAmbe3600x2450Data(frame); // channel whitening is involutory
}
static void encrypt(char bits[49],unsigned seed,int position) {
    unsigned char stream[784];
    for(int i=0;i<15;++i) stream[i]=(seed>>i)&1U;
    for(int i=15;i<784;++i) stream[i]=stream[i-15]^stream[i-14];
    for(int i=0;i<49;++i) bits[i]^=(char)stream[position*49+i];
}
int main(void) {
    dsd_opts* opts=calloc(1,sizeof(*opts)); dsd_state* state=calloc(1,sizeof(*state));
    CHECK(opts && state); initOpts(opts); initState(state);
    opts->frame_nxdn48=1; opts->frame_nxdn96=0; opts->payload=0;
    state->synctype=DSD_SYNC_NXDN_POS; state->nxdn_cipher_type=1; state->nxdn_cipher_class_est=1;
    state->nxdn_confirmed=1; state->nxdn_search_part_valid=1; state->nxdn_sacch_non_superframe=0;
    state->nxdn_last_ran=1; state->nxdn_key=2;
    const dsd_call_observation obs={.protocol=DSD_SYNC_NXDN_POS,.kind=DSD_CALL_KIND_GROUP_VOICE,.ota_target_id=2,.ota_source_id=3};
    CHECK(dsd_call_state_observe(state,&obs,DSD_CALL_BOUNDARY_BEGIN)>0);
    dsd_nxdn_search_enable(1); double energy=0;
    for(int n=0;n<40;++n) {
        const int position=n%16; const uint64_t word=n<8?UINT64_C(0xE8154638273800):UINT64_C(0xA80524124EB280);
        char plain[49],bits[49],frame[4][24],check[49]; mbe_process_result result;
        for(int i=0;i<49;++i) plain[i]=(char)((word>>(55-i))&1U);
        memcpy(bits,plain,49); encrypt(bits,12345,position); encode(bits,frame);
        CHECK(mbe_decodeAmbe3600x2450Frame((const char(*)[24])frame,check,&result)>=0);
        CHECK(memcmp(check,bits,49)==0);
        state->nxdn_part_of_frame=position/4; state->nxdn_search_voice_index=position%4;
        mbe_frame_ctx_t context={0}; mbe_process_nxdn(opts,state,frame,NULL,&context);
        if(n>=15) {
            CHECK(state->nxdn_search.ready && state->nxdn_search.key==12345);
            CHECK(memcmp(context.ambe_d,plain,49)==0);
            CHECK(dsd_nxdn_search_audio_allowed(&state->nxdn_search) && !state->dmr_encL);
            for(int i=0;i<160;++i) { CHECK(isfinite(state->audio_out_temp_buf[i])); energy+=fabs(state->audio_out_temp_buf[i]); }
        } else CHECK(!dsd_nxdn_search_audio_allowed(&state->nxdn_search));
    }
    CHECK(energy>1); dsd_nxdn_search_enable(0);
    CHECK(!dsd_nxdn_search_audio_allowed(&state->nxdn_search));
    printf("PASS: native NXDN FEC -> recovered seed -> exact AMBE payload -> nonzero finite PCM; energy %.3f\n",energy);
    freeState(state); free(state); free(opts); return 0;
}
