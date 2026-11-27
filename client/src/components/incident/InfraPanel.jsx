import { Activity, ClipboardList, HardHat, Package, ShieldAlert, Wrench } from 'lucide-react'
import { fmtMin, fmtTime, titleCase } from '../../lib/format'
import { Badge, Card, CardHeader, KeyValue, Progress, cx } from '../ui'

const MIN = 60000

export function RepairTimeline({ window: w, dispatchAt, onSiteAt }) {
  // Milestones are spaced evenly: their gaps in time vary a lot, and spacing by time made labels collide.
  const steps = [
    { label: 'Dispatched', at: dispatchAt, dot: 'bg-slate-400' },
    { label: 'On site', at: onSiteAt, dot: 'bg-sky-500' },
    { label: 'Work starts', at: w.start, dot: 'bg-violet-500' },
    { label: 'P50 restore', at: w.p50, dot: 'bg-emerald-500' },
    { label: 'P90 restore', at: w.p90, dot: 'bg-amber-500' },
  ]
  const segments = ['bg-slate-200', 'bg-sky-200', 'bg-violet-200', 'bg-emerald-200']
  const sinceStart = (at) => Math.max(0, Math.round((new Date(at).getTime() - new Date(w.start).getTime()) / MIN))
  return (
    <div>
      <div className="relative">
        <div className="absolute inset-x-[10%] top-[5px] flex h-[3px]">
          {segments.map((c, i) => (
            <div key={i} className={cx('flex-1', c)} />
          ))}
        </div>
        <div className="relative grid grid-cols-5">
          {steps.map((s) => (
            <div key={s.label} className="flex justify-center">
              <span className={cx('h-3 w-3 rounded-full ring-4 ring-white', s.dot)} />
            </div>
          ))}
        </div>
      </div>
      <div className="mt-2.5 grid grid-cols-5 text-center">
        {steps.map((s) => (
          <div key={s.label} className="min-w-0 px-0.5">
            <p className="text-[10.5px] font-medium leading-tight text-slate-700 sm:text-[11px]">{s.label}</p>
            <p className="tabular mt-0.5 text-[10px] text-slate-400 sm:text-[10.5px]">{fmtTime(s.at)}</p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-[12px] text-slate-500">
        Restore in about <span className="font-semibold text-slate-800">{fmtMin(sinceStart(w.p50))}</span> (P50), up to{' '}
        <span className="font-semibold text-slate-800">{fmtMin(sinceStart(w.p90))}</span> (P90) after work starts.
      </p>
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
