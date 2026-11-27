import { useEffect, useRef, useState } from 'react'
import { AudioLines, CheckCircle2, Loader2, Mic, MicOff, PhoneOff, Send, TriangleAlert } from 'lucide-react'
import { cx } from '../ui'
import { useApi } from '../../lib/useApi'
import { useVoiceAgent } from '../../lib/useVoiceAgent'

const LANGUAGES = [
  { id: 'en', label: 'English', native: 'English' },
  { id: 'ta', label: 'Tamil', native: 'தமிழ்' },
  { id: 'te', label: 'Telugu', native: 'తెలుగు' },
]

const STATUS_TEXT = {
  en: { idle: 'Ready when you are', connecting: 'Connecting…', listening: 'Listening', thinking: 'One moment…', speaking: 'Speaking', error: 'Unable to connect' },
  ta: { idle: 'பேச தயார்', connecting: 'இணைக்கிறது…', listening: 'கேட்கிறேன்', thinking: 'யோசிக்கிறேன்…', speaking: 'பேசுகிறேன்', error: 'இணைக்க முடியவில்லை' },
  te: { idle: 'మాట్లాడటానికి సిద్ధం', connecting: 'కనెక్ట్ అవుతోంది…', listening: 'వింటున్నాను', thinking: 'ఆలోచిస్తున్నాను…', speaking: 'మాట్లాడుతున్నాను', error: 'కనెక్ట్ కాలేదు' },
}

const HINTS = {
  idle: 'Start a conversation and speak naturally.',
  connecting: 'Setting up a secure voice connection.',
  listening: 'Go ahead, I am listening.',
  thinking: 'Working on your request.',
  speaking: 'Start talking at any time to interrupt.',
  error: 'Check your microphone and try again.',
}

const SUGGESTIONS = {
  en: ['What happened to my journey?', 'Show me other options', 'I would like a refund'],
  ta: ['என் பயணத்திற்கு என்ன ஆனது?', 'வேறு வழிகளைக் காட்டுங்கள்', 'எனக்கு பணத்தைத் திரும்பப் பெற வேண்டும்'],
  te: ['నా ప్రయాణానికి ఏమైంది?', 'ఇతర ఎంపికలు చూపించండి', 'నాకు రీఫండ్ కావాలి'],
}

const TOOL_TEXT = {
  get_booking_status: ['Checking your booking…', 'Checked your booking'],
  get_alternatives: ['Looking up available options…', 'Looked up available options'],
  rebook: ['Rebooking your journey…', 'Journey rebooked'],
  request_refund: ['Processing your refund…', 'Refund requested'],
}

const BAR_SHAPE = [0.35, 0.55, 0.8, 0.5, 0.95, 0.65, 0.4, 0.85, 1, 0.7, 0.45, 0.9, 0.6, 0.8, 0.5, 0.95, 0.7, 0.4, 0.75, 0.55, 0.35]

const ORB = {
  idle: { core: 'from-brand-400 to-brand-700', glow: 'rgba(95,133,241,0.45)', ring: 'border-brand-300/40' },
  connecting: { core: 'from-slate-400 to-slate-600', glow: 'rgba(148,163,184,0.35)', ring: 'border-slate-300/30' },
  listening: { core: 'from-emerald-400 to-emerald-600', glow: 'rgba(52,211,153,0.5)', ring: 'border-emerald-300/50' },
  thinking: { core: 'from-amber-300 to-amber-500', glow: 'rgba(251,191,36,0.45)', ring: 'border-amber-200/40' },
  speaking: { core: 'from-brand-300 to-brand-600', glow: 'rgba(95,133,241,0.6)', ring: 'border-brand-200/50' },
  error: { core: 'from-rose-400 to-rose-600', glow: 'rgba(251,113,133,0.45)', ring: 'border-rose-300/40' },
}

