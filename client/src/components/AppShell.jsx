import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  AlertTriangle,
  CalendarClock,
  ExternalLink,
  LayoutDashboard,
  RotateCcw,
  Workflow,
  Wrench,
  Zap,
} from 'lucide-react'
import { api } from '../lib/api'
import { useStreamStatus } from '../lib/stream'
import { useApi } from '../lib/useApi'
import ProviderSwitch from './ProviderSwitch'
import ScenarioLauncher from './ScenarioLauncher'
import { Button, cx } from './ui'

const NAV = [
  { to: '/', label: 'Operations overview', icon: LayoutDashboard, end: true },
  { to: '/incidents', label: 'Incidents', icon: AlertTriangle, badge: 'awaiting' },
  { to: '/orchestration', label: 'Agent orchestration', icon: Workflow },
  { to: '/schedule', label: 'Schedule & bookings', icon: CalendarClock },
  { to: '/assets', label: 'Assets & work orders', icon: Wrench },
]

const TITLES = {
  '/': ['Operations overview', 'Live network picture across air and rail'],
  '/incidents': ['Incidents', 'Detected disruptions and recovery decisions'],
  '/orchestration': ['Agent orchestration', 'Execution graph of the recovery workflow'],
  '/schedule': ['Schedule & bookings', 'Flights, trains, crew and passengers'],
  '/assets': ['Assets & work orders', 'Infrastructure health and field maintenance'],
}

export function Logo({ dark }) {
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="h-8 w-8 shrink-0">
        <rect width="32" height="32" rx="8" fill="#2F5BEA" />
        <path d="M8 22 L16 8 L24 22" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M11.5 17.5 H20.5" stroke="#9DB6FF" strokeWidth="2.6" strokeLinecap="round" />
      </svg>
      <div className="leading-tight">
        <p className={cx('text-[15px] font-semibold tracking-tight', dark ? 'text-white' : 'text-slate-900')}>ARRO</p>
        <p className={cx('text-[11px]', dark ? 'text-slate-400' : 'text-slate-500')}>Disruption Recovery Center</p>
      </div>
    </div>
  )
}

function Clock() {
  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="tabular text-right leading-tight">
      <p className="text-[13px] font-semibold text-slate-800">
        {now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
      </p>
      <p className="text-[11px] text-slate-500">{now.toLocaleDateString([], { weekday: 'short', day: '2-digit', month: 'short' })} · IST</p>
    </div>
  )
}

export default function AppShell() {
  const [launcher, setLauncher] = useState(false)
  const [resetting, setResetting] = useState(false)
  const connected = useStreamStatus()
  const location = useLocation()
  const { data: incidents } = useApi('/incidents', { refreshOn: ['incident.'] })
  const awaiting = (incidents?.items || []).filter((i) => i.status === 'AWAITING_APPROVAL').length

  const base = '/' + (location.pathname.split('/')[1] || '')
  const [title, subtitle] = TITLES[base] || TITLES['/']

  const reset = async () => {
    if (!window.confirm('Reset the simulated operating day? All incidents, plans and notifications will be cleared.')) return
    setResetting(true)
    try {
      await api.post('/simulation/reset')
      window.location.assign('/')
    } finally {
      setResetting(false)
    }
  }

  return (
    <div className="flex h-full">
      <aside className="flex w-[244px] shrink-0 flex-col bg-navy-900">
        <div className="px-5 pb-6 pt-5">
          <Logo dark />
        </div>
        <p className="px-5 pb-2 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-slate-500">Operations</p>
        <nav className="flex flex-col gap-0.5 px-3">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cx(
                  'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors',
                  isActive ? 'bg-white/[0.08] text-white' : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-200',
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && <span className="absolute left-0 top-1.5 h-[calc(100%-12px)] w-[3px] rounded-r bg-brand-400" />}
                  <item.icon size={17} className={isActive ? 'text-brand-300' : ''} />
                  <span className="flex-1">{item.label}</span>
                  {item.badge === 'awaiting' && awaiting > 0 && (
                    <span className="rounded-full bg-amber-400 px-1.5 text-[11px] font-semibold text-navy-950">{awaiting}</span>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <p className="px-5 pb-2 pt-6 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-slate-500">Travelers</p>
        <nav className="px-3">
          <a
            href="/traveler"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"
          >
            <ExternalLink size={17} />
            Traveler self-service
          </a>
        </nav>

        <div className="mt-auto space-y-3 border-t border-white/[0.06] p-4">
          <div className="flex items-center gap-2 text-[12px] text-slate-400">
            <span className={cx('h-2 w-2 rounded-full', connected ? 'bg-emerald-400' : 'bg-rose-400')} />
            {connected ? 'Live feeds connected' : 'Reconnecting to feeds'}
          </div>
          <button
            onClick={reset}
            disabled={resetting}
            className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-[12px] text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"
          >
            <RotateCcw size={14} className={resetting ? 'animate-spin' : ''} />
            Reset simulated day
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[64px] shrink-0 items-center gap-4 border-b border-slate-200 bg-white px-6">
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-[16px] font-semibold text-slate-900">{title}</h1>
            <p className="truncate text-[12px] text-slate-500">{subtitle}</p>
          </div>
          <ProviderSwitch />
          <div className="h-8 w-px bg-slate-200" />
          <Clock />
          <Button icon={Zap} onClick={() => setLauncher(true)}>Inject event</Button>
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-navy-800 text-[12px] font-semibold text-white" title="Duty controller">
            DC
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
      <ScenarioLauncher open={launcher} onClose={() => setLauncher(false)} />
    </div>
  )
}
