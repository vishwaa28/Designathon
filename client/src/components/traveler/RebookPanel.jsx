import { AlertTriangle, ArrowLeft, ArrowRight, BellRing, Check, CheckCircle2, Luggage, Plane, Undo2 } from 'lucide-react'
import { Badge, Button, Card, TripStatus, cx } from '../ui'
import { FlightOption } from './ChatParts'
import SeatPicker from './SeatPicker'
import { fmtMin, fmtTime } from '../../lib/format'

const SELF_SERVICE = new Set(['SELF_REBOOKED', 'REFUNDED'])

function Leg({ leg, actionable, attention, active, onManage }) {
  return (
    <div className={cx('rounded-xl border bg-white p-4', attention ? 'border-amber-300' : 'border-slate-200', active && 'ring-2 ring-brand-100')}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2 text-[12.5px] text-slate-500">
          <Plane size={15} className="shrink-0" /> <span className="truncate">{leg.operator}</span> · <span className="font-mono font-semibold text-slate-700">{leg.number}</span>
        </div>
        <TripStatus status={leg.status} />
      </div>
      <div className="mt-3 grid grid-cols-[1fr_auto_1fr] items-center gap-2 sm:gap-4">
        <div className="min-w-0">
          <p className="text-[20px] font-semibold tracking-tight text-slate-900 sm:text-[22px]">{leg.origin}</p>
          <p className="text-[12px] text-slate-500">{leg.origin_city}</p>
          <p className="tabular mt-1 text-[14px] font-semibold text-slate-800">
            {fmtTime(leg.est_dep)}
            {leg.delay_min > 0 && <span className="ml-2 text-[12px] font-normal text-slate-400 line-through">{fmtTime(leg.sched_dep)}</span>}
          </p>
        </div>
        <div className="flex flex-col items-center text-slate-300">
          <ArrowRight size={18} />
          {leg.delay_min > 0 && <span className="mt-1 text-[11px] font-medium text-amber-600">+{fmtMin(leg.delay_min)}</span>}
        </div>
        <div className="min-w-0 text-right">
          <p className="text-[20px] font-semibold tracking-tight text-slate-900 sm:text-[22px]">{leg.destination}</p>
          <p className="text-[12px] text-slate-500">{leg.destination_city}</p>
          <p className="tabular mt-1 text-[14px] font-semibold text-slate-800">{fmtTime(leg.est_arr)}</p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3 text-[12px] text-slate-500">
        <span>
          Gate {leg.gate}{leg.seat ? ` · Seat ${leg.seat}` : ''}{leg.remarks && ` · ${leg.remarks}`}
        </span>
        {actionable && (
          <Button size="sm" variant={active ? 'primary' : 'secondary'} onClick={onManage}>
            {active ? 'Choosing options' : 'Change or refund'}
          </Button>
        )}
      </div>
    </div>
  )
}

function Stepper({ step }) {
  const steps = [
    ['options', 'Choose flight'],
    ['seat', 'Pick seat'],
    ['done', 'Confirmed'],
  ]
  const current = steps.findIndex(([id]) => id === step)
  return (
    <ol className="flex items-center gap-2 px-5 py-3.5 text-[12px]">
      {steps.map(([id, label], i) => (
        <li key={id} className="flex flex-1 items-center gap-2 last:flex-none">
          <span
            className={cx(
              'flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold',
              i < current ? 'bg-emerald-500 text-white' : i === current ? 'bg-brand-600 text-white' : 'bg-slate-200 text-slate-500',
            )}
          >
            {i < current ? <Check size={13} /> : i + 1}
          </span>
          <span className={cx('whitespace-nowrap font-medium', i === current ? 'text-slate-900' : 'text-slate-500')}>{label}</span>
          {i < steps.length - 1 && <span className={cx('h-px flex-1', i < current ? 'bg-emerald-300' : 'bg-slate-200')} />}
        </li>
      ))}
    </ol>
  )
}

