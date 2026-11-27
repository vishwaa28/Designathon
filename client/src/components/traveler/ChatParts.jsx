import { ArrowRight, CheckCircle2, Loader2, Mic, Plane, Route, TriangleAlert, Undo2 } from 'lucide-react'
import { Badge, Button, TripStatus, cx } from '../ui'
import SeatPicker from './SeatPicker'
import { fmtMin, fmtTime } from '../../lib/format'

const TOOL_TEXT = {
  get_booking_status: ['Checking your booking…', 'Checked your booking'],
  get_alternatives: ['Looking up available options…', 'Looked up available options'],
  rebook: ['Rebooking your journey…', 'Journey rebooked'],
  request_refund: ['Processing your refund…', 'Refund requested'],
}

export function ToolLine({ m, dark }) {
  const text = TOOL_TEXT[m.name] || [m.name, m.name]
  return (
    <div className="flex justify-center">
      <span
        className={cx(
          'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11.5px] font-medium',
          m.status === 'failed' ? 'bg-rose-50 text-rose-700' : dark ? 'bg-white/10 text-slate-200' : 'bg-slate-100 text-slate-600',
        )}
      >
        {m.status === 'running' ? <Loader2 size={12} className="animate-spin" /> : m.status === 'failed' ? <TriangleAlert size={12} /> : <CheckCircle2 size={12} className="text-emerald-600" />}
        {m.status === 'running' ? text[0] : m.status === 'failed' ? `Could not complete: ${text[1].toLowerCase()}` : text[1]}
      </span>
    </div>
  )
}

export function Bubble({ m, dark }) {
  const user = m.role === 'user'
  return (
    <div className={cx('flex animate-feed-in', user ? 'justify-end' : 'justify-start')}>
      <div
        className={cx(
          'max-w-[88%] rounded-2xl px-3.5 py-2.5 text-[13.5px] leading-relaxed',
          user
            ? 'rounded-br-md bg-brand-500 text-white'
            : dark
              ? 'rounded-bl-md bg-white/10 text-slate-50 ring-1 ring-inset ring-white/10 backdrop-blur'
              : 'rounded-bl-md bg-slate-100 text-slate-800',
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
            {m.streaming && <span className={cx('ml-0.5 inline-block h-3.5 w-[2px] translate-y-0.5 animate-pulse', dark ? 'bg-slate-300' : 'bg-slate-500')} />}
          </>
        )}
      </div>
    </div>
  )
}

/** One bookable alternative, shown as a tappable reference inside the chat and in the right-hand panel. */
export function FlightOption({ trip, selected, onSelect, disabled, compact }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onSelect(trip)}
      className={cx(
        'group flex w-full items-center gap-3 rounded-xl border bg-white p-3 text-left transition-all disabled:cursor-not-allowed disabled:opacity-60',
        selected ? 'border-brand-500 ring-2 ring-brand-100' : 'border-slate-200 hover:border-brand-300 hover:shadow-sm',
      )}
    >
      <span className={cx('flex h-9 w-9 shrink-0 items-center justify-center rounded-lg', selected ? 'bg-brand-600 text-white' : 'bg-brand-50 text-brand-600')}>
        <Plane size={16} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[12.5px] font-semibold text-slate-900">{trip.number}</span>
          <span className="truncate text-[12px] text-slate-500">{trip.origin} → {trip.destination}</span>
        </div>
        <p className="tabular mt-0.5 text-[13.5px] font-semibold text-slate-900">
          {fmtTime(trip.est_dep)} <ArrowRight size={12} className="mx-0.5 inline text-slate-400" /> {fmtTime(trip.est_arr)}
          {trip.delay_min >= 15 && <span className="ml-2 text-[11.5px] font-medium text-amber-600">+{fmtMin(trip.delay_min)}</span>}
        </p>
        {!compact && <p className="text-[11.5px] text-slate-500">{trip.vehicle_type} · Gate {trip.gate}</p>}
      </div>
      <div className="text-right">
        <p className="text-[12px] font-semibold text-emerald-700">{trip.seats_left} seats</p>
        <p className="text-[11px] font-medium text-brand-600 group-hover:underline">{selected ? 'Selected' : 'Choose seat'}</p>
      </div>
    </button>
  )
}

