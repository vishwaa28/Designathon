import { useEffect } from 'react'
import { Loader2, X } from 'lucide-react'
import { titleCase } from '../lib/format'

export function cx(...parts) {
  return parts.filter(Boolean).join(' ')
}

export function Card({ className, children, ...rest }) {
  return (
    <div
      className={cx('rounded-xl border border-slate-200/80 bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]', className)}
      {...rest}
    >
      {children}
    </div>
  )
}

export function CardHeader({ title, subtitle, icon: Icon, actions, className }) {
  return (
    <div className={cx('flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-4 py-3.5 sm:px-5', className)}>
      <div className="flex min-w-0 flex-1 items-center gap-2.5">
        {Icon && (
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-slate-100 text-slate-600">
            <Icon size={15} />
          </span>
        )}
        <div className="min-w-0">
          <h3 className="truncate text-[13.5px] font-semibold text-slate-900">{title}</h3>
          {subtitle && <p className="truncate text-xs text-slate-500">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

const TONES = {
  slate: 'bg-slate-100 text-slate-700 ring-slate-200',
  blue: 'bg-blue-50 text-blue-700 ring-blue-200',
  brand: 'bg-brand-50 text-brand-700 ring-brand-200',
  sky: 'bg-sky-50 text-sky-700 ring-sky-200',
  emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200',
  orange: 'bg-orange-50 text-orange-700 ring-orange-200',
  rose: 'bg-rose-50 text-rose-700 ring-rose-200',
  violet: 'bg-violet-50 text-violet-700 ring-violet-200',
}
const DOTS = {
  slate: 'bg-slate-400', blue: 'bg-blue-500', brand: 'bg-brand-500', sky: 'bg-sky-500', emerald: 'bg-emerald-500',
  amber: 'bg-amber-500', orange: 'bg-orange-500', rose: 'bg-rose-500', violet: 'bg-violet-500',
}

export function Badge({ tone = 'slate', dot, children, className }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-0.5 text-[11.5px] font-medium ring-1 ring-inset',
        TONES[tone],
        className,
      )}
    >
      {dot && <span className={cx('h-1.5 w-1.5 rounded-full', DOTS[tone])} />}
      {children}
    </span>
  )
}

const INCIDENT_TONE = {
  DETECTING: 'blue', ANALYZING: 'blue', PLANNING: 'blue', PROCESSING: 'blue', REPLANNING: 'blue', EXECUTING: 'blue',
  AWAITING_APPROVAL: 'amber', RESOLVED: 'emerald', REJECTED: 'slate', FAILED: 'rose', NO_ACTION: 'slate',
}
const INCIDENT_LABEL = { AWAITING_APPROVAL: 'Awaiting approval', NO_ACTION: 'No action', RESOLVED: 'Resolved' }

export function IncidentStatus({ status }) {
  return (
    <Badge tone={INCIDENT_TONE[status] || 'slate'} dot>
      {INCIDENT_LABEL[status] || titleCase(status)}
    </Badge>
  )
}

const SEVERITY_TONE = { CRITICAL: 'rose', HIGH: 'orange', MODERATE: 'amber', LOW: 'slate', PENDING: 'slate' }
export function SeverityBadge({ severity }) {
  return <Badge tone={SEVERITY_TONE[severity] || 'slate'}>{titleCase(severity)}</Badge>
}

const TRIP_TONE = {
  ON_TIME: 'emerald', BOARDING: 'sky', DELAYED: 'amber', CANCELLED: 'rose', DIVERTED: 'violet',
  EN_ROUTE: 'blue', ARRIVED: 'slate',
}
export function TripStatus({ status }) {
  return (
    <Badge tone={TRIP_TONE[status] || 'slate'} dot>
      {status === 'EN_ROUTE' ? 'En route' : titleCase(status)}
    </Badge>
  )
}

