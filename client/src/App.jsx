import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './components/AppShell'
import { PageLoader } from './components/ui'
import { StreamProvider } from './lib/stream'

const Landing = lazy(() => import('./pages/Landing'))
const Overview = lazy(() => import('./pages/Overview'))
const Incidents = lazy(() => import('./pages/Incidents'))
const IncidentDetail = lazy(() => import('./pages/IncidentDetail'))
const IncidentOrchestration = lazy(() => import('./pages/IncidentOrchestration'))
const Schedule = lazy(() => import('./pages/Schedule'))
const Assets = lazy(() => import('./pages/Assets'))
const CrowdMonitor = lazy(() => import('./pages/CrowdMonitor'))
const TravelerPortal = lazy(() => import('./pages/TravelerPortal'))

const page = (Component) => (
  <Suspense fallback={<PageLoader />}>
    <Component />
  </Suspense>
)

export default function App() {
  return (
    <StreamProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={page(Landing)} />
          <Route path="/traveler" element={page(TravelerPortal)} />
          <Route element={<AppShell />}>
            <Route path="/overview" element={page(Overview)} />
            <Route path="/incidents" element={page(Incidents)} />
            <Route path="/incidents/:id" element={page(IncidentDetail)} />
            <Route path="/incidents/:id/orchestration" element={page(IncidentOrchestration)} />
            <Route path="/orchestration/*" element={<Navigate to="/incidents" replace />} />
            <Route path="/crowd" element={page(CrowdMonitor)} />
            <Route path="/schedule" element={page(Schedule)} />
            <Route path="/assets" element={page(Assets)} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </StreamProvider>
  )
}
