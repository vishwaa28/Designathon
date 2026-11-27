import { useState } from 'react'
import { ArrowDownToLine, ArrowUpFromLine, ChevronDown, Cpu, Wrench } from 'lucide-react'
import { AGENT_META, providerLabel } from '../../lib/agents'
import { fmtDuration, fmtTime } from '../../lib/format'
import { Badge, cx } from '../ui'

function Chips({ icon: Icon, label, items }) {
  if (!items?.length) return null
  return (
    <div>
      <p className="mb-1.5 flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-wide text-slate-500">
        <Icon size={12} /> {label}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {items.map((i) => (
          <span key={i} className="rounded-md bg-slate-100 px-2 py-0.5 text-[11.5px] text-slate-700">{i}</span>
        ))}
      </div>
    </div>
  )
}

function JsonView({ value }) {
  const [open, setOpen] = useState(true)
  if (!value || !Object.keys(value).length) return null
  return (
    <div>
      <button onClick={() => setOpen(!open)} className="mb-1.5 flex items-center gap-1 text-[11.5px] font-semibold uppercase tracking-wide text-slate-500">
        <ChevronDown size={13} className={cx('transition-transform', !open && '-rotate-90')} /> Output
      </button>
      {open && (
        <pre className="max-h-72 overflow-auto rounded-lg bg-navy-900 p-3 font-mono text-[11px] leading-relaxed text-slate-200">
          {JSON.stringify(value, null, 2)}
        </pre>
      )}
    </div>
  )
}

export default function Inspector({ nodeId, nodeMeta, executions, selectedExec, onSelectExec }) {
  if (!nodeId) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-[13px] text-slate-400">
        Select a node to inspect its role, inputs, outputs and executions.
      </div>
    )
  }
  const meta = AGENT_META[nodeId]
  const ex = selectedExec || executions[executions.length - 1]
  return (
    <div className="space-y-5 p-5">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-white" style={{ background: meta.color }}>
          <meta.icon size={19} />
        </span>
        <div>
          <p className="text-[15px] font-semibold text-slate-900">{meta.title}</p>
          <p className="text-[12px] text-slate-500">{nodeMeta?.kind === 'human' ? 'Human-in-the-loop gate' : nodeMeta?.kind === 'terminal' ? 'Graph terminal' : 'LangGraph agent node'}</p>
        </div>
      </div>
      {nodeMeta?.role && <p className="text-[13px] leading-relaxed text-slate-600">{nodeMeta.role}</p>}
      <div className="space-y-3">
        <Chips icon={ArrowDownToLine} label="Inputs" items={nodeMeta?.inputs} />
        <Chips icon={ArrowUpFromLine} label="Outputs" items={nodeMeta?.outputs} />
        <Chips icon={Wrench} label="Tools" items={nodeMeta?.tools} />
      </div>

      {executions.length > 0 && (
        <div className="border-t border-slate-100 pt-4">
          <p className="mb-2 text-[11.5px] font-semibold uppercase tracking-wide text-slate-500">Executions</p>
          <div className="flex flex-wrap gap-1.5">
            {executions.map((e, i) => (
              <button
                key={e.id}
                onClick={() => onSelectExec(e)}
                className={cx(
                  'rounded-md px-2 py-1 text-[11.5px] font-medium ring-1 ring-inset',
                  ex?.id === e.id ? 'bg-brand-50 text-brand-700 ring-brand-200' : 'text-slate-600 ring-slate-200 hover:bg-slate-50',
                )}
              >
                Run {i + 1} · v{e.plan_version}
              </button>
            ))}
          </div>
        </div>
      )}

      {ex && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3 rounded-lg bg-slate-50 p-3 text-[12px]">
            <div>
              <p className="text-slate-500">Status</p>
              <p className="font-semibold capitalize text-slate-800">{ex.status}</p>
            </div>
            <div>
              <p className="text-slate-500">Started</p>
              <p className="tabular font-semibold text-slate-800">{fmtTime(ex.started_at)}</p>
            </div>
            <div>
              <p className="text-slate-500">Duration</p>
              <p className="tabular font-semibold text-slate-800">{ex.status === 'waiting' ? '—' : fmtDuration(ex.duration_ms)}</p>
            </div>
          </div>
          {ex.summary && <p className="text-[13px] leading-relaxed text-slate-700">{ex.summary}</p>}
          {ex.llm?.length > 0 && (
            <div>
              <p className="mb-1.5 flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-wide text-slate-500">
                <Cpu size={12} /> Model calls
              </p>
              <div className="space-y-1.5">
                {ex.llm.map((c, i) => (
                  <div key={i} className="rounded-lg border border-slate-200 p-2.5 text-[12px]">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-slate-800">{c.purpose}</span>
                      <Badge tone={c.ok ? 'emerald' : 'amber'}>{c.ok ? 'OK' : 'Fallback used'}</Badge>
                    </div>
                    <p className="mt-0.5 text-slate-500">
                      {providerLabel(c.provider)} · <span className="font-mono">{c.model}</span> · {c.latency_ms} ms
                    </p>
                    {c.error && <p className="mt-1 text-[11.5px] text-amber-700">{c.error}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
          <JsonView value={ex.output} />
        </div>
      )}
    </div>
  )
}
