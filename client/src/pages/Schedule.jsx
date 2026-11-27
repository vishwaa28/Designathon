import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Plane, Search, UserRound, Users } from 'lucide-react'
import { PaxTags } from '../components/incident/ImpactPanel'
import {
  Badge,
  Card,
  Drawer,
  KeyValue,
  PageLoader,
  Progress,
  Stat,
  Table,
  TripStatus,
  cx,
  inputBase,
} from '../components/ui'
import { fmtMin, fmtNum, fmtTime } from '../lib/format'
import { useApi } from '../lib/useApi'

function TripDrawer({ tripId, onClose }) {
  const { data } = useApi(tripId ? `/trips/${tripId}` : null)
  const [q, setQ] = useState('')
  const t = data?.trip
  const pax = (data?.passengers || []).filter((p) => !q || `${p.name} ${p.pnr}`.toLowerCase().includes(q.toLowerCase()))

  return (
    <Drawer
      open={!!tripId}
      onClose={onClose}
      title={t ? `${t.number} · ${t.origin_city} to ${t.destination_city}` : 'Loading…'}
      subtitle={t ? `${t.operator} · ${t.vehicle_type} ${t.vehicle_id}` : ''}
    >
      {!data ? (
        <PageLoader />
      ) : (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-2">
            <TripStatus status={t.status} />
            {t.delay_min > 0 && <Badge tone="amber">+{fmtMin(t.delay_min)}</Badge>}
            {t.disruption_ids.map((d) => (
              <Link key={d} to={`/incidents/${d}`} onClick={onClose}>
                <Badge tone="rose">{d}</Badge>
              </Link>
            ))}
            {t.remarks && <span className="text-[12.5px] text-slate-500">{t.remarks}</span>}
          </div>
          <KeyValue
            cols={4}
            items={[
              ['Scheduled', `${fmtTime(t.sched_dep)} – ${fmtTime(t.sched_arr)}`],
              ['Estimated', `${fmtTime(t.est_dep)} – ${fmtTime(t.est_arr)}`],
              ['Gate', t.gate],
              ['Load', `${t.booked} / ${t.capacity} (${Math.round(t.load_factor * 100)}%)`],
            ]}
          />

          <div className="grid grid-cols-2 gap-4 rounded-lg bg-slate-50 p-4 sm:grid-cols-4">
            <Stat label="Passengers" value={fmtNum(data.passenger_count)} />
            <Stat label="Connecting" value={data.summary.connections} />
            <Stat label="Priority" value={data.summary.priority} />
            <Stat label="Special needs" value={Object.values(data.summary.ssr).reduce((a, b) => a + b, 0)} />
          </div>

          <section>
            <h4 className="mb-2 text-[13px] font-semibold text-slate-900">Crew roster</h4>
            {data.duty && (
              <p className="mb-2 text-[12.5px] text-slate-500">
                Duty from {fmtTime(data.duty.start)} to projected {fmtTime(data.duty.projected_end)} ·{' '}
                <span className={cx('font-semibold', data.duty.projected_h > Math.min(...data.crew.map((c) => c.duty_limit_h)) ? 'text-rose-600' : 'text-slate-700')}>
                  {data.duty.projected_h.toFixed(1)} h
                </span>{' '}
                · pairing {data.duty.trips.join(' → ')}
              </p>
            )}
            <div className="grid gap-2 sm:grid-cols-2">
              {data.crew.map((c) => (
                <div key={c.id} className="flex items-center gap-2.5 rounded-lg border border-slate-200 px-3 py-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 text-slate-500"><UserRound size={14} /></span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12.5px] font-medium text-slate-800">{c.name}</p>
                    <p className="text-[11.5px] text-slate-500">{c.role_label} · limit {c.duty_limit_h} h</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section>
            <h4 className="mb-2 text-[13px] font-semibold text-slate-900">Aircraft rotation</h4>
            <div className="flex flex-wrap items-center gap-1.5">
              {data.rotation.map((r, i) => (
                <div key={r.id} className="flex items-center gap-1.5">
                  <div className={cx('rounded-lg border px-2.5 py-1.5 text-[11.5px]', r.id === t.id ? 'border-brand-400 bg-brand-50' : 'border-slate-200')}>
                    <p className="font-mono font-semibold text-slate-800">{r.number}</p>
                    <p className="text-slate-500">{r.origin}→{r.destination} {fmtTime(r.est_dep)}</p>
                    {r.delay_min > 0 && <p className="font-medium text-amber-600">+{fmtMin(r.delay_min)}</p>}
                  </div>
                  {i < data.rotation.length - 1 && <span className="text-slate-300">›</span>}
                </div>
              ))}
            </div>
          </section>

          <section>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h4 className="flex items-center gap-1.5 text-[13px] font-semibold text-slate-900"><Users size={14} /> Passenger manifest</h4>
              <input className={cx(inputBase, 'h-8 w-full sm:w-56')} placeholder="Search name or PNR" value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            <div className="max-h-96 overflow-y-auto rounded-lg border border-slate-200">
              <Table
                dense
                rows={pax.slice(0, 200)}
                columns={[
                  { key: 'name', label: 'Passenger', render: (p) => <span className="font-medium text-slate-800">{p.name}</span> },
                  { key: 'pnr', label: 'PNR', render: (p) => <span className="font-mono text-[12px]">{p.pnr}</span> },
                  { key: 'tags', label: 'Profile', render: (p) => <PaxTags tier={p.tier} ssr={p.ssr} /> },
                  { key: 'it', label: 'Itinerary', render: (p) => <span className="font-mono text-[11.5px] text-slate-600">{p.itinerary.join(' → ')}</span> },
                  { key: 'cabin', label: 'Cabin', render: (p) => p.cabin },
                  { key: 'status', label: 'Status', render: (p) => <Badge tone={p.status === 'CONFIRMED' ? 'slate' : 'blue'}>{p.status.replace('_', ' ').toLowerCase()}</Badge> },
                ]}
              />
            </div>
          </section>
        </div>
      )}
    </Drawer>
  )
}

export default function Schedule() {
  const [status, setStatus] = useState('')
  const [q, setQ] = useState('')
  const [disrupted, setDisrupted] = useState(false)
  const [trip, setTrip] = useState(null)
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (q) params.set('q', q)
  if (disrupted) params.set('disrupted', 'true')
  const { data } = useApi(`/trips?${params}`, { refreshOn: ['notifications.', 'simulation.', 'traveler.'], interval: 60000 })

  const columns = [
    {
      key: 'number',
      label: 'Service',
      render: (t) => (
        <div className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-100 text-slate-500">
            <Plane size={14} />
          </span>
          <div>
            <p className="font-mono text-[12.5px] font-semibold text-slate-900">{t.number}</p>
            <p className="text-[11.5px] text-slate-500">{t.vehicle_type}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'route',
      label: 'Route',
      render: (t) => (
        <div>
          <p className="font-medium text-slate-800">{t.origin} → {t.destination}</p>
          <p className="text-[11.5px] text-slate-500">{t.origin_city} – {t.destination_city}</p>
        </div>
      ),
    },
    { key: 'dep', label: 'Departure', render: (t) => <span className="tabular">{fmtTime(t.sched_dep)}</span> },
    {
      key: 'est',
      label: 'Estimated',
      render: (t) => <span className={cx('tabular', t.delay_min >= 15 ? 'font-semibold text-amber-700' : 'text-slate-600')}>{fmtTime(t.est_dep)}</span>,
    },
    { key: 'arr', label: 'Arrival', render: (t) => <span className="tabular text-slate-600">{fmtTime(t.est_arr)}</span> },
    { key: 'status', label: 'Status', render: (t) => <TripStatus status={t.status} /> },
    { key: 'delay', label: 'Delay', align: 'right', render: (t) => (t.delay_min ? <span className="text-amber-600">+{fmtMin(t.delay_min)}</span> : '—') },
    {
      key: 'load',
      label: 'Load',
      render: (t) => (
        <div className="w-24">
          <div className="flex justify-between text-[11px] text-slate-500">
            <span>{t.booked}</span>
            <span>{Math.round(t.load_factor * 100)}%</span>
          </div>
          <Progress value={t.load_factor * 100} tone={t.load_factor > 0.92 ? 'amber' : 'brand'} />
        </div>
      ),
    },
    { key: 'gate', label: 'Gate', render: (t) => <span className="text-slate-600">{t.gate}</span> },
    { key: 'inc', label: 'Incident', render: (t) => (t.disruption_ids.length ? <Badge tone="rose">{t.disruption_ids.join(', ')}</Badge> : '') },
  ]

  return (
    <div className="space-y-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-center gap-2 sm:gap-3">
        <select className={cx(inputBase, 'flex-1 sm:w-44 sm:flex-none')} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any status</option>
          {['ON_TIME', 'BOARDING', 'DELAYED', 'EN_ROUTE', 'ARRIVED', 'CANCELLED', 'DIVERTED'].map((s) => (
            <option key={s} value={s}>{s.replace('_', ' ').toLowerCase()}</option>
          ))}
        </select>
        <div className="relative w-full sm:w-auto">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input className={cx(inputBase, 'w-full pl-8 sm:w-64')} placeholder="Service, city or vehicle" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <label className="flex items-center gap-2 text-[13px] text-slate-600">
          <input type="checkbox" checked={disrupted} onChange={(e) => setDisrupted(e.target.checked)} className="rounded border-slate-300" />
          Disrupted only
        </label>
        <span className="ml-auto text-[12.5px] text-slate-500">{data ? `${data.total} services` : ''}</span>
      </div>
      <Card className="hidden md:block">
        {data ? <Table columns={columns} rows={data.items} onRowClick={(t) => setTrip(t.id)} dense /> : <PageLoader />}
      </Card>
      <Card className="divide-y divide-slate-100 md:hidden">
        {!data && <PageLoader />}
        {(data?.items || []).map((t) => (
          <button key={t.id} onClick={() => setTrip(t.id)} className="flex w-full items-center gap-3 px-4 py-3 text-left active:bg-slate-50">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-slate-100 text-slate-500">
              <Plane size={15} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[12.5px] font-semibold text-slate-900">{t.number}</span>
                <span className="truncate text-[12.5px] font-medium text-slate-700">{t.origin} → {t.destination}</span>
              </div>
              <p className="mt-0.5 text-[11.5px] text-slate-500">
                <span className={cx('tabular', t.delay_min >= 15 && 'font-semibold text-amber-700')}>{fmtTime(t.est_dep)}</span>
                {t.delay_min >= 15 && <span className="tabular text-slate-400 line-through"> {fmtTime(t.sched_dep)}</span>}
                {' '}· {t.booked}/{t.capacity} · {t.gate}
              </p>
            </div>
            <TripStatus status={t.status} />
          </button>
        ))}
      </Card>
      <TripDrawer tripId={trip} onClose={() => setTrip(null)} />
    </div>
  )
}
