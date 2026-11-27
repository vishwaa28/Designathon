import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  Gauge,
  ScanEye,
  Send,
  Timer,
  Users,
  Video,
} from 'lucide-react'
import LiveFlights from '../components/LiveFlights'
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Empty,
  Kpi,
  Modal,
  PageLoader,
  Spinner,
  Table,
  cx,
} from '../components/ui'
import { api } from '../lib/api'
import { fmtDateTime, fmtMin, fmtNum, relTime } from '../lib/format'
import { useApi } from '../lib/useApi'

const LEVEL = {
  LOW: { tone: 'emerald', label: 'Low density', bar: 'emerald' },
  MODERATE: { tone: 'amber', label: 'Moderate', bar: 'amber' },
  HIGH: { tone: 'orange', label: 'High density', bar: 'amber' },
  CRITICAL: { tone: 'rose', label: 'Critical', bar: 'rose' },
}
const MOVEMENT = { flowing: 'Flowing', slow: 'Slow moving', stationary: 'Stationary' }
const FRAME_WIDTH = 960

function Sparkline({ points, color = '#2f5bea' }) {
  if (!points || points.length < 2) {
    return <p className="text-[11.5px] text-slate-400">Trend appears after a few readings</p>
  }
  const w = 220
  const h = 36
  const max = Math.max(...points)
  const min = Math.min(...points)
  const span = Math.max(1, max - min)
  const step = w / (points.length - 1)
  const d = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${(i * step).toFixed(1)},${(h - 4 - ((p - min) / span) * (h - 8)).toFixed(1)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-9 w-full" preserveAspectRatio="none">
      <path d={d} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

function Metric({ label, value, sub, tone }) {
  const color = { rose: 'text-rose-600', amber: 'text-amber-600', emerald: 'text-emerald-600', orange: 'text-orange-600' }[tone] || 'text-slate-900'
  return (
    <div className="min-w-0">
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={cx('tabular mt-0.5 text-xl font-semibold leading-tight', color)}>{value}</p>
      {sub && <p className="truncate text-[11.5px] text-slate-500">{sub}</p>}
    </div>
  )
}

function CameraTile({ cam, videoRef, busy, error }) {
  const lv = LEVEL[cam.level] || LEVEL.LOW
  const noData = cam.status === 'no_data'
  const waitTone = cam.wait_min >= 12 ? 'rose' : cam.wait_min >= 8 ? 'amber' : 'emerald'
  return (
    <Card className="overflow-hidden">
      <div className="relative bg-slate-900">
        <video
          ref={videoRef}
          src={cam.video}
          muted
          loop
          autoPlay
          playsInline
          preload="auto"
          className="aspect-video w-full object-cover"
        />
        <div className="absolute left-3 top-3 flex items-center gap-2">
          <span className="flex items-center gap-1.5 rounded-md bg-rose-600 px-2 py-0.5 text-[11px] font-semibold tracking-wide text-white">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-white" /> LIVE
          </span>
          <span className="rounded-md bg-slate-900/70 px-2 py-0.5 font-mono text-[11px] text-white">{cam.id}</span>
        </div>
        <div className="absolute right-3 top-3 flex items-center gap-2">
          {busy && (
            <span className="flex items-center gap-1.5 rounded-md bg-slate-900/70 px-2 py-0.5 text-[11px] text-white">
              <Spinner size={11} className="text-white" /> Counting
            </span>
          )}
        </div>
        {!noData && (
          <div className="absolute bottom-3 left-3 flex items-center gap-2">
            <span className="tabular rounded-lg bg-slate-900/80 px-2.5 py-1 text-[13px] font-semibold text-white backdrop-blur">
              {cam.people_total} people
            </span>
            <span className="tabular rounded-lg bg-slate-900/80 px-2.5 py-1 text-[13px] font-medium text-white backdrop-blur">
              {cam.people_in_queue} in queue
            </span>
          </div>
        )}
      </div>

      <div className="space-y-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <h3 className="truncate text-[14px] font-semibold text-slate-900">{cam.name}</h3>
            <p className="truncate text-xs text-slate-500">{cam.zone} · {cam.area_m2} m² · {cam.service_points} screening lanes</p>
          </div>
          {noData ? (
            <Badge tone="slate" dot>Waiting for first count</Badge>
          ) : (
            <Badge tone={lv.tone} dot>{lv.label}</Badge>
          )}
        </div>

        {error && (
          <p className="flex items-start gap-2 rounded-lg bg-rose-50 px-3 py-2 text-[12.5px] text-rose-700">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" /> {error}
          </p>
        )}

        {!noData && (
          <>
            <div className="grid grid-cols-3 gap-3">
              <Metric label="Density" value={cam.density.toFixed(2)} sub="people / m²" tone={lv.tone} />
              <Metric label="Est. wait" value={fmtMin(cam.wait_min)} sub={`${cam.throughput_per_min}/min cleared`} tone={waitTone} />
              <Metric label="Queue" value={MOVEMENT[cam.movement] || '—'} sub={cam.queue_lanes ? `${cam.queue_lanes} lanes` : null} />
            </div>
            <div>
              <Sparkline points={cam.history.map((h) => h.people)} />
              <div className="mt-1 flex items-center justify-between text-[11.5px] text-slate-500">
                <span>People in view, last {cam.history.length} readings</span>
                <span>
                  {cam.status === 'stale' ? <span className="font-medium text-amber-600">Stale · </span> : null}
                  {relTime(cam.observed_at)}
                </span>
              </div>
            </div>
            <p className="text-[11.5px] text-slate-400">
              Median of {cam.samples} reading{cam.samples > 1 ? 's' : ''} · confidence {Math.round((cam.confidence || 0) * 100)}%
            </p>
          </>
        )}
      </div>
    </Card>
  )
}

const ACTION_STYLE = {
  REDIRECT: { tone: 'brand', label: 'Reroute' },
  OPEN_LANES: { tone: 'violet', label: 'Staffing' },
}

function ReroutePanel({ plan, onSend, sending }) {
  const status = plan?.status
  const tone = { action: 'rose', watch: 'amber', normal: 'emerald', no_data: 'slate' }[status] || 'slate'
  const label = { action: 'Action needed', watch: 'Watch', normal: 'Normal', no_data: 'No data' }[status] || ''
  return (
    <Card>
      <CardHeader
        title="Rerouting plan"
        subtitle="Computed from the live queue and each checkpoint's screening rate"
        icon={ArrowRight}
        actions={<Badge tone={tone} dot>{label}</Badge>}
      />
      <div className="space-y-4 p-4 sm:p-5">
        <p className="text-[13.5px] font-medium text-slate-800">{plan.headline}</p>

        {plan.actions.length > 0 ? (
          <ul className="space-y-2.5">
            {plan.actions.map((a, i) => (
              <li key={i} className="flex items-start gap-3 rounded-lg border border-slate-200 bg-slate-50/60 p-3">
                <Badge tone={ACTION_STYLE[a.type]?.tone || 'slate'}>{ACTION_STYLE[a.type]?.label || a.type}</Badge>
                <div className="min-w-0">
                  <p className="text-[13px] font-medium text-slate-900">{a.title}</p>
                  <p className="mt-0.5 text-[12.5px] text-slate-500">{a.detail}</p>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          status !== 'no_data' && <p className="text-[13px] text-slate-500">No steering or staffing changes are needed right now.</p>
        )}

        {status !== 'no_data' && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
            <p className="text-[12.5px] text-slate-500">
              <span className="font-semibold text-slate-800">{fmtNum(plan.recipients.total)}</span> travelers would be notified
              ({fmtNum(plan.recipients.at_risk)} on at-risk flights, {plan.recipients.contacts} real e-mail/SMS contacts).
            </p>
            <Button icon={Send} onClick={onSend} loading={sending} variant={status === 'action' ? 'primary' : 'secondary'}>
              Send reroute advisory
            </Button>
          </div>
        )}
      </div>
    </Card>
  )
}

function FlightsAtRisk({ flights }) {
  return (
    <Card>
      <CardHeader title="Departures affected by the queue" subtitle="Terminal 1, next 2.5 hours, slack before the gate closes" icon={Timer} />
      <Table
        dense
        rowKey="trip_id"
        rows={flights}
        empty={<Empty icon={Timer} title="No departures in the window" text="No Terminal 1 departures are scheduled in the next 2.5 hours." />}
        columns={[
          { key: 'number', label: 'Flight', render: (f) => <span className="whitespace-nowrap font-mono font-medium text-slate-900">{f.number}</span> },
          { key: 'destination', label: 'To' },
          { key: 'gate', label: 'Gate', render: (f) => <span className="font-mono text-slate-600">{f.gate}</span> },
          { key: 'minutes_to_departure', label: 'Departs', align: 'right', render: (f) => `in ${fmtMin(f.minutes_to_departure)}` },
          { key: 'passengers', label: 'Pax', align: 'right', render: (f) => fmtNum(f.passengers) },
          {
            key: 'slack_min',
            label: 'Slack now',
            align: 'right',
            render: (f) => <span className={cx('font-medium', f.slack_min < 10 ? 'text-rose-600' : 'text-slate-700')}>{fmtMin(f.slack_min)}</span>,
          },
          {
            key: 'slack_after_min',
            label: 'After plan',
            align: 'right',
            render: (f) => <span className={cx('font-medium', f.slack_after_min < 10 ? 'text-amber-600' : 'text-emerald-600')}>{fmtMin(f.slack_after_min)}</span>,
          },
          {
            key: 'at_risk',
            label: '',
            render: (f) => (f.at_risk ? <Badge tone="rose" dot>At risk</Badge> : <Badge tone="slate">OK</Badge>),
          },
        ]}
      />
    </Card>
  )
}

function History({ rows }) {
  if (!rows.length) return null
  return (
    <Card>
      <CardHeader title="Advisories sent" subtitle="Recorded in SQLite" icon={Send} />
      <ul className="divide-y divide-slate-100">
        {rows.map((r) => (
          <li key={r.id} className="px-4 py-3 sm:px-5">
            <p className="text-[13px] text-slate-800">{r.summary}</p>
            <p className="mt-0.5 text-[11.5px] text-slate-500">{fmtDateTime(r.created_at)}</p>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function captureFrame(video) {
  if (!video || video.readyState < 2 || !video.videoWidth) return null
  const scale = Math.min(1, FRAME_WIDTH / video.videoWidth)
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(video.videoWidth * scale)
  canvas.height = Math.round(video.videoHeight * scale)
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
  return canvas.toDataURL('image/jpeg', 0.72)
}

export default function CrowdMonitor() {
  const { data, error, reload } = useApi('/crowd/overview', { refreshOn: ['crowd.'], interval: 15000 })
  const terminalId = data?.terminals?.[0]?.id
  const { data: plan, reload: reloadPlan } = useApi(terminalId ? `/crowd/terminals/${terminalId}/plan` : null, {
    refreshOn: ['crowd.'],
    interval: 30000,
  })

  const videos = useRef({})
  const inFlight = useRef(false)
  const [busy, setBusy] = useState({})
  const [camErrors, setCamErrors] = useState({})
  const [sending, setSending] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [result, setResult] = useState(null)
  const [sendError, setSendError] = useState(null)

  const cameras = data?.terminals?.flatMap((t) => t.cameras) ?? []
  const interval = (data?.frame_interval_s || 20) * 1000
  const camIds = cameras.map((c) => c.id).join(',')

  const analyzeAll = useCallback(async () => {
    if (inFlight.current || document.hidden) return
    inFlight.current = true
    try {
      for (const id of camIds.split(',').filter(Boolean)) {
        const image = captureFrame(videos.current[id])
        if (!image) continue
        setBusy((b) => ({ ...b, [id]: true }))
        try {
          await api.post(`/crowd/cameras/${id}/frame`, { image })
          setCamErrors((e) => ({ ...e, [id]: null }))
        } catch (err) {
          setCamErrors((e) => ({ ...e, [id]: err.message }))
        } finally {
          setBusy((b) => ({ ...b, [id]: false }))
        }
      }
    } finally {
      inFlight.current = false
    }
    reload()
    reloadPlan()
  }, [camIds, reload, reloadPlan])

  useEffect(() => {
    if (!camIds) return undefined
    const first = setTimeout(analyzeAll, 2500)
    const id = setInterval(analyzeAll, interval)
    return () => {
      clearTimeout(first)
      clearInterval(id)
    }
  }, [camIds, interval, analyzeAll])

  const send = async () => {
    setConfirm(false)
    setSending(true)
    setSendError(null)
    try {
      const force = plan?.status === 'normal'
      setResult(await api.post(`/crowd/terminals/${terminalId}/reroute`, { force }))
      reload()
      reloadPlan()
    } catch (e) {
      setSendError(e.message)
    } finally {
      setSending(false)
    }
  }

  if (error && !data) {
    return (
      <div className="p-6">
        <Empty icon={AlertTriangle} title="Crowd monitor unavailable" text={error} />
      </div>
    )
  }
  if (!data) return <PageLoader />

  const t = data.terminals[0]
  const vision = data.vision
  const lv = LEVEL[t.level]
  const anyBusy = Object.values(busy).some(Boolean)

  return (
    <div className="space-y-4 p-4 sm:space-y-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="brand"><Video size={12} /> {t.name} · {t.description}</Badge>
          <Badge tone={vision.configured ? 'emerald' : 'rose'} dot>
            {vision.configured ? `Vision: ${vision.model}` : 'Vision model not configured'}
          </Badge>
          <span className="text-[12px] text-slate-500">Frame analysed every {data.frame_interval_s}s</span>
        </div>
        <Button size="sm" variant="secondary" icon={ScanEye} loading={anyBusy} onClick={analyzeAll}>
          Analyse now
        </Button>
      </div>

      {!vision.configured && (
        <div className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-[13px] text-rose-800">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          People counting needs a vision-capable model. Add the Azure OpenAI or Gemini key to server/.env. No numbers are shown until a real count is made.
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <Kpi
          label="People in terminal"
          value={fmtNum(t.total_people)}
          sub={`${t.occupancy_pct}% of ${fmtNum(t.capacity)} capacity (cameras in view)`}
          icon={Users}
        />
        <Kpi
          label="Average density"
          value={t.cameras_live || t.total_people ? `${t.avg_density.toFixed(2)}` : '—'}
          sub={lv ? `${lv.label}, people per m²` : 'Waiting for counts'}
          icon={Gauge}
          tone={lv?.tone === 'rose' ? 'rose' : lv?.tone === 'emerald' ? 'emerald' : 'amber'}
        />
        <Kpi
          label="Longest queue wait"
          value={fmtMin(t.max_wait_min)}
          sub={`${fmtNum(t.queue_people)} people queuing`}
          icon={Timer}
          tone={t.max_wait_min >= 12 ? 'rose' : t.max_wait_min >= 8 ? 'amber' : 'emerald'}
        />
        <Kpi
          label="Cameras live"
          value={`${t.cameras_live}/${t.cameras_total}`}
          sub={t.needs_action ? 'Rerouting recommended' : 'No zone needs action'}
          icon={Video}
          tone={t.needs_action ? 'rose' : 'slate'}
          emphasis={t.needs_action}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2 sm:gap-5">
        {t.cameras.map((c) => (
          <CameraTile
            key={c.id}
            cam={c}
            busy={busy[c.id]}
            error={camErrors[c.id]}
            videoRef={(el) => {
              videos.current[c.id] = el
            }}
          />
        ))}
      </div>

      {sendError && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-[13px] text-rose-800">{sendError}</div>
      )}
      {result && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-[13px] text-emerald-900">
          <p className="font-semibold">Advisory sent</p>
          <p className="mt-0.5">{result.summary}</p>
          <p className="mt-1 text-[12.5px]">
            E-mail sent: {result.delivery.email_sent} · SMS sent: {result.delivery.sms_sent} · failed: {result.delivery.failed}
            {result.delivery.not_configured ? ` · not configured: ${result.delivery.not_configured}` : ''}
          </p>
        </div>
      )}

      {plan && (
        <div className="grid gap-4 xl:grid-cols-5 sm:gap-5">
          <div className="space-y-4 sm:space-y-5 xl:col-span-2">
            <ReroutePanel plan={plan} onSend={() => setConfirm(true)} sending={sending} />
            <History rows={plan.history} />
          </div>
          <div className="xl:col-span-3">
            <FlightsAtRisk flights={plan.flights} />
          </div>
        </div>
      )}

      <LiveFlights
        direction="departures"
        terminalFilter="1"
        title="Live departures from Terminal 1"
        subtitle="Real-time schedule from AviationStack: the inflow that feeds these checkpoints"
      />

      <Modal
        open={confirm}
        onClose={() => setConfirm(false)}
        title="Send reroute advisory"
        subtitle={plan ? `${fmtNum(plan.recipients.total)} travelers on ${plan.flights.filter((f) => f.at_risk).length} at-risk departures` : ''}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirm(false)}>Cancel</Button>
            <Button icon={Send} onClick={send}>Send now</Button>
          </>
        }
      >
        <div className="space-y-3 text-[13px] text-slate-600">
          <p>Each traveler is told which checkpoint has the shorter wait and when to reach security.</p>
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900">
            Real e-mail and SMS go out to the {plan?.recipients.contacts} registered contact travelers (Vishwaa, Lathifunisa, Amal and
            Sushmitha). All other passengers are recorded in the notification log only.
          </p>
        </div>
      </Modal>
    </div>
  )
}