export function OptionsCard({ m, session, dark }) {
  const { flow, busy, chooseTrip } = session
  const picked = flow?.trip?.id
  return (
    <div className="animate-feed-in space-y-2">
      <p className={cx('px-1 text-[11.5px] font-medium uppercase tracking-wide', dark ? 'text-slate-300' : 'text-slate-400')}>
        {m.items.length ? 'Available flights' : 'No flights available'}
        {m.leg && m.items.length > 0 ? ` · ${m.leg.origin_city} to ${m.leg.destination_city}` : ''}
      </p>
      {m.items.map((t) => (
        <FlightOption key={t.id} trip={t} selected={picked === t.id} disabled={busy || flow?.step === 'done'} onSelect={(trip) => chooseTrip(trip, m.legId)} />
      ))}
      {!m.items.length && (
        <p className="rounded-xl bg-slate-50 px-3 py-3 text-[12.5px] text-slate-600">
          There are no flights with open seats on this route in the next 24 hours. I can start a full refund for you instead.
        </p>
      )}
    </div>
  )
}

export function ConfirmationCard({ m }) {
  const r = m.record
  const refunded = r?.outcome === 'REFUNDED'
  return (
    <div className="animate-feed-in rounded-2xl border border-emerald-200 bg-emerald-50 p-3.5">
      <div className="flex items-start gap-2.5">
        <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-emerald-600" />
        <div className="min-w-0">
          <p className="text-[13.5px] font-semibold text-emerald-900">{refunded ? 'Refund started' : 'Booking confirmed'}</p>
          <p className="mt-0.5 text-[12.5px] leading-relaxed text-emerald-800">{r?.message}</p>
          {r?.seat && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge tone="emerald">{r.new_trip}</Badge>
              <Badge tone="emerald">Seat {r.seat}</Badge>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function BookingCard({ session }) {
  const p = session.who
  if (!p) return null
  return (
    <div className="animate-feed-in rounded-2xl border border-slate-200 bg-white p-3.5 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-[13px] font-semibold text-slate-900">{p.name}</p>
          <p className="font-mono text-[11.5px] text-slate-500">{p.pnr} · {p.cabin}</p>
        </div>
        <Badge tone="blue">{p.status.replace('_', ' ').toLowerCase()}</Badge>
      </div>
      <div className="mt-3 space-y-2">
        {p.legs.map((leg) => (
          <div key={leg.id} className="rounded-xl bg-slate-50 p-2.5">
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-[12px] font-semibold text-slate-800">{leg.number}</span>
              <TripStatus status={leg.status} />
            </div>
            <p className="mt-1 text-[13px] font-semibold text-slate-900">
              {leg.origin} <ArrowRight size={12} className="mx-0.5 inline text-slate-400" /> {leg.destination}
            </p>
            <p className="tabular text-[12px] text-slate-500">
              {fmtTime(leg.est_dep)} → {fmtTime(leg.est_arr)} · Gate {leg.gate}{leg.seat ? ` · Seat ${leg.seat}` : ''}
              {leg.delay_min > 0 && <span className="ml-1 font-medium text-amber-600">(+{fmtMin(leg.delay_min)})</span>}
            </p>
          </div>
        ))}
        {!p.legs.length && <p className="text-[12.5px] text-slate-500">This booking has been refunded.</p>}
      </div>
    </div>
  )
}

export function RefundPrompt({ m, session }) {
  const { flow, busy, requestRefund } = session
  const done = flow?.step === 'done'
  return (
    <div className="animate-feed-in flex gap-2">
      <Button size="sm" variant="danger" icon={Undo2} loading={busy} disabled={done} onClick={() => requestRefund(m.legId)}>Yes, refund me</Button>
      <Button size="sm" variant="secondary" disabled={done} onClick={() => session.showOptions(m.legId)}>Show other flights</Button>
    </div>
  )
}

/** Seat map rendered inside the chat (mobile layout). Only the latest map for the active flow is interactive. */
export function InlineSeatMap({ m, session }) {
  const { flow, busy, pickSeat, confirmSeat } = session
  const active = flow?.step === 'seat' && flow.trip?.id === m.tripId
  if (!active) {
    return flow?.trip?.id === m.tripId && flow.step === 'done' ? null : (
      <p className="px-1 text-center text-[11.5px] text-slate-400">Seat selection closed</p>
    )
  }
  return (
    <div className="animate-feed-in rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="mb-2 flex items-center justify-between gap-2 px-1">
        <p className="text-[13px] font-semibold text-slate-900">
          Choose your seat <span className="font-mono text-[12px] font-normal text-slate-500">{flow.trip.number}</span>
        </p>
        <p className="tabular text-[12px] text-slate-500">{fmtTime(flow.trip.est_dep)}</p>
      </div>
      <SeatPicker map={flow.seatMap} selected={flow.seat} onSelect={pickSeat} onConfirm={confirmSeat} busy={busy} error={flow.error} maxHeight={260} confirmLabel="Book seat" />
    </div>
  )
}

const MENU = [
  { id: 'status', label: 'Trip status', hint: 'What changed', icon: Route, ask: 'What is my trip status?' },
  { id: 'flights', label: 'Other flights', hint: 'See open seats', icon: Plane, ask: 'Show other available flights' },
  { id: 'refund', label: 'Refund', hint: 'Cancel and get money back', icon: Undo2, ask: 'I would like a refund' },
  { id: 'voice', label: 'Talk to me', hint: 'Use your voice', icon: Mic },
]

/** Quick-action menu shown in the chat, so the traveler can tap instead of typing. */
export function MenuCard({ session }) {
  const { ask, voice, voiceAvailable, connected, busy } = session
  return (
    <div className="animate-feed-in grid grid-cols-2 gap-2">
      {MENU.map((item) => {
        const Icon = item.icon
        const disabled = busy || (item.id === 'voice' && (!voiceAvailable || connected))
        return (
          <button
            key={item.id}
            type="button"
            disabled={disabled}
            onClick={() => (item.id === 'voice' ? voice.start() : ask(item.ask))}
            className="flex flex-col items-start gap-1 rounded-2xl border border-white/10 bg-white/95 px-3 py-2.5 text-left shadow-sm transition-all hover:bg-white hover:shadow-md active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><Icon size={15} /></span>
            <span className="text-[13px] font-semibold text-slate-900">{item.label}</span>
            <span className="text-[11px] leading-tight text-slate-500">{item.id === 'voice' && !voiceAvailable ? 'Not set up on this server' : item.hint}</span>
          </button>
        )
      })}
    </div>
  )
}

export function ChatMessage({ m, session, inline, dark }) {
  if (m.kind === 'tool') return <ToolLine m={m} dark={dark} />
  if (m.kind === 'options') return <OptionsCard m={m} session={session} dark={dark} />
  if (m.kind === 'confirmation') return <ConfirmationCard m={m} />
  if (m.kind === 'booking') return <BookingCard session={session} />
  if (m.kind === 'menu') return <MenuCard session={session} />
  if (m.kind === 'refund_prompt') return <RefundPrompt m={m} session={session} />
  if (m.kind === 'seatmap') {
    return inline ? (
      <InlineSeatMap m={m} session={session} />
    ) : (
      <p className={cx('animate-feed-in px-1 text-center text-[11.5px]', dark ? 'text-slate-300' : 'text-slate-500')}>Choose your seat in the panel on the right →</p>
    )
  }
  return <Bubble m={m} dark={dark} />
}
