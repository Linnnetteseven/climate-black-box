/**
 * Procedural ambience: an orbital pad that becomes a forest.
 *
 * Still synthesised rather than sampled -- nothing to license, nothing to
 * attribute, a few kB instead of a few MB -- but the previous version was
 * three oscillators through a low-pass, which is a drone, not a soundtrack.
 *
 * What makes this read as "space" rather than "noise":
 *
 *  - A slow chord progression. Static harmony is what made it sound like
 *    white noise; movement between chords is most of the feeling.
 *  - Organ-style stacked partials (octave, fifth, octave-and-a-third) rather
 *    than one fundamental, so each voice has body.
 *  - A long convolution reverb built from shaped noise, which is what gives
 *    the sense of enormous empty space.
 *  - A shimmer layer an octave up, delayed and detuned, swelling on its own
 *    slow cycle so the pad never sits still.
 *
 * The forest scene is the same engine with different sources: filtered noise
 * shaped into running water, and short frequency-swept bursts for birdsong.
 *
 * The orbital scene prefers a supplied recording (public/audio/orbit.mp3) and
 * falls back to the synthesised pad if the file is missing or will not decode.
 * A track written for the piece beats anything generated here; the synth stays
 * so the page is never silent on a machine that cannot play it.
 */

export type Scene = "space" | "forest";

//: Deliberately not pretty.
//:
//: The first version was a consonant organ progression -- warm, resolved,
//: closer to a meditation app than to something with dread in it. This sits
//: lower and keeps a minor second inside every chord, so each one is slightly
//: wrong and never settles. The root barely moves; the tension above it does.
//:
//: Frequencies are in Hz. The top note of each chord is a semitone or tritone
//: against the one below it, which is what produces the slow beating you hear
//: rather than a clean pad.
const PROGRESSION: number[][] = [
  [36.71, 55.00, 73.42, 77.78],   // D1  A1  D2  Eb2  -- minor 2nd at the top
  [36.71, 55.00, 69.30, 73.42],   // D1  A1  Db2 D2
  [32.70, 49.00, 65.41, 69.30],   // C1  G1  C2  Db2
  [36.71, 51.91, 73.42, 77.78],   // D1  Ab1 D2  Eb2  -- tritone in the middle
];

//: Long holds. Nothing should feel like it is going anywhere.
const CHORD_SECONDS = 16;

/** A long, smooth impulse response. Cheaper and more controllable than
 *  shipping a reverb file, and it is what sells the scale of the space. */
function makeReverb(ctx: AudioContext, seconds = 5.5, decay = 2.6): ConvolverNode {
  const rate = ctx.sampleRate;
  const length = Math.floor(rate * seconds);
  const buffer = ctx.createBuffer(2, length, rate);
  for (let ch = 0; ch < 2; ch++) {
    const data = buffer.getChannelData(ch);
    for (let i = 0; i < length; i++) {
      const t = i / length;
      // Noise shaped by an exponential tail, with the very start softened so
      // the reverb blooms instead of clicking.
      data[i] = (Math.random() * 2 - 1) * Math.pow(1 - t, decay) * Math.min(1, t * 40);
    }
  }
  const convolver = ctx.createConvolver();
  convolver.buffer = buffer;
  return convolver;
}