function Orb({ status, level }) {
  const tone = ORB[status] || ORB.idle
  const active = status === 'listening' || status === 'speaking'
  return (
    <div className="relative flex h-48 w-48 items-center justify-center">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={cx('absolute inset-0 rounded-full border transition-[transform,opacity] duration-150 ease-out', tone.ring)}
          style={{
            transform: `scale(${active ? 0.62 + level * (0.5 + i * 0.28) + i * 0.1 : 0.6 + i * 0.12})`,
            opacity: active ? 0.8 - i * 0.22 : 0.35 - i * 0.1,
          }}
        />
      ))}
      {status === 'thinking' && <span className="absolute h-[118px] w-[118px] animate-spin rounded-full border-2 border-transparent border-t-amber-200" />}
      <div
        className={cx(
          'relative flex h-[104px] w-[104px] items-center justify-center rounded-full bg-gradient-to-br text-white transition-all duration-200',
          tone.core,
          status === 'idle' && 'orb-breathe',
        )}
        style={{
          boxShadow: `0 0 ${24 + level * 56}px ${6 + level * 14}px ${tone.glow}, inset 0 2px 6px rgba(255,255,255,0.35)`,
          transform: `scale(${1 + (active ? level * 0.12 : 0)})`,
        }}
      >
        {status === 'connecting' ? <Loader2 size={34} className="animate-spin" /> : status === 'error' ? <TriangleAlert size={34} /> : <AudioLines size={36} />}
      </div>
    </div>
  )
}

function Equalizer({ status, level }) {
  const live = status === 'listening' || status === 'speaking'
  return (
    <div className="flex h-12 items-center justify-center gap-[3px]" aria-hidden="true">
      {BAR_SHAPE.map((shape, i) => (
        <span
          key={i}
          className={cx(
            'w-[3px] rounded-full transition-[height,background-color] duration-100',
            status === 'speaking' ? 'bg-brand-300' : live ? 'bg-emerald-300' : status === 'thinking' ? 'bg-amber-300/80' : 'bg-white/25',
            status === 'thinking' && 'bar-wave',
          )}
          style={{
            height: live ? `${5 + level * shape * 40}px` : '5px',
            animationDelay: status === 'thinking' ? `${i * 70}ms` : undefined,
          }}
        />
      ))}
    </div>
  )
}

function ToolLine({ m }) {
  const text = TOOL_TEXT[m.name] || [m.name, m.name]
  return (
    <div className="flex justify-center">
      <span
        className={cx(
          'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11.5px] font-medium',
          m.status === 'failed' ? 'bg-rose-50 text-rose-700' : 'bg-slate-100 text-slate-600',
        )}
      >
        {m.status === 'running' ? <Loader2 size={12} className="animate-spin" /> : m.status === 'failed' ? <TriangleAlert size={12} /> : <CheckCircle2 size={12} className="text-emerald-600" />}
        {m.status === 'running' ? text[0] : m.status === 'failed' ? `Could not complete: ${text[1].toLowerCase()}` : text[1]}
      </span>
    </div>
  )
}

function Bubble({ m }) {
  const user = m.role === 'user'
  return (
    <div className={cx('flex animate-feed-in', user ? 'justify-end' : 'justify-start')}>
      <div
        className={cx(
          'max-w-[84%] rounded-2xl px-3.5 py-2.5 text-[13.5px] leading-relaxed',
          user ? 'rounded-br-md bg-brand-600 text-white' : 'rounded-bl-md bg-slate-100 text-slate-800',
        )}
      >
        {m.pending && !m.text ? (
          <span className="flex items-center gap-1 py-1">
            {[0, 1, 2].map((i) => (
              <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-white/80" style={{ animationDelay: `${i * 120}ms` }} />
            ))}
          </span>
        ) : (
          <>
            {m.text}
            {m.streaming && <span className="ml-0.5 inline-block h-3.5 w-[2px] translate-y-0.5 animate-pulse bg-slate-500" />}
          </>
        )}
      </div>
    </div>
  )
}

