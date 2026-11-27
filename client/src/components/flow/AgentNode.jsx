import { Handle, Position } from '@xyflow/react'
import { Check, Hourglass, Loader2, X, Zap, Flag } from 'lucide-react'
import { AGENT_META } from '../../lib/agents'
import { fmtDuration } from '../../lib/format'
import { cx } from '../ui'

function Handles() {
  return (
    <>
      <Handle id="in" type="target" position={Position.Left} />
      <Handle id="out" type="source" position={Position.Right} />
      <Handle id="t-in" type="target" position={Position.Top} className="hidden-handle" />
      <Handle id="t-out" type="source" position={Position.Top} className="hidden-handle" />
      <Handle id="b-in" type="target" position={Position.Bottom} className="hidden-handle" />
      <Handle id="b-out" type="source" position={Position.Bottom} className="hidden-handle" />
    </>
  )
}

const STATUS_STYLE = {
  idle: { ring: 'border-slate-200', chip: 'bg-slate-100 text-slate-500', label: 'Idle' },
  running: { ring: 'border-brand-500 animate-pulse-ring', chip: 'bg-brand-50 text-brand-700', label: 'Running' },
  completed: { ring: 'border-emerald-300', chip: 'bg-emerald-50 text-emerald-700', label: 'Completed' },
  waiting: { ring: 'border-amber-400 animate-pulse-amber', chip: 'bg-amber-50 text-amber-800', label: 'Awaiting decision' },
  failed: { ring: 'border-rose-400', chip: 'bg-rose-50 text-rose-700', label: 'Failed' },
}

export function AgentNode({ id, data, selected }) {
  const meta = AGENT_META[id]
  const st = STATUS_STYLE[data.status] || STATUS_STYLE.idle
  const Icon = meta.icon
  const human = data.kind === 'human'
  return (
    <div
      className={cx(
        'relative w-[210px] rounded-xl border-2 bg-white shadow-[0_2px_8px_rgba(15,23,42,0.06)] transition-all',
        st.ring,
        selected && 'ring-4 ring-brand-100',
      )}
    >
      <Handles />
      {data.status === 'completed' && (
        <span className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 text-white shadow">
          <Check size={12} strokeWidth={3} />
        </span>
      )}
      {data.status === 'failed' && (
        <span className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full bg-rose-500 text-white shadow">
          <X size={12} strokeWidth={3} />
        </span>
      )}
      <div className="flex items-center gap-3 px-3 pb-2.5 pt-3">
        <span
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-white"
          style={{ background: meta.color }}
        >
          <Icon size={19} />
        </span>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-semibold text-slate-900">{meta.title}</p>
          <p className="text-[11px] text-slate-500">{human ? 'Human in the loop' : 'Agent'}</p>
        </div>
      </div>
      <div className="flex items-center justify-between border-t border-slate-100 px-3 py-1.5">
        <span className={cx('flex items-center gap-1 rounded px-1.5 py-0.5 text-[10.5px] font-semibold', st.chip)}>
          {data.status === 'running' && <Loader2 size={10} className="animate-spin" />}
          {data.status === 'waiting' && <Hourglass size={10} />}
          {st.label}
        </span>
        <span className="tabular text-[10.5px] text-slate-400">
          {data.runs > 0 && `${data.runs} run${data.runs > 1 ? 's' : ''}`}
          {data.duration != null && data.status === 'completed' && ` · ${fmtDuration(data.duration)}`}
        </span>
      </div>
    </div>
  )
}

export function TerminalNode({ id, data }) {
  const start = id === '__start__'
  return (
    <div
      className={cx(
        'flex h-[52px] items-center gap-2 border-2 bg-white px-4 shadow-sm',
        start ? 'rounded-l-[26px] rounded-r-xl' : 'rounded-l-xl rounded-r-[26px]',
        data.status === 'completed' ? 'border-emerald-300' : 'border-slate-200',
      )}
    >
      <Handles />
      <span className={cx('flex h-7 w-7 items-center justify-center rounded-full', start ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-600')}>
        {start ? <Zap size={14} /> : <Flag size={14} />}
      </span>
      <span className="text-[12.5px] font-semibold text-slate-700">{start ? 'Feed event' : 'Complete'}</span>
    </div>
  )
}
