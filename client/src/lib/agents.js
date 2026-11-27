import { CircleDot, Network, Radar, Route, Scale, Send, UserCheck, Wrench } from 'lucide-react'

export const AGENT_META = {
  __start__: { title: 'Feed event', icon: CircleDot, color: '#64748b' },
  detection: { title: 'Disruption Detection', icon: Radar, color: '#2f5bea' },
  impact_analysis: { title: 'Impact Analysis', icon: Network, color: '#7c3aed' },
  infra_triage: { title: 'Infrastructure Triage', icon: Wrench, color: '#ea580c' },
  recovery_planner: { title: 'Recovery Planner', icon: Route, color: '#0891b2' },
  tradeoff_analyst: { title: 'Trade-off Analyst', icon: Scale, color: '#0d9488' },
  controller_approval: { title: 'Controller Approval', icon: UserCheck, color: '#d97706' },
  traveler_notification: { title: 'Traveler Notification', icon: Send, color: '#16a34a' },
  __end__: { title: 'Complete', icon: CircleDot, color: '#64748b' },
}

export const IN_PROGRESS = new Set(['DETECTING', 'ANALYZING', 'PLANNING', 'PROCESSING', 'REPLANNING', 'EXECUTING'])

export function providerLabel(p) {
  if (p === 'azure') return 'Azure AI Foundry'
  if (p === 'gemini') return 'Google Gemini'
  return 'Rule engine'
}
