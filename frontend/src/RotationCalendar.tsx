// The 12-month calendar: weather-stress months on top, then one row per rotation
// (current first), showing which crop is in the field each month and when it is bare.
import type { Strategy, StressMonth } from './api'
import { STRESS_LABELS, cropColors } from './reportText'

const MONTHS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export default function RotationCalendar({
  strategies,
  stress,
  names,
}: {
  strategies: Strategy[]
  stress: StressMonth[]
  names?: Record<string, string>
}) {
  const ordered = [...strategies].sort((a, b) => (a.key === 'current' ? -1 : b.key === 'current' ? 1 : a.rank - b.rank))
  const crops = [...new Set(ordered.flatMap((s) => s.calendar.flatMap((m) => m.crops.map((c) => c.crop))))]
  const flags = [...new Set(stress.flatMap((m) => m.flags))]
  const colors = cropColors(crops)
  const cropColor = (c: string) => colors[c] ?? '#888'

  return (
    <div className="calendar" role="table" aria-label="12-month rotation calendar">
      <div className="cal-row cal-head" role="row">
        <span className="cal-label" role="columnheader">Month</span>
        <div className="cal-cells">
          {MONTHS.map((m, i) => (
            <span key={i} className="cal-month" role="columnheader" title={MONTH_NAMES[i]}>
              {m}
            </span>
          ))}
        </div>
      </div>

      <div className="cal-row cal-stress" role="row">
        <span className="cal-label" role="rowheader">Weather stress</span>
        <div className="cal-cells">
          {Array.from({ length: 12 }, (_, i) => {
            const month = stress.find((m) => m.month === i + 1)
            const f = month?.flags ?? []
            return (
              <span
                key={i}
                className={f.length ? 'cal-cell stress-cell has-stress' : 'cal-cell stress-cell'}
                role="cell"
                title={f.length ? `${MONTH_NAMES[i]}: ${f.map((x) => STRESS_LABELS[x]?.label ?? x).join(', ')}` : `${MONTH_NAMES[i]}: no stress flagged`}
              >
                {f.map((x) => (
                  <b key={x} className={`stress-${x}`}>{STRESS_LABELS[x]?.icon ?? '!'}</b>
                ))}
              </span>
            )
          })}
        </div>
      </div>

      {ordered.map((s) => (
        <div key={s.key} className={s.key === 'current' ? 'cal-row is-current' : 'cal-row'} role="row">
          <span className="cal-label" role="rowheader">
            {s.key === 'current' ? 'Now' : `#${s.rank}`} · {names?.[s.key] ?? s.name}
          </span>
          <div className="cal-cells">
            {s.calendar.map((m) => {
              const years = [...new Set(m.crops.map((c) => c.year))].sort()
              const multiYear = new Set(s.calendar.flatMap((x) => x.crops.map((c) => c.year))).size > 1
              const title = m.crops.length
                ? `${m.name}: ${m.crops.map((c) => `${multiYear ? `year ${c.year} ` : ''}${c.crop}${c.new ? ' (new)' : ''}`).join(', ')}${m.bare > 0 ? ` · bare ${Math.round(m.bare * 100)}% of the month` : ''}`
                : `${m.name}: bare`
              return (
                <span key={m.month} className={m.crops.length ? 'cal-cell' : 'cal-cell is-bare'} role="cell" title={title}>
                  {years.map((y) => {
                    const inYear = m.crops.filter((c) => c.year === y)
                    return (
                      <span key={y} className="cal-band" style={{ flex: 1 }}>
                        {inYear.map((c) => (
                          <span
                            key={c.crop}
                            className={c.new ? 'cal-crop is-new' : 'cal-crop'}
                            style={{ background: cropColor(c.crop), flex: c.share }}
                          />
                        ))}
                        {m.bare > 0 && inYear.length ? <span className="cal-bare-part" style={{ flex: m.bare }} /> : null}
                      </span>
                    )
                  })}
                </span>
              )
            })}
          </div>
        </div>
      ))}

      <div className="cal-legend">
        {crops.map((c) => (
          <span key={c} className="legend-item">
            <span className="legend-swatch" style={{ background: cropColor(c) }} />
            {c}
          </span>
        ))}
        <span className="legend-item">
          <span className="legend-swatch is-bare" />
          bare soil
        </span>
        <span className="legend-item">
          <span className="legend-swatch is-new" />
          new crop
        </span>
        {flags.map((f) => (
          <span key={f} className="legend-item" title={STRESS_LABELS[f]?.plain}>
            <b className={`stress-badge stress-${f}`}>{STRESS_LABELS[f]?.icon}</b> {STRESS_LABELS[f]?.label ?? f}
          </span>
        ))}
      </div>
      {ordered.some((s) => new Set(s.calendar.flatMap((x) => x.crops.map((c) => c.year))).size > 1) ? (
        <p className="helper">Two-year rotations show year 1 on top and year 2 below in each month.</p>
      ) : null}
    </div>
  )
}
