import { CheckCircle2, Eye, Gauge, Radar, Route, XCircle } from 'lucide-react'
import { fmtINR, fmtMin, fmtNum, fmtTime, titleCase } from '../../lib/format'
import { providerLabel } from '../../lib/agents'
import { Badge, Card, CardHeader, KeyValue, Progress, Stat, cx } from '../ui'

export default function DetectionPanel({ inc, onOpenTab }) {
  const d = inc.detection
  const ev = inc.event
  const imp = inc.impact?.summary
  const rec = inc.options?.find((o) => o.recommended)

  return (
    <div className="grid gap-5 xl:grid-cols-3">
      <div className="space-y-5 xl:col-span-2">
        <Card>
          <CardHeader
            title="Situation report"
            subtitle={`${ev.source} · received ${fmtTime(ev.received_at)}`}
            icon={Radar}
            actions={d && <Badge tone="slate">{providerLabel(d.narrative_source)}</Badge>}
          />
          <div className="space-y-4 p-5">
            {d ? (
              <>
                <div>
                  <p className="text-[15px] font-semibold text-slate-900">{d.headline}</p>
                  <p className="mt-1.5 text-[13.5px] leading-relaxed text-slate-600">{d.summary}</p>
                </div>
                <KeyValue
                  cols={4}
                  items={[
                    ['Disruption type', d.type],
                    ['Location', d.location_label],
                    ['Initial window', `${fmtTime(d.initial_window.start)} – ${fmtTime(d.initial_window.end)}`],
                    ['Asset', ev.asset_name],
                  ]}
                />
              </>
            ) : (
              <p className="text-[13px] text-slate-500">{ev.description}</p>
            )}
          </div>
        </Card>

        {d && (
          <Card>
            <CardHeader title="Threshold evaluation" subtitle="Feed readings against operating limits" icon={Gauge} />
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/70 text-left text-[11.5px] uppercase tracking-wide text-slate-500">
                  <th className="px-5 py-2 font-semibold">Signal</th>
                  <th className="px-5 py-2 text-right font-semibold">Reading</th>
                  <th className="px-5 py-2 text-right font-semibold">Limit</th>
                  <th className="px-5 py-2 font-semibold">Rule</th>
                  <th className="px-5 py-2 font-semibold">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {d.triggers.map((t) => (
                  <tr key={t.signal}>
                    <td className="px-5 py-2.5 font-medium text-slate-800">{t.signal}</td>
                    <td className={cx('tabular px-5 py-2.5 text-right font-semibold', t.breached ? 'text-rose-600' : 'text-slate-700')}>
                      {String(t.value)} <span className="font-normal text-slate-400">{t.unit}</span>
                    </td>
                    <td className="tabular px-5 py-2.5 text-right text-slate-500">
                      {String(t.threshold)} {t.unit}
                    </td>
                    <td className="px-5 py-2.5 text-[12.5px] text-slate-500">{t.rule}</td>
                    <td className="px-5 py-2.5">
                      {t.breached ? (
                        <span className="inline-flex items-center gap-1 text-[12px] font-medium text-rose-600">
                          <XCircle size={14} /> Breached
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[12px] font-medium text-emerald-600">
                          <CheckCircle2 size={14} /> Within limit
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      <div className="space-y-5">
        {d && (
          <Card className="p-5">
            <p className="text-[12px] font-medium text-slate-500">Detection confidence</p>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="tabular text-[28px] font-semibold text-slate-900">{Math.round(d.confidence * 100)}%</span>
              <span className="text-[12.5px] text-slate-500">{d.breached} of {d.triggers.length} signals breached</span>
            </div>
            <Progress value={d.confidence * 100} tone={d.confidence > 0.8 ? 'emerald' : 'amber'} className="mt-2" />
            {d.watch_items?.length > 0 && (
              <div className="mt-5 border-t border-slate-100 pt-4">
                <p className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold text-slate-700">
                  <Eye size={13} /> Watch items
                </p>
                <ul className="space-y-1.5">
                  {d.watch_items.map((w) => (
                    <li key={w} className="flex gap-2 text-[12.5px] text-slate-600">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-400" />
                      {w}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </Card>
        )}

        {imp && (
          <Card className="p-5">
            <div className="mb-4 flex items-center justify-between">
              <p className="text-[13px] font-semibold text-slate-900">Impact at a glance</p>
              <button onClick={() => onOpenTab('impact')} className="text-[12.5px] font-medium text-brand-600 hover:text-brand-700">
                Details
              </button>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Stat label="Services" value={imp.trips_direct + imp.trips_cascade} hint={`${imp.trips_cascade} via cascade`} />
              <Stat label="Passengers" value={fmtNum(imp.pax_affected)} tone="amber" />
              <Stat label="Missed connections" value={imp.missed_connections} tone={imp.missed_connections ? 'rose' : undefined} />
              <Stat label="Crew breaches" value={imp.crew_pairings_breached} tone={imp.crew_pairings_breached ? 'rose' : undefined} />
              <Stat label="Max delay" value={fmtMin(imp.max_delay_min)} />
              <Stat label="Cost if no action" value={fmtINR(imp.baseline_cost)} />
            </div>
          </Card>
        )}

        {rec && (
          <Card className="border-brand-200 p-5">
            <p className="flex items-center gap-1.5 text-[12px] font-medium text-brand-700">
              <Route size={13} /> Recommended plan
            </p>
            <p className="mt-1 text-[15px] font-semibold text-slate-900">
              {rec.letter}. {rec.name}
            </p>
            <p className="mt-1 text-[12.5px] text-slate-500">
              Score {rec.score} · confidence {Math.round(rec.confidence * 100)}% · {fmtINR(rec.cost.total)}
            </p>
            <button
              onClick={() => onOpenTab('options')}
              className="mt-3 text-[12.5px] font-medium text-brand-600 hover:text-brand-700"
            >
              {inc.status === 'AWAITING_APPROVAL' ? 'Review and decide' : 'View options'}
            </button>
          </Card>
        )}
        {inc.status === 'NO_ACTION' && (
          <Card className="p-5 text-[13px] text-slate-600">No operating threshold was breached. {titleCase(inc.status)}.</Card>
        )}
      </div>
    </div>
  )
}
