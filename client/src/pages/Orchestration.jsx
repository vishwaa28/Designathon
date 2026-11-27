import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Background, Controls, MarkerType, ReactFlow } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { ExternalLink, ListTree, Workflow, Zap } from 'lucide-react'
import ExecutionLog from '../components/flow/ExecutionLog'
import { AgentNode, TerminalNode } from '../components/flow/AgentNode'
import Inspector from '../components/flow/Inspector'
import ScenarioLauncher from '../components/ScenarioLauncher'
import { Button, Card, CardHeader, IncidentStatus, PageLoader, cx } from '../components/ui'
import { fmtDuration } from '../lib/format'
import { useApi } from '../lib/useApi'

const POSITIONS = {
  __start__: { x: 0, y: 167 },
  detection: { x: 160, y: 150 },
  impact_analysis: { x: 430, y: 35 },
  infra_triage: { x: 430, y: 265 },
  recovery_planner: { x: 700, y: 150 },
  tradeoff_analyst: { x: 970, y: 150 },
  controller_approval: { x: 1240, y: 150 },
  traveler_notification: { x: 1510, y: 150 },
  __end__: { x: 1780, y: 167 },
}

const EDGE_ROUTING = {
  'detection->__end__': { sh: 'b-out', th: 'b-in', label: 'No disruption', offset: 210 },
  'controller_approval->impact_analysis': { sh: 't-out', th: 't-in', label: 'New information', offset: 30 },
  'controller_approval->infra_triage': { sh: 'b-out', th: 'b-in', label: 'New information', offset: 34 },
  'controller_approval->recovery_planner': { sh: 'b-out', th: 'b-in', label: 'Re-plan', offset: 40 },
  'controller_approval->__end__': { sh: 't-out', th: 't-in', label: 'Rejected', offset: 60 },
  'controller_approval->traveler_notification': { label: 'Approved' },
  'detection->impact_analysis': { label: 'Disruption' },
  'detection->infra_triage': { label: 'Disruption' },
}

const REASSESS = new Set(['restoration_delayed', 'early_restoration'])
const REPLAN_UPDATES = new Set(['crew_shortage', 'inventory_drop'])
const ENDED = new Set(['RESOLVED', 'REJECTED', 'NO_ACTION'])

const nodeTypes = { agent: AgentNode, terminal: TerminalNode }

function buildFlow(graph, inc, selectedNode) {
  const trace = inc?.trace || []
  const byNode = {}
  trace.forEach((e) => {
    ;(byNode[e.node] ||= []).push(e)
  })
  const approvals = (byNode.controller_approval || []).map((e) => e.output || {})
  const ended = inc && ENDED.has(inc.status)

  const nodeStatus = (id) => {
    if (id === '__start__') return trace.length ? 'completed' : 'idle'
    if (id === '__end__') return ended ? 'completed' : 'idle'
    const runs = byNode[id]
    return runs ? runs[runs.length - 1].status : 'idle'
  }
  const ran = (id) => nodeStatus(id) !== 'idle'

  const traversed = (e) => {
    const key = `${e.source}->${e.target}`
    if (key === 'detection->__end__') return inc?.status === 'NO_ACTION'
    if (key === 'controller_approval->__end__') return inc?.status === 'REJECTED'
    if (key === 'controller_approval->recovery_planner') return approvals.some((o) => o.action === 'replan' || REPLAN_UPDATES.has(o.type))
    if (key === 'controller_approval->impact_analysis' || key === 'controller_approval->infra_triage')
      return approvals.some((o) => REASSESS.has(o.type))
    return ran(e.source) && ran(e.target)
  }

  const nodes = graph.nodes.map((n) => {
    const runs = byNode[n.id] || []
    const last = runs[runs.length - 1]
    return {
      id: n.id,
      type: n.kind === 'terminal' ? 'terminal' : 'agent',
      position: POSITIONS[n.id] || { x: 0, y: 0 },
      selected: selectedNode === n.id,
      data: { kind: n.kind, status: nodeStatus(n.id), runs: runs.length, duration: last?.duration_ms },
    }
  })

  const edges = graph.edges.map((e) => {
    const key = `${e.source}->${e.target}`
    const r = EDGE_ROUTING[key] || {}
    const done = inc && traversed(e)
    const active = done && nodeStatus(e.target) === 'running'
    const color = done ? '#2f5bea' : '#cbd5e1'
    return {
      id: key,
      source: e.source,
      target: e.target,
      sourceHandle: r.sh || 'out',
      targetHandle: r.th || 'in',
      type: 'smoothstep',
      animated: active || (done && nodeStatus(e.target) === 'waiting'),
      pathOptions: { offset: r.offset ?? 20, borderRadius: 14 },
      label: r.label,
      labelStyle: { fontSize: 10.5, fill: done ? '#1f3ba3' : '#94a3b8', fontWeight: 500 },
      labelBgPadding: [6, 3],
      labelBgBorderRadius: 4,
      labelBgStyle: { fill: done ? '#eef3fe' : '#f8fafc' },
      style: { stroke: color, strokeWidth: done ? 2.25 : 1.5, strokeDasharray: e.conditional && !done ? '5 4' : undefined },
      markerEnd: { type: MarkerType.ArrowClosed, color, width: 16, height: 16 },
    }
  })
  return { nodes, edges, byNode }
}