function OptionsStep({ session }) {
  const { flow, busy, chooseTrip, requestRefund, closeFlow } = session
  const items = flow.alts?.items
  const leg = flow.alts?.leg
  return (
    <>
      <div className="border-t border-slate-100 px-5 py-3.5">
        <p className="text-[14px] font-semibold text-slate-900">Other flights with open seats</p>
        <p className="text-[12.5px] text-slate-500">
          {leg ? `${leg.origin_city} to ${leg.destination_city}, next 24 hours. ` : ''}Select a flight to choose your seat.
        </p>
      </div>
      <div className="space-y-2 px-4 pb-4 sm:px-5">
        {!items && <p className="py-6 text-center text-[13px] text-slate-400">Searching…</p>}
        {items?.map((t) => (
          <FlightOption key={t.id} trip={t} disabled={busy} onSelect={(trip) => chooseTrip(trip, flow.legId)} />
        ))}
        {items && !items.length && <p className="py-6 text-center text-[13px] text-slate-500">No alternatives with open seats. You can request a full refund.</p>}
      </div>
      <div className="flex flex-wrap justify-between gap-2 border-t border-slate-100 px-4 py-3 sm:px-5">
        <Button variant="ghost" size="sm" onClick={closeFlow}>Keep current booking</Button>
        <Button variant="danger" size="sm" icon={Undo2} loading={busy} onClick={() => { if (window.confirm('Cancel this leg and request a full refund?')) requestRefund(flow.legId) }}>
          Request full refund
        </Button>
      </div>
    </>
  )
}

function SeatStep({ session }) {
  const { flow, busy, pickSeat, confirmSeat, showOptions } = session
  const t = flow.trip
  return (
    <>
      <div className="flex items-center gap-3 border-t border-slate-100 px-5 py-3.5">
        <button type="button" onClick={() => showOptions(flow.legId)} className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100" aria-label="Back to flights">
          <ArrowLeft size={16} />
        </button>
        <div className="min-w-0">
          <p className="text-[14px] font-semibold text-slate-900">
            Seat arrangement · <span className="font-mono">{t.number}</span>
          </p>
          <p className="tabular text-[12.5px] text-slate-500">
            {t.origin} → {t.destination} · {fmtTime(t.est_dep)} – {fmtTime(t.est_arr)} · {t.vehicle_type}
          </p>
        </div>
      </div>
      <div className="px-4 pb-5 sm:px-5">
        <SeatPicker map={flow.seatMap} selected={flow.seat} onSelect={pickSeat} onConfirm={confirmSeat} busy={busy} error={flow.error} confirmLabel="Book this seat" maxHeight={420} />
      </div>
    </>
  )
}

function DoneStep({ session }) {
  const { flow, closeFlow } = session
  const r = flow.record
  const refunded = r?.outcome === 'REFUNDED'
  return (
    <div className="border-t border-slate-100 px-5 py-6">
      <div className="flex flex-col items-center text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
          <CheckCircle2 size={30} />
        </span>
        <p className="mt-3 text-[17px] font-semibold text-slate-900">{refunded ? 'Refund started' : 'You are all set'}</p>
        <p className="mt-1 max-w-md text-[13px] leading-relaxed text-slate-600">{r?.message}</p>
      </div>
      {!refunded && r?.seat && (
        <div className="mx-auto mt-5 max-w-sm overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center justify-between bg-navy-900 px-4 py-2.5 text-white">
            <span className="flex items-center gap-2 text-[12px] font-medium"><Luggage size={14} /> Boarding details</span>
            <span className="font-mono text-[12px]">{r.new_trip}</span>
          </div>
          <div className="grid grid-cols-3 divide-x divide-slate-100 px-2 py-4 text-center">
            <div><p className="text-[10.5px] uppercase tracking-wide text-slate-400">Flight</p><p className="mt-0.5 font-mono text-[15px] font-semibold text-slate-900">{r.new_trip}</p></div>
            <div><p className="text-[10.5px] uppercase tracking-wide text-slate-400">Seat</p><p className="mt-0.5 text-[15px] font-semibold text-brand-600">{r.seat}</p></div>
            <div><p className="text-[10.5px] uppercase tracking-wide text-slate-400">Departs</p><p className="tabular mt-0.5 text-[15px] font-semibold text-slate-900">{flow.trip ? fmtTime(flow.trip.est_dep) : '—'}</p></div>
          </div>
        </div>
      )}
      <div className="mt-5 flex justify-center">
        <Button variant="secondary" onClick={closeFlow}>Back to my trip</Button>
      </div>
    </div>
  )
}

