/* Microphone capture worklet: resamples to 24 kHz mono PCM16 in 40 ms frames and reports input level. */
/* global AudioWorkletProcessor, sampleRate, registerProcessor */
class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super()
    this.step = sampleRate / 24000
    this.queue = []
    this.t = 0
    this.frame = new Int16Array(960)
    this.filled = 0
    this.energy = 0
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0]
    if (!channel) return true
    for (let i = 0; i < channel.length; i++) this.queue.push(channel[i])

    while (this.t + 1 < this.queue.length) {
      const i = Math.floor(this.t)
      const frac = this.t - i
      const sample = this.queue[i] * (1 - frac) + this.queue[i + 1] * frac
      const clamped = Math.max(-1, Math.min(1, sample))
      this.frame[this.filled++] = clamped < 0 ? clamped * 32768 : clamped * 32767
      this.energy += clamped * clamped
      this.t += this.step

      if (this.filled === this.frame.length) {
        const rms = Math.sqrt(this.energy / this.filled)
        const pcm = this.frame.buffer
        this.port.postMessage({ pcm, rms }, [pcm])
        this.frame = new Int16Array(960)
        this.filled = 0
        this.energy = 0
      }
    }

    const consumed = Math.floor(this.t)
    if (consumed > 0) {
      this.queue.splice(0, consumed)
      this.t -= consumed
    }
    return true
  }
}

registerProcessor('pcm-capture', PcmCapture)
