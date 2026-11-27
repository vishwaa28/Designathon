import { useCallback, useEffect, useRef, useState } from 'react'

const PLAYBACK_RATE = 24000

/**
 * Real-time voice conversation with the backend voice bridge.
 * Captures the microphone as 24 kHz PCM16, streams it over a WebSocket and plays the assistant's audio back,
 * with barge-in (speaking over the assistant stops its playback).
 */
export function useVoiceAgent({ pnr, name, language, onBookingChanged }) {
  const [status, setStatus] = useState('idle') // idle | connecting | listening | thinking | speaking | error
  const [error, setError] = useState(null)
  const [messages, setMessages] = useState([])
  const [level, setLevel] = useState(0)
  const [muted, setMutedState] = useState(false)
  const rt = useRef({ serverState: 'connecting', micLevel: 0, nextTime: 0, sources: new Set(), counter: 0 })
  const bookingCb = useRef(onBookingChanged)

  useEffect(() => {
    bookingCb.current = onBookingChanged
  })

  const stopPlayback = useCallback(() => {
    const r = rt.current
    r.sources.forEach((s) => {
      try {
        s.stop()
      } catch {
        /* already stopped */
      }
    })
    r.sources.clear()
    r.nextTime = 0
  }, [])

  const teardown = useCallback(() => {
    const r = rt.current
    r.closing = true
    clearInterval(r.timer)
    if (r.ws && r.ws.readyState <= 1) {
      try {
        r.ws.send(JSON.stringify({ type: 'end' }))
      } catch {
        /* socket not open */
      }
      r.ws.close()
    }
    stopPlayback()
    r.node?.disconnect()
    r.stream?.getTracks().forEach((t) => t.stop())
    r.ctx?.close().catch(() => {})
    Object.assign(r, { ws: null, ctx: null, node: null, stream: null, analyser: null, gain: null, ready: false, micLevel: 0 })
  }, [stopPlayback])

  const stop = useCallback(() => {
    teardown()
    setStatus('idle')
    setLevel(0)
    setMutedState(false)
  }, [teardown])

  const enqueueAudio = useCallback((buffer) => {
    const r = rt.current
    if (!r.ctx || r.dropAudio) return
    let data = buffer
    if (r.carry) {
      const merged = new Uint8Array(r.carry.length + buffer.byteLength)
      merged.set(r.carry, 0)
      merged.set(new Uint8Array(buffer), r.carry.length)
      data = merged.buffer
      r.carry = null
    }
    const samples = Math.floor(data.byteLength / 2)
    if (data.byteLength % 2) r.carry = new Uint8Array(data.slice(samples * 2))
    if (!samples) return
    const pcm = new Int16Array(data, 0, samples)
    const floats = new Float32Array(samples)
    for (let i = 0; i < samples; i++) floats[i] = pcm[i] / 32768
    const audio = r.ctx.createBuffer(1, samples, PLAYBACK_RATE)
    audio.copyToChannel(floats, 0)
    const source = r.ctx.createBufferSource()
    source.buffer = audio
    source.connect(r.gain)
    const startAt = Math.max(r.ctx.currentTime + 0.05, r.nextTime)
    source.start(startAt)
    r.nextTime = startAt + audio.duration
    r.sources.add(source)
    source.onended = () => r.sources.delete(source)
  }, [])

  const upsertMessage = useCallback((key, patch) => {
    setMessages((prev) => {
      const i = prev.findIndex((m) => m.key === key)
      if (i === -1) return [...prev, { key, ...patch(null) }]
      const next = prev.slice()
      next[i] = { ...prev[i], ...patch(prev[i]) }
      return next
    })
  }, [])

  const handleEvent = useCallback(
    (msg) => {
      const r = rt.current
      switch (msg.type) {
        case 'ready':
          r.ready = true
          r.serverState = 'listening'
          break
        case 'state':
          r.serverState = msg.state
          break
        case 'response_started':
          r.dropAudio = false
          setMessages((prev) => prev.filter((m) => !(m.pending && !m.text)))
          break
        case 'speech_started':
          stopPlayback()
          r.dropAudio = true
          r.carry = null
          r.serverState = 'listening'
          setMessages((prev) => (prev.some((m) => m.pending) ? prev : [...prev, { key: `u-${++r.counter}`, role: 'user', text: '', pending: true }]))
          break
        case 'transcript': {
          if (msg.role === 'user') {
            setMessages((prev) => {
              const i = prev.findIndex((m) => m.pending)
              if (i !== -1) {
                const next = prev.slice()
                next[i] = { ...prev[i], text: msg.text, pending: false }
                return next
              }
              return [...prev, { key: `u-${++r.counter}`, role: 'user', text: msg.text }]
            })
          } else {
            const key = `a-${msg.id || r.counter}`
            upsertMessage(key, (m) => ({
              role: 'assistant',
              text: msg.final ? msg.text || m?.text || '' : (m?.text || '') + msg.text,
              streaming: !msg.final,
            }))
          }
          break
        }
        case 'tool': {
          const label = msg.name
          if (msg.status === 'running') {
            setMessages((prev) => [...prev, { key: `t-${++r.counter}`, kind: 'tool', name: label, status: 'running' }])
          } else {
            setMessages((prev) => {
              const next = prev.slice()
              for (let i = next.length - 1; i >= 0; i--) {
                if (next[i].kind === 'tool' && next[i].name === label && next[i].status === 'running') {
                  next[i] = { ...next[i], status: msg.ok === false ? 'failed' : 'done' }
                  break
                }
              }
              return next
            })
          }
          break
        }
        case 'booking_changed':
          bookingCb.current?.()
          break
        case 'error':
          teardown()
          setError(msg.message)
          setStatus('error')
          setLevel(0)
          break
        default:
      }
    },
    [stopPlayback, teardown, upsertMessage],
  )

  const start = useCallback(
    async (langOverride) => {
      const r = rt.current
      if (r.ws) return
      setError(null)
      setMessages([])
      setStatus('connecting')
      r.closing = false
      r.dropAudio = false
      r.carry = null
      r.serverState = 'connecting'
      try {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error('This browser does not support microphone access.')
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        })
        const ctx = new AudioContext({ latencyHint: 'interactive' })
        await ctx.resume()
        await ctx.audioWorklet.addModule('/pcm-worklet.js')

        const node = new AudioWorkletNode(ctx, 'pcm-capture')
        ctx.createMediaStreamSource(stream).connect(node)

        const gain = ctx.createGain()
        const analyser = ctx.createAnalyser()
        analyser.fftSize = 512
        gain.connect(analyser)
        analyser.connect(ctx.destination)

        const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
        const query = new URLSearchParams({ pnr, name, lang: langOverride || language })
        const ws = new WebSocket(`${proto}://${window.location.host}/api/voice/ws?${query}`)
        ws.binaryType = 'arraybuffer'
        Object.assign(r, { ws, ctx, node, stream, gain, analyser, ready: false, nextTime: 0, muted: false })

        node.port.onmessage = ({ data }) => {
          r.micLevel = data.rms
          if (r.ws === ws && ws.readyState === WebSocket.OPEN && r.ready && !r.muted) ws.send(data.pcm)
        }
        ws.onmessage = (event) => {
          if (event.data instanceof ArrayBuffer) enqueueAudio(event.data)
          else {
            try {
              handleEvent(JSON.parse(event.data))
            } catch {
              /* ignore malformed frame */
            }
          }
        }
        ws.onclose = () => {
          if (r.closing || r.ws !== ws) return
          teardown()
          setError((e) => e || 'The voice connection was closed.')
          setStatus('error')
          setLevel(0)
        }

        const buf = new Uint8Array(analyser.fftSize)
        r.timer = setInterval(() => {
          if (!r.ctx) return
          const playing = r.ctx.currentTime < r.nextTime
          let derived = playing ? 'speaking' : r.serverState
          if (derived === 'connecting' && r.ready) derived = 'listening'
          setStatus(derived)
          let value
          if (playing) {
            analyser.getByteTimeDomainData(buf)
            let sum = 0
            for (let i = 0; i < buf.length; i++) {
              const v = (buf[i] - 128) / 128
              sum += v * v
            }
            value = Math.sqrt(sum / buf.length) * 3.2
          } else {
            value = r.muted ? 0 : r.micLevel * 7
          }
          setLevel(Math.min(1, value))
        }, 60)
      } catch (e) {
        teardown()
        const denied = e?.name === 'NotAllowedError' || e?.name === 'SecurityError'
        setError(denied ? 'Microphone access was blocked. Allow it in your browser to talk to the assistant.' : e?.message || 'Could not start the voice assistant.')
        setStatus('error')
      }
    },
    [pnr, name, language, enqueueAudio, handleEvent, teardown],
  )

  const sendText = useCallback((text) => {
    const ws = rt.current.ws
    if (ws && ws.readyState === WebSocket.OPEN && rt.current.ready && text.trim()) {
      stopPlayback()
      ws.send(JSON.stringify({ type: 'text', text }))
    }
  }, [stopPlayback])

  const setMuted = useCallback((value) => {
    rt.current.muted = value
    setMutedState(value)
  }, [])

  useEffect(() => teardown, [teardown])

  return { status, error, messages, level, muted, setMuted, start, stop, sendText }
}
