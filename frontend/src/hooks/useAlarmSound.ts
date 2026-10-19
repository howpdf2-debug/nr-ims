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

    osc.type = "sine";
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    gain.gain.setValueAtTime(0.1, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.3);
  } catch (e) {
    console.error("Audio playback failed", e);
  }
}

export function useAlarmSound() {
  const [isMuted, setIsMuted] = useState(
    () => localStorage.getItem("alarm_mute") === "true"
  );
  const [isAudioLocked, setIsAudioLocked] = useState(true); // NEW: Track browser lock
  const prevAlarmCount = useRef<number>(0);
  const lastBeepTime = useRef<number>(0);

  // ── 1. Audio Unlock Logic (Autoplay Policy Bypass) ──
  useEffect(() => {
    const ctx = getAudioContext();

    const checkState = () => {
      setIsAudioLocked(ctx.state === "suspended");
    };

    const unlockAudio = () => {
      if (ctx.state === "suspended") {
        ctx.resume().then(() => {
          setIsAudioLocked(false);
          playBeep(); // Confirmation beep
        }).catch(console.error);
      }
    };

    // Check immediately
    checkState();

    // Listen for ANY first click or keypress globally
    document.addEventListener("click", unlockAudio, { once: true });
    document.addEventListener("keydown", unlockAudio, { once: true });

    // Sync mute state
    const handleMuteChange = () => {
      setIsMuted(localStorage.getItem("alarm_mute") === "true");
    };
    window.addEventListener("alarm_mute_changed", handleMuteChange);

    // Polling fallback for context state
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
    if (isMuted || isAudioLocked) {
      prevAlarmCount.current = criticalAlarms;
      return;
    }

    if (criticalAlarms > prevAlarmCount.current) {
      const now = Date.now();
      if (now - lastBeepTime.current > 3000) {
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