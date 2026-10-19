import { useEffect, useRef, useState } from "react";
import { useAlarmsQuery } from "./useAlarmsQuery";

// ── Singleton AudioContext ──────
let sharedAudioCtx: AudioContext | null = null;

function getAudioContext(): AudioContext {
  if (!sharedAudioCtx || sharedAudioCtx.state === "closed") {
    const AudioContextClass =
      window.AudioContext || (window as any).webkitAudioContext;
    sharedAudioCtx = new AudioContextClass();
  }
  return sharedAudioCtx;
}

function playBeep() {
  try {
    const ctx = getAudioContext();
    if (ctx.state === "suspended") {
      ctx.resume().catch(() => {});
    }

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    // तेज़ और स्पष्ट आवाज़ के लिए (0.5 मतलब 50% वॉल्यूम)
    osc.type = "square"; // 'square' wave ज्यादा तेज़ सुनाई देती है
    osc.frequency.setValueAtTime(1000, ctx.currentTime); 
    gain.gain.setValueAtTime(0.5, ctx.currentTime); 
    
    // 0.5 सेकंड की तेज़ बीप
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.5);
  } catch (e) {
    console.error("Audio playback failed", e);
  }
}

export function useAlarmSound() {
  const [isMuted, setIsMuted] = useState(
    () => localStorage.getItem("alarm_mute") === "true"
  );
  const [isAudioLocked, setIsAudioLocked] = useState(true);
  const prevAlarmCount = useRef<number>(0);
  const lastBeepTime = useRef<number>(0);

  // ── 1. Audio Unlock Logic ──
  useEffect(() => {
    const ctx = getAudioContext();

    const checkState = () => {
      setIsAudioLocked(ctx.state === "suspended");
    };

    const unlockAudio = () => {
      if (ctx.state === "suspended") {
        ctx.resume().then(() => {
          setIsAudioLocked(false);
          // क्लिक करते ही एक कन्फर्मेशन बीप बजाएं
          playBeep(); 
        }).catch(console.error);
      }
    };

    checkState();

    // पेज पर पहले क्लिक या कीप्रेस पर ऑडियो अनलॉक करें
    document.addEventListener("click", unlockAudio, { once: true });
    document.addEventListener("keydown", unlockAudio, { once: true });

    const handleMuteChange = () => {
      setIsMuted(localStorage.getItem("alarm_mute") === "true");
    };
    window.addEventListener("alarm_mute_changed", handleMuteChange);

    const interval = setInterval(checkState, 2000);

    return () => {
      document.removeEventListener("click", unlockAudio);
      document.removeEventListener("keydown", unlockAudio);
      window.removeEventListener("alarm_mute_changed", handleMuteChange);
      clearInterval(interval);
    };
  }, []);

  // ── 2. Alarm Fetching & Beeping ──
  const { data: alarms = [] } = useAlarmsQuery();

  const criticalAlarms = alarms.filter(
    (a: any) =>
      a.status === "active" &&
      a.severity === "critical" &&
      !a.is_suppressed
  ).length;

  useEffect(() => {
    if (isMuted) {
      prevAlarmCount.current = criticalAlarms;
      return;
    }

    // अगर ऑडियो लॉक है, तो हम काउंट को अपडेट नहीं करेंगे ताकि क्लिक करने पर बीप बज सके
    if (isAudioLocked) return;

    if (criticalAlarms > prevAlarmCount.current) {
      const now = Date.now();
      if (now - lastBeepTime.current > 2000) { // 2 सेकंड का गैप
        playBeep();
        lastBeepTime.current = now;
      }
    }
    prevAlarmCount.current = criticalAlarms;
  }, [criticalAlarms, isMuted, isAudioLocked]);

  const toggleMute = () => {
    const newMuted = !isMuted;
    setIsMuted(newMuted);
    localStorage.setItem("alarm_mute", String(newMuted));
    window.dispatchEvent(new Event("alarm_mute_changed"));

    if (!newMuted) {
      const ctx = getAudioContext();
      ctx.resume().then(() => {
        setIsAudioLocked(false);
        if (criticalAlarms > 0) playBeep();
      });
    }
  };

  return { isMuted, toggleMute, criticalAlarms, isAudioLocked };
}