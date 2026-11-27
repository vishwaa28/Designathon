import { useEffect, useRef, useState } from 'react'
import { AudioLines, Loader2, Mic, MicOff, PhoneOff, Plane, RotateCcw, Search, Send, TriangleAlert } from 'lucide-react'
import { ChatMessage } from './ChatParts'
import { cx } from '../ui'
import { LANGUAGES, describeBooking } from '../../lib/useTravelerSession'
import { STATUS_TEXT, SUGGESTIONS } from '../../lib/voiceText'

const HINTS = {
  idle: 'Type below or tap the microphone to talk.',
  connecting: 'Setting up a secure voice connection.',
  listening: 'Go ahead, I am listening.',
  thinking: 'Working on your request.',
  speaking: 'Start talking at any time to interrupt.',
  error: 'Check your microphone and try again.',
}

const ORB = {
  idle: { core: 'from-brand-400 to-brand-700', glow: 'rgba(95,133,241,0.5)', ring: 'border-brand-300/40' },
  connecting: { core: 'from-slate-400 to-slate-600', glow: 'rgba(148,163,184,0.35)', ring: 'border-slate-300/30' },
  listening: { core: 'from-emerald-400 to-emerald-600', glow: 'rgba(52,211,153,0.5)', ring: 'border-emerald-300/50' },
  thinking: { core: 'from-amber-300 to-amber-500', glow: 'rgba(251,191,36,0.45)', ring: 'border-amber-200/40' },
  speaking: { core: 'from-brand-300 to-brand-600', glow: 'rgba(95,133,241,0.65)', ring: 'border-brand-200/50' },
  error: { core: 'from-rose-400 to-rose-600', glow: 'rgba(251,113,133,0.45)', ring: 'border-rose-300/40' },
}

const BAR_SHAPE = [0.35, 0.55, 0.8, 0.5, 0.95, 0.65, 0.4, 0.85, 1, 0.7, 0.45, 0.9, 0.6, 0.8, 0.5, 0.95, 0.7, 0.4, 0.75, 0.55, 0.35]

function StatusIcon({ status, size }) {
  if (status === 'connecting') return <Loader2 size={size} className="animate-spin" />
  if (status === 'error') return <TriangleAlert size={size} />
  return <AudioLines size={size} />
}

/** Large glowing orb that reacts to the voice level. `scale` shrinks it for the phone layout. */
function Orb({ status, level, scale = 1 }) {
  const tone = ORB[status] || ORB.idle
  const active = status === 'listening' || status === 'speaking'
  const box = 160 * scale
  return (
    <div className="relative" style={{ width: box, height: box }}>
      <div className="absolute left-0 top-0 flex h-40 w-40 items-center justify-center" style={{ transform: `scale(${scale})`, transformOrigin: 'top left' }}>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={cx('absolute inset-0 rounded-full border transition-[transform,opacity] duration-150 ease-out', tone.ring)}
            style={{
              transform: `scale(${active ? 0.62 + level * (0.5 + i * 0.28) + i * 0.1 : 0.6 + i * 0.12})`,
              opacity: active ? 0.8 - i * 0.22 : 0.4 - i * 0.1,
            }}
          />
        ))}
        {status === 'thinking' && <span className="absolute h-[100px] w-[100px] animate-spin rounded-full border-2 border-transparent border-t-amber-200" />}
        <div
          className={cx(
            'relative flex h-[88px] w-[88px] items-center justify-center rounded-full bg-gradient-to-br text-white transition-all duration-200',
            tone.core,
            status === 'idle' && 'orb-breathe',
          )}
          style={{
            boxShadow: `0 0 ${24 + level * 56}px ${6 + level * 14}px ${tone.glow}, inset 0 2px 6px rgba(255,255,255,0.35)`,
            transform: `scale(${1 + (active ? level * 0.12 : 0)})`,
          }}
        >
          <StatusIcon status={status} size={32} />
        </div>
      </div>
    </div>
  )
}

