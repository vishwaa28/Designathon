import { CheckCircle2, CircleAlert, Hourglass, Loader2, XCircle } from 'lucide-react'
import { AGENT_META } from '../../lib/agents'
import { fmtDuration, fmtTime } from '../../lib/format'
import { cx } from '../ui'

const STATUS = {
  running: { icon: Loader2, cls: 'text-brand-600', spin: true, label: 'Running' },
  completed: { icon: CheckCircle2, cls: 'text-emerald-600', label: 'Completed' },
  waiting: { icon: Hourglass, cls: 'text-amber-600', label: 'Waiting' },
  failed: { icon: XCircle, cls: 'text-rose-600', label: 'Failed' },
}

export default function ExecutionLog({ trace, selectedId, onSelect, compact }) {
  if (!trace?.length) return <p className="px-5 py-8 text-center text-[13px] text-slate-400">No executions yet.</p>
  return (
    <div className="divide-y divide-slate-100">
      {trace.map((ex, i) => {
        const meta = AGENT_META[ex.node] || { title: ex.node, color: '#64748b' }
        const st = STATUS[ex.status] || STATUS.completed
        const failedCalls = ex.llm?.filter((c) => !c.ok).length
        return (
          <button
            key={ex.id}
            onClick={() => onSelect?.(ex)}
            className={cx(
              'flex w-full items-start gap-3 px-5 py-2.5 text-left transition-colors hover:bg-slate-50',
              selectedId === ex.id && 'bg-brand-50/60',
            )}
          >
            <span className="tabular w-5 pt-0.5 text-right text-[11px] text-slate-400">{i + 1}</span>
            <span className="mt-0.5 h-5 w-1 shrink-0 rounded-full" style={{ background: meta.color }} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-[12.5px] font-semibold text-slate-800">{meta.title}</span>
                <span className="rounded bg-slate-100 px-1.5 font-mono text-[10.5px] text-slate-500">v{ex.plan_version}</span>
                {failedCalls > 0 && (
                  <span className="flex items-center gap-1 text-[11px] text-amber-600" title="Model call failed; rule-based output used">
                    <CircleAlert size={12} /> fallback
                  </span>
                )}
              </div>
              {!compact && <p className="truncate text-[12px] text-slate-500">{ex.summary || st.label}</p>}
            </div>
            <div className="shrink-0 text-right">
              <span className={cx('flex items-center justify-end gap-1 text-[11.5px] font-medium', st.cls)}>
                <st.icon size={13} className={st.spin ? 'animate-spin' : ''} /> {st.label}
              </span>
              <span className="tabular text-[11px] text-slate-400">
                {fmtTime(ex.started_at)} · {ex.status === 'waiting' ? '—' : fmtDuration(ex.duration_ms)}
              </span>
            </div>
          </button>
        )
      })}
    </div>
  )
}
