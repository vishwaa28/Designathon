import { useState } from 'react'
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  GitBranch,
  History,
  Minus,
  RefreshCw,
  ShieldCheck,
  ThumbsDown,
  XCircle,
} from 'lucide-react'
import { api } from '../../lib/api'
import { providerLabel } from '../../lib/agents'
import { fmtINR, fmtMin, fmtNum, fmtTime, relTime, titleCase } from '../../lib/format'
import { useApi } from '../../lib/useApi'
import { Badge, Button, Card, CardHeader, Field, Modal, Progress, Segmented, cx, inputClass } from '../ui'

const CONSTRAINT_ICON = {
  PASS: <CheckCircle2 size={14} className="shrink-0 text-emerald-500" />,
  WARN: <CircleAlert size={14} className="shrink-0 text-amber-500" />,
  FAIL: <XCircle size={14} className="shrink-0 text-rose-500" />,
}
const PRIORITY_OPTIONS = [
  { value: 'balanced', label: 'Balanced' },
  { value: 'passenger', label: 'Passengers first' },
  { value: 'cost', label: 'Lowest cost' },
  { value: 'speed', label: 'Fastest recovery' },
]

function ScoreRing({ score, highlight }) {
  const r = 20
  const c = 2 * Math.PI * r
  return (
    <div className="relative h-14 w-14 shrink-0">
      <svg viewBox="0 0 48 48" className="h-14 w-14 -rotate-90">
        <circle cx="24" cy="24" r={r} fill="none" stroke="#eef2f7" strokeWidth="4.5" />
        <circle
          cx="24" cy="24" r={r} fill="none" strokeWidth="4.5" strokeLinecap="round"
          stroke={highlight ? '#2f5bea' : '#94a3b8'} strokeDasharray={c} strokeDashoffset={c * (1 - score / 100)}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
        <span className="tabular text-[15px] font-semibold text-slate-900">{score}</span>
        <span className="text-[9px] uppercase tracking-wide text-slate-400">score</span>
      </div>
    </div>
  )
}

function Metric({ label, value, tone }) {
  return (
    <div>
      <p className="text-[11px] text-slate-500">{label}</p>
      <p className={cx('tabular text-[13.5px] font-semibold', tone === 'rose' ? 'text-rose-600' : tone === 'amber' ? 'text-amber-600' : 'text-slate-900')}>
        {value}
      </p>
    </div>
  )
}

