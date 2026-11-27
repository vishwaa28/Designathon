import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import {
  AlertTriangle,
  ArrowRight,
  BellRing,
  CalendarClock,
  Clock3,
  Plane,
  ShieldCheck,
  TrainFront,
  Users,
  Wrench,
  Zap,
} from 'lucide-react'
import LiveFeed from '../components/LiveFeed'
import ScenarioLauncher from '../components/ScenarioLauncher'
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Empty,
  IncidentStatus,
  Kpi,
  PageLoader,
  SeverityBadge,
  cx,
} from '../components/ui'
import { fmtNum, relTime } from '../lib/format'
import { useApi } from '../lib/useApi'

const HUB_STATUS = {
  NORMAL: { tone: 'emerald', label: 'Normal' },
  STRAINED: { tone: 'amber', label: 'Strained' },
  DISRUPTED: { tone: 'rose', label: 'Disrupted' },
}

function HubCard({ hub }) {
  const s = HUB_STATUS[hub.status]
  const w = hub.weather
  return (
    <div
      className={cx(
        'rounded-lg border p-3.5 transition-colors',
        hub.status === 'DISRUPTED' ? 'border-rose-200 bg-rose-50/40' : 'border-slate-200 bg-white',
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          {hub.mode === 'FLIGHT' ? <Plane size={14} className="text-slate-400" /> : <TrainFront size={14} className="text-slate-400" />}
          <span className="font-mono text-[14px] font-semibold text-slate-900">{hub.code}</span>
        </div>
        <Badge tone={s.tone} dot>{s.label}</Badge>
      </div>
      <p className="mt-1 truncate text-[12px] text-slate-500">{hub.city}</p>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div>
          <p className="tabular text-[15px] font-semibold text-slate-900">{hub.movements_3h}</p>
          <p className="text-[10.5px] text-slate-500">Next 3h</p>
        </div>
        <div>
          <p className={cx('tabular text-[15px] font-semibold', hub.delayed ? 'text-amber-600' : 'text-slate-900')}>{hub.delayed}</p>
          <p className="text-[10.5px] text-slate-500">Delayed</p>
        </div>
        <div>
          <p className={cx('tabular text-[15px] font-semibold', hub.cancelled ? 'text-rose-600' : 'text-slate-900')}>{hub.cancelled}</p>
          <p className="text-[10.5px] text-slate-500">Cancelled</p>
        </div>
      </div>
      {w && (
        <p className={cx('mt-3 truncate border-t border-slate-100 pt-2 text-[11.5px]', w.severe ? 'font-medium text-rose-600' : 'text-slate-500')}>
          {w.condition} · {w.temperature_c != null ? `${Math.round(w.temperature_c)}°C` : '—'} · gusts {w.gust_kmh != null ? Math.round(w.gust_kmh) : '—'} km/h
        </p>
      )}
    </div>
  )
}

export default function Overview() {
  const { data } = useApi('/dashboard', {
    refreshOn: ['incident.', 'notifications.', 'work_order.', 'simulation.', 'traveler.'],
    interval: 30000,
  })
  const [launcher, setLauncher] = useState(false)
  const navigate = useNavigate()
  if (!data) return <PageLoader />
  const k = data.kpis

  return (
    <div className="space-y-5 p-6">
      {k.awaiting_approval > 0 && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
          <ShieldCheck size={18} className="text-amber-600" />
          <p className="flex-1 text-[13px] text-amber-900">
            <span className="font-semibold">{k.awaiting_approval} recovery plan{k.awaiting_approval > 1 ? 's' : ''}</span> waiting
            for controller approval.
          </p>
          <Button size="sm" variant="secondary" onClick={() => navigate('/incidents')}>Review</Button>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        <Kpi label="Services today" value={k.trips_total} sub={`${k.flights} flights · ${k.trains} trains`} icon={CalendarClock} />
        <Kpi
          label="On-time performance"
          value={`${k.on_time_pct}%`}
          sub={`${k.delayed} delayed · ${k.cancelled} cancelled`}
          icon={Clock3}
          tone={k.on_time_pct >= 90 ? 'emerald' : k.on_time_pct >= 80 ? 'amber' : 'rose'}
        />
        <Kpi
          label="Active incidents"
          value={k.active_incidents}
          sub={k.awaiting_approval ? `${k.awaiting_approval} awaiting approval` : 'None awaiting approval'}
          icon={AlertTriangle}
          tone={k.active_incidents ? 'rose' : 'slate'}
          emphasis={k.awaiting_approval > 0}
        />
        <Kpi label="Passengers affected" value={fmtNum(k.pax_affected)} sub={`of ${fmtNum(k.passengers)} booked today`} icon={Users} tone="amber" />
        <Kpi label="Open work orders" value={k.open_work_orders} sub="Field teams dispatched" icon={Wrench} tone="violet" />
        <Kpi label="Traveler messages" value={fmtNum(k.notifications_sent)} sub="Proactive notifications sent" icon={BellRing} tone="emerald" />
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Network status" subtitle="Hub movements in the next 3 hours with current weather" icon={Plane} />
          <div className="grid grid-cols-2 gap-3 p-4 md:grid-cols-4">
            {data.hubs.map((h) => (
              <HubCard key={h.code} hub={h} />
            ))}
          </div>
        </Card>
        <LiveFeed className="h-[420px]" />
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Departures by hour" subtitle="Scheduled services with delays and cancellations" icon={CalendarClock} />
          <div className="h-[280px] px-3 pb-3 pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.hourly} barGap={2}>
                <CartesianGrid vertical={false} stroke="#eef2f7" />
                <XAxis dataKey="hour" tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} interval={1} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#64748b' }} axisLine={false} tickLine={false} width={28} />
                <Tooltip
                  cursor={{ fill: '#f1f5f9' }}
                  contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0', fontSize: 12, boxShadow: '0 4px 12px rgba(15,23,42,0.08)' }}
                />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="flights" name="Flights" stackId="s" fill="#2f5bea" radius={[0, 0, 0, 0]} />
                <Bar dataKey="trains" name="Trains" stackId="s" fill="#8eabf7" radius={[3, 3, 0, 0]} />
                <Bar dataKey="delayed" name="Delayed" fill="#f59e0b" radius={[3, 3, 0, 0]} />
                <Bar dataKey="cancelled" name="Cancelled" fill="#e11d48" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="flex flex-col">
          <CardHeader
            title="Recent incidents"
            icon={AlertTriangle}
            actions={
              <Link to="/incidents" className="flex items-center gap-1 text-[12.5px] font-medium text-brand-600 hover:text-brand-700">
                View all <ArrowRight size={13} />
              </Link>
            }
          />
          <div className="flex-1 divide-y divide-slate-100">
            {data.recent_incidents.map((i) => (
              <Link key={i.id} to={`/incidents/${i.id}`} className="block px-5 py-3 hover:bg-slate-50">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[11.5px] text-slate-500">{i.id}</span>
                  <IncidentStatus status={i.status} />
                </div>
                <p className="mt-1 truncate text-[13px] font-medium text-slate-800">{i.title}</p>
                <div className="mt-1 flex items-center gap-2 text-[11.5px] text-slate-500">
                  <SeverityBadge severity={i.severity} />
                  {i.pax_affected != null && <span>{fmtNum(i.pax_affected)} pax</span>}
                  <span>· {relTime(i.created_at)}</span>
                </div>
              </Link>
            ))}
            {!data.recent_incidents.length && (
              <Empty
                icon={ShieldCheck}
                title="No disruptions detected"
                text="Inject a simulated weather or asset-health event to watch detection, planning and approval end to end."
                action={<Button icon={Zap} onClick={() => setLauncher(true)}>Inject event</Button>}
              />
            )}
          </div>
        </Card>
      </div>
      <ScenarioLauncher open={launcher} onClose={() => setLauncher(false)} />
    </div>
  )
}
