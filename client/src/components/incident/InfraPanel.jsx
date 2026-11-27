import { Activity, ClipboardList, HardHat, Package, ShieldAlert, Wrench } from 'lucide-react'
import { fmtTime, titleCase } from '../../lib/format'
import { Badge, Card, CardHeader, KeyValue, Progress, cx } from '../ui'

export function RepairTimeline({ window: w, dispatchAt, onSiteAt }) {
  const points = [
    { label: 'Dispatched', at: dispatchAt, color: 'bg-slate-400' },
    { label: 'On site', at: onSiteAt, color: 'bg-sky-500' },
    { label: 'Work starts', at: w.start, color: 'bg-violet-500' },
    { label: 'P50 restore', at: w.p50, color: 'bg-emerald-500' },
    { label: 'P90 restore', at: w.p90, color: 'bg-amber-500' },
  ]
  const t0 = new Date(dispatchAt).getTime()
  const t1 = new Date(w.p90).getTime()
  const span = Math.max(1, t1 - t0)
  const pos = (at) => ((new Date(at).getTime() - t0) / span) * 100
  return (
    <div className="px-1 pb-1 pt-7">
      <div className="relative h-2 rounded-full bg-slate-100">
        <div className="absolute h-2 rounded-full bg-emerald-200" style={{ left: `${pos(w.start)}%`, width: `${pos(w.p50) - pos(w.start)}%` }} />
        <div className="absolute h-2 rounded-r-full bg-amber-200" style={{ left: `${pos(w.p50)}%`, width: `${100 - pos(w.p50)}%` }} />
        {points.map((p, i) => (
          <div key={p.label} className="absolute -translate-x-1/2" style={{ left: `${pos(p.at)}%` }}>
            <span className={cx('absolute -top-[3px] left-1/2 h-3.5 w-3.5 -translate-x-1/2 rounded-full ring-2 ring-white', p.color)} />
            <div className={cx('absolute whitespace-nowrap text-center', i % 2 ? 'top-4' : '-top-7', '-translate-x-1/2 left-1/2')}>
              <p className="text-[11px] font-medium text-slate-700">{p.label}</p>
              <p className="tabular text-[10.5px] text-slate-400">{fmtTime(p.at)}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="h-8" />
    </div>
  )
}

export default function InfraPanel({ inc }) {
  const infra = inc.infra
  const wo = inc.work_order
  if (!infra || !wo) return <p className="p-6 text-[13px] text-slate-500">Infrastructure triage is running…</p>
  const asset = infra.asset

  return (
    <div className="grid gap-5 xl:grid-cols-3">
      <div className="space-y-5 xl:col-span-2">
        <Card>
          <CardHeader
            title={`${wo.id} · ${wo.title}`}
            subtitle={`Revision ${wo.revision} · created ${fmtTime(wo.created_at)} · updated ${fmtTime(wo.updated_at)}`}
            icon={ClipboardList}
            actions={
              <>
                <Badge tone={wo.priority === 'P1' ? 'rose' : 'amber'}>{wo.priority}</Badge>
                <Badge tone="blue" dot>{titleCase(wo.status)}</Badge>
              </>
            }
          />
          <div className="space-y-5 p-5">
            <p className="text-[13.5px] leading-relaxed text-slate-700">{wo.description}</p>
            <KeyValue
              cols={4}
              items={[
                ['Assigned team', wo.team.name],
                ['Crew size', `${wo.team.members} technicians`],
                ['Travel ETA', `${wo.team.eta_min} min from ${wo.team.base}`],
                ['Asset', `${wo.asset_name} (${wo.location})`],
              ]}
            />
            <div>
              <p className="mb-1 text-[12px] font-semibold text-slate-700">Repair window estimate</p>
              <RepairTimeline window={wo.repair_window} dispatchAt={infra.dispatch_at} onSiteAt={wo.on_site_at} />
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Probable root causes" subtitle="Ranked by the fault model for this asset class" icon={Wrench} />
          <div className="divide-y divide-slate-100">
            {wo.probable_causes.map((c, i) => (
              <div key={c.cause} className="flex items-center gap-4 px-5 py-3">
                <span className={cx('flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold', i === 0 ? 'bg-orange-100 text-orange-700' : 'bg-slate-100 text-slate-500')}>
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-medium text-slate-800">{c.cause}</p>
                  <p className="text-[12px] text-slate-500">Repair {c.repair_min[0]}–{c.repair_min[1]} min</p>
                </div>
                <div className="w-40">
                  <div className="flex justify-between text-[11.5px]">
                    <span className="text-slate-500">Likelihood</span>
                    <span className="tabular font-semibold text-slate-800">{Math.round(c.probability * 100)}%</span>
                  </div>
                  <Progress value={c.probability * 100} tone={i === 0 ? 'amber' : 'slate'} className="mt-1" />
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="space-y-5">
        <Card>
          <CardHeader title="Asset telemetry" subtitle={`${asset.name} · health ${asset.health}%`} icon={Activity} />
          <div className="divide-y divide-slate-100">
            {Object.entries(asset.metrics).map(([k, v]) => {
              const base = asset.baseline?.[k]
              const changed = base != null && Math.abs(v - base) > Math.abs(base) * 0.05
              return (
                <div key={k} className="flex items-center justify-between px-5 py-2.5 text-[12.5px]">
                  <span className="text-slate-600">{titleCase(k)}</span>
                  <span className="tabular">
                    <span className={cx('font-semibold', changed ? 'text-rose-600' : 'text-slate-800')}>{v}</span>
                    {base != null && <span className="text-slate-400"> / {base} nominal</span>}
                  </span>
                </div>
              )
            })}
          </div>
        </Card>

        <Card>
          <CardHeader title="First checks" icon={HardHat} />
          <ol className="space-y-2 p-5">
            {wo.first_checks.map((c, i) => (
              <li key={c} className="flex gap-2.5 text-[12.5px] text-slate-700">
                <span className="tabular font-semibold text-slate-400">{i + 1}.</span> {c}
              </li>
            ))}
          </ol>
        </Card>

        <Card>
          <CardHeader title="Parts" icon={Package} />
          <div className="divide-y divide-slate-100">
            {wo.parts.map((p) => (
              <div key={p.part} className="flex items-center justify-between gap-3 px-5 py-2.5 text-[12.5px]">
                <div>
                  <p className="font-medium text-slate-800">{p.part}</p>
                  <p className="text-[11.5px] text-slate-500">{p.source}</p>
                </div>
                <Badge tone={p.available ? 'emerald' : 'amber'}>{p.available ? 'In stock' : 'Lead time'}</Badge>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="Safety precautions" icon={ShieldAlert} />
          <ul className="space-y-2 p-5">
            {wo.safety_notes.map((s) => (
              <li key={s} className="flex gap-2 text-[12.5px] text-slate-700">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400" /> {s}
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}
