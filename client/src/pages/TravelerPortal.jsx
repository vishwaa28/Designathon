import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AlertTriangle, ArrowRight, BellRing, CheckCircle2, Plane, Search, Undo2 } from 'lucide-react'
import VoiceAgent from '../components/traveler/VoiceAgent'
import { Badge, Button, Card, Field, TripStatus, cx, inputClass } from '../components/ui'
import { api } from '../lib/api'
import { fmtMin, fmtTime } from '../lib/format'

const SELF_SERVICE = new Set(['SELF_REBOOKED', 'REFUNDED'])

function Leg({ leg, actionable, attention, active, onManage }) {
  const Icon = Plane
  return (
    <div className={cx('rounded-xl border bg-white p-4', attention ? 'border-amber-300' : 'border-slate-200', active && 'ring-2 ring-brand-100')}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2 text-[12.5px] text-slate-500">
          <Icon size={15} className="shrink-0" /> <span className="truncate">{leg.operator}</span> · <span className="font-mono font-semibold text-slate-700">{leg.number}</span>
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
        <span>Gate {leg.gate}{leg.remarks && ` · ${leg.remarks}`}</span>
        {actionable && (
          <Button size="sm" variant={active ? 'primary' : 'secondary'} onClick={onManage}>
            {active ? 'Choosing options' : 'Change or refund'}
          </Button>
        )}
      </div>
    </div>
  )
}

