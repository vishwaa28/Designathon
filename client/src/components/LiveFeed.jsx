import { useEffect, useState } from 'react'
import { Activity, CloudSun, Cpu, Radio } from 'lucide-react'
import { api } from '../lib/api'
import { fmtTime } from '../lib/format'
import { useStream } from '../lib/stream'
import { Card, CardHeader, cx } from './ui'

const SOURCE = {
  WEATHER: { icon: CloudSun, label: 'Weather' },
  ASSET: { icon: Cpu, label: 'Asset health' },
  OPS: { icon: Activity, label: 'Ops status' },
}
const LEVEL = {
  info: 'bg-slate-100 text-slate-500',
  warning: 'bg-amber-50 text-amber-600',
  critical: 'bg-rose-50 text-rose-600',
}

export default function LiveFeed({ className, max = 40 }) {
  const [items, setItems] = useState([])

  useEffect(() => {
    api.get('/feeds/live?limit=40').then((d) => setItems(d.items)).catch(() => {})
  }, [])

  useStream((e) => {
    if (e.type === 'feed') setItems((prev) => [e.data, ...prev].slice(0, max))
    if (e.type === 'simulation.reset') setItems([])
  })

  return (
    <Card className={cx('flex flex-col', className)}>
      <CardHeader
        title="Live feeds"
        subtitle="Weather, asset telemetry and service status"
        icon={Radio}
        actions={
          <span className="flex items-center gap-1.5 text-[11.5px] font-medium text-emerald-600">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            Streaming
          </span>
        }
      />
      <div className="min-h-0 flex-1 divide-y divide-slate-100 overflow-y-auto">
        {items.map((item) => {
          const src = SOURCE[item.source] || SOURCE.OPS
          return (
            <div key={item.id} className="animate-feed-in flex gap-3 px-5 py-2.5">
              <span className={cx('mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md', LEVEL[item.level] || LEVEL.info)}>
                <src.icon size={14} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <p className={cx('truncate text-[12.5px] font-medium', item.level === 'critical' ? 'text-rose-700' : 'text-slate-800')}>
                    {item.title}
                  </p>
                  <span className="tabular shrink-0 text-[11px] text-slate-400">{fmtTime(item.ts)}</span>
                </div>
                {item.detail && <p className="truncate text-[11.5px] text-slate-500">{item.detail}</p>}
              </div>
            </div>
          )
        })}
        {!items.length && <p className="px-5 py-8 text-center text-[13px] text-slate-400">Waiting for feed events…</p>}
      </div>
    </Card>
  )
}
