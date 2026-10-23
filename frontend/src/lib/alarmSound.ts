// Alarm sound engine (F-4).
//
// Why a singleton engine instead of per-component state: `useAlarmSound` is mounted by AppShell AND by the
// Alarms page AND by the Wallboard. When each instance kept its own counter, every new alarm beeped once per
// mounted instance (double beep). Now ALL instances feed one engine which remembers which alarm IDs it has
// already announced, so a given alarm sounds exactly once no matter how many components observe it.
//
// A beep is triggered by a NEW alarm id entering the "soundworthy" set (active + critical + not suppressed):
//   * a brand-new alarm, a recurrence after resolve, an alarm escalated to critical, or an alarm whose root-cause
//     suppression just ended all beep;
//   * acknowledging/resolving one alarm while another arrives in the same poll no longer hides the new one
//     (the old logic compared COUNTS: 3 -> 3).

export interface SoundAlarm {
  id: string;
  status: string;
  severity: string;
  is_suppressed: boolean;
}

/** Ids of alarms that should make noise. */
export function soundworthyIds(alarms: readonly SoundAlarm[]): Set<string> {
  return new Set(
    alarms.filter((a) => a.status === "active" && a.severity === "critical" && !a.is_suppressed).map((a) => a.id),
  );
}

/** Ids present in `current` that were not announced yet. */
export function newIds(announced: ReadonlySet<string>, current: ReadonlySet<string>): string[] {
  return [...current].filter((id) => !announced.has(id));
}

export const MUTE_KEY = "alarm_mute";
export const THROTTLE_MS = 2000;

export interface SoundState {
  muted: boolean;
  /** Browsers keep audio suspended until the first user gesture. */
  locked: boolean;
}

type AudioCtor = typeof AudioContext;

function defaultCreateContext(): AudioContext | null {
  const w = window as unknown as { AudioContext?: AudioCtor; webkitAudioContext?: AudioCtor };
  const Ctor = w.AudioContext ?? w.webkitAudioContext;
  return Ctor ? new Ctor() : null;
}

function readMuted(): boolean {
  try {
    return localStorage.getItem(MUTE_KEY) === "true";
  } catch {
    return false;
  }
}

export interface EngineOptions {
  createContext?: () => AudioContext | null;
  now?: () => number;
}

export class AlarmSoundEngine {
  private ctx: AudioContext | null = null;
  private attached = false;
  private announced: Set<string> = new Set();
  private lastBeep = 0;
  private state: SoundState = { muted: readMuted(), locked: true };
  private listeners = new Set<() => void>();
  private readonly createContext: () => AudioContext | null;
  private readonly now: () => number;

  constructor(options: EngineOptions = {}) {
    this.createContext = options.createContext ?? defaultCreateContext;
    this.now = options.now ?? Date.now;
  }

  // ── external-store API (React `useSyncExternalStore`) ──
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  getSnapshot = (): SoundState => this.state;

  private setState(patch: Partial<SoundState>): void {
    const next = { ...this.state, ...patch };
    if (next.muted === this.state.muted && next.locked === this.state.locked) return;
    this.state = next;
    this.listeners.forEach((l) => l());
  }

  /** Idempotent: create the AudioContext, watch its state (no polling) and unlock it on the first gesture. */
  attach(): void {
    if (this.attached) return;
    this.attached = true;
    this.ctx = this.createContext();
    if (this.ctx) {
      this.ctx.onstatechange = () => this.syncLocked();
      this.syncLocked();
    }
    document.addEventListener("click", this.unlock, { once: true });
    document.addEventListener("keydown", this.unlock, { once: true });
    // Mute set in another tab/window of the same browser.
    window.addEventListener("storage", (e: StorageEvent) => {
      if (e.key === MUTE_KEY || e.key === null) this.setState({ muted: readMuted() });
    });
  }

  private syncLocked(): void {
    this.setState({ locked: !this.ctx || this.ctx.state !== "running" });
  }

  private unlock = (): void => {
    const ctx = this.ctx;
    if (!ctx) return;
    ctx.resume().then(
      () => {
        this.syncLocked();
        this.beep(); // audible confirmation that sound now works
      },
      () => this.syncLocked(),
    );
  };

  /** Feed the current ACTIVE alarms. Safe to call from any number of components. */
  observe(alarms: readonly SoundAlarm[]): void {
    const current = soundworthyIds(alarms);
    const fresh = newIds(this.announced, current);
    if (this.state.muted) {
      this.announced = current; // swallowed: no backlog burst when the operator unmutes
      return;
    }
    if (this.state.locked) return; // keep them pending until audio can play
    this.announced = current;
    if (fresh.length > 0) this.beep();
  }

  toggleMute = (): void => {
    const muted = !this.state.muted;
    try {
      localStorage.setItem(MUTE_KEY, String(muted));
    } catch {
      // storage blocked: the mute still applies for this tab
    }
    this.setState({ muted });
    if (!muted && this.ctx) {
      this.ctx.resume().then(
        () => {
          this.syncLocked();
          if (this.announced.size > 0) this.beep(); // unmuting while criticals are open: remind once
        },
        () => this.syncLocked(),
      );
    }
  };

  private beep(): void {
    const t = this.now();
    if (t - this.lastBeep < THROTTLE_MS) return;
    this.lastBeep = t;
    const ctx = this.ctx;
    if (!ctx) return;
    try {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "square"; // carries better than a sine in a noisy NOC
      osc.frequency.setValueAtTime(1000, ctx.currentTime);
      gain.gain.setValueAtTime(0.5, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.5);
    } catch (err) {
      console.error("Alarm beep failed", err);
    }
  }
}

/** The one engine of the app. */
export const alarmSound = new AlarmSoundEngine();