function OptionCard({ option: o, selected, onSelect, decided, approved }) {
  const [open, setOpen] = useState(false)
  const m = o.metrics
  return (
    <div
      className={cx(
        'relative flex flex-col rounded-xl border bg-white transition-all',
        approved ? 'border-emerald-400 ring-2 ring-emerald-100' : selected ? 'border-brand-500 ring-2 ring-brand-100' : 'border-slate-200',
      )}
    >
      {o.recommended && (
        <div className="absolute -top-2.5 left-4 rounded-full bg-brand-600 px-2.5 py-0.5 text-[11px] font-semibold text-white shadow-sm">
          Recommended
        </div>
      )}
      <div className="flex items-start gap-3 p-4 pb-3">
        <span className={cx('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[14px] font-bold', o.recommended ? 'bg-brand-50 text-brand-700' : 'bg-slate-100 text-slate-600')}>
          {o.letter}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[14px] font-semibold text-slate-900">{o.name}</p>
          <p className="mt-0.5 text-[12px] leading-snug text-slate-500">{o.summary}</p>
        </div>
        <ScoreRing score={o.score} highlight={o.recommended} />
      </div>

      <div className="px-4">
        <div className="flex items-center justify-between text-[11.5px]">
          <span className="text-slate-500">Confidence</span>
          <span className="tabular font-semibold text-slate-800">{Math.round(o.confidence * 100)}%</span>
        </div>
        <Progress value={o.confidence * 100} tone={o.confidence >= 0.75 ? 'emerald' : o.confidence >= 0.55 ? 'amber' : 'rose'} className="mt-1" />
      </div>

      <div className="mx-4 mt-3 grid grid-cols-3 gap-x-3 gap-y-2.5 rounded-lg bg-slate-50 p-3">
        <Metric label="Total cost" value={fmtINR(o.cost.total)} />
        <Metric label="Delayed / cancelled" value={`${m.trips_delayed} / ${m.trips_cancelled}`} />
        <Metric label="Avg delay" value={fmtMin(m.avg_delay_min)} tone={m.avg_delay_min > 120 ? 'amber' : undefined} />
        <Metric label="Rebooked" value={fmtNum(m.pax_rebooked)} />
        <Metric label="Unaccommodated" value={fmtNum(m.pax_unaccommodated)} tone={m.pax_unaccommodated ? 'rose' : undefined} />
        <Metric label="Recovered by" value={fmtTime(m.recovery_by)} />
      </div>

      <p className="px-4 pt-3 text-[12.5px] leading-relaxed text-slate-600">{o.explanation}</p>

      <div className="grid grid-cols-2 gap-3 px-4 pt-3">
        <ul className="space-y-1.5">
          {o.pros.map((p) => (
            <li key={p} className="flex gap-1.5 text-[12px] text-slate-700">
              <Check size={13} className="mt-0.5 shrink-0 text-emerald-500" /> {p}
            </li>
          ))}
        </ul>
        <ul className="space-y-1.5">
          {o.cons.map((p) => (
            <li key={p} className="flex gap-1.5 text-[12px] text-slate-700">
              <Minus size={13} className="mt-0.5 shrink-0 text-amber-500" /> {p}
            </li>
          ))}
        </ul>
      </div>

      <div className="mx-4 mt-3 space-y-1.5 border-t border-slate-100 pt-3">
        {o.constraints.map((c) => (
          <div key={c.name} className="flex gap-2 text-[12px]" title={c.detail}>
            {CONSTRAINT_ICON[c.status]}
            <div className="min-w-0">
              <span className="font-medium text-slate-700">{c.name}</span>
              <span className="text-slate-500"> · {c.detail}</span>
            </div>
          </div>
        ))}
      </div>

      {o.sensitivity && (
        <div className="mx-4 mt-3 flex gap-2 rounded-lg bg-amber-50 px-3 py-2 text-[12px] text-amber-900">
          <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber-600" />
          <span>
            If restoration slips to P90 ({fmtTime(o.sensitivity.restoration)}): {o.sensitivity.extra_cost >= 0 ? '+' : ''}
            {fmtINR(o.sensitivity.extra_cost)} and average delay {fmtMin(o.sensitivity.avg_delay_min)}.
          </span>
        </div>
      )}

      <button onClick={() => setOpen(!open)} className="mx-4 mt-3 flex items-center gap-1 text-[12px] font-medium text-slate-500 hover:text-slate-800">
        <ChevronDown size={14} className={cx('transition-transform', open && 'rotate-180')} />
        {o.action_count} planned actions · cost breakdown
      </button>
      {open && (
        <div className="mx-4 mt-2 grid gap-3 text-[12px]">
          <ul className="max-h-48 space-y-1 overflow-y-auto rounded-lg border border-slate-100 p-2.5">
            {o.actions.map((a, i) => (
              <li key={i} className="flex gap-2">
                <Badge tone="slate" className="!px-1.5 !text-[10px]">{titleCase(a.type)}</Badge>
                <span className="text-slate-600">{a.detail}</span>
              </li>
            ))}
            {o.action_count > o.actions.length && <li className="text-slate-400">+ {o.action_count - o.actions.length} more</li>}
          </ul>
          <div className="space-y-1 rounded-lg border border-slate-100 p-2.5">
            {Object.entries(o.cost.breakdown).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span className="text-slate-500">{k}</span>
                <span className="tabular font-medium text-slate-800">{fmtINR(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-auto p-4 pt-3">
        {approved ? (
          <div className="flex h-9 items-center justify-center gap-2 rounded-lg bg-emerald-50 text-[13px] font-semibold text-emerald-700">
            <ShieldCheck size={15} /> Approved plan
          </div>
        ) : (
          <Button
            variant={selected ? 'primary' : 'secondary'}
            className="w-full"
            disabled={decided}
            icon={selected ? Check : undefined}
            onClick={onSelect}
          >
            {selected ? 'Selected' : 'Select this option'}
          </Button>
        )}
      </div>
    </div>
  )
}

function CriteriaTable({ options, recommendation }) {
  const labels = recommendation.criteria_labels
  return (
    <table className="w-full text-[12.5px]">
      <thead>
        <tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
          <th className="py-1.5 font-semibold">Criterion</th>
          <th className="py-1.5 font-semibold">Weight</th>
          {options.map((o) => (
            <th key={o.id} className="py-1.5 font-semibold">Option {o.letter}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {Object.entries(labels).map(([key, label]) => (
          <tr key={key} className="border-t border-slate-100">
            <td className="py-2 font-medium text-slate-700">{label}</td>
            <td className="tabular py-2 text-slate-500">{Math.round(recommendation.weights[key] * 100)}%</td>
            {options.map((o) => (
              <td key={o.id} className="py-2 pr-4">
                <div className="flex items-center gap-2">
                  <Progress value={o.criteria[key]} tone={o.criteria[key] >= 70 ? 'emerald' : o.criteria[key] >= 40 ? 'amber' : 'rose'} className="w-20" />
                  <span className="tabular w-7 text-slate-600">{o.criteria[key]}</span>
                </div>
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function ReplanModal({ open, onClose, initial, onSubmit, busy }) {
  const [priority, setPriority] = useState(initial?.priority || 'balanced')
  const [maxDelay, setMaxDelay] = useState(initial?.max_delay_min || '')
  const [avoid, setAvoid] = useState(!!initial?.avoid_cancellations)
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Re-plan with new priorities"
      subtitle="The planner regenerates options and the analyst re-scores them under your constraints."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            icon={RefreshCw}
            loading={busy}
            onClick={() => onSubmit({ priority, max_delay_min: maxDelay ? Number(maxDelay) : null, avoid_cancellations: avoid })}
          >
            Re-plan
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Optimisation priority">
          <Segmented value={priority} onChange={setPriority} options={PRIORITY_OPTIONS} />
        </Field>
        <Field label="Maximum acceptable delay (minutes)" hint="Options exceeding this are flagged and penalised.">
          <input type="number" min={15} className={inputClass} value={maxDelay} onChange={(e) => setMaxDelay(e.target.value)} placeholder="No limit" />
        </Field>
        <label className="flex items-center gap-2 text-[13px] text-slate-700">
          <input type="checkbox" checked={avoid} onChange={(e) => setAvoid(e.target.checked)} className="h-4 w-4 rounded border-slate-300 text-brand-600" />
          Avoid cancellations where possible
        </label>
      </div>
    </Modal>
  )
}

export default function OptionsPanel({ inc }) {
  const rec = inc.recommendation
  const options = inc.options || []
  const awaiting = inc.status === 'AWAITING_APPROVAL'
  const approvedId = inc.decision?.action === 'approve' ? inc.decision.option_id : null
  const [choice, setChoice] = useState({ version: null, id: null })
  const selected = choice.version === inc.plan_version && choice.id ? choice.id : rec?.option_id
  const setSelected = (id) => setChoice({ version: inc.plan_version, id })
  const [controller, setController] = useState('A. Menon (Duty Controller)')
  const [notes, setNotes] = useState('')
  const [overrideReason, setOverrideReason] = useState('')
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [replan, setReplan] = useState(false)
  const { data: catalog } = useApi('/feeds/scenarios')

  if (!options.length) {
    return <p className="p-6 text-[13px] text-slate-500">Recovery options are being generated…</p>
  }

  const isOverride = selected && rec && selected !== rec.option_id
  const send = async (kind, body, path = 'decision') => {
    setBusy(kind)
    setError(null)
    try {
      await api.post(`/incidents/${inc.id}/${path}`, body)
      setReplan(false)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-5">
      {rec && (
        <Card className="p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <p className="flex items-center gap-2 text-[12px] font-medium text-slate-500">
                Plan v{inc.plan_version} · weighting: <Badge tone="brand">{PRIORITY_OPTIONS.find((p) => p.value === rec.priority)?.label}</Badge>
                <Badge tone="slate">{providerLabel(rec.narrative_source)}</Badge>
              </p>
              <p className="mt-2 text-[13.5px] leading-relaxed text-slate-700">{rec.rationale}</p>
            </div>
            <div className="w-full min-w-0 overflow-x-auto lg:w-auto lg:min-w-[420px] lg:flex-1 xl:max-w-[520px]">
              <CriteriaTable options={options} recommendation={rec} />
            </div>
          </div>
        </Card>
      )}

      <div className="grid gap-5 pt-1 lg:grid-cols-3">
        {options.map((o) => (
          <OptionCard
            key={o.id}
            option={o}
            selected={selected === o.id && !approvedId}
            approved={approvedId === o.id}
            decided={!awaiting}
            onSelect={() => setSelected(o.id)}
          />
        ))}
      </div>

      {awaiting && (
        <Card className="z-10 border-amber-200 shadow-lg sm:sticky sm:bottom-4">
          <div className="flex flex-wrap items-end gap-3 p-4 sm:gap-4">
            <div className="flex items-center gap-3">
              <span className="animate-pulse-amber flex h-9 w-9 items-center justify-center rounded-full bg-amber-500 text-white">
                <ShieldCheck size={17} />
              </span>
              <div>
                <p className="text-[13.5px] font-semibold text-slate-900">Controller decision required</p>
                <p className="text-[12px] text-slate-500">
                  Selected: Option {options.find((o) => o.id === selected)?.letter} · {options.find((o) => o.id === selected)?.name}
                  {isOverride && <span className="font-medium text-amber-700"> (overrides recommendation)</span>}
                </p>
              </div>
            </div>
            <div className="w-full sm:w-56">
              <Field label="Controller">
                <input className={inputClass} value={controller} onChange={(e) => setController(e.target.value)} />
              </Field>
            </div>
            <div className="w-full min-w-[200px] flex-1 sm:w-auto">
              <Field label={isOverride ? 'Override reason (required)' : 'Notes'}>
                <input
                  className={inputClass}
                  value={isOverride ? overrideReason : notes}
                  onChange={(e) => (isOverride ? setOverrideReason(e.target.value) : setNotes(e.target.value))}
                  placeholder={isOverride ? 'Why is the recommendation being overridden?' : 'Optional'}
                />
              </Field>
            </div>
            <div className="flex w-full flex-wrap gap-2 sm:w-auto">
              <Button variant="danger" icon={ThumbsDown} loading={busy === 'reject'}
                onClick={() => window.confirm('Reject all options and hand over to manual handling?') &&
                  send('reject', { action: 'reject', controller, notes })}>
                Reject
              </Button>
              <Button variant="secondary" icon={RefreshCw} onClick={() => setReplan(true)}>Re-plan</Button>
              <Button
                className="flex-1 sm:flex-none"
                icon={ShieldCheck}
                loading={busy === 'approve'}
                disabled={isOverride && !overrideReason.trim()}
                onClick={() => send('approve', { action: 'approve', option_id: selected, controller, notes, override_reason: isOverride ? overrideReason : null })}
              >
                Approve & notify travelers
              </Button>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 px-4 py-2.5">
            <span className="text-[12px] font-medium text-slate-500">New information from the field:</span>
            {(catalog?.updates || []).map((u) => (
              <button
                key={u.id}
                title={u.detail}
                disabled={!!busy}
                onClick={() => send(u.id, { update_type: u.id, controller }, 'updates')}
                className="rounded-md border border-slate-200 px-2.5 py-1 text-[12px] font-medium text-slate-600 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 disabled:opacity-50"
              >
                {u.label}
              </button>
            ))}
          </div>
          {error && <p className="border-t border-rose-100 bg-rose-50 px-4 py-2 text-[12.5px] text-rose-700">{error}</p>}
        </Card>
      )}

      {inc.decision && (
        <Card className="flex items-center gap-3 p-4">
          <span className={cx('flex h-9 w-9 items-center justify-center rounded-full', inc.decision.action === 'approve' ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-500')}>
            {inc.decision.action === 'approve' ? <ShieldCheck size={17} /> : <GitBranch size={17} />}
          </span>
          <div className="text-[13px]">
            <p className="font-semibold text-slate-900">
              {inc.decision.action === 'approve'
                ? `Approved ${inc.decision.option_name}${inc.decision.override ? ' (override)' : ''}`
                : inc.decision.action === 'reject' ? 'All options rejected, manual handling' : `Last action: ${inc.decision.action}`}
            </p>
            <p className="text-slate-500">
              {inc.decision.controller} · {fmtTime(inc.decision.decided_at)}
              {inc.decision.override_reason && ` · Reason: ${inc.decision.override_reason}`}
              {inc.decision.notes && ` · ${inc.decision.notes}`}
            </p>
          </div>
        </Card>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Plan history" subtitle="Each re-plan is versioned for audit" icon={History} />
          <ol className="divide-y divide-slate-100">
            {[...(inc.plan_history || [])].reverse().map((h) => (
              <li key={h.version} className="flex items-center gap-3 px-5 py-3">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 font-mono text-[11.5px] font-semibold text-slate-600">v{h.version}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-medium text-slate-800">{h.reason}</p>
                  <p className="text-[12px] text-slate-500">Recommended {h.recommended_name} · score {h.score} · {fmtINR(h.cost)}</p>
                </div>
                <span className="text-[11.5px] text-slate-400">{relTime(h.at)}</span>
              </li>
            ))}
          </ol>
        </Card>
        <Card>
          <CardHeader title="Field updates" subtitle="New information that triggered dynamic re-planning" icon={RefreshCw} />
          <ol className="divide-y divide-slate-100">
            {(inc.updates || []).map((u, i) => (
              <li key={i} className="px-5 py-3">
                <p className="text-[13px] font-medium text-slate-800">{u.label}</p>
                <p className="text-[12px] text-slate-500">{u.detail} · {fmtTime(u.at)}</p>
              </li>
            ))}
            {!inc.updates?.length && <li className="px-5 py-6 text-center text-[13px] text-slate-400">No field updates yet.</li>}
          </ol>
        </Card>
      </div>

      <ReplanModal
        open={replan}
        onClose={() => setReplan(false)}
        initial={inc.preferences}
        busy={busy === 'replan'}
        onSubmit={(prefs) => send('replan', { action: 'replan', controller, notes, preferences: prefs })}
      />
    </div>
  )
}
