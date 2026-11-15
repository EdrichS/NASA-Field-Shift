// The Year Strip: the 12 months as labeled bars, one row per rotation (or per thing we know about
// the field so far), with a risk row on top. Used on the setup steps, the results and the PDF.
// Positions are in half months (0-24): a crop planted in June starts mid-June, one harvested in
// September ends mid-September, which matches the engine's calendar shares.
import type { Card, Strategy, StressMonth } from './api'
import { STRESS_LABELS, cropColors } from './reportText'

const LETTERS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const GREEN = 'looks green'

export type StripSegment = { crop: string | null; start: number; end: number; isNew?: boolean }
export type StripRow = { key: string; label: string; years: StripSegment[][]; highlight?: boolean }

type Half = { crop: string; isNew: boolean } | null

function runs(halves: Half[]): StripSegment[] {
  const out: StripSegment[] = []
  halves.forEach((h, i) => {
    const last = out[out.length - 1]
    if (last && last.crop === (h?.crop ?? null) && Boolean(last.isNew) === Boolean(h?.isNew)) last.end = i + 1
    else out.push({ crop: h?.crop ?? null, start: i, end: i + 1, isNew: h?.isNew })
  })
  return out
}

function yearHalves(steps: Strategy['rotation'][number]): Half[] {
  const halves: Half[] = Array(24).fill(null)
  for (const step of steps) {
    const start = 2 * (step.plant_month - 1) + 1
    const end = 2 * (step.harvest_month - 1) + 1
    const length = (end - start + 24) % 24 || 1
    for (let i = 0; i < length; i++) halves[(start + i) % 24] = { crop: step.crop, isNew: step.new }
  }
  return halves
}

/** One row per rotation; a multi-year rotation gets one bar per year. */
export function rowFromStrategy(s: Strategy, label: string): StripRow {
  return { key: s.key, label, years: s.rotation.map((year) => runs(yearHalves(year))) }
}

/** The satellite's view: months the field looks bare vs green. */
export function rowFromBareMonths(bare: number[], label = 'Field'): StripRow {
  const halves: Half[] = Array.from({ length: 24 }, (_, i) => (bare.includes(Math.floor(i / 2) + 1) ? null : { crop: GREEN, isNew: false }))
  return { key: 'satellite', label, years: [runs(halves)] }
}

/** The farmer's own crops (quick mode), before any analysis has run. */
export function rowFromCrops(crops: { crop: string; plant_month: number; harvest_month: number }[], label = 'You'): StripRow {
  return { key: 'farmer', label, years: [runs(yearHalves(crops.map((c) => ({ ...c, new: false }))))] }
}

/** Heat and frost months from the satellite cards, for the risk row before an analysis exists. */
export function stressFromCards(cards: Card[]): StressMonth[] {
  const months = (id: string) => {
    const value = cards.find((c) => c.id === id)?.value
    return Array.isArray(value) ? value.filter((m): m is number => typeof m === 'number') : []
  }
  const heat = months('heat')
  const frost = months('frost')
  return MONTH_NAMES.map((name, i) => ({
    month: i + 1,
    name,
    flags: [...(heat.includes(i + 1) ? ['heat'] : []), ...(frost.includes(i + 1) ? ['frost'] : [])],
    evidence: [],
  }))
}

