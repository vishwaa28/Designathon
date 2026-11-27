import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import AppShell from './components/AppShell'
import { PageLoader } from './components/ui'
import { StreamProvider } from './lib/stream'

const Overview = lazy(() => import('./pages/Overview'))
const Incidents = lazy(() => import('./pages/Incidents'))
const IncidentDetail = lazy(() => import('./pages/IncidentDetail'))
const Orchestration = lazy(() => import('./pages/Orchestration'))
const Schedule = lazy(() => import('./pages/Schedule'))
const Assets = lazy(() => import('./pages/Assets'))
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
          <Route path="/traveler" element={page(TravelerPortal)} />
          <Route element={<AppShell />}>
            <Route path="/" element={page(Overview)} />
            <Route path="/incidents" element={page(Incidents)} />
            <Route path="/incidents/:id" element={page(IncidentDetail)} />
            <Route path="/orchestration" element={page(Orchestration)} />
            <Route path="/orchestration/:id" element={page(Orchestration)} />
            <Route path="/schedule" element={page(Schedule)} />
            <Route path="/assets" element={page(Assets)} />
          </Route>
        </Routes>
      </BrowserRouter>
    </StreamProvider>
  )
}
