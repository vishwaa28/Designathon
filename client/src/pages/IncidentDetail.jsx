import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ClipboardList, ListTree, Loader2, MapPin, Plane, Workflow } from 'lucide-react'
import DetectionPanel from '../components/incident/DetectionPanel'
import ImpactPanel from '../components/incident/ImpactPanel'
import InfraPanel from '../components/incident/InfraPanel'
import Lifecycle from '../components/incident/Lifecycle'
import NotificationsPanel from '../components/incident/NotificationsPanel'
import OptionsPanel from '../components/incident/OptionsPanel'
import ExecutionLog from '../components/flow/ExecutionLog'
import { Badge, Card, CardHeader, IncidentStatus, PageLoader, SeverityBadge, Tabs } from '../components/ui'
import { AGENT_META, IN_PROGRESS } from '../lib/agents'
import { fmtDateTime, fmtNum, relTime } from '../lib/format'
import { useApi } from '../lib/useApi'

export default function IncidentDetail() {
  const { id } = useParams()
  const { data: inc, error } = useApi(`/incidents/${id}`, {
    refreshOn: ['incident.updated', 'agent.', 'work_order.', 'notifications.'],
    match: (e) => (e.data.id || e.data.incident_id) === id || e.type.startsWith('work_order'),
  })
  const [params] = useSearchParams()
  const [tab, setTab] = useState(params.get('tab'))

  if (error) return <p className="p-6 text-[13px] text-rose-600">{error}</p>
  if (!inc) return <PageLoader />

  const awaiting = inc.status === 'AWAITING_APPROVAL'
  const activeTab = tab ?? (awaiting ? 'options' : 'overview')
  const running = [...(inc.trace || [])].reverse().find((e) => e.status === 'running')
  const busy = IN_PROGRESS.has(inc.status)

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'impact', label: 'Impact', badge: inc.impact ? fmtNum(inc.impact.summary.pax_affected) : null },
    { id: 'options', label: 'Recovery options', badge: awaiting ? 'Decision' : inc.options?.length || null, badgeTone: awaiting ? 'amber' : undefined },
    { id: 'infra', label: 'Infrastructure & work order' },
    { id: 'notifications', label: 'Traveler notifications', badge: inc.notifications ? fmtNum(inc.notifications.total) : null },
    { id: 'audit', label: 'Audit trail', badge: inc.trace?.length || null },
  ]

  return (
    <div className="space-y-4 p-4 sm:space-y-5 sm:p-6">
      <div>
        <Link to="/incidents" className="inline-flex items-center gap-1 text-[12.5px] font-medium text-slate-500 hover:text-slate-800">
          <ArrowLeft size={14} /> Incidents
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[12.5px] text-slate-500">{inc.id}</span>
              <SeverityBadge severity={inc.severity} />
              <IncidentStatus status={inc.status} />
              <Badge tone={inc.category === 'WEATHER' ? 'sky' : 'orange'}>{inc.category === 'WEATHER' ? 'Weather' : 'Asset health'}</Badge>
            </div>
            <h2 className="mt-1.5 flex items-start gap-2 text-[17px] font-semibold leading-snug tracking-tight text-slate-900 sm:items-center sm:text-[20px]">
              <Plane size={20} className="mt-0.5 shrink-0 text-slate-400 sm:mt-0" />
              {inc.title}
            </h2>
            <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px] text-slate-500">
              <span className="flex items-center gap-1"><MapPin size={13} /> {inc.detection?.location_label || inc.location}</span>
              <span>Detected {fmtDateTime(inc.created_at)} ({relTime(inc.created_at)})</span>
              <span>Plan v{inc.plan_version}</span>
              {inc.work_order_id && (
                <span className="flex items-center gap-1"><ClipboardList size={13} /> {inc.work_order_id}</span>
              )}
            </div>
          </div>
          <Link
            to={`/incidents/${inc.id}/orchestration`}
            className="inline-flex h-9 shrink-0 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 text-[13px] font-medium text-slate-700 shadow-sm transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
          >
            <Workflow size={15} /> Agent orchestration
            {inc.trace?.length ? <span className="rounded-full bg-slate-100 px-1.5 text-[11px] font-semibold text-slate-600">{inc.trace.length}</span> : null}
          </Link>
        </div>
      </div>

      <Card className="px-4 py-4 sm:px-6">
        <Lifecycle inc={inc} />
        {busy && (
          <div className="mt-4 flex items-center gap-2.5 rounded-lg bg-brand-50 px-3.5 py-2 text-[12.5px] text-brand-800">
            <Loader2 size={14} className="animate-spin" />
            {running ? (
              <span><span className="font-semibold">{AGENT_META[running.node]?.title}</span> is working on plan v{running.plan_version}…</span>
            ) : (
              <span>Workflow in progress…</span>
            )}
          </div>
        )}
        {inc.status === 'FAILED' && <p className="mt-4 rounded-lg bg-rose-50 px-3.5 py-2 text-[12.5px] text-rose-700">{inc.error}</p>}
      </Card>

      <Tabs tabs={tabs} value={activeTab} onChange={setTab} />

      {activeTab === 'overview' && <DetectionPanel inc={inc} onOpenTab={setTab} />}
      {activeTab === 'impact' && <ImpactPanel inc={inc} />}
      {activeTab === 'options' && <OptionsPanel inc={inc} />}
      {activeTab === 'infra' && <InfraPanel inc={inc} />}
      {activeTab === 'notifications' && <NotificationsPanel inc={inc} />}
      {activeTab === 'audit' && (
        <Card>
          <CardHeader title="Agent execution log" subtitle="Every node execution, model call and controller action is recorded" icon={ListTree} />
          <ExecutionLog trace={inc.trace} />
        </Card>
      )}
    </div>
  )
}
