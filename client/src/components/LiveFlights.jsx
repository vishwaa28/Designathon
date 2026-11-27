import { useEffect, useState } from 'react'
import { ArrowDownToLine, ArrowUpFromLine, Plane, RefreshCw } from 'lucide-react'
import { api } from '../lib/api'
import { fmtNum, relTime } from '../lib/format'
import { useApi } from '../lib/useApi'
import { Badge, Button, Card, CardHeader, Empty, Segmented, Spinner, Table, cx } from './ui'

const STATUS = {
  scheduled: { tone: 'sky', label: 'Scheduled' },
  active: { tone: 'emerald', label: 'In air' },
  landed: { tone: 'slate', label: 'Landed' },
  cancelled: { tone: 'rose', label: 'Cancelled' },
  incident: { tone: 'rose', label: 'Incident' },
  diverted: { tone: 'violet', label: 'Diverted' },
  unknown: { tone: 'slate', label: 'Unknown' },
}
const SOURCE = {
  live: { tone: 'emerald', label: 'Live from AviationStack' },
  cache: { tone: 'sky', label: 'Cached' },
  'stale-cache': { tone: 'amber', label: 'Stale cache' },
}
const PAGE = 25

function hhmm(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' })
}

export default function LiveFlights({
  direction: initial = 'departures',
  terminalFilter,
  title = 'Live flights at Chennai (MAA)',
  subtitle = 'Real-time flight data from AviationStack',
  className,
}) {
  const [direction, setDirection] = useState(initial)
  const [scope, setScope] = useState('upcoming')
  const [limit, setLimit] = useState(PAGE)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshError, setRefreshError] = useState(null)
  const [clock, setClock] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setClock(Date.now()), 60000)
    return () => clearInterval(id)
  }, [])
  const path = `/flights/live?direction=${direction}`
  const { data, error, loading, setData } = useApi(path, { interval: 120000 })

  const refresh = async () => {
    setRefreshing(true)
    setRefreshError(null)
    try {
      setData(await api.get(`${path}&refresh=true`))
    } catch (e) {
      setRefreshError(e.message)
    } finally {
      setRefreshing(false)
    }
  }

  const out = direction === 'departures'
  const cutoff = clock - 30 * 60 * 1000
  let rows = (data?.items ?? []).map((r) => ({ ...r, id: `${r.flight}-${r.scheduled}` }))
  if (terminalFilter) rows = rows.filter((r) => String(r.terminal) === String(terminalFilter))
  if (scope === 'upcoming') rows = rows.filter((r) => new Date(r.estimated).getTime() >= cutoff && r.status !== 'landed')
  const shown = rows.slice(0, limit)
  const src = data && (SOURCE[data.source] || SOURCE.cache)

  const columns = [
    {
      key: 'flight',
      label: 'Flight',
      render: (r) => (
        <div>
          <span className="font-mono font-semibold text-slate-900">{r.flight}</span>
          <p className="max-w-[150px] truncate text-[11.5px] text-slate-500">{r.airline}</p>
        </div>
      ),
    },
    {
      key: 'other',
      label: out ? 'To' : 'From',
      render: (r) => (
        <div>
          <span className="font-mono font-medium text-slate-800">{r.other.iata}</span>
          <p className="max-w-[170px] truncate text-[11.5px] text-slate-500">{r.other.airport}</p>
        </div>
      ),
    },
    {
      key: 'scheduled',
      label: 'Scheduled',
      render: (r) => <span className="font-mono text-slate-700">{hhmm(r.scheduled)}</span>,
    },
    {
      key: 'estimated',
      label: 'Estimated',
      render: (r) => (
        <span className={cx('font-mono', r.delay_min > 15 ? 'font-semibold text-amber-600' : 'text-slate-700')}>
          {hhmm(r.estimated)}
          {r.delay_min > 0 && <span className="ml-1.5 text-[11px] font-sans">+{r.delay_min}m</span>}
        </span>
      ),
    },
    {
      key: 'terminal',
      label: 'Terminal / gate',
      render: (r) => (
        <span className="text-slate-700">
          {r.terminal ? `T${r.terminal}` : '—'}
          {r.gate ? <span className="text-slate-400"> · </span> : null}
          {r.gate}
        </span>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      render: (r) => {
        const s = STATUS[r.status] || STATUS.unknown
        return <Badge tone={s.tone} dot>{s.label}</Badge>
      },
    },
    {
      key: 'live',
      label: 'In flight',
      className: 'hidden lg:table-cell',
      cellClass: 'hidden lg:table-cell',
      render: (r) =>
        r.live && !r.live.on_ground ? (
          <span className="text-[12px] text-slate-600">
            {r.live.altitude_m != null ? `${fmtNum(r.live.altitude_m)} m` : ''} {r.live.speed_kmh != null ? `· ${r.live.speed_kmh} km/h` : ''}
          </span>
        ) : (
          <span className="text-slate-300">—</span>
        ),
    },
  ]

  return (
    <Card className={className}>
      <CardHeader
        title={title}
        subtitle={subtitle}
        icon={Plane}
        actions={
          <>
            <Segmented
              size="sm"
              value={direction}
              onChange={(v) => {
                setDirection(v)
                setLimit(PAGE)
              }}
              options={[
                { value: 'departures', label: 'Departures', icon: ArrowUpFromLine },
                { value: 'arrivals', label: 'Arrivals', icon: ArrowDownToLine },
              ]}
            />
            <Button size="sm" variant="secondary" icon={RefreshCw} loading={refreshing} onClick={refresh}>
              Refresh
            </Button>
          </>
        }
      />

      {loading && !data && (
        <div className="flex h-40 items-center justify-center">
          <Spinner size={20} />
        </div>
      )}

      {error && !data && (
        <Empty icon={Plane} title="Live flights unavailable" text={error} />
      )}

      {data && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-2.5 sm:px-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={src.tone} dot>{src.label}</Badge>
              <span className="text-[12px] text-slate-500">
                Updated {relTime(data.fetched_at)} · {data.count} flights today
                {terminalFilter ? ` · Terminal ${terminalFilter} shown` : ''}
              </span>
            </div>
            <Segmented
              size="sm"
              value={scope}
              onChange={(v) => {
                setScope(v)
                setLimit(PAGE)
              }}
              options={[
                { value: 'upcoming', label: 'Upcoming' },
                { value: 'all', label: 'All day' },
              ]}
            />
          </div>

          {(data.error || refreshError) && (
            <p className="border-b border-amber-100 bg-amber-50 px-4 py-2 text-[12.5px] text-amber-800 sm:px-5">
              {refreshError || data.error}. Showing the last saved board.
            </p>
          )}

          <Table
            dense
            rows={shown}
            columns={columns}
            empty={<Empty icon={Plane} title="No flights to show" text="Nothing matches this filter. Try All day." />}
          />

          {rows.length > shown.length && (
            <div className="border-t border-slate-100 p-3 text-center">
              <Button size="sm" variant="ghost" onClick={() => setLimit((l) => l + PAGE)}>
                Show more ({rows.length - shown.length} left)
              </Button>
            </div>
          )}
        </>
      )}
    </Card>
  )
}