export default function Orchestration() {
  const { id: paramId } = useParams()
  const navigate = useNavigate()
  const { data: graph } = useApi('/agents/graph')
  const { data: list } = useApi('/incidents', { refreshOn: ['incident.created', 'simulation.'] })
  const incidentId = paramId || list?.items?.[0]?.id
  const { data: inc } = useApi(incidentId ? `/incidents/${incidentId}` : null, {
    refreshOn: ['agent.', 'incident.updated'],
    match: (e) => (e.data.id || e.data.incident_id) === incidentId,
  })
  const [selectedNode, setSelectedNode] = useState('detection')
  const [selectedExec, setSelectedExec] = useState(null)
  const [launcher, setLauncher] = useState(false)

  const flow = useMemo(() => (graph ? buildFlow(graph, inc, selectedNode) : null), [graph, inc, selectedNode])
  if (!graph || !list) return <PageLoader />

  const trace = inc?.trace || []
  const calls = trace.flatMap((e) => e.llm || [])
  const totalMs = trace.reduce((a, e) => a + (e.node === 'controller_approval' ? 0 : e.duration_ms || 0), 0)
  const nodeMeta = graph.nodes.find((n) => n.id === selectedNode)
  const execs = flow.byNode[selectedNode] || []
  const exec = selectedExec && selectedExec.node === selectedNode ? execs.find((e) => e.id === selectedExec.id) : null

  return (
    <div className="space-y-5 p-6">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-[12.5px] font-medium text-slate-500">Incident</span>
          <select
            value={incidentId || ''}
            onChange={(e) => navigate(`/orchestration/${e.target.value}`)}
            className="h-9 min-w-[320px] rounded-lg border border-slate-300 bg-white px-3 text-[13px] focus:border-brand-500 focus:outline-none"
          >
            {!list.items.length && <option value="">No incidents yet</option>}
            {list.items.map((i) => (
              <option key={i.id} value={i.id}>
                {i.id} · {i.title}
              </option>
            ))}
          </select>
          {inc && <IncidentStatus status={inc.status} />}
        </div>
        <div className="ml-auto flex items-center gap-2">
          {inc && (
            <Button variant="secondary" icon={ExternalLink} onClick={() => navigate(`/incidents/${inc.id}`)}>
              Incident workspace
            </Button>
          )}
          <Button icon={Zap} onClick={() => setLauncher(true)}>Inject event</Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        {[
          ['Node executions', trace.length],
          ['Plan versions', inc?.plan_version ?? 0],
          ['Model calls', calls.length ? `${calls.filter((c) => c.ok).length} ok / ${calls.filter((c) => !c.ok).length} fallback` : '0'],
          ['Agent processing time', fmtDuration(totalMs)],
          ['Graph', `${graph.nodes.length - 2} nodes · ${graph.edges.length} edges`],
        ].map(([k, v]) => (
          <Card key={k} className="px-4 py-3">
            <p className="text-[11.5px] font-medium text-slate-500">{k}</p>
            <p className="tabular mt-0.5 text-[16px] font-semibold text-slate-900">{v}</p>
          </Card>
        ))}
      </div>

      <Card className="overflow-hidden">
        <CardHeader
          title="Recovery workflow"
          subtitle="LangGraph state graph · parallel fan-out, human-in-the-loop interrupt and re-planning loops"
          icon={Workflow}
          actions={
            <div className="flex items-center gap-3 text-[11.5px] text-slate-500">
              {[
                ['bg-brand-500', 'Running'],
                ['bg-emerald-500', 'Completed'],
                ['bg-amber-500', 'Waiting'],
                ['bg-slate-300', 'Idle'],
              ].map(([c, l]) => (
                <span key={l} className="flex items-center gap-1.5">
                  <span className={cx('h-2 w-2 rounded-full', c)} /> {l}
                </span>
              ))}
            </div>
          }
        />
        <div className="h-[500px] bg-[#fafbfd]">
          <ReactFlow
            nodes={flow.nodes}
            edges={flow.edges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.06 }}
            minZoom={0.3}
            maxZoom={1.6}
            nodesConnectable={false}
            nodesDraggable
            onNodeClick={(_, n) => {
              setSelectedNode(n.id)
              setSelectedExec(null)
            }}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={18} size={1.2} color="#d5dbe5" />
            <Controls showInteractive={false} position="bottom-left" />
          </ReactFlow>
        </div>
      </Card>

      <div className="grid items-start gap-5 xl:grid-cols-[1fr_420px]">
        <Card>
          <CardHeader title="Execution log" subtitle="Chronological node executions for this incident thread" icon={ListTree} />
          <ExecutionLog
            trace={trace}
            selectedId={exec?.id}
            onSelect={(e) => {
              setSelectedNode(e.node)
              setSelectedExec(e)
            }}
          />
        </Card>
        <Card className="max-h-[720px] overflow-y-auto xl:sticky xl:top-4">
          <Inspector
            nodeId={selectedNode}
            nodeMeta={nodeMeta}
            executions={execs}
            selectedExec={exec}
            onSelectExec={setSelectedExec}
          />
        </Card>
      </div>
      <ScenarioLauncher open={launcher} onClose={() => setLauncher(false)} />
    </div>
  )
}
