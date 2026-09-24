// SPDX-License-Identifier: GPL-3.0-or-later
// Exercise the actual NXDN element loader, not a second implementation.
#include "../upstream/dsd-neo/src/protocol/nxdn/nxdn_element.c"
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "Key selection failure at %d\n", __LINE__); return 1; } } while (0)
int main(void) {
    static dsd_state state;
    static dsd_opts opts;
    state.keyloader = 1;
    opts.frame_nxdn48 = 1;
    struct nxdn_vcall_info call = {0};
    call.cipher_type = 1; call.key_id = 7; call.destination_id = 1200;
    state.rkey_array[7] = 12345;
    state.rkey_array[1200] = 32767;
    nxdn_vcall_load_key(&opts, &state, &call);
    CHECK(state.R == 12345 && dsd_key_scalar_present(&state, 0));
    state.payload_miN = 123;
    nxdn_vcall_load_key(&opts, &state, &call);
    CHECK(state.payload_miN == 123); // Repeated headers must not restart the stream.
    call.key_id = 8;
    nxdn_vcall_load_key(&opts, &state, &call);
    CHECK(state.R == 32767 && state.payload_miN == 0); // Destination fallback.
    call.destination_id = 1201;
    nxdn_vcall_load_key(&opts, &state, &call);
    CHECK(state.R == 0 && !dsd_key_scalar_present(&state, 0)); // No stale key.
    state.rkey_array_loaded[8] = 1; // Zero is a supplied value, not a missing row.
    nxdn_vcall_load_key(&opts, &state, &call);
    CHECK(state.R == 0 && dsd_key_scalar_present(&state, 0));
    opts.frame_nxdn48 = 0; opts.frame_nxdn96 = 1; call.destination_id = 1200;
    nxdn_vcall_load_key(&opts, &state, &call);
    CHECK(state.R == 32767); // NXDN96 uses the configured destination mapping.
    call.destination_id = 1201;
    nxdn_vcall_load_key(&opts, &state, &call);
    CHECK(!dsd_key_scalar_present(&state, 0));
    state.keyloader = 0; state.R = 1; state.scalar_key_present[0] = 1;
    nxdn_vcall_load_key(&opts, &state, &call);
    CHECK(state.R == 1); // A direct override remains explicitly controlled by the user.
    state.keyloader = 1;
    state.payload_keyid = 7; state.payload_keyidR = 8;
    keyring_activate_slot(&opts, &state, 0); keyring_activate_slot(&opts, &state, 1);
    CHECK(state.R == 12345 && state.RR == 0 && dsd_key_scalar_present(&state, 1));
    CHECK(keyring_kid_satisfies_need(&state, 8, DSD_KEY_NEED_SCALAR));
    state.payload_keyid = 900; keyring_activate_slot(&opts, &state, 0);
    CHECK(!dsd_key_scalar_present(&state, 0) && dsd_key_scalar_present(&state, 1));
    CHECK(!keyring_scalar_present(&state, -1) && !keyring_scalar_present(&state, 1000000));
    puts("Native NXDN lookup, zero material, missing-key clearing and slot isolation passed");
    return 0;
}
