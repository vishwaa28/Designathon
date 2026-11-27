export function fmtTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
}

export function fmtDateTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.toLocaleDateString([], { day: '2-digit', month: 'short' })} ${fmtTime(iso)}`
}

export function fmtINR(n) {
  if (n == null) return '—'
  if (Math.abs(n) >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`
  if (Math.abs(n) >= 1e5) return `₹${(n / 1e5).toFixed(1)} L`
  return `₹${Math.round(n).toLocaleString('en-IN')}`
}

export function fmtNum(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('en-IN')
}

export function fmtMin(m) {
  if (m == null) return '—'
  const v = Math.round(m)
  if (Math.abs(v) < 60) return `${v}m`
  const h = Math.floor(v / 60)
  const rest = v % 60
  return rest ? `${h}h ${rest}m` : `${h}h`
}

export function fmtDuration(ms) {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms} ms`
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(1)} s`
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`
}

export function relTime(iso) {
  if (!iso) return ''
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 10) return 'just now'
  if (diff < 60) return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`
  return fmtDateTime(iso)
}

export function titleCase(s) {
  if (!s) return ''
  return s
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export function pct(v, digits = 0) {
  if (v == null) return '—'
  return `${(v * 100).toFixed(digits)}%`
}