function luminance(hex: string) {
  const n = parseInt(hex.slice(1), 16)
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const c = v / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

/** White text when it reads at 4.5:1 on the bar, otherwise ink. */
function textOn(hex: string) {
  return 1.05 / (luminance(hex) + 0.05) >= 4.5 ? '#ffffff' : '#183323'
}

function monthSpan(seg: StripSegment) {
  const first = MONTH_NAMES[Math.floor(seg.start / 2)]
  const last = MONTH_NAMES[Math.floor((seg.end - 1) / 2)]
  return first === last ? first : `${first}–${last}`
}

function describe(segs: StripSegment[]) {
  const crops = segs.filter((s) => s.crop)
  if (!crops.length) return 'bare all year'
  return crops.map((s) => `${s.crop}${s.isNew ? ' (new)' : ''} ${monthSpan(s)}`).join(', ') + '; bare otherwise'
}

function flagClass(flags: string[]) {
  if (flags.some((f) => f === 'heat' || f === 'dry')) return 'ys-risk-hot'
  if (flags.length) return 'ys-risk-cold'
  return ''
}

export default function YearStrip({
  rows,
  stress,
  legend = true,
  caption,
  colors: shared,
}: {
  rows: StripRow[]
  stress?: StressMonth[]
  legend?: boolean
  caption?: string
  /** Crop colors shared with other strips on the page (see strategyColors). */
  colors?: Record<string, string>
}) {
  const crops = [...new Set(rows.flatMap((r) => r.years.flatMap((y) => y.map((s) => s.crop))))].filter(
    (c): c is string => Boolean(c) && c !== GREEN,
  )
  const colors = { ...cropColors(crops), ...shared }
  const flags = [...new Set((stress ?? []).flatMap((m) => m.flags))]
  const hasNew = rows.some((r) => r.years.some((y) => y.some((s) => s.isNew)))

  return (
    <div className="year-strip" role="table" aria-label={caption ?? '12-month calendar'}>
      <div className="ys-row ys-head" role="row">
        <span className="ys-label" role="columnheader">
          <span className="visually-hidden">Row</span>
        </span>
        <div className="ys-months">
          {LETTERS.map((m, i) => (
            <span key={i} role="columnheader" title={MONTH_NAMES[i]}>
              {m}
            </span>
          ))}
        </div>
      </div>

      {stress ? (
        <div className="ys-row ys-risk" role="row">
          <span className="ys-label" role="rowheader">Risk</span>
          <div className="ys-months">
            {Array.from({ length: 12 }, (_, i) => {
              const f = stress.find((m) => m.month === i + 1)?.flags ?? []
              return (
                <span
                  key={i}
                  role="cell"
                  className={flagClass(f)}
                  title={f.length ? `${MONTH_NAMES[i]}: ${f.map((x) => STRESS_LABELS[x]?.label ?? x).join(', ')}` : `${MONTH_NAMES[i]}: no stress flagged`}
                >
                  {f.map((x) => STRESS_LABELS[x]?.icon ?? '!').join('')}
                </span>
              )
            })}
          </div>
        </div>
      ) : null}

      {rows.map((row) => (
        <div key={row.key} className={row.highlight ? 'ys-row is-highlight' : 'ys-row'} role="row">
          <span className="ys-label" role="rowheader">{row.label}</span>
          <div className="ys-years">
            {row.years.map((segs, y) => (
              <div key={y} className="ys-bars" role="cell" aria-label={`${row.years.length > 1 ? `Year ${y + 1}: ` : ''}${describe(segs)}`}>
                {segs.map((seg) => {
                  const green = seg.crop === GREEN
                  const bg = seg.crop && !green ? colors[seg.crop] : undefined
                  return (
                    <span
                      key={seg.start}
                      aria-hidden="true"
                      className={`ys-seg${seg.crop ? '' : ' is-bare'}${green ? ' is-green' : ''}${seg.isNew ? ' is-new' : ''}`}
                      style={{ flexGrow: seg.end - seg.start, background: bg, color: bg ? textOn(bg) : undefined }}
                      title={seg.crop ? `${green ? 'Looks green' : seg.crop}${seg.isNew ? ' (new)' : ''}: ${monthSpan(seg)}` : `Bare: ${monthSpan(seg)}`}
                    >
                      {seg.crop && seg.end - seg.start >= 4 ? (green ? 'Green' : seg.crop) : ''}
                    </span>
                  )
                })}
              </div>
            ))}
          </div>
        </div>
      ))}

      {legend ? (
        <p className="ys-legend">
          {crops.map((c) => (
            <span key={c}>
              <i style={{ background: colors[c] }} aria-hidden="true" />
              {c}
            </span>
          ))}
          <span>
            <i className="is-bare" aria-hidden="true" />
            bare
          </span>
          {hasNew ? (
            <span>
              <i className="is-new" aria-hidden="true" />
              new crop
            </span>
          ) : null}
          {flags.map((f) => (
            <span key={f} title={STRESS_LABELS[f]?.plain}>
              <b className={flagClass([f])}>{STRESS_LABELS[f]?.icon ?? '!'}</b> {STRESS_LABELS[f]?.label ?? f}
            </span>
          ))}
        </p>
      ) : null}
    </div>
  )
}
