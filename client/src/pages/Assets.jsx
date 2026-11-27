import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, ClipboardList, HardHat, Wrench } from 'lucide-react'
import { RepairTimeline } from '../components/incident/InfraPanel'
import { Badge, Button, Card, CardHeader, Empty, PageLoader, Progress, Segmented, Table, cx } from '../components/ui'
import { api } from '../lib/api'
import { fmtDateTime, fmtTime, titleCase } from '../lib/format'
import { useApi } from '../lib/useApi'

const WO_FLOW = ['DISPATCHED', 'ON_SITE', 'IN_PROGRESS', 'COMPLETED']
const ASSET_STATUS_TONE = { OPERATIONAL: 'emerald', DEGRADED: 'amber', MAINTENANCE: 'blue', OUT_OF_SERVICE: 'rose' }

function WorkOrderCard({ wo, onAdvance }) {
  const idx = WO_FLOW.indexOf(wo.status)
  const next = WO_FLOW[idx + 1]
  return (
    <section>
      <div className="flex flex-wrap items-start justify-between gap-3 px-4 pb-1 pt-4 sm:px-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[12.5px] font-semibold text-slate-700">{wo.id}</span>
            <Badge tone={wo.priority === 'P1' ? 'rose' : 'amber'}>{wo.priority}</Badge>
            <span className="text-[11.5px] text-slate-400">rev {wo.revision}</span>
            <Link to={`/incidents/${wo.incident_id}`} className="text-[12px] font-medium text-brand-600 hover:underline">{wo.incident_id}</Link>
          </div>
          <p className="mt-0.5 text-[14px] font-semibold text-slate-900">{wo.title}</p>
          <p className="text-[12px] text-slate-500">{wo.asset_name} · {wo.location} · {wo.team.name}</p>
        </div>
        {next ? (
          <Button size="sm" variant={next === 'COMPLETED' ? 'primary' : 'secondary'} onClick={() => onAdvance(wo.id, next)}>
            Mark {titleCase(next).toLowerCase()}
          </Button>
        ) : (
          <Badge tone="emerald" dot>Completed {fmtTime(wo.completed_at)}</Badge>
        )}
      </div>
      <div className="grid gap-5 px-4 pb-5 pt-3 sm:px-5 lg:grid-cols-[1fr_220px]">
        <div className="min-w-0">
          <p className="text-[12.5px] leading-relaxed text-slate-600">{wo.description}</p>
          <div className="mt-4">
            <RepairTimeline window={wo.repair_window} dispatchAt={wo.created_at} onSiteAt={wo.on_site_at} />
          </div>
        </div>
        <ol className="h-fit space-y-2.5 rounded-lg bg-slate-50 p-3.5">
          {WO_FLOW.map((s, i) => (
            <li key={s} className="flex items-center gap-2.5 text-[12.5px]">
              <span className={cx('flex h-5 w-5 items-center justify-center rounded-full text-[10.5px] font-semibold',
                i <= idx ? 'bg-emerald-500 text-white' : 'bg-slate-100 text-slate-400')}>{i + 1}</span>
              <span className={i <= idx ? 'font-medium text-slate-800' : 'text-slate-400'}>{titleCase(s)}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}

export default function Assets() {
  const { data: wos, reload: reloadWos } = useApi('/work-orders', { refreshOn: ['work_order.', 'simulation.'] })
  const { data: assets, reload: reloadAssets } = useApi('/assets', { refreshOn: ['work_order.', 'incident.created', 'simulation.'], interval: 15000 })
  const [category, setCategory] = useState('infra')

  const advance = async (id, status) => {
    await api.patch(`/work-orders/${id}`, { status })
    reloadWos()
    reloadAssets()
  }

  if (!wos || !assets) return <PageLoader />
  const items = assets.items.filter((a) =>
    category === 'infra' ? a.category !== 'Fleet' : a.category === 'Fleet',
  )
  const down = assets.items.filter((a) => a.status !== 'OPERATIONAL').length
  const openCount = wos.items.filter((w) => w.status !== 'COMPLETED').length

  return (
    <div className="space-y-4 p-4 sm:space-y-5 sm:p-6">
      <div className="grid grid-cols-1 items-start gap-4 sm:gap-5 xl:grid-cols-3">
        <Card className="min-w-0 xl:col-span-2">
          <CardHeader
            title="Work orders"
            subtitle="Raised by the infrastructure triage agent"
            icon={ClipboardList}
            actions={<Badge tone={openCount ? 'amber' : 'slate'}>{openCount} open</Badge>}
          />
          {wos.items.length ? (
            <div className="divide-y divide-slate-100">
              {wos.items.map((wo) => (
                <WorkOrderCard key={wo.id} wo={wo} onAdvance={advance} />
              ))}
            </div>
          ) : (
            <Empty icon={Wrench} title="No work orders" text="The infrastructure triage agent raises work orders automatically when a fault is detected." />
          )}
        </Card>
        <Card className="min-w-0">
          <CardHeader title="Maintenance teams" subtitle={`${down} asset${down === 1 ? '' : 's'} out of service`} icon={HardHat} />
          <div className="divide-y divide-slate-100">
            {assets.teams.map((t) => (
              <div key={t.id} className="flex items-start justify-between gap-3 px-4 py-3 sm:px-5">
                <div className="min-w-0">
                  <p className="text-[12.5px] font-medium leading-snug text-slate-800">{t.name}</p>
                  <p className="mt-0.5 text-[11.5px] text-slate-500">{titleCase(t.skill)} · {t.members} technicians · ETA {t.eta_min} min</p>
                </div>
                <Badge tone={t.status === 'AVAILABLE' ? 'emerald' : 'blue'} dot className="mt-0.5 shrink-0">{titleCase(t.status)}</Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>
      <Card>
        <CardHeader
          title="Asset health"
          subtitle="Live telemetry from the asset-health stream"
          icon={Activity}
          actions={
            <Segmented
              size="sm"
              value={category}
              onChange={setCategory}
              options={[
                { value: 'infra', label: 'Infrastructure' },
                { value: 'fleet', label: 'Aircraft' },
              ]}
            />
          }
        />
        <Table
          dense
          rows={items}
          columns={[
            { key: 'name', label: 'Asset', render: (a) => <div><p className="font-medium text-slate-800">{a.name}</p><p className="font-mono text-[11px] text-slate-500">{a.id}</p></div> },
            { key: 'cat', label: 'Category', render: (a) => <span className="text-slate-600">{a.category}</span> },
            { key: 'loc', label: 'Location', render: (a) => a.location },
            { key: 'crit', label: 'Criticality', render: (a) => <Badge tone={a.criticality === 'CRITICAL' ? 'rose' : a.criticality === 'HIGH' ? 'orange' : 'slate'}>{titleCase(a.criticality)}</Badge> },
            { key: 'status', label: 'Status', render: (a) => <Badge tone={ASSET_STATUS_TONE[a.status]} dot>{titleCase(a.status)}</Badge> },
            {
              key: 'health',
              label: 'Health',
              render: (a) => (
                <div className="flex w-32 items-center gap-2">
                  <Progress value={a.health} tone={a.health >= 80 ? 'emerald' : a.health >= 50 ? 'amber' : 'rose'} />
                  <span className="tabular w-8 text-[12px] text-slate-600">{a.health}%</span>
                </div>
              ),
            },
            {
              key: 'metrics',
              label: 'Telemetry',
              render: (a) => (
                <div className="flex flex-wrap gap-1">
                  {Object.entries(a.metrics).map(([k, v]) => {
                    const b = a.baseline[k]
                    const off = b && Math.abs(v - b) > Math.abs(b) * 0.05
                    return (
                      <span key={k} className={cx('rounded px-1.5 py-0.5 text-[11px]', off ? 'bg-rose-50 text-rose-700' : 'bg-slate-100 text-slate-600')}>
                        {titleCase(k)} {v}
                      </span>
                    )
                  })}
                </div>
              ),
            },
            { key: 'insp', label: 'Last inspection', render: (a) => <span className="text-[12px] text-slate-500">{fmtDateTime(a.last_inspection)}</span> },
          ]}
        />
      </Card>
    </div>
  )
}
