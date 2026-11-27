import { useState } from 'react'
import { AlertOctagon, Network, Plane, TrainFront, UserRound, Users } from 'lucide-react'
import { fmtINR, fmtMin, fmtNum, fmtTime } from '../../lib/format'
import { Badge, Card, CardHeader, Segmented, Stat, Table, cx } from '../ui'

const SSR_LABEL = { WCHR: 'Wheelchair', UMNR: 'Unaccompanied minor', MEDA: 'Medical', SRCT: 'Senior citizen' }

export function PaxTags({ tier, ssr }) {
  return (
    <span className="flex flex-wrap gap-1">
      {tier && <Badge tone={tier === 'PLATINUM' ? 'violet' : tier === 'GOLD' ? 'amber' : 'slate'}>{tier[0] + tier.slice(1).toLowerCase()}</Badge>}
      {ssr && <Badge tone={ssr === 'SRCT' ? 'slate' : 'rose'}>{SSR_LABEL[ssr] || ssr}</Badge>}
    </span>
  )
}

export default function ImpactPanel({ inc }) {
  const imp = inc.impact
  const [paxView, setPaxView] = useState('connections')
  if (!imp) return <p className="p-6 text-[13px] text-slate-500">Impact analysis is running…</p>
  const s = imp.summary

  const tripCols = [
    {
      key: 'number',
      label: 'Service',
      render: (t) => (
        <div className="flex items-center gap-2">
          {t.mode === 'FLIGHT' ? <Plane size={14} className="text-slate-400" /> : <TrainFront size={14} className="text-slate-400" />}
          <div>
            <p className="font-mono text-[12.5px] font-semibold text-slate-900">{t.number}</p>
            <p className="text-[11.5px] text-slate-500">{t.vehicle_id}</p>
          </div>
        </div>
      ),
    },
    { key: 'route', label: 'Route', render: (t) => <span className="font-medium text-slate-700">{t.origin} → {t.destination}</span> },
    { key: 'dep', label: 'Scheduled', render: (t) => <span className="tabular">{fmtTime(t.sched_dep)}</span> },
    {
      key: 'proj',
      label: 'Projected',
      render: (t) => <span className="tabular font-medium text-amber-700">{fmtTime(t.projected_dep)}</span>,
    },
    {
      key: 'delay',
      label: 'Delay',
      align: 'right',
      render: (t) => (
        <span className={cx('font-semibold', t.projected_delay_min >= 120 ? 'text-rose-600' : 'text-amber-600')}>
          +{fmtMin(t.projected_delay_min)}
        </span>
      ),
    },
    {
      key: 'type',
      label: 'Impact',
      render: (t) => <Badge tone={t.impact_type === 'DIRECT' ? 'rose' : 'violet'}>{t.impact_type === 'DIRECT' ? 'Direct' : 'Cascade'}</Badge>,
    },
    { key: 'pax', label: 'Pax', align: 'right', render: (t) => fmtNum(t.pax_affected) },
    { key: 'conn', label: 'Conn. at risk', align: 'right', render: (t) => (t.connections_at_risk ? <span className="font-medium text-rose-600">{t.connections_at_risk}</span> : '—') },
    { key: 'prio', label: 'Priority', align: 'right', render: (t) => t.priority_pax || '—' },
    {
      key: 'crew',
      label: 'Crew',
      render: (t) => (t.crew_breach ? <Badge tone="rose">Duty breach</Badge> : <span className="text-slate-400">OK</span>),
    },
  ]

  return (
    <div className="space-y-5">
      <Card className="grid grid-cols-2 gap-5 p-5 md:grid-cols-4 xl:grid-cols-7">
        <Stat label="Direct services" value={s.trips_direct} />
        <Stat label="Cascade services" value={s.trips_cascade} tone="brand" />
        <Stat label="Passengers" value={fmtNum(s.pax_affected)} tone="amber" />
        <Stat label="Missed connections" value={s.missed_connections} tone={s.missed_connections ? 'rose' : undefined} />
        <Stat label="Crew breaches" value={`${s.crew_pairings_breached} / ${s.crew_members_breached}`} hint="pairings / crew" tone={s.crew_pairings_breached ? 'rose' : undefined} />
        <Stat label="Priority pax" value={s.priority_pax} />
        <Stat label="Cost if no action" value={fmtINR(s.baseline_cost)} />
      </Card>

      <Card className="p-5">
        <p className="flex items-center gap-2 text-[13px] font-semibold text-slate-900">
          <Network size={15} className="text-violet-600" /> How the disruption cascades
        </p>
        <p className="mt-2 text-[13.5px] leading-relaxed text-slate-600">{imp.narrative}</p>
        {imp.key_risks?.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {imp.key_risks.map((r) => (
              <Badge key={r} tone="amber">{r}</Badge>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Impacted services" subtitle="Projected delays if no recovery action is taken" icon={Plane} />
        <Table columns={tripCols} rows={imp.trips} dense />
      </Card>

      <div className="grid gap-5 xl:grid-cols-5">
        <Card className="xl:col-span-2">
          <CardHeader title="Crew duty-time breaches" subtitle="Pairings that would exceed flight / duty limits" icon={AlertOctagon} />
          <div className="space-y-3 p-4">
            {imp.crew_breaches.map((b) => (
              <div key={b.pairing_id} className="rounded-lg border border-rose-100 bg-rose-50/40 p-3">
                <div className="flex items-center justify-between">
                  <p className="text-[13px] font-semibold text-slate-900">
                    Pairing {b.pairing_id} <span className="font-normal text-slate-500">· {b.trips.join(' → ')}</span>
                  </p>
                  <Badge tone="rose">{b.projected_duty_h.toFixed(1)} h projected</Badge>
                </div>
                <p className="mt-1 text-[12px] text-slate-600">
                  Replace before <span className="font-mono font-medium">{b.swap_trip}</span> at {b.swap_station}; reserve pool {b.reserve_base.replace('R:', '')}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {b.members.map((m) => (
                    <span key={m.id} className="inline-flex items-center gap-1 rounded-md bg-white px-2 py-0.5 text-[11.5px] text-slate-700 ring-1 ring-slate-200">
                      <UserRound size={11} /> {m.name} · {m.role_label} · +{m.excess_min} min over {m.limit_h} h
                    </span>
                  ))}
                </div>
              </div>
            ))}
            {!imp.crew_breaches.length && <p className="py-6 text-center text-[13px] text-slate-500">All crew remain within duty limits.</p>}
          </div>
        </Card>

        <Card className="xl:col-span-3">
          <CardHeader
            title="Affected passengers"
            icon={Users}
            actions={
              <Segmented
                size="sm"
                value={paxView}
                onChange={setPaxView}
                options={[
                  { value: 'connections', label: `Missed connections (${s.missed_connections})` },
                  { value: 'priority', label: `Priority (${s.priority_pax})` },
                ]}
              />
            }
          />
          <div className="max-h-[360px] overflow-y-auto">
            {paxView === 'connections' ? (
              <Table
                dense
                rowKey="pax_id"
                rows={imp.missed_connections}
                columns={[
                  { key: 'name', label: 'Passenger', render: (p) => <div><p className="font-medium text-slate-800">{p.name}</p><p className="font-mono text-[11px] text-slate-500">{p.pnr}</p></div> },
                  { key: 'tags', label: '', render: (p) => <PaxTags tier={p.tier} ssr={p.ssr} /> },
                  { key: 'conn', label: 'Connection', render: (p) => <span className="font-mono text-[12px]">{p.from_trip} → {p.to_trip}</span> },
                  { key: 'at', label: 'At', render: (p) => p.connection_at },
                  { key: 'avail', label: 'Available / needed', align: 'right', render: (p) => <span><span className="font-semibold text-rose-600">{p.available_min}</span> / {p.required_min} min</span> },
                ]}
                empty={<p className="py-8 text-center text-[13px] text-slate-500">No connections at risk.</p>}
              />
            ) : (
              <Table
                dense
                rowKey="pax_id"
                rows={imp.priority_passengers}
                columns={[
                  { key: 'name', label: 'Passenger', render: (p) => <div><p className="font-medium text-slate-800">{p.name}</p><p className="font-mono text-[11px] text-slate-500">{p.pnr}</p></div> },
                  { key: 'tags', label: 'Needs', render: (p) => <PaxTags tier={p.tier} ssr={p.ssr} /> },
                  { key: 'trip', label: 'Service', render: (p) => <span className="font-mono text-[12px]">{p.trip}</span> },
                  { key: 'delay', label: 'Delay', align: 'right', render: (p) => (p.delay_min ? `+${fmtMin(p.delay_min)}` : '—') },
                  { key: 'mc', label: 'Connection', render: (p) => (p.missed_connection ? <Badge tone="rose">At risk</Badge> : '—') },
                ]}
              />
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}
