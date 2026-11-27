import { Armchair, Check, Loader2 } from 'lucide-react'
import { Button, cx } from '../ui'

function Seat({ seat, selected, onSelect }) {
  const taken = seat.status === 'taken'
  const mine = seat.status === 'mine'
  return (
    <button
      type="button"
      disabled={taken}
      onClick={() => onSelect(seat.id)}
      aria-label={`Seat ${seat.id}${taken ? ' occupied' : ''}`}
      aria-pressed={selected}
      className={cx(
        'flex h-7 w-7 items-center justify-center rounded-md border text-[9.5px] font-semibold transition-colors sm:h-8 sm:w-8 sm:text-[10.5px]',
        taken && 'cursor-not-allowed border-slate-200 bg-slate-200 text-slate-400',
        mine && 'border-emerald-500 bg-emerald-500 text-white',
        !taken && !mine && !selected && 'border-brand-200 bg-white text-brand-700 hover:border-brand-500 hover:bg-brand-50',
        selected && 'border-brand-600 bg-brand-600 text-white shadow-sm',
      )}
    >
      {selected || mine ? <Check size={13} /> : taken ? '' : seat.id.slice(-1)}
    </button>
  )
}

/** Cabin seat map. Rows are shown with an aisle gap; occupied seats are disabled. */
export default function SeatPicker({ map, selected, onSelect, onConfirm, busy, error, confirmLabel = 'Confirm booking', maxHeight = 340 }) {
  if (!map) {
    return (
      <div className="flex items-center justify-center gap-2 py-10 text-[13px] text-slate-400">
        <Loader2 size={16} className="animate-spin" /> Loading seat map…
      </div>
    )
  }
  const gap = map.aisle_after
  return (
    <div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-1 pb-3 text-[11.5px] text-slate-500">
        <span className="flex items-center gap-1.5"><span className="h-3.5 w-3.5 rounded border border-brand-200 bg-white" /> Available</span>
        <span className="flex items-center gap-1.5"><span className="h-3.5 w-3.5 rounded border border-slate-200 bg-slate-200" /> Occupied</span>
        <span className="flex items-center gap-1.5"><span className="h-3.5 w-3.5 rounded border border-brand-600 bg-brand-600" /> Your pick</span>
        <span className="ml-auto font-medium text-slate-600">{map.free} seats free</span>
      </div>

      <div className="mx-auto w-fit rounded-t-[44px] rounded-b-xl border border-slate-200 bg-slate-50/70 px-3 pb-3 pt-6 sm:px-5">
        <div className="mb-2 flex items-center justify-center gap-2 text-[10.5px] font-medium uppercase tracking-wide text-slate-400">
          <Armchair size={12} /> Front of cabin
        </div>
        <div className="overflow-y-auto pr-1" style={{ maxHeight }}>
          <div className="mb-1 flex items-center gap-1 pl-7 sm:pl-8">
            {map.letters.map((l, i) => (
              <span key={l} className={cx('w-7 text-center text-[10px] font-semibold text-slate-400 sm:w-8', i === gap && 'ml-5')}>{l}</span>
            ))}
          </div>
          <div className="space-y-1">
            {map.rows.map((r) => (
              <div key={r.row} className="flex items-center gap-1">
                <span className="w-6 pr-1 text-right text-[10px] font-medium tabular-nums text-slate-400 sm:w-7">{r.row}</span>
                {r.seats.map((s, i) => (
                  <div key={s.id} className={cx(i === gap && 'ml-5')}>
                    <Seat seat={s} selected={selected === s.id} onSelect={onSelect} />
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>

      {error && <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-[12.5px] text-rose-700">{error}</p>}
      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="text-[13px] text-slate-600">
          {selected ? (
            <>Seat <span className="font-semibold text-slate-900">{selected}</span> selected</>
          ) : (
            'Tap a seat to select it'
          )}
        </p>
        <Button size="md" disabled={!selected} loading={busy} onClick={onConfirm}>{confirmLabel}</Button>
      </div>
    </div>
  )
}
