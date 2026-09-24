// SPDX-License-Identifier: GPL-3.0-or-later
package io.github.arancormonk.dsdneo

/** Select produced audio, never infer speech from a rest-channel indicator.
 * Pure policy, shared by the Android service and host regression tests. */
class SiteAudioSelector(private val count:Int) {
    private val frames=LongArray(count)
    private val heardAt=LongArray(count) { Long.MIN_VALUE / 2 }
    fun reset() { frames.fill(0); heardAt.fill(Long.MIN_VALUE / 2) }
    fun choose(now:Long, nonzero:List<Long>, active:List<Boolean>, current:Int):Int {
        require(nonzero.size==count && active.size==count)
        for(i in 0 until count) {
            if(nonzero[i]>frames[i] && active[i]) heardAt[i]=now
            if(nonzero[i]<frames[i] || !active[i]) heardAt[i]=Long.MIN_VALUE / 2
            frames[i]=nonzero[i]
        }
        fun ready(i:Int)=i in 0 until count && active[i] && now-heardAt[i]<=750
        // Stay with an ongoing call; simultaneous callers do not steal playback.
        if(ready(current)) return current
        return (0 until count).firstOrNull { ready(it) } ?: -1
    }
}
