import io.github.arancormonk.dsdneo.SiteAudioSelector
fun main() {
    val s=SiteAudioSelector(4)
    val active=listOf(true,true,true,true)
    check(s.choose(1000,listOf(0,0,0,0),active,-1)==-1) // Control data is not audio.
    check(s.choose(1250,listOf(0,80,0,0),active,-1)==1)
    check(s.choose(1500,listOf(80,160,0,0),active,1)==1) // Don't steal a current call.
    check(s.choose(2500,listOf(160,160,0,0),active,1)==0)
    check(s.choose(3500,listOf(160,160,0,0),active,0)==-1) // Stale call metadata.
    check(s.choose(3750,listOf(160,160,120,0),listOf(true,true,false,true),-1)==-1)
    check(s.choose(4000,listOf(160,160,0,100),active,-1)==3) // Fourth lane works.
    s.reset()
    check(s.choose(4250,listOf(0,0,0,0),active,3)==-1)
    println("PASS: eight automatic audio policies, including silence, stale calls, contention, restart and fourth lane")
}
