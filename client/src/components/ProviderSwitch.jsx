import { useState } from 'react'
import { api } from '../lib/api'
import { useApi } from '../lib/useApi'
import { cx } from './ui'

function GeminiMark() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5">
      <path d="M12 2c.6 5.2 4.8 9.4 10 10-5.2.6-9.4 4.8-10 10-.6-5.2-4.8-9.4-10-10 5.2-.6 9.4-4.8 10-10z" fill="#4285F4" />
    </svg>
  )
}

function AzureMark() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5">
      <path d="M9.5 3h5L8 21H3z" fill="#0078D4" />
      <path d="M14.5 6.5 21 21h-9.5l3.2-3.6-3.4-.1z" fill="#50A0E8" />
    </svg>
  )
}

export default function ProviderSwitch() {
  const { data, setData } = useApi('/settings/llm', { refreshOn: ['settings.'] })
  const [error, setError] = useState(null)
  if (!data) return null

  const choose = async (id) => {
    if (id === data.active) return
    try {
      setData(await api.put('/settings/llm', { provider: id }))
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="flex items-center gap-2">
      <span className="hidden text-[11.5px] font-medium uppercase tracking-wide text-slate-400 xl:inline">Model</span>
      <div className="inline-flex rounded-lg bg-slate-100 p-0.5" title={error || undefined}>
        {data.providers.map((p) => {
          const active = data.active === p.id
          return (
            <button
              key={p.id}
              onClick={() => p.configured && choose(p.id)}
              disabled={!p.configured}
              title={p.configured ? `${p.label} · ${p.model}` : `${p.label}: API key not configured`}
              className={cx(
                'flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[12.5px] font-medium transition-all',
                active ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700',
                !p.configured && 'cursor-not-allowed opacity-45 hover:text-slate-500',
              )}
            >
              {p.id === 'gemini' ? <GeminiMark /> : <AzureMark />}
              {p.id === 'gemini' ? 'Gemini' : 'Azure Foundry'}
              {active && <span className="font-mono text-[10.5px] text-slate-400">{p.model}</span>}
            </button>
          )
        })}
      </div>
    </div>
  )
}
