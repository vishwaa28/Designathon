import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CloudLightning, Droplets, Plane, Signal, TrainFront, Zap } from 'lucide-react'
import { api } from '../lib/api'
import { useApi } from '../lib/useApi'
import { Badge, Button, Modal, Segmented, cx } from './ui'

const ICONS = {
  'wx-del-thunderstorm': CloudLightning,
  'sig-ndls-agc': Signal,
  'aog-bom-hydraulic': Plane,
  'flood-csmt-pune': Droplets,
}

export default function ScenarioLauncher({ open, onClose }) {
  const { data } = useApi(open ? '/feeds/scenarios' : null)
  const [selected, setSelected] = useState('wx-del-thunderstorm')
  const [destination, setDestination] = useState('incident')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  const launch = async () => {
    setBusy(true)
    setError(null)
    try {
      const inc = await api.post('/feeds/trigger', { scenario_id: selected })
      onClose()
      navigate(destination === 'flow' ? `/orchestration/${inc.id}` : `/incidents/${inc.id}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      width="max-w-2xl"
      title="Inject feed event"
      subtitle="Push a simulated weather or asset-health event into the live feed. The detection agent picks it up immediately."
      footer={
        <>
          <div className="mr-auto flex items-center gap-2 text-[12.5px] text-slate-500">
            Open
            <Segmented
              size="sm"
              value={destination}
              onChange={setDestination}
              options={[
                { value: 'incident', label: 'Incident workspace' },
                { value: 'flow', label: 'Agent flow' },
              ]}
            />
          </div>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button icon={Zap} loading={busy} onClick={launch}>Inject event</Button>
        </>
      }
    >
      <div className="grid gap-2.5">
        {(data?.items || []).map((s) => {
          const Icon = ICONS[s.id] || Zap
          const active = selected === s.id
          return (
            <button
              key={s.id}
              onClick={() => setSelected(s.id)}
              className={cx(
                'flex gap-3.5 rounded-xl border p-3.5 text-left transition-all',
                active ? 'border-brand-500 bg-brand-50/50 ring-2 ring-brand-100' : 'border-slate-200 hover:border-slate-300',
              )}
            >
              <span
                className={cx(
                  'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
                  s.category === 'WEATHER' ? 'bg-sky-50 text-sky-600' : 'bg-orange-50 text-orange-600',
                )}
              >
                <Icon size={19} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-[13.5px] font-semibold text-slate-900">{s.title}</p>
                  <Badge tone={s.category === 'WEATHER' ? 'sky' : 'orange'}>
                    {s.category === 'WEATHER' ? 'Weather' : 'Asset health'}
                  </Badge>
                  <Badge>
                    {s.mode === 'FLIGHT' ? <Plane size={11} /> : <TrainFront size={11} />}
                    {s.mode === 'FLIGHT' ? 'Air' : 'Rail'}
                  </Badge>
                </div>
                <p className="mt-1 text-[12.5px] leading-relaxed text-slate-600">{s.description}</p>
                <p className="mt-1.5 text-[11.5px] text-slate-400">Source: {s.source}</p>
              </div>
            </button>
          )
        })}
      </div>
      {error && <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-[13px] text-rose-700">{error}</p>}
    </Modal>
  )
}
