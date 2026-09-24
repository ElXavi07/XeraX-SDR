// SPDX-License-Identifier: GPL-3.0-or-later
.pragma library

// Explain only states the engine reports. A strong-looking spectrum, SNR or
// carrier lock alone cannot establish valid speech or the correct privacy key.
function assess(m, running, analogMode) {
    if (!running)
        return {code: "idle", title: qsTr("Receiver stopped"), detail: qsTr("Start a system or scan list to check reception."), canDisableSquelch: false};
    if (!m || m.optionsKnown !== true)
        return {code: "starting", title: qsTr("Waiting for receiver status"), detail: qsTr("Live settings are not available yet."), canDisableSquelch: false};
    var radio = m.radioInput === true;
    var airspy = m.airspy && m.airspy.gain_mode !== undefined;
    if (radio && !airspy && m.streamActive === false)
        return {code: "no_samples", title: qsTr("No incoming RTL samples"), detail: qsTr("Check USB permission, receiver power and cable, or the RTL-TCP connection. A retune may briefly interrupt samples."), canDisableSquelch: false};
    var squelched = radio && m.squelchOff === false;
    if (m.audioMuted === true)
        return {code: "muted", title: qsTr("Audio is muted"), detail: qsTr("Use the monitor's mute control to hear decoded speech. Muting does not stop decoding."), canDisableSquelch: squelched};
    if (analogMode)
        return {code: "analog", title: qsTr("Analog FM listening"), detail: squelched
            ? qsTr("Analog voice does not need digital frame sync. Try squelch off, check media volume and the audio route if the channel is silent.")
            : qsTr("Squelch is off: channel noise should be audible. Tune to the carrier center; check media volume, mute and the audio route if silent. Analog audio has no digital talkgroup or color code."), canDisableSquelch: squelched};
    if (!m.syncedHere && squelched)
        return {code: "squelch", title: qsTr("Squelch is enabled; no frame sync"), detail: qsTr("A threshold can clip digital bursts. Try squelch off while checking the correct frequency and protocol."), canDisableSquelch: true};
    if (!m.syncedHere)
        return {code: "no_sync", title: qsTr("Waiting for digital frame sync"),
            detail: radio ? qsTr("The channel may be idle. Verify frequency and NXDN rate/DMR/P25 mode. For P25 simulcast, try QPSK. Compare gain and antenna position; maximum gain can overload a receiver.")
                          : qsTr("Verify that the input contains supported demodulated audio and uses the correct format and protocol. RF measurements are unavailable for this input."), canDisableSquelch: false};
    var privateCall = (m.slot1CallState === 2 && m.slot1CallEnc === true)
                   || (m.slot2CallState === 2 && m.slot2CallEnc === true);
    if (privateCall)
        return {code: "private_call", title: qsTr("Frame sync; private call flagged"), detail: qsTr("If speech is unclear, check the configured key and algorithm. The privacy flag alone does not show whether a supplied key is correct."), canDisableSquelch: squelched};
    return {code: "synced", title: qsTr("Digital frame sync acquired"), detail: qsTr("Sync confirms recognized framing, not guaranteed voice quality. For broken speech, compare gain, antenna position and the correct modulation. Control or data traffic can be silent."), canDisableSquelch: squelched};
}

function measurements(m, running) {
    if (!running || !m || m.optionsKnown !== true || m.radioInput !== true)
        return "";
    var airspy = m.airspy && m.airspy.gain_mode !== undefined;
    if (!airspy && m.streamActive !== true)
        return "";
    var parts = [];
    if (m.syncedHere && m.syncLabel)
        parts.push(String(m.syncLabel));
    if (m.snrValid === true && typeof m.snrDb === "number" && isFinite(m.snrDb))
        parts.push(qsTr("SNR estimate %1 dB").arg(m.snrDb.toFixed(1)));
    return parts.join(" · ");
}