export default function TravelerPortal() {
  const [params] = useSearchParams()
  const [pnr, setPnr] = useState(params.get('pnr') || '')
  const [name, setName] = useState(params.get('name') || '')
  const [booking, setBooking] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [managing, setManaging] = useState(null)
  const [alts, setAlts] = useState(null)
  const [confirmation, setConfirmation] = useState(null)

  const lookup = async (e) => {
    e?.preventDefault()
    if (!pnr || !name) return
    setBusy(true)
    setError(null)
    try {
      setBooking(await api.get(`/traveler/${encodeURIComponent(pnr)}?last_name=${encodeURIComponent(name)}`))
    } catch (err) {
      setBooking(null)
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    const qp = params.get('pnr')
    const qn = params.get('name')
    if (!qp || !qn) return
    api
      .get(`/traveler/${encodeURIComponent(qp)}?last_name=${encodeURIComponent(qn)}`)
      .then(setBooking)
      .catch((err) => setError(err.message))
  }, [params])

  const refreshBooking = async () => {
    const who = booking?.passenger
    if (!who) return
    setBooking(await api.get(`/traveler/${encodeURIComponent(who.pnr)}?last_name=${encodeURIComponent(who.last_name)}`))
    setManaging(null)
    setAlts(null)
  }

  const manage = async (legId) => {
    setManaging(legId)
    setAlts(null)
    setAlts(await api.get(`/traveler/${pnr}/alternatives?last_name=${encodeURIComponent(name)}&leg_trip_id=${legId}`))
  }

  const rebook = async (newId) => {
    setBusy(true)
    try {
      const res = await api.post(`/traveler/${pnr}/rebook`, { last_name: name, leg_trip_id: managing, new_trip_id: newId })
      setConfirmation(res.notification)
      setManaging(null)
      setAlts(null)
      await lookup()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const refund = async () => {
    if (!window.confirm('Cancel this journey and request a full refund?')) return
    setBusy(true)
    try {
      const res = await api.post(`/traveler/${pnr}/refund`, { last_name: name, leg_trip_id: managing })
      setConfirmation(res.notification)
      setManaging(null)
      setAlts(null)
      await lookup()
    } finally {
      setBusy(false)
    }
  }

  const p = booking?.passenger
  const latest = booking?.notifications?.[0]
  const settled = latest && SELF_SERVICE.has(latest.outcome)

  // The booking details live inside the conversation panel, above the chat messages.
  const details = p ? (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <div className="min-w-0">
          <p className="text-[12px] text-slate-500">Passenger</p>
          <p className="text-[16px] font-semibold text-slate-900">{p.name}</p>
          <p className="mt-1 text-[12px] text-slate-500">
            Updates by {p.channel.toLowerCase()} in {p.language_label}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge className="font-mono">{p.pnr}</Badge>
          <Badge>{p.cabin}</Badge>
          {p.tier && <Badge tone="violet">{p.tier.toLowerCase()} member</Badge>}
          <Badge tone="blue">{p.status.replace('_', ' ').toLowerCase()}</Badge>
        </div>
      </div>

      {confirmation && (
        <div className="flex gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-4">
          <CheckCircle2 size={20} className="mt-0.5 shrink-0 text-emerald-600" />
          <div>
            <p className="text-[14px] font-semibold text-emerald-900">{confirmation.subject}</p>
            <p className="mt-0.5 text-[13px] text-emerald-800">{confirmation.message}</p>
          </div>
        </div>
      )}

      {latest && !confirmation && (settled || booking.actionable_legs.length > 0) && (
        <div className={cx('flex gap-3 rounded-xl border px-4 py-4', settled ? 'border-slate-200 bg-white' : 'border-amber-200 bg-amber-50')}>
          {settled ? (
            <CheckCircle2 size={20} className="mt-0.5 shrink-0 text-emerald-600" />
          ) : (
            <AlertTriangle size={20} className="mt-0.5 shrink-0 text-amber-600" />
          )}
          <div className="min-w-0">
            <p className={cx('text-[14px] font-semibold', settled ? 'text-slate-900' : 'text-amber-900')}>{latest.subject}</p>
            <p className={cx('mt-0.5 break-words text-[13px] leading-relaxed', settled ? 'text-slate-600' : 'text-amber-900/90')}>{latest.message}</p>
          </div>
        </div>
      )}

      {p.legs.map((leg) => (
        <Leg
          key={leg.id}
          leg={leg}
          actionable={booking.actionable_legs.includes(leg.id)}
          attention={!settled && booking.actionable_legs.includes(leg.id)}
          active={managing === leg.id}
          onManage={() => manage(leg.id)}
        />
      ))}
      {!p.legs.length && <div className="rounded-xl border border-slate-200 bg-white p-4 text-[13px] text-slate-600">This booking has been refunded.</div>}

      {managing && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-4 py-3">
            <p className="text-[14px] font-semibold text-slate-900">Choose a new option</p>
            <p className="text-[12.5px] text-slate-500">Flights with open seats in the next 24 hours.</p>
          </div>
          <div className="divide-y divide-slate-100">
            {!alts && <p className="px-4 py-6 text-center text-[13px] text-slate-400">Searching…</p>}
            {alts?.items.map((a) => (
              <div key={a.id} className="flex items-center gap-3 px-4 py-3">
                <span className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500 sm:flex">
                  <Plane size={16} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[13.5px] font-semibold text-slate-900">
                    {fmtTime(a.est_dep)} → {fmtTime(a.est_arr)}{' '}
                    <span className="font-mono text-[12px] font-normal text-slate-500">{a.number}</span>
                  </p>
                  <p className="text-[12px] text-slate-500">
                    {a.origin} – {a.destination} · {a.seats_left} seats left
                  </p>
                </div>
                <Button size="sm" loading={busy} onClick={() => rebook(a.id)}>Select</Button>
              </div>
            ))}
            {alts && !alts.items.length && (
              <p className="px-4 py-6 text-center text-[13px] text-slate-500">No alternatives with open seats. You can request a full refund.</p>
            )}
          </div>
          <div className="flex flex-wrap justify-between gap-2 border-t border-slate-100 px-4 py-3">
            <Button variant="ghost" size="sm" onClick={() => setManaging(null)}>Keep current booking</Button>
            <Button variant="danger" size="sm" icon={Undo2} onClick={refund}>Request full refund</Button>
          </div>
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-2.5 text-[13px] font-semibold text-slate-900">
          <BellRing size={14} /> Messages sent to you
        </div>
        <div className="divide-y divide-slate-100">
          {booking.notifications.map((n) => (
            <div key={n.id} className="px-4 py-3">
              <p className="text-[12.5px] font-medium text-slate-800">{n.subject}</p>
              <p className="mt-0.5 break-words text-[12px] leading-relaxed text-slate-600">{n.message}</p>
              <p className="mt-1 text-[11px] text-slate-400">{fmtTime(n.sent_at)} · {n.channel.toLowerCase()}</p>
            </div>
          ))}
          {!booking.notifications.length && <p className="px-4 py-4 text-[12.5px] text-slate-400">No messages for this booking.</p>}
        </div>
      </div>
    </>
  ) : null

  return (
    <div className="relative min-h-full bg-canvas">
      <div className="absolute inset-x-0 top-0 h-[230px] bg-navy-900" />
      <header className="relative mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-4 sm:px-6 sm:py-5">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/10 text-white"><Plane size={18} /></span>
          <div className="min-w-0 leading-tight">
            <p className="truncate text-[14px] font-semibold text-white sm:text-[15px]">Meridian Airways</p>
            <p className="text-[12px] text-slate-400">Manage your trip</p>
          </div>
        </div>
        <a href="tel:18002004040" className="shrink-0 text-[12px] text-slate-400 hover:text-white">
          <span className="hidden sm:inline">Help desk </span>1800 200 4040
        </a>
      </header>

      <main className="relative mx-auto max-w-6xl space-y-4 px-3 pb-16 sm:space-y-5 sm:px-6">
        <Card className="p-4 sm:p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4">
            <h1 className="text-[18px] font-semibold tracking-tight text-slate-900 sm:text-[20px]">Find your booking</h1>
            <p className="text-[13px] text-slate-500">Check live status, see changes and rebook yourself without queuing at the desk.</p>
          </div>
          <form onSubmit={lookup} className="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end sm:gap-4">
            <Field label="Booking reference (PNR)">
              <input className={cx(inputClass, 'h-10 font-mono uppercase')} value={pnr} onChange={(e) => setPnr(e.target.value.toUpperCase())} placeholder="e.g. K7Q2MX" />
            </Field>
            <Field label="Last name">
              <input className={cx(inputClass, 'h-10')} value={name} onChange={(e) => setName(e.target.value)} placeholder="As on ticket" />
            </Field>
            <Button size="lg" icon={Search} loading={busy && !booking} type="submit" className="w-full sm:w-auto">Find booking</Button>
          </form>
          {error && <p className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-[13px] text-rose-700">{error}</p>}
        </Card>

        <VoiceAgent key={booking?.passenger?.pnr || 'none'} booking={booking} onBookingChanged={refreshBooking} details={details} />
      </main>
    </div>
  )
}