const BTN = {
  primary: 'bg-brand-600 text-white hover:bg-brand-700 shadow-sm disabled:bg-brand-300',
  secondary: 'bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 disabled:text-slate-400',
  ghost: 'text-slate-600 hover:bg-slate-100 disabled:text-slate-300',
  danger: 'bg-white text-rose-700 ring-1 ring-inset ring-rose-200 hover:bg-rose-50 disabled:text-rose-300',
  dark: 'bg-navy-900 text-white hover:bg-navy-800 disabled:bg-slate-400',
}
const SIZES = { sm: 'h-8 px-3 text-[12.5px] gap-1.5', md: 'h-9 px-3.5 text-[13px] gap-2', lg: 'h-10 px-4 text-sm gap-2' }

export function Button({ variant = 'primary', size = 'md', icon: Icon, loading, children, className, ...rest }) {
  return (
    <button
      className={cx(
        'inline-flex items-center justify-center rounded-lg font-medium transition-colors disabled:cursor-not-allowed',
        BTN[variant],
        SIZES[size],
        className,
      )}
      {...rest}
      disabled={loading || rest.disabled}
    >
      {loading ? <Loader2 size={15} className="animate-spin" /> : Icon && <Icon size={15} />}
      {children}
    </button>
  )
}

export function Kpi({ label, value, sub, icon: Icon, tone = 'brand', emphasis }) {
  const iconTone = {
    brand: 'bg-brand-50 text-brand-600', emerald: 'bg-emerald-50 text-emerald-600', amber: 'bg-amber-50 text-amber-600',
    rose: 'bg-rose-50 text-rose-600', slate: 'bg-slate-100 text-slate-600', violet: 'bg-violet-50 text-violet-600',
  }[tone]
  return (
    <Card className={cx('p-4', emphasis && 'ring-1 ring-amber-300')}>
      <div className="flex items-start justify-between">
        <p className="text-[12px] font-medium text-slate-500">{label}</p>
        {Icon && (
          <span className={cx('flex h-7 w-7 items-center justify-center rounded-md', iconTone)}>
            <Icon size={15} />
          </span>
        )}
      </div>
      <p className="tabular mt-1.5 text-[24px] font-semibold leading-tight tracking-tight text-slate-900">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
    </Card>
  )
}

export function Stat({ label, value, tone, hint }) {
  const color = { rose: 'text-rose-600', amber: 'text-amber-600', emerald: 'text-emerald-600', brand: 'text-brand-600' }[tone] || 'text-slate-900'
  return (
    <div>
      <p className="text-[11.5px] font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={cx('tabular mt-0.5 text-lg font-semibold', color)}>{value}</p>
      {hint && <p className="text-[11.5px] text-slate-500">{hint}</p>}
    </div>
  )
}

