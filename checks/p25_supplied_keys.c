// SPDX-License-Identifier: GPL-3.0-or-later
#include "../upstream/dsd-neo/src/core/vocoder/dsd_mbe.c"
#include <dsd-neo/protocol/p25/p25_lfsr.h>
#include "privacy_vectors.h"
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"P25 reference failed at %d\n",__LINE__); return 1; } } while(0)
static void unpack(const uint8_t* bytes,char* out,int n) { for(int i=0;i<n;++i) out[i]=(bytes[i/8]>>(7-i%8))&1; }
static void configure(dsd_state* s,const privacy_vector* v) {
    memset(s,0,sizeof(*s)); s->payload_algid=s->payload_algidR=v->alg;
    s->payload_miP=s->payload_miN=v->mi;
    s->R=s->RR=0x0001020304050607ULL;
    for(int slot=0;slot<2;++slot) {
        s->A1[slot]=0x0001020304050607ULL; s->A2[slot]=0x08090a0b0c0d0e0fULL;
        s->A3[slot]=0x1011121314151617ULL; s->A4[slot]=0x18191a1b1c1d1e1fULL;
        s->aes_key_loaded[slot]=1; s->scalar_key_present[slot]=1;
        p25_lfsr128_slot(s,slot);
    }
}
int main(void) {
    static dsd_state s; static dsd_opts opts;
    const uint8_t plain[]={0x11,0x22,0x33,0x44,0x55,0x66,0x77,0x88,0x99,0xaa,0xbb};
    char expected[88]; unpack(plain,expected,88);
    for(size_t test=0;test<sizeof(privacy_vectors)/sizeof(privacy_vectors[0]);++test) {
        const privacy_vector* v=&privacy_vectors[test]; configure(&s,v);
        CHECK(!memcmp(s.aes_iv,v->iv,16) && !memcmp(s.aes_ivR,v->iv,16));
        CHECK(mbe_p25p1_multicrypt_enabled(&s));
        for(int frame=0;frame<2;++frame) {
            char bits[88]; unpack(v->p1+11*frame,bits,88); s.p25vc=frame;
            mbe_apply_p25p1_multicrypt(&s,bits); CHECK(!memcmp(bits,expected,88));
        }
        configure(&s,v); s.aes_key_loaded[0]=0; s.scalar_key_present[0]=0; s.R=0;
        CHECK(!mbe_p25p1_multicrypt_enabled(&s));
        configure(&s,v); s.A1[0]^=2; s.R^=2;
        char wrong[88]; unpack(v->p1,wrong,88); mbe_apply_p25p1_multicrypt(&s,wrong);
        CHECK(memcmp(wrong,expected,88));
        configure(&s,v); s.synctype=DSD_SYNC_P25P2_POS;
        for(int frame=0;frame<2;++frame) for(int slot=0;slot<2;++slot) {
            mbe_frame_ctx_t ctx={0}; unpack(v->p2+7*frame,ctx.ambe_d,49);
            const long other=slot?s.bit_counterL:s.bit_counterR;
            if(v->alg==0x81) { if(slot) mbeslot_right_apply_des(&s,&ctx); else mbeslot_left_apply_des(&s,&ctx); }
            else { if(slot) mbeslot_right_apply_aes_and_streams(&opts,&s,&ctx); else mbeslot_left_apply_aes_and_streams(&opts,&s,&ctx); }
            CHECK(!memcmp(ctx.ambe_d,expected,49));
            CHECK((slot?s.bit_counterL:s.bit_counterR)==other);
        }
        if(v->alg!=0x81) {
            configure(&s,v); s.aes_key_loaded[0]=0;
            mbe_frame_ctx_t ctx={0}; char original[49]; unpack(v->p2,ctx.ambe_d,49); memcpy(original,ctx.ambe_d,49);
            mbeslot_left_apply_aes_and_streams(&opts,&s,&ctx);
            CHECK(!memcmp(original,ctx.ambe_d,49) && s.bit_counterL==0 && s.DMRvcL==0);
        }
    }
    puts("P25 AES-128/AES-256/DES: independent Phase 1 and both Phase 2 slots; MI changes, wrong/missing keys, slot isolation passed");
    return 0;
}