export default function VoiceAgent({ booking, onBookingChanged, details = null }) {
  const passenger = booking?.passenger
  const { data: voiceStatus } = useApi('/voice/status')
  const [language, setLanguage] = useState(() => (LANGUAGES.some((l) => l.id === passenger?.language) ? passenger.language : 'en'))
  const [draft, setDraft] = useState('')
  const voice = useVoiceAgent({ pnr: passenger?.pnr || '', name: passenger?.last_name || '', language, onBookingChanged })
  const scroller = useRef(null)

  const connected = ['connecting', 'listening', 'thinking', 'speaking'].includes(voice.status)
  const available = Boolean(passenger) && voiceStatus?.configured !== false
  const labels = STATUS_TEXT[language]
  const displayStatus = voice.status

  useEffect(() => {
    const el = scroller.current
    if (el && voice.messages.length) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [voice.messages])

  const pickLanguage = (id) => {
    if (id === language) return
    setLanguage(id)
    if (connected) {
      voice.stop()
      setTimeout(() => voice.start(id), 250)
    }
  }

  const submit = (e) => {
    e.preventDefault()
    if (!draft.trim() || !connected) return
    voice.sendText(draft.trim())
    setDraft('')
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04),0_8px_24px_-12px_rgba(16,24,40,0.12)]">
      <div className="grid lg:grid-cols-[380px_1fr]">
        {/* Voice stage */}
        <div className="relative flex flex-col items-center overflow-hidden bg-gradient-to-b from-navy-900 via-navy-800 to-brand-900 px-4 pb-6 pt-5 text-white sm:px-6 sm:pb-7 sm:pt-6">
          <div className="pointer-events-none absolute -top-24 left-1/2 h-64 w-64 -translate-x-1/2 rounded-full bg-brand-500/20 blur-3xl" />
          <div className="relative flex w-full items-center justify-between">
            <div>
              <p className="text-[15px] font-semibold tracking-tight">Talk to us</p>
              <p className="text-[12px] text-slate-400">Voice assistant for this booking</p>
            </div>
            <span className={cx('flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium', connected ? 'bg-emerald-400/15 text-emerald-300' : 'bg-white/10 text-slate-300')}>
              <span className={cx('h-1.5 w-1.5 rounded-full', connected ? 'bg-emerald-400 animate-pulse-ring' : 'bg-slate-400')} />
              {connected ? 'Live' : 'Offline'}
            </span>
          </div>

          <div className="relative mt-4 flex gap-1.5 rounded-full bg-white/10 p-1">
            {LANGUAGES.map((l) => (
              <button
                key={l.id}
                type="button"
                onClick={() => pickLanguage(l.id)}
                className={cx(
                  'rounded-full px-3.5 py-1.5 text-[12.5px] font-medium transition-colors',
                  language === l.id ? 'bg-white text-navy-900 shadow-sm' : 'text-slate-300 hover:text-white',
                )}
                aria-pressed={language === l.id}
              >
                {l.native}
              </button>
            ))}
          </div>

          <div className="relative mt-3">
            <Orb status={displayStatus} level={voice.level} />
          </div>

          <div className="relative -mt-1 text-center">
            <p className="text-[19px] font-semibold tracking-tight">{labels[displayStatus]}</p>
            <p className="mt-0.5 min-h-[18px] text-[12.5px] text-slate-400">{HINTS[displayStatus]}</p>
          </div>

          <div className="relative mt-3 w-full">
            <Equalizer status={displayStatus} level={voice.level} />
          </div>

          <div className="relative mt-4 flex items-center gap-3">
            {connected ? (
              <>
                <button
                  type="button"
                  onClick={() => voice.setMuted(!voice.muted)}
                  className={cx(
                    'flex h-11 w-11 items-center justify-center rounded-full transition-colors',
                    voice.muted ? 'bg-amber-400 text-navy-900' : 'bg-white/10 text-white hover:bg-white/20',
                  )}
                  aria-label={voice.muted ? 'Unmute microphone' : 'Mute microphone'}
                  title={voice.muted ? 'Unmute' : 'Mute'}
                >
                  {voice.muted ? <MicOff size={18} /> : <Mic size={18} />}
                </button>
                <button
                  type="button"
                  onClick={voice.stop}
                  className="flex h-11 items-center gap-2 rounded-full bg-rose-500 px-5 text-[13.5px] font-semibold text-white shadow-lg shadow-rose-900/30 transition-colors hover:bg-rose-600"
                >
                  <PhoneOff size={16} /> End conversation
                </button>
              </>
            ) : (
              <button
                type="button"
                disabled={!available}
                onClick={() => voice.start()}
                className="flex h-11 items-center gap-2 rounded-full bg-white px-6 text-[13.5px] font-semibold text-navy-900 shadow-lg shadow-black/20 transition hover:bg-brand-50 disabled:cursor-not-allowed disabled:bg-white/20 disabled:text-slate-400 disabled:shadow-none"
              >
                <Mic size={16} /> {displayStatus === 'error' ? 'Try again' : 'Start conversation'}
              </button>
            )}
          </div>

          {voice.error && <p className="relative mt-4 w-full rounded-lg bg-rose-500/15 px-3 py-2 text-center text-[12px] text-rose-200">{voice.error}</p>}
          {!passenger && <p className="relative mt-4 text-center text-[12px] text-slate-400">Find your booking above to start talking.</p>}
          {voiceStatus?.configured === false && <p className="relative mt-4 text-center text-[12px] text-amber-300">Voice is not configured on this server.</p>}
        </div>

        {/* Conversation */}
        <div className="flex min-h-[360px] min-w-0 flex-col sm:min-h-[420px]">
          <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-3.5 sm:px-5">
            <div className="min-w-0">
              <p className="text-[13.5px] font-semibold text-slate-900">Conversation</p>
              <p className="text-[12px] text-slate-500">
                {passenger ? `${passenger.name} · ${passenger.pnr}` : 'Your conversation will appear here'}
              </p>
            </div>
            <span className="rounded-md bg-slate-100 px-2 py-1 text-[11.5px] font-medium text-slate-600">{LANGUAGES.find((l) => l.id === language).label}</span>
          </div>

          <div ref={scroller} className="flex-1 space-y-3 overflow-y-auto px-4 py-4 sm:px-5" style={{ maxHeight: details ? 640 : 360 }}>
            {details && (
              <>
                <div className="space-y-3">{details}</div>
                <div className="flex items-center gap-3 pt-1 text-[11.5px] font-medium uppercase tracking-wide text-slate-400">
                  <span className="h-px flex-1 bg-slate-200" />
                  Conversation
                  <span className="h-px flex-1 bg-slate-200" />
                </div>
              </>
            )}
            {!voice.messages.length && (
              <div className={cx('flex flex-col items-center justify-center text-center', details ? 'py-6' : 'h-full min-h-[240px]')}>
                <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
                  <AudioLines size={22} />
                </span>
                <p className="mt-3 text-[14px] font-semibold text-slate-900">Ask about your journey, in your language</p>
                <p className="mt-1 max-w-sm text-[12.5px] leading-relaxed text-slate-500">
                  The assistant can explain what changed, find other flights with seats, rebook you or start a refund once you confirm.
                </p>
              </div>
            )}
            {voice.messages.map((m) => (m.kind === 'tool' ? <ToolLine key={m.key} m={m} /> : <Bubble key={m.key} m={m} />))}
          </div>

          <div className="border-t border-slate-100 px-4 py-3 sm:px-5">
            <div className="mb-2.5 flex flex-wrap gap-1.5">
              {SUGGESTIONS[language].map((s) => (
                <button
                  key={s}
                  type="button"
                  disabled={!connected || voice.status === 'connecting'}
                  onClick={() => voice.sendText(s)}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[12px] text-slate-600 transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-slate-200 disabled:hover:bg-white disabled:hover:text-slate-600"
                >
                  {s}
                </button>
              ))}
            </div>
            <form onSubmit={submit} className="flex items-center gap-2">
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                disabled={!connected}
                placeholder={connected ? 'Or type a message' : 'Start the conversation to type or speak'}
                className="h-10 flex-1 rounded-lg border border-slate-300 bg-white px-3 text-[13px] text-slate-800 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:bg-slate-50"
              />
              <button
                type="submit"
                disabled={!connected || !draft.trim()}
                className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-600 text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
                aria-label="Send message"
              >
                <Send size={16} />
              </button>
            </form>
          </div>
        </div>
      </div>
    </section>
  )
}