export function Empty({ icon: Icon, title, text, action, className }) {
  return (
    <div className={cx('flex flex-col items-center justify-center px-6 py-12 text-center', className)}>
      {Icon && (
        <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-slate-100 text-slate-500">
          <Icon size={20} />
        </span>
      )}
      <p className="text-sm font-semibold text-slate-800">{title}</p>
      {text && <p className="mt-1 max-w-sm text-[13px] text-slate-500">{text}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Spinner({ className, size = 16 }) {
  return <Loader2 size={size} className={cx('animate-spin text-brand-500', className)} />
}

export function PageLoader() {
  return (
    <div className="flex h-64 items-center justify-center">
      <Spinner size={22} />
    </div>
  )
}

export function Tabs({ tabs, value, onChange, className }) {
  return (
    <div className={cx('no-scrollbar flex gap-1 overflow-x-auto border-b border-slate-200', className)}>
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={cx(
            '-mb-px flex shrink-0 items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-[13px] font-medium transition-colors',
            value === t.id ? 'border-brand-600 text-brand-700' : 'border-transparent text-slate-500 hover:text-slate-800',
          )}
        >
          {t.label}
          {t.badge != null && (
            <span
              className={cx(
                'rounded-full px-1.5 text-[11px] font-semibold',
                t.badgeTone === 'amber' ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-600',
              )}
            >
              {t.badge}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}

export function Segmented({ options, value, onChange, size = 'md' }) {
  return (
    <div className="inline-flex rounded-lg bg-slate-100 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => !o.disabled && onChange(o.value)}
          disabled={o.disabled}
          title={o.title}
          className={cx(
            'flex items-center gap-1.5 rounded-md font-medium transition-all',
            size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-[12.5px]',
            value === o.value ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700',
            o.disabled && 'cursor-not-allowed opacity-50 hover:text-slate-500',
          )}
        >
          {o.icon && <o.icon size={13} />}
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Progress({ value, tone = 'brand', className }) {
  const color = {
    brand: 'bg-brand-500', emerald: 'bg-emerald-500', amber: 'bg-amber-500', rose: 'bg-rose-500', slate: 'bg-slate-400',
  }[tone]
  return (
    <div className={cx('h-1.5 w-full overflow-hidden rounded-full bg-slate-100', className)}>
      <div className={cx('h-full rounded-full transition-all', color)} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  )
}

export function Modal({ open, onClose, title, subtitle, children, footer, width = 'max-w-lg' }) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-[2px]" onClick={onClose} />
      <div className={cx('relative w-full rounded-t-2xl bg-white shadow-2xl sm:rounded-xl', width)}>
        <div className="flex items-start justify-between border-b border-slate-100 px-5 py-4">
          <div>
            <h3 className="text-[15px] font-semibold text-slate-900">{title}</h3>
            {subtitle && <p className="mt-0.5 text-[13px] text-slate-500">{subtitle}</p>}
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <X size={18} />
          </button>
        </div>
        <div className="max-h-[72vh] overflow-y-auto px-4 py-4 sm:px-5">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 px-4 py-3 sm:px-5">{footer}</div>}
      </div>
    </div>
  )
}

export function Drawer({ open, onClose, title, subtitle, children, width = 'max-w-2xl' }) {
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-slate-900/30" onClick={onClose} />
      <div className={cx('relative flex h-full w-full flex-col bg-white shadow-2xl', width)}>
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-4 sm:px-6">
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-slate-900">{title}</h3>
            {subtitle && <p className="mt-0.5 text-[13px] text-slate-500">{subtitle}</p>}
          </div>
          <button onClick={onClose} className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">{children}</div>
      </div>
    </div>
  )
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[12.5px] font-medium text-slate-700">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
    </label>
  )
}

export const inputBase =
  'h-9 rounded-lg border border-slate-300 bg-white px-3 text-[13px] text-slate-800 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100'
export const inputClass = `${inputBase} w-full`

export function Table({ columns, rows, onRowClick, empty, rowKey = 'id', dense }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-[13px]">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50/70">
            {columns.map((c) => (
              <th
                key={c.key}
                className={cx(
                  'whitespace-nowrap px-4 py-2.5 text-[11.5px] font-semibold uppercase tracking-wide text-slate-500',
                  c.align === 'right' && 'text-right',
                  c.className,
                )}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r, i) => (
            <tr
              key={r[rowKey] ?? i}
              onClick={onRowClick ? () => onRowClick(r) : undefined}
              className={cx(onRowClick && 'cursor-pointer hover:bg-slate-50')}
            >
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={cx(dense ? 'px-4 py-2' : 'px-4 py-2.5', 'align-middle', c.align === 'right' && 'text-right tabular', c.cellClass)}
                >
                  {c.render ? c.render(r) : r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && empty}
    </div>
  )
}

export function KeyValue({ items, cols = 2 }) {
  return (
    <dl className={cx('grid grid-cols-2 gap-x-6 gap-y-3', cols === 3 ? 'sm:grid-cols-3' : cols === 4 ? 'sm:grid-cols-4' : '')}>
      {items.map(([k, v]) => (
        <div key={k}>
          <dt className="text-[11.5px] font-medium text-slate-500">{k}</dt>
          <dd className="mt-0.5 text-[13px] font-medium text-slate-800">{v}</dd>
        </div>
      ))}
    </dl>
  )
}
