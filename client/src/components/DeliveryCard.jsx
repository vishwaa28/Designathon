import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Mail, MessageSquareText, Send, UserRound } from 'lucide-react'
import { api } from '../lib/api'
import { relTime } from '../lib/format'
import { useApi } from '../lib/useApi'
import { Badge, Button, Card, CardHeader, cx } from './ui'

const RESULT = {
  SENT: { tone: 'emerald', label: 'Sent' },
  FAILED: { tone: 'rose', label: 'Failed' },
  NOT_CONFIGURED: { tone: 'slate', label: 'Not configured' },
}

export function DeliveryChips({ deliveries }) {
  if (!deliveries?.length) return null
  return (
    <div className="flex flex-wrap gap-1.5">
      {deliveries.map((d) => {
        const r = RESULT[d.status] || RESULT.FAILED
        const Icon = d.channel === 'EMAIL' ? Mail : MessageSquareText
        return (
          <span key={d.channel} title={d.detail || undefined}>
            <Badge tone={r.tone}>
              <Icon size={11} />
              {d.channel === 'EMAIL' ? 'E-mail' : 'SMS'} {r.label.toLowerCase()}
            </Badge>
          </span>
        )
      })}
    </div>
  )
}

function Provider({ icon: Icon, label, info }) {
  return (
    <div className="flex items-center gap-2.5 rounded-lg border border-slate-200 px-3 py-2">
      <span className={cx('flex h-7 w-7 items-center justify-center rounded-md', info.configured ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-500')}>
        <Icon size={14} />
      </span>
      <div className="min-w-0 leading-tight">
        <p className="text-[12.5px] font-medium text-slate-800">{label}</p>
        <p className="truncate text-[11.5px] text-slate-500">
          {info.configured ? `${info.provider}${info.sender ? ` · ${info.sender}` : ''}` : 'Credentials not set'}
        </p>
      </div>
    </div>
  )
}

export default function DeliveryCard() {
  const { data, reload } = useApi('/delivery/status', { refreshOn: ['notifications.', 'traveler.', 'simulation.'] })
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState(null)

  const test = async () => {
    setSending(true)
    try {
      const res = await api.post('/delivery/test', {})
      const sent = res.results.flatMap((r) => r.deliveries).filter((d) => d.status === 'SENT').length
      const total = res.results.flatMap((r) => r.deliveries).length
      setResult(`${sent} of ${total} test messages sent`)
      reload()
    } catch (e) {
      setResult(e.message)
    } finally {
      setSending(false)
    }
  }

  if (!data) return null
  return (
    <Card>
      <CardHeader
        title="Traveler e-mail & SMS"
        subtitle="Real messages go to these passengers in every disruption"
        icon={Send}
        actions={<Button size="sm" variant="secondary" icon={Send} loading={sending} onClick={test}>Send test</Button>}
      />
      <div className="grid gap-2.5 px-4 pt-4 sm:grid-cols-2 sm:px-5">
        <Provider icon={Mail} label="E-mail" info={data.email} />
        <Provider icon={MessageSquareText} label="SMS" info={data.sms} />
      </div>
      {result && <p className="px-4 pt-3 text-[12.5px] text-slate-600 sm:px-5">{result}</p>}
      <div className="grid gap-3 p-4 sm:grid-cols-2 sm:p-5 xl:grid-cols-4">
        {data.contacts.map((c) => {
          const last = c.last_notification
          return (
            <div key={c.pnr} className="rounded-lg border border-slate-200 p-3.5">
              <div className="flex items-start gap-2.5">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600">
                  <UserRound size={15} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-semibold text-slate-900">{c.name}</p>
                  <p className="truncate text-[11.5px] text-slate-500">{c.email}</p>
                  <p className="text-[11.5px] text-slate-500">{c.phone}</p>
                </div>
              </div>
              <div className="mt-3 flex items-center justify-between gap-2 text-[12px]">
                <Link
                  to={`/traveler?pnr=${c.pnr}&name=${encodeURIComponent(c.last_name)}`}
                  target="_blank"
                  className="font-mono font-medium text-brand-600 hover:text-brand-700"
                >
                  {c.pnr}
                </Link>
                {c.trip && <span className="truncate text-slate-600">{c.trip.number} · {c.trip.origin}-{c.trip.destination}</span>}
              </div>
              <div className="mt-2.5 border-t border-slate-100 pt-2.5">
                {last ? (
                  <>
                    <p className="truncate text-[12px] text-slate-700">{last.subject} · {relTime(last.sent_at)}</p>
                    <div className="mt-1.5"><DeliveryChips deliveries={last.deliveries} /></div>
                  </>
                ) : (
                  <p className="text-[12px] text-slate-400">No messages yet</p>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
