import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Plane, TrainFront, Zap } from 'lucide-react'
import ScenarioLauncher from '../components/ScenarioLauncher'
import { Button, Card, Empty, IncidentStatus, PageLoader, Segmented, SeverityBadge, Table } from '../components/ui'
import { fmtDateTime, fmtNum, relTime } from '../lib/format'
import { useApi } from '../lib/useApi'

const ACTIVE = new Set(['DETECTING', 'ANALYZING', 'PLANNING', 'AWAITING_APPROVAL', 'PROCESSING', 'REPLANNING', 'EXECUTING'])

export default function Incidents() {
  const { data } = useApi('/incidents', { refreshOn: ['incident.'] })
  const [filter, setFilter] = useState('all')
  const [launcher, setLauncher] = useState(false)
  const navigate = useNavigate()
  if (!data) return <PageLoader />

  const rows = data.items.filter((i) =>
    filter === 'all' ? true : filter === 'active' ? ACTIVE.has(i.status) : !ACTIVE.has(i.status),
  )

  const columns = [
    { key: 'id', label: 'Incident', render: (i) => <span className="font-mono text-[12px] font-medium text-slate-600">{i.id}</span> },
    {
      key: 'title',
      label: 'Disruption',
      render: (i) => (
        <div className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-slate-100 text-slate-500">
            {i.mode === 'FLIGHT' ? <Plane size={14} /> : <TrainFront size={14} />}
          </span>
          <div className="min-w-0">
            <p className="truncate font-medium text-slate-900">{i.title}</p>
            <p className="text-[11.5px] text-slate-500">{i.category === 'WEATHER' ? 'Weather feed' : 'Asset-health stream'} · {i.location}</p>
          </div>
        </div>
      ),
    },
    { key: 'severity', label: 'Severity', render: (i) => <SeverityBadge severity={i.severity} /> },
    { key: 'status', label: 'Status', render: (i) => <IncidentStatus status={i.status} /> },
    { key: 'trips', label: 'Services', align: 'right', render: (i) => fmtNum(i.trips_affected) },
    { key: 'pax', label: 'Passengers', align: 'right', render: (i) => fmtNum(i.pax_affected) },
    { key: 'plan', label: 'Plan', align: 'right', render: (i) => `v${i.plan_version}` },
    {
      key: 'created',
      label: 'Detected',
      render: (i) => (
        <div>
          <p className="text-slate-700">{fmtDateTime(i.created_at)}</p>
          <p className="text-[11.5px] text-slate-400">{relTime(i.created_at)}</p>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <Segmented
          value={filter}
          onChange={setFilter}
          options={[
            { value: 'all', label: `All (${data.items.length})` },
            { value: 'active', label: 'Active' },
            { value: 'closed', label: 'Closed' },
          ]}
        />
        <Button icon={Zap} variant="secondary" onClick={() => setLauncher(true)}>Inject event</Button>
      </div>
      <Card>
        <Table
          columns={columns}
          rows={rows}
          onRowClick={(i) => navigate(`/incidents/${i.id}`)}
          empty={
            <Empty
              icon={AlertTriangle}
              title="No incidents"
              text="Disruptions detected from the weather and asset-health feeds appear here."
              action={<Button icon={Zap} onClick={() => setLauncher(true)}>Inject event</Button>}
            />
          }
        />
      </Card>
      <ScenarioLauncher open={launcher} onClose={() => setLauncher(false)} />
    </div>
  )
}
