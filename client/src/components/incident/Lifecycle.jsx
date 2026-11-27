import { Check } from 'lucide-react'
import { fmtTime } from '../../lib/format'
import { cx } from '../ui'

export default function Lifecycle({ inc }) {
  const approved = inc.decision?.action === 'approve'
  const stages = [
    { label: 'Detected', done: !!inc.detection, at: inc.detection?.detected_at },
    { label: 'Impact & triage', done: !!inc.impact && !!inc.infra },
    { label: 'Options generated', done: inc.options?.length > 0, at: inc.recommendation?.generated_at },
    {
      label: inc.status === 'REJECTED' ? 'Rejected' : 'Controller decision',
      done: approved || inc.status === 'REJECTED',
      waiting: inc.status === 'AWAITING_APPROVAL',
      at: inc.decision?.decided_at,
    },
    { label: 'Travelers notified', done: !!inc.notifications, at: inc.notifications?.sent_at },
  ]
  const current = stages.findIndex((s) => !s.done)

  return (
    <ol className="flex items-center">
      {stages.map((s, i) => {
        const active = i === current && inc.status !== 'REJECTED' && inc.status !== 'NO_ACTION'
        return (
          <li key={s.label} className="flex flex-1 items-center last:flex-none">
            <div className="flex items-center gap-2.5">
              <span
                className={cx(
                  'flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold',
                  s.done && 'bg-emerald-500 text-white',
                  !s.done && active && s.waiting && 'animate-pulse-amber bg-amber-500 text-white',
                  !s.done && active && !s.waiting && 'animate-pulse-ring bg-brand-600 text-white',
                  !s.done && !active && 'bg-slate-100 text-slate-400 ring-1 ring-slate-200',
                )}
              >
                {s.done ? <Check size={14} strokeWidth={3} /> : i + 1}
              </span>
              <div className="leading-tight">
                <p className={cx('whitespace-nowrap text-[12.5px] font-medium', s.done || active ? 'text-slate-900' : 'text-slate-400')}>
                  {s.label}
                </p>
                <p className="tabular text-[11px] text-slate-400">
                  {s.done && s.at ? fmtTime(s.at) : active ? (s.waiting ? 'Waiting' : 'In progress') : ' '}
                </p>
              </div>
            </div>
            {i < stages.length - 1 && (
              <div className={cx('mx-3 h-px flex-1', s.done ? 'bg-emerald-300' : 'bg-slate-200')} />
            )}
          </li>
        )
      })}
    </ol>
  )
}
