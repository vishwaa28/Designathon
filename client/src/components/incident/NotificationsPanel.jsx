import { useState } from 'react'
import { BellRing, ExternalLink, Mail, MessageCircle, MessageSquareText, PhoneCall, Search, Smartphone } from 'lucide-react'
import { fmtNum, fmtTime, titleCase } from '../../lib/format'
import { providerLabel } from '../../lib/agents'
import { useApi } from '../../lib/useApi'
import { Badge, Card, CardHeader, Empty, Segmented, Stat, cx, inputBase } from '../ui'

const CHANNEL_ICON = { SMS: MessageSquareText, EMAIL: Mail, WHATSAPP: MessageCircle, APP: Smartphone }
const OUTCOME_TONE = {
  DELAYED: 'amber', REBOOKED: 'blue', ALT_MODE: 'violet', BUS_BRIDGE: 'violet', DIVERTED: 'violet',
  UNACCOMMODATED: 'rose', SELF_REBOOKED: 'emerald', REFUNDED: 'slate',
}
const OUTCOME_LABEL = { ALT_MODE: 'Alternate mode', BUS_BRIDGE: 'Coach bridge', UNACCOMMODATED: 'Refund offered' }

function Breakdown({ title, data }) {
  const total = Object.values(data || {}).reduce((a, b) => a + b, 0) || 1
  return (
    <div>
      <p className="mb-2 text-[12px] font-semibold text-slate-700">{title}</p>
      <div className="space-y-1.5">
        {Object.entries(data || {}).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
          <div key={k} className="flex items-center gap-2 text-[12px]">
            <span className="w-28 truncate text-slate-600">{OUTCOME_LABEL[k] || titleCase(k)}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-brand-400" style={{ width: `${(v / total) * 100}%` }} />
            </div>
            <span className="tabular w-12 text-right font-medium text-slate-700">{fmtNum(v)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function NotificationsPanel({ inc }) {
  const [outcome, setOutcome] = useState('')
  const [q, setQ] = useState('')
  const [priority, setPriority] = useState(false)
  const params = new URLSearchParams({ limit: '60' })
  if (outcome) params.set('outcome', outcome)
  if (q) params.set('q', q)
  if (priority) params.set('priority', 'true')
  const n = inc.notifications
  const { data } = useApi(n ? `/incidents/${inc.id}/notifications?${params}` : null, { refreshOn: ['notifications.'] })

  if (!n) {
    return (
      <Card>
        <Empty
          icon={BellRing}
          title="No notifications sent yet"
          text="Travelers are notified automatically once the controller approves a recovery plan."
        />
      </Card>
    )
  }

  return (
    <div className="space-y-5">
      <Card className="grid gap-6 p-5 lg:grid-cols-5">
        <div className="space-y-4">
          <Stat label="Messages delivered" value={fmtNum(n.total)} tone="emerald" />
          <Stat label="Priority travelers" value={fmtNum(n.priority)} />
          <Stat label="Assisted calls queued" value={fmtNum(n.agent_calls)} hint="Wheelchair, minors, medical" />
        </div>
        <Breakdown title="By outcome" data={n.by_outcome} />
        <Breakdown title="By channel" data={n.by_channel} />
        <Breakdown title="By language" data={n.by_language} />
        <div className="space-y-2 text-[12.5px]">
          <p className="text-[12px] font-semibold text-slate-700">Plan executed</p>
          {Object.entries(n.plan_changes || {}).map(([k, v]) => (
            <div key={k} className="flex justify-between text-slate-600">
              <span>{titleCase(k)}</span>
              <span className="tabular font-medium text-slate-800">{v}</span>
            </div>
          ))}
          <p className="pt-2 text-[11.5px] text-slate-400">Templates: {providerLabel(n.template_source)}</p>
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Traveler messages"
          subtitle={`${fmtNum(data?.total ?? 0)} matching · sent ${fmtTime(n.sent_at)}`}
          icon={BellRing}
          actions={
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input className={cx(inputBase, 'h-8 w-48 pl-8')} placeholder="PNR, name or service" value={q} onChange={(e) => setQ(e.target.value)} />
              </div>
              <Segmented
                size="sm"
                value={outcome}
                onChange={setOutcome}
                options={[{ value: '', label: 'All' }, ...Object.keys(n.by_outcome).map((k) => ({ value: k, label: OUTCOME_LABEL[k] || titleCase(k) }))]}
              />
              <label className="flex items-center gap-1.5 text-[12px] text-slate-600">
                <input type="checkbox" checked={priority} onChange={(e) => setPriority(e.target.checked)} className="rounded border-slate-300" />
                Priority only
              </label>
            </div>
          }
        />
        <div className="max-h-[560px] divide-y divide-slate-100 overflow-y-auto">
          {(data?.items || []).map((m) => {
            const Icon = CHANNEL_ICON[m.channel] || Smartphone
            return (
              <div key={m.id} className="flex gap-4 px-5 py-3">
                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500" title={m.channel}>
                  <Icon size={15} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[13px] font-semibold text-slate-900">{m.name}</span>
                    <span className="font-mono text-[11.5px] text-slate-500">{m.pnr}</span>
                    <Badge tone={OUTCOME_TONE[m.outcome] || 'slate'}>{OUTCOME_LABEL[m.outcome] || titleCase(m.outcome)}</Badge>
                    <Badge>{m.language_label}</Badge>
                    {m.priority && <Badge tone="violet">Priority</Badge>}
                    {m.escalation && (
                      <Badge tone="rose"><PhoneCall size={11} /> Assisted call</Badge>
                    )}
                  </div>
                  <p className="mt-1 text-[13px] leading-relaxed text-slate-700">{m.message}</p>
                  <p className="mt-1 text-[11.5px] text-slate-400">
                    {m.subject} · {titleCase(m.channel)} · {titleCase(m.status)} {fmtTime(m.sent_at)}
                    {m.new_trip && ` · ${m.trip} → ${m.new_trip}`}
                  </p>
                </div>
                {m.self_service_url && (
                  <a
                    href={`/traveler?pnr=${m.pnr}&name=${encodeURIComponent(m.last_name)}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex h-8 shrink-0 items-center gap-1 rounded-md px-2 text-[12px] font-medium text-brand-600 hover:bg-brand-50"
                  >
                    Self-service <ExternalLink size={12} />
                  </a>
                )}
              </div>
            )
          })}
        </div>
      </Card>
    </div>
  )
}
