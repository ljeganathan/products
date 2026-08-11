// Short two-tone "ding" for a new KOT ticket arriving on the Kitchen Display —
// synthesized with the Web Audio API rather than an embedded audio file, so there's no
// asset to ship/load and it works the instant the page does.
let ctx: AudioContext | null = null;

function getContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  if (!ctx) ctx = new Ctor();
  return ctx;
}

function tone(audio: AudioContext, freq: number, startAt: number, duration: number) {
  const osc = audio.createOscillator();
  const gain = audio.createGain();
  osc.type = "sine";
  osc.frequency.value = freq;
  gain.gain.setValueAtTime(0, startAt);
  gain.gain.linearRampToValueAtTime(0.25, startAt + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.001, startAt + duration);
  osc.connect(gain);
  gain.connect(audio.destination);
  osc.start(startAt);
  osc.stop(startAt + duration);
}

export function playNewTicketSound(): void {
  const audio = getContext();
  if (!audio) return;
  // Browsers suspend a freshly-created AudioContext until a user gesture; a KOT
  // screen left open all shift will have had one already (login, a click), so this
  // just guards the rare case it hasn't.
  if (audio.state === "suspended") void audio.resume();
  const now = audio.currentTime;
  tone(audio, 880, now, 0.18);
  tone(audio, 1175, now + 0.14, 0.22);
}