function MiniOrb({ status, level }) {
  const tone = ORB[status] || ORB.idle
  const active = status === 'listening' || status === 'speaking'
  return (
    <span
      className={cx('flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br text-white transition-all duration-150', tone.core, status === 'idle' && 'orb-breathe')}
      style={{ boxShadow: `0 0 ${10 + level * 22}px ${2 + level * 6}px ${tone.glow}`, transform: `scale(${1 + (active ? level * 0.1 : 0)})` }}
    >
      <StatusIcon status={status} size={16} />
    </span>
  )
}

function Equalizer({ status, level }) {
  const live = status === 'listening' || status === 'speaking'
  return (
    <div className="flex h-8 items-center justify-center gap-[3px]" aria-hidden="true">
      {BAR_SHAPE.map((shape, i) => (
        <span
          key={i}
          className={cx(
            'w-[3px] rounded-full transition-[height,background-color] duration-100',
            status === 'speaking' ? 'bg-brand-300' : live ? 'bg-emerald-300' : status === 'thinking' ? 'bg-amber-300/80' : 'bg-white/25',
            status === 'thinking' && 'bar-wave',
          )}
          style={{ height: live ? `${4 + level * shape * 26}px` : '4px', animationDelay: status === 'thinking' ? `${i * 70}ms` : undefined }}
        />
      ))}
    </div>
  )
}

const fieldClass =
  'h-11 w-full rounded-xl border border-white/15 bg-white/10 px-3.5 text-[14px] text-white placeholder:text-slate-400 focus:border-brand-300 focus:outline-none focus:ring-2 focus:ring-brand-400/30'

/** Booking lookup shown inside the assistant until a booking is found. */
function LookupForm({ session }) {
  const { pnr, setPnr, name, setName, busy, error, lookup } = session
  return (
    <form
      className="mt-5 space-y-3"
      onSubmit={(e) => {
        e.preventDefault()
        lookup()
      }}
    >
      <label className="block">
        <span className="mb-1 block text-[12px] font-medium text-slate-300">Booking reference (PNR)</span>
        <input className={cx(fieldClass, 'font-mono uppercase tracking-wide')} value={pnr} onChange={(e) => setPnr(e.target.value.toUpperCase())} placeholder="e.g. K7Q2MX" autoComplete="off" />
      </label>
      <label className="block">
        <span className="mb-1 block text-[12px] font-medium text-slate-300">Last name</span>
        <input className={fieldClass} value={name} onChange={(e) => setName(e.target.value)} placeholder="As on ticket" autoComplete="off" />
      </label>
      <button
        type="submit"
        disabled={busy || !pnr.trim() || !name.trim()}
        className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-white text-[14px] font-semibold text-navy-900 shadow-lg shadow-black/20 transition hover:bg-brand-50 disabled:cursor-not-allowed disabled:bg-white/20 disabled:text-slate-400 disabled:shadow-none"
      >
        {busy ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />} Find my booking
      </button>
      {error && <p className="rounded-lg bg-rose-500/15 px-3 py-2 text-[12.5px] text-rose-200">{error}</p>}
    </form>
  )
}

/**
 * The traveler assistant: voice and chat merged into one surface. Until a booking is found it asks for the PNR and
 * last name; after that the conversation (typed or spoken) happens in the same place.
 * `variant="pc"` fills its column and leaves flight details and seats to the right-hand panel;
 * `variant="mobile"` shows everything, including seat selection, inside the chat.
 */
