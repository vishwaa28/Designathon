import { useState } from 'react'
import { BellRing, ExternalLink, Mail, MessageCircle, MessageSquareText, PhoneCall, RotateCw, Search, Smartphone } from 'lucide-react'
import { api } from '../../lib/api'
import { fmtNum, fmtTime, titleCase } from '../../lib/format'
import { providerLabel } from '../../lib/agents'
import { useApi } from '../../lib/useApi'
import { DeliveryChips } from '../DeliveryCard'
import { Badge, Button, Card, CardHeader, Empty, Segmented, Stat, cx, inputBase } from '../ui'

const CHANNEL_ICON = { SMS: MessageSquareText, EMAIL: Mail, WHATSAPP: MessageCircle, APP: Smartphone }
const OUTCOME_TONE = {
  DELAYED: 'amber', REBOOKED: 'blue', DIVERTED: 'violet',
  UNACCOMMODATED: 'rose', SELF_REBOOKED: 'emerald', REFUNDED: 'slate',
}
const OUTCOME_LABEL = { UNACCOMMODATED: 'Refund offered' }

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
  const { data, reload } = useApi(n ? `/incidents/${inc.id}/notifications?${params}` : null, { refreshOn: ['notifications.'] })
  const [resending, setResending] = useState(null)

  const resend = async (id) => {
    setResending(id)
    try {
      await api.post(`/notifications/${id}/resend`)
      reload()
    } finally {
      setResending(null)
    }
  }

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
      <Card className="grid gap-6 p-4 sm:grid-cols-2 sm:p-5 lg:grid-cols-5">
        <div className="space-y-4">
          <Stat label="Messages delivered" value={fmtNum(n.total)} tone="emerald" />
          <Stat label="Priority travelers" value={fmtNum(n.priority)} />
          <Stat label="Assisted calls queued" value={fmtNum(n.agent_calls)} hint="Wheelchair, minors, medical" />
          {n.delivery && (
            <Stat
              label="Real e-mail / SMS"
              value={`${n.delivery.email_sent} / ${n.delivery.sms_sent}`}
              tone={n.delivery.failed ? 'amber' : n.delivery.email_sent + n.delivery.sms_sent ? 'emerald' : undefined}
              hint={n.delivery.not_configured ? 'Provider credentials not set' : `${n.delivery.recipients} contact travelers`}
            />
          )}
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
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative w-full sm:w-auto">
                <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input className={cx(inputBase, 'h-8 w-full pl-8 sm:w-48')} placeholder="PNR, name or service" value={q} onChange={(e) => setQ(e.target.value)} />
              </div>
              <div className="no-scrollbar max-w-full overflow-x-auto">
              <Segmented
                size="sm"
                value={outcome}
                onChange={setOutcome}
                options={[{ value: '', label: 'All' }, ...Object.keys(n.by_outcome).map((k) => ({ value: k, label: OUTCOME_LABEL[k] || titleCase(k) }))]}
              />
              </div>
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
              <div key={m.id} className={cx('flex gap-3 px-4 py-3 sm:gap-4 sm:px-5', m.contact && 'bg-brand-50/40')}>
                <span className="mt-0.5 hidden h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500 sm:flex" title={m.channel}>
                  <Icon size={15} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[13px] font-semibold text-slate-900">{m.name}</span>
                    <span className="font-mono text-[11.5px] text-slate-500">{m.pnr}</span>
                    <Badge tone={OUTCOME_TONE[m.outcome] || 'slate'}>{OUTCOME_LABEL[m.outcome] || titleCase(m.outcome)}</Badge>
                    <Badge>{m.language_label}</Badge>
                    {m.contact && <Badge tone="brand"><Mail size={11} /> E-mail & SMS</Badge>}
                    {m.priority && <Badge tone="violet">Priority</Badge>}
                    {m.escalation && (
                      <Badge tone="rose"><PhoneCall size={11} /> Assisted call</Badge>
                    )}
                  </div>
                  <p className="mt-1 break-words text-[13px] leading-relaxed text-slate-700">{m.message}</p>
                  <p className="mt-1 text-[11.5px] text-slate-400">
                    {m.subject} · {m.contact ? 'E-mail + SMS' : titleCase(m.channel)} · {m.contact ? '' : `${titleCase(m.status)} `}{fmtTime(m.sent_at)}
                    {m.new_trip && ` · ${m.trip} → ${m.new_trip}`}
                  </p>
                  {m.contact && (
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <DeliveryChips deliveries={m.deliveries} />
                      {m.deliveries && !m.deliveries.length && (
                        <span className="text-[11.5px] text-slate-500">
                          Not sent externally: already messaged for another affected flight. Use Resend to send this one.
                        </span>
                      )}
                      <Button size="sm" variant="ghost" icon={RotateCw} loading={resending === m.id} onClick={() => resend(m.id)}>
                        Resend
                      </Button>
                    </div>
                  )}
                  {m.self_service_url && (
                    <a
                      href={`/traveler?pnr=${m.pnr}&name=${encodeURIComponent(m.last_name)}`}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1.5 inline-flex items-center gap-1 text-[12px] font-medium text-brand-600 hover:text-brand-700 sm:hidden"
                    >
                      Self-service <ExternalLink size={12} />
                    </a>
                  )}
                </div>
                {m.self_service_url && (
                  <a
                    href={`/traveler?pnr=${m.pnr}&name=${encodeURIComponent(m.last_name)}`}
                    target="_blank"
                    rel="noreferrer"
                    className="hidden h-8 shrink-0 items-center gap-1 rounded-md px-2 text-[12px] font-medium text-brand-600 hover:bg-brand-50 sm:flex"
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