function TripOverview({ session }) {
  const { booking, flow, showOptions } = session
  const p = booking.passenger
  const latest = booking.notifications?.[0]
  const settled = latest && SELF_SERVICE.has(latest.outcome)
  return (
    <div className="space-y-4">
      <Card className="p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[12px] text-slate-500">Passenger</p>
            <p className="text-[16px] font-semibold text-slate-900">{p.name}</p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <Badge className="font-mono">{p.pnr}</Badge>
            <Badge>{p.cabin}</Badge>
            {p.tier && <Badge tone="violet">{p.tier.toLowerCase()} member</Badge>}
            <Badge tone="blue">{p.status.replace('_', ' ').toLowerCase()}</Badge>
          </div>
        </div>
      </Card>

      {latest && (settled || booking.actionable_legs.length > 0) && (
        <div className={cx('flex gap-3 rounded-xl border px-4 py-4 sm:px-5', settled ? 'border-slate-200 bg-white' : 'border-amber-200 bg-amber-50')}>
          {settled ? <CheckCircle2 size={20} className="mt-0.5 shrink-0 text-emerald-600" /> : <AlertTriangle size={20} className="mt-0.5 shrink-0 text-amber-600" />}
          <div>
            <p className={cx('text-[14px] font-semibold', settled ? 'text-slate-900' : 'text-amber-900')}>{latest.subject}</p>
            <p className={cx('mt-0.5 text-[13px] leading-relaxed', settled ? 'text-slate-600' : 'text-amber-900/90')}>{latest.message}</p>
          </div>
        </div>
      )}

      {p.legs.map((leg) => (
        <Leg
          key={leg.id}
          leg={leg}
          actionable={booking.actionable_legs.includes(leg.id)}
          attention={!settled && booking.actionable_legs.includes(leg.id)}
          active={flow?.legId === leg.id}
          onManage={() => showOptions(leg.id)}
        />
      ))}
      {!p.legs.length && <Card className="p-5 text-[13px] text-slate-600">This booking has been refunded.</Card>}

      <Card>
        <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-3 text-[13px] font-semibold text-slate-900">
          <BellRing size={14} /> Messages
        </div>
        <div className="divide-y divide-slate-100">
          {booking.notifications.map((n) => (
            <div key={n.id} className="px-5 py-3">
              <p className="text-[12.5px] font-medium text-slate-800">{n.subject}</p>
              <p className="mt-0.5 text-[12px] leading-relaxed text-slate-600">{n.message}</p>
              <p className="mt-1 text-[11px] text-slate-400">{fmtTime(n.sent_at)} · {n.channel.toLowerCase()}</p>
            </div>
          ))}
          {!booking.notifications.length && <p className="px-5 py-5 text-[12.5px] text-slate-400">No messages for this booking.</p>}
        </div>
      </Card>
    </div>
  )
}

/** Right-hand side of the desktop layout: the trip by default, the rebook flow while the traveler is changing it. */
export default function RebookPanel({ session }) {
  const { booking, flow } = session
  if (!booking) {
    return (
      <Card className="flex min-h-[320px] flex-col items-center justify-center px-6 py-14 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-50 text-brand-600"><Plane size={22} /></span>
        <p className="mt-3 text-[15px] font-semibold text-slate-900">Your trip will appear here</p>
        <p className="mt-1 max-w-sm text-[13px] leading-relaxed text-slate-500">
          Find your booking, then ask the assistant about your journey. If a flight changed you can pick another one and choose your seat right here.
        </p>
      </Card>
    )
  }
  if (!flow || !flow.step) return <TripOverview session={session} />
  return (
    <Card className="overflow-hidden">
      <Stepper step={flow.step} />
      {flow.step === 'options' && <OptionsStep session={session} />}
      {flow.step === 'seat' && <SeatStep session={session} />}
      {flow.step === 'done' && <DoneStep session={session} />}
    </Card>
  )
}