export default function Assistant({ session, variant = 'pc' }) {
  const { voice, who, booking, connected, language, setLanguage, voiceAvailable } = session
  const mobile = variant === 'mobile'
  const [draft, setDraft] = useState('')
  const scroller = useRef(null)
  const welcomed = useRef(null)
  const status = voice.status
  const labels = STATUS_TEXT[language]

  const activity = connected || voice.messages.some((m) => m.role === 'user' || (m.kind && !['booking', 'menu'].includes(m.kind)))
  const hero = !who || !activity

  // First message after a booking is found (also covers links that open the page with ?pnr=&name=).
  useEffect(() => {
    if (!who) {
      welcomed.current = null
      return
    }
    if (welcomed.current === who.pnr || voice.messages.length) return
    welcomed.current = who.pnr
    voice.pushMessage({ role: 'assistant', text: `Hi ${who.first_name}, I found your booking ${who.pnr}. ${describeBooking(booking)}` })
    if (mobile) voice.pushMessage({ kind: 'booking' })
    voice.pushMessage({ kind: 'menu' })
  }, [who, booking, voice, mobile])

  useEffect(() => {
    const el = scroller.current
    if (el && !hero) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [voice.messages, session.flow?.step, session.flow?.seatMap, hero])

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
    if (!draft.trim() || !who) return
    session.ask(draft.trim())
    setDraft('')
  }

  const affected = booking?.actionable_legs?.length > 0
  const subtitle = connected
    ? HINTS[status]
    : who
      ? affected
        ? 'Your journey has changed. Pick an option below or just ask me.'
        : 'How can I help with your trip today?'
      : 'Enter your booking details and I will take care of the rest.'

  return (
    <section
      className={cx(
        'relative flex h-full min-h-0 flex-col overflow-hidden bg-gradient-to-b from-navy-900 via-navy-800 to-brand-900 text-white',
        !mobile && 'rounded-2xl shadow-[0_1px_2px_rgba(16,24,40,0.1),0_16px_40px_-16px_rgba(16,24,40,0.45)]',
      )}
    >
      <div className="pointer-events-none absolute -left-16 -top-20 h-64 w-64 rounded-full bg-fuchsia-500/20 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 top-24 h-64 w-64 rounded-full bg-brand-500/30 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 -left-10 h-56 w-72 rounded-full bg-teal-400/15 blur-3xl" />

      {/* Header */}
      <div className={cx('relative flex items-center gap-2.5 px-4 pb-2', mobile ? 'pt-4 sm:pt-9' : 'pt-4')}>
        {hero ? (
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/10 text-white ring-1 ring-white/15"><Plane size={16} /></span>
        ) : (
          <MiniOrb status={status} level={voice.level} />
        )}
        <div className="min-w-0 flex-1 leading-tight">
          <p className="truncate text-[14px] font-semibold">Meridian Assistant</p>
          <p className="flex items-center gap-1.5 text-[11.5px] text-slate-300">
            <span className={cx('h-1.5 w-1.5 rounded-full', connected ? 'animate-pulse-ring bg-emerald-400' : 'bg-slate-400')} />
            {connected ? labels[status] : who ? `${who.name} · ${who.pnr}` : 'Chat and voice'}
          </p>
        </div>
        <div className="flex rounded-full bg-white/10 p-0.5">
          {LANGUAGES.map((l) => (
            <button
              key={l.id}
              type="button"
              onClick={() => pickLanguage(l.id)}
              aria-pressed={language === l.id}
              className={cx('rounded-full px-2.5 py-1 text-[11.5px] font-medium transition-colors', language === l.id ? 'bg-white text-navy-900 shadow-sm' : 'text-slate-300 hover:text-white')}
            >
              {l.id === 'en' ? 'EN' : l.native}
            </button>
          ))}
        </div>
        {who && (
          <button type="button" onClick={session.reset} className="flex h-8 w-8 items-center justify-center rounded-full text-slate-300 transition-colors hover:bg-white/10 hover:text-white" aria-label="Use a different booking" title="Use a different booking">
            <RotateCcw size={15} />
          </button>
        )}
      </div>

      {/* Conversation */}
      <div ref={scroller} className="relative min-h-0 flex-1 overflow-y-auto px-4 pb-3">
        {hero && (
          <div className={cx('flex flex-col items-center text-center', mobile ? 'pt-1' : 'pt-4')}>
            <Orb status={status} level={voice.level} scale={mobile ? 0.8 : 1} />
            <h2 className={cx('-mt-1 font-semibold tracking-tight', mobile ? 'text-[22px]' : 'text-[26px]')}>
              {who ? `Hi ${who.first_name},` : 'Welcome to Meridian Airways'}
            </h2>
            <p className={cx('mt-1 max-w-xs leading-snug text-slate-300', mobile ? 'text-[13px]' : 'text-[14px]')}>{subtitle}</p>
            {connected && <div className="mt-3 w-full"><Equalizer status={status} level={voice.level} /></div>}
          </div>
        )}

        {!who ? (
          <LookupForm session={session} />
        ) : (
          <div className={cx('space-y-3', hero ? 'mt-5' : 'pt-2')}>
            {voice.messages.map((m) => <ChatMessage key={m.key} m={m} session={session} inline={mobile} dark />)}
          </div>
        )}
      </div>

      {/* Composer */}
      {who && (
        <div className="relative px-3 pb-3 pt-1">
          {connected && !hero && <div className="mb-1.5"><Equalizer status={status} level={voice.level} /></div>}
          {voice.error && <p className="mb-2 rounded-lg bg-rose-500/15 px-3 py-1.5 text-center text-[12px] text-rose-200">{voice.error}</p>}
          {!voiceAvailable && !connected && <p className="mb-1.5 text-center text-[11px] text-amber-300/90">Voice is not set up on this server. Chat works as usual.</p>}
          <div className="no-scrollbar -mx-1 mb-2 flex gap-1.5 overflow-x-auto px-1">
            {SUGGESTIONS[language].map((s) => (
              <button
                key={s}
                type="button"
                disabled={voice.status === 'connecting'}
                onClick={() => session.ask(s)}
                className="shrink-0 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-[12px] text-slate-200 transition-colors hover:bg-white/15 disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </div>
          <form onSubmit={submit} className="flex items-center gap-1.5 rounded-full bg-white/10 py-1.5 pl-4 pr-1.5 ring-1 ring-white/15 focus-within:ring-brand-300/60">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={connected ? 'Speak, or type here' : 'Type a message'}
              className="h-9 min-w-0 flex-1 bg-transparent text-[14px] text-white placeholder:text-slate-400 focus:outline-none"
            />
            {draft.trim() ? (
              <button type="submit" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-500 text-white transition-colors hover:bg-brand-400" aria-label="Send message">
                <Send size={16} />
              </button>
            ) : connected ? (
              <>
                <button
                  type="button"
                  onClick={() => voice.setMuted(!voice.muted)}
                  className={cx('flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition-colors', voice.muted ? 'bg-amber-400 text-navy-900' : 'bg-white/10 text-white hover:bg-white/20')}
                  aria-label={voice.muted ? 'Unmute microphone' : 'Mute microphone'}
                >
                  {voice.muted ? <MicOff size={17} /> : <Mic size={17} />}
                </button>
                <button type="button" onClick={voice.stop} className="flex h-10 shrink-0 items-center gap-1.5 rounded-full bg-rose-500 px-3.5 text-[12.5px] font-semibold text-white transition-colors hover:bg-rose-600" aria-label="End voice conversation">
                  <PhoneOff size={15} /> End
                </button>
              </>
            ) : (
              <button
                type="button"
                disabled={!voiceAvailable}
                onClick={() => voice.start()}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-navy-900 transition-colors hover:bg-brand-50 disabled:cursor-not-allowed disabled:bg-white/15 disabled:text-slate-400"
                aria-label="Talk to the assistant"
                title={voiceAvailable ? 'Talk to the assistant' : 'Voice is not available'}
              >
                <Mic size={17} />
              </button>
            )}
          </form>
        </div>
      )}
    </section>
  )
}
