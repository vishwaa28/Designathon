import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Workflow } from 'lucide-react'
import AgentFlow from '../components/flow/AgentFlow'
import { Button, IncidentStatus, PageLoader, SeverityBadge } from '../components/ui'
import { useApi } from '../lib/useApi'

/** Agent orchestration for one incident, opened from the incident page. Back returns to that incident. */
export default function IncidentOrchestration() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data: inc, error } = useApi(`/incidents/${id}`, {
    refreshOn: ['incident.updated', 'agent.'],
    match: (e) => (e.data.id || e.data.incident_id) === id,
  })

  if (error) {
    return (
      <div className="space-y-3 p-6">
        <p className="text-[13px] text-rose-600">{error}</p>
        <Link to="/incidents" className="text-[13px] font-medium text-brand-600 hover:underline">Back to incidents</Link>
      </div>
    )
  }
  if (!inc) return <PageLoader />

  return (
    <div className="space-y-4 p-4 sm:space-y-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" icon={ArrowLeft} onClick={() => navigate(`/incidents/${inc.id}`)}>
          Back to incident
        </Button>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <Workflow size={16} className="shrink-0 text-slate-400" />
          <h2 className="text-[15px] font-semibold text-slate-900 sm:text-[16px]">Agent orchestration</h2>
          <span className="font-mono text-[12.5px] text-slate-500">{inc.id}</span>
          <SeverityBadge severity={inc.severity} />
          <IncidentStatus status={inc.status} />
        </div>
        <p className="w-full truncate text-[12.5px] text-slate-500 sm:ml-auto sm:w-auto">{inc.title}</p>
      </div>
      <AgentFlow inc={inc} />
    </div>
  )
}
