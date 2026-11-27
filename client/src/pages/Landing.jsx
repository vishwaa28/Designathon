import { Link } from 'react-router-dom'
import { Activity, ArrowRight, BellRing, LogIn, Mic, Network, Users } from 'lucide-react'
import { Logo } from '../components/AppShell'

const FEATURES = [
  {
    icon: Activity,
    title: 'Detect early',
    text: 'Weather, runway, signalling and asset-health feeds are watched against live thresholds, so a disruption is flagged the moment it starts.',
  },
  {
    icon: Network,
    title: 'See the cascade',
    text: 'Delayed aircraft, missed connections, crew duty limits and rail corridors are traced across the whole Chennai network.',
  },
  {
    icon: Users,
    title: 'Decide with confidence',
    text: 'Three scored recovery plans with a clear trade-off. The controller approves, overrides or re-plans as new information arrives.',
  },
  {
    icon: BellRing,
    title: 'Reach every traveler',
    text: 'E-mail and SMS go out as soon as a plan is approved, and travelers can rebook or talk to a voice assistant in English, Tamil or Telugu.',
  },
]

const focusRing = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-300 focus-visible:ring-offset-2 focus-visible:ring-offset-navy-950'

export default function Landing() {
  return (
    <div className="relative isolate min-h-full overflow-x-hidden bg-navy-950 text-white">
      {/* Backdrop: fading grid and brand glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)',
          backgroundSize: '56px 56px',
          maskImage: 'radial-gradient(ellipse 80% 70% at 70% 35%, black 20%, transparent 75%)',
          WebkitMaskImage: 'radial-gradient(ellipse 80% 70% at 70% 35%, black 20%, transparent 75%)',
        }}
      />
      <div aria-hidden className="pointer-events-none absolute -right-40 -top-40 -z-10 h-[620px] w-[620px] rounded-full bg-brand-600/20 blur-3xl" />

      <header className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-4 sm:px-8 sm:py-6">
        <Link to="/" className={`rounded-lg ${focusRing}`} aria-label="ARRO home">
          <Logo dark />
        </Link>
        <nav className="flex items-center gap-2 sm:gap-3">
          
          
        </nav>
      </header>

      <main>
        <section className="mx-auto grid max-w-7xl items-center gap-10 px-4 pb-14 pt-8 sm:px-8 sm:pt-12 lg:min-h-[calc(100vh-200px)] lg:grid-cols-[1.05fr_0.95fr] lg:gap-6 lg:pb-20 lg:pt-6">
          <div className="max-w-2xl">

            <h1 className="mt-6 text-[38px] font-semibold leading-[1.08] tracking-tight sm:text-5xl lg:text-[58px]">
              Recover from disruption
              <span className="block bg-gradient-to-r from-brand-300 to-sky-300 bg-clip-text text-transparent">before travelers feel it.</span>
            </h1>

            <p className="mt-5 max-w-xl text-[15px] leading-relaxed text-slate-300 sm:text-[17px]">
              ARRO is an agent-driven control center for airlines, airports and rail. It detects a disruption, maps the knock-on impact, proposes
              scored recovery plans and keeps every affected traveler informed, with a duty controller approving each decision.
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center">
              <Link
                to="/overview"
                className={`inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-brand-500 px-6 text-[14.5px] font-semibold text-white shadow-lg shadow-brand-900/40 transition-colors hover:bg-brand-400 ${focusRing}`}
              >
                Open control center <ArrowRight size={17} />
              </Link>
              
            </div>

            <p className="mt-5 text-[12.5px] text-slate-400">
              Travelers get updates and self-service in <span className="text-slate-200">English</span>,{' '}
              <span className="text-slate-200">தமிழ்</span> and <span className="text-slate-200">తెలుగు</span>.
            </p>
          </div>

          {/* Animated radar */}
          <div className="relative mx-auto aspect-square w-full max-w-[320px] sm:max-w-[460px] lg:max-w-[600px]">
            <div aria-hidden className="absolute inset-[6%] rounded-full bg-brand-500/25 blur-3xl" />
            {/* The artwork keeps its rings near the middle of its canvas, so it is scaled up inside a round radar disc */}
            <div className="absolute inset-0 overflow-hidden rounded-full border border-white/10 bg-[radial-gradient(circle_at_center,rgba(47,91,234,0.22),rgba(10,17,29,0.7)_72%)] shadow-[0_0_80px_-20px_rgba(47,91,234,0.5)]">
              <img
                src="/flight-radar.svg"
                alt="Animated radar showing aircraft circling a hub airport"
                className="pointer-events-none absolute inset-0 h-full w-full scale-[1.55] select-none"
                draggable={false}
              />
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-8 sm:pb-20">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 lg:gap-4">
            {FEATURES.map((f) => (
              <div key={f.title} className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500/15 text-brand-300">
                  <f.icon size={19} />
                </span>
                <h2 className="mt-4 text-[15px] font-semibold text-white">{f.title}</h2>
                <p className="mt-1.5 text-[13px] leading-relaxed text-slate-400">{f.text}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-white/[0.06]">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-5 text-[12px] text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <span>ARRO · Airline and Rail Recovery Orchestrator</span>
          <span>Demo environment with simulated operations data</span>
        </div>
      </footer>
    </div>
  )
}