function noiseBuffer(ctx: AudioContext, seconds = 4): AudioBuffer {
  const length = ctx.sampleRate * seconds;
  const buffer = ctx.createBuffer(1, length, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  // Brown-ish noise: smoother than white, which is what makes it read as
  // water or wind rather than static.
  let last = 0;
  for (let i = 0; i < length; i++) {
    const white = Math.random() * 2 - 1;
    last = (last + 0.02 * white) / 1.02;
    data[i] = last * 3.5;
  }
  return buffer;
}

const ORBIT_TRACK = "/audio/orbit.mp3";

export class Ambience {
  private ctx: AudioContext;
  private track: HTMLAudioElement | null = null;
  private synthSpace: GainNode | null = null;
  private master: GainNode;
  private spaceBus: GainNode;
  private forestBus: GainNode;
  private reverb: ConvolverNode;
  private voices: OscillatorNode[] = [];
  private timers: number[] = [];
  private stopped = false;

  constructor(target = 0.075) {
    type Ctor = typeof AudioContext;
    const Ctx: Ctor =
      window.AudioContext ?? (window as unknown as { webkitAudioContext: Ctor }).webkitAudioContext;
    this.ctx = new Ctx();

    this.master = this.ctx.createGain();
    this.master.gain.setValueAtTime(0.0001, this.ctx.currentTime);
    this.master.gain.linearRampToValueAtTime(target, this.ctx.currentTime + 2.5);
    this.master.connect(this.ctx.destination);

    // Longer and darker: a bigger, emptier room.
    this.reverb = makeReverb(this.ctx, 7.5, 3.1);
    const wet = this.ctx.createGain();
    wet.gain.value = 0.62;
    this.reverb.connect(wet).connect(this.master);

    this.spaceBus = this.ctx.createGain();
    this.forestBus = this.ctx.createGain();
    this.spaceBus.gain.value = 1;
    this.forestBus.gain.value = 0;
    for (const bus of [this.spaceBus, this.forestBus]) {
      bus.connect(this.master);
      bus.connect(this.reverb);
    }

    this.buildForest();
    this.buildOrbit();
  }

  /** Supplied recording if it plays, synthesised pad if it does not. */
  private buildOrbit() {
    const audio = new Audio(ORBIT_TRACK);
    audio.loop = true;
    audio.crossOrigin = "anonymous";
    audio.preload = "auto";

    const fallback = () => {
      if (this.synthSpace) return;        // already running
      this.track = null;
      this.buildSpace();
    };

    audio.addEventListener("error", fallback, { once: true });
    audio.addEventListener("canplay", () => {
      if (this.stopped || this.synthSpace) return;
      try {
        const source = this.ctx.createMediaElementSource(audio);
        // Into the scene bus, not straight to the destination, so the existing
        // cross-fade between scenes applies to it unchanged.
        source.connect(this.spaceBus);
        audio.play().catch(fallback);
        this.track = audio;
      } catch {
        fallback();
      }
    }, { once: true });

    // Do not wait indefinitely on a slow network: if nothing has loaded in a
    // few seconds, start the synth so there is something playing.
    this.timers.push(window.setTimeout(() => {
      if (!this.track && !this.synthSpace) fallback();
    }, 4000));
  }

  /** Stacked organ partials per chord tone, swelling on their own cycles. */
  private buildSpace() {
    const ctx = this.ctx;
    const marker = ctx.createGain();
    marker.gain.value = 1;
    this.synthSpace = marker;
    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    // Much darker than before: almost everything above the low mids is gone,
    // so what is left is felt in the chest rather than heard as melody.
    filter.frequency.value = 340;
    filter.Q.value = 0.9;
    filter.connect(this.spaceBus);

    // A slow machine pulse under everything -- the sense that something large
    // is running whether or not anyone is watching.
    const pulse = ctx.createOscillator();
    const pulseGain = ctx.createGain();
    const pulseFilter = ctx.createBiquadFilter();
    pulse.type = "sine";
    pulse.frequency.value = 27.5;            // A0, below most speakers' pitch
    pulseFilter.type = "lowpass";
    pulseFilter.frequency.value = 90;
    pulseGain.gain.value = 0;
    pulse.connect(pulseFilter).connect(pulseGain).connect(this.spaceBus);
    const heartbeat = ctx.createOscillator();
    const beatDepth = ctx.createGain();
    heartbeat.type = "triangle";
    heartbeat.frequency.value = 0.19;        // roughly one swell every 5s
    beatDepth.gain.value = 0.33;
    heartbeat.connect(beatDepth).connect(pulseGain.gain);
    pulse.start();
    heartbeat.start();
    this.voices.push(pulse, heartbeat);

    // A breath of filtered noise, so the pad has air in it and does not sound
    // purely synthetic.
    const airSrc = ctx.createBufferSource();
    airSrc.buffer = noiseBuffer(ctx, 6);
    airSrc.loop = true;
    const airFilter = ctx.createBiquadFilter();
    airFilter.type = "bandpass";
    airFilter.frequency.value = 220;
    airFilter.Q.value = 0.5;
    const airGain = ctx.createGain();
    airGain.gain.value = 0.12;
    airSrc.connect(airFilter).connect(airGain).connect(this.spaceBus);
    airSrc.start();

    // Four voices, each re-tuned when the chord changes.
    const voiceGains: GainNode[] = [];
    for (let v = 0; v < 4; v++) {
      const gain = ctx.createGain();
      gain.gain.value = v === 0 ? 0.5 : 0.26;
      gain.connect(filter);
      voiceGains.push(gain);

      // Fundamental plus octave only. Dropping the fifth removes most of the
      // "organ chord" character and leaves something closer to a struck
      // string ringing in a very large room.
      [1, 2].forEach((mult, k) => {
        const osc = ctx.createOscillator();
        osc.type = "sine";
        const partial = ctx.createGain();
        partial.gain.value = [1, 0.22][k];
        osc.connect(partial).connect(gain);
        osc.start();
        this.voices.push(osc);
        (gain as GainNode & { partials?: OscillatorNode[] }).partials ??= [];
        (gain as GainNode & { partials?: OscillatorNode[] }).partials!.push(osc);
      });

      // Each voice breathes on a slightly different cycle.
      const lfo = ctx.createOscillator();
      const depth = ctx.createGain();
      lfo.frequency.value = 0.035 + v * 0.013;
      depth.gain.value = v === 0 ? 0.14 : 0.1;
      lfo.connect(depth).connect(gain.gain);
      lfo.start();
      this.voices.push(lfo);
    }

    const applyChord = (index: number) => {
      if (this.stopped) return;
      const chord = PROGRESSION[index % PROGRESSION.length];
      voiceGains.forEach((gain, v) => {
        const partials = (gain as GainNode & { partials?: OscillatorNode[] }).partials ?? [];
        partials.forEach((osc, k) => {
          const base = chord[v] * (k + 1);
          // Glide rather than jump: an instant retune is audible as a click.
          osc.frequency.setTargetAtTime(base * (1 + (v - 1.5) * 0.0012), ctx.currentTime, 2.2);
        });
      });
      this.timers.push(
        window.setTimeout(() => applyChord(index + 1), CHORD_SECONDS * 1000),
      );
    };
    applyChord(0);

    // Shimmer: a quiet octave-up layer, delayed, that swells and recedes.
    const shimmer = ctx.createOscillator();
    const shimmerGain = ctx.createGain();
    const delay = ctx.createDelay(2.4);
    delay.delayTime.value = 1.3;
    shimmer.type = "sine";
    // A bare fifth far above the pad, arriving late and fading. Sparse enough
    // that it reads as a signal from somewhere rather than as melody.
    shimmer.frequency.value = 330.0;
    shimmerGain.gain.value = 0;
    shimmer.connect(shimmerGain).connect(delay).connect(this.reverb);
    const swell = ctx.createOscillator();
    const swellDepth = ctx.createGain();
    swell.frequency.value = 0.013;
    swellDepth.gain.value = 0.013;
    swell.connect(swellDepth).connect(shimmerGain.gain);
    shimmer.start();
    swell.start();
    this.voices.push(shimmer, swell);
  }

  /** Running water plus occasional birdsong. */
  private buildForest() {
    const ctx = this.ctx;

    // Brook: brown noise through a resonant band, wobbling slowly.
    const water = ctx.createBufferSource();
    water.buffer = noiseBuffer(ctx, 6);
    water.loop = true;
    const waterFilter = ctx.createBiquadFilter();
    waterFilter.type = "bandpass";
    waterFilter.frequency.value = 1100;
    waterFilter.Q.value = 0.7;
    const waterGain = ctx.createGain();
    waterGain.gain.value = 0.5;
    water.connect(waterFilter).connect(waterGain).connect(this.forestBus);
    const wobble = ctx.createOscillator();
    const wobbleDepth = ctx.createGain();
    wobble.frequency.value = 0.12;
    wobbleDepth.gain.value = 260;
    wobble.connect(wobbleDepth).connect(waterFilter.frequency);
    water.start();
    wobble.start();
    this.voices.push(wobble);

    // Wind through canopy: a darker noise layer underneath.
    const wind = ctx.createBufferSource();
    wind.buffer = noiseBuffer(ctx, 5);
    wind.loop = true;
    const windFilter = ctx.createBiquadFilter();
    windFilter.type = "lowpass";
    windFilter.frequency.value = 420;
    const windGain = ctx.createGain();
    windGain.gain.value = 0.35;
    wind.connect(windFilter).connect(windGain).connect(this.forestBus);
    const gust = ctx.createOscillator();
    const gustDepth = ctx.createGain();
    gust.frequency.value = 0.05;
    gustDepth.gain.value = 0.18;
    gust.connect(gustDepth).connect(windGain.gain);
    wind.start();
    gust.start();
    this.voices.push(gust);

    // Birdsong: short frequency-swept blips at irregular intervals. Two or
    // three notes with a falling contour reads as a bird; a single tone reads
    // as a test signal.
    const chirp = () => {
      if (this.stopped) return;
      const notes = 2 + Math.floor(Math.random() * 3);
      const base = 1900 + Math.random() * 1700;
      for (let n = 0; n < notes; n++) {
        const t = ctx.currentTime + n * (0.09 + Math.random() * 0.07);
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(base * (1 + n * 0.06), t);
        osc.frequency.exponentialRampToValueAtTime(base * (0.72 - n * 0.04), t + 0.085);
        gain.gain.setValueAtTime(0.0001, t);
        gain.gain.exponentialRampToValueAtTime(0.22, t + 0.012);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.11);
        osc.connect(gain).connect(this.forestBus);
        gain.connect(this.reverb);
        osc.start(t);
        osc.stop(t + 0.14);
      }
      this.timers.push(window.setTimeout(chirp, 2200 + Math.random() * 6500));
    };
    this.timers.push(window.setTimeout(chirp, 1800));
  }

  /** Cross-fade between scenes over a few seconds. */
  setScene(scene: Scene) {
    const now = this.ctx.currentTime;
    const toForest = scene === "forest";
    this.spaceBus.gain.setTargetAtTime(toForest ? 0.12 : 1, now, 1.6);
    this.forestBus.gain.setTargetAtTime(toForest ? 1 : 0, now, 1.6);
  }

  async stop() {
    this.stopped = true;
    this.timers.forEach(clearTimeout);
    if (this.track) {
      this.track.pause();
      this.track.src = "";
      this.track = null;
    }
    const now = this.ctx.currentTime;
    this.master.gain.cancelScheduledValues(now);
    this.master.gain.setValueAtTime(this.master.gain.value, now);
    this.master.gain.linearRampToValueAtTime(0.0001, now + 0.8);
    await new Promise((r) => setTimeout(r, 900));
    this.voices.forEach((v) => {
      try {
        v.stop();
      } catch {
        /* already stopped */
      }
    });
    await this.ctx.close().catch(() => {});
  }
}
