// The printable report (PDF = the browser's "Save as PDF"). Hidden on screen. A4 pages, following
// CLAUDE.md section 12: a cover with the field photo, the best match and the disclaimer;
// 1 summary and what the satellites see (NASA greenness and rain chart); 2 the year month by month
// and how the options compare; 3 one page per option; 4 fruit for the field's edges (when the
// engine found any), questions for your local expert and words in plain language; 5 data sources
// and limits. Page numbers come from the @page rules in Results.css.
import { useState } from 'react'
import type { Geometry } from 'geojson'
import type { AnalyzeResponse, Evidence, FruitIdea, Strategy, Tier1Content } from './api'
import { bufferCircle, centerOf } from './mapkit'
import { BASE_GLOSSARY, COMPONENT_LABELS, STRESS_LABELS, expertQuestions, languageName, optionNumbers, strategyColors, stripScore } from './reportText'
import YearStrip, { rowFromStrategy } from './YearStrip'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
const EARTH_R = 6378137

// --- the field photo ---------------------------------------------------------------------------

type FieldMap = { url: string; width: number; height: number; outline: string; scalePx: number; scaleM: number }

function mercator(lon: number, lat: number): [number, number] {
  const rad = Math.PI / 180
  return [EARTH_R * lon * rad, EARTH_R * Math.log(Math.tan(Math.PI / 4 + (lat * rad) / 2))]
}

/** Esri World Imagery (a cloud-free mosaic) around the field, with the analyzed area as an SVG
 *  outline. The image box is in Web Mercator with the image's own aspect, so lon/lat map to pixels
 *  linearly. A daily satellite pass would often show only clouds over a tropical farm. */
function fieldMap(analysis: AnalyzeResponse, geometry?: Geometry): FieldMap {
  const { lat, lon } = analysis.field
  const shape = geometry?.type === 'Polygon' ? geometry : bufferCircle({ lat, lng: lon }).geometry
  const ring = shape.coordinates[0]
  const width = 1400
  const height = 700
  const stretch = 1 / Math.cos((lat * Math.PI) / 180) // Mercator metres per ground metre here
  const [cx, cy] = mercator(lon, lat)
  const pts = ring.map(([x, y]) => mercator(x, y))
  const extentM = Math.max(...pts.map(([x]) => Math.abs(x - cx)), ...pts.map(([, y]) => Math.abs(y - cy)) ) / stretch
  const groundWidth = Math.max(1600, extentM * 2 * 2.6) // the field fills about 40% of the width
  const halfW = (groundWidth / 2) * stretch
  const halfH = halfW * (height / width)
  const [xmin, ymin, xmax, ymax] = [cx - halfW, cy - halfH, cx + halfW, cy + halfH]
  const toPx = ([x, y]: [number, number]) => [((x - xmin) / (xmax - xmin)) * width, ((ymax - y) / (ymax - ymin)) * height]
  const outline = pts.map((p) => toPx(p).map((v) => v.toFixed(1)).join(',')).join(' ')
  const scaleM = groundWidth > 3000 ? 1000 : 500
  const params = new URLSearchParams({
    bbox: [xmin, ymin, xmax, ymax].map((v) => v.toFixed(1)).join(','),
    bboxSR: '3857',
    imageSR: '3857',
    size: `${width},${height}`,
    format: 'jpg',
    f: 'image',
  })
  return {
    url: `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export?${params}`,
    width,
    height,
    outline,
    scalePx: (scaleM / groundWidth) * width,
    scaleM,
  }
}

/** NASA Blue Marble (a cloud-free monthly composite) for the region, to show where the field is. */
function locatorMap(analysis: AnalyzeResponse) {
  const { lat, lon } = analysis.field
  const d = 4
  const params = new URLSearchParams({
    SERVICE: 'WMS',
    REQUEST: 'GetMap',
    VERSION: '1.3.0',
    LAYERS: 'BlueMarble_NextGeneration',
    STYLES: '',
    CRS: 'EPSG:4326',
    BBOX: [lat - d, lon - d, lat + d, lon + d].map((x) => x.toFixed(4)).join(','), // WMS 1.3.0: lat,lon order
    WIDTH: '360',
    HEIGHT: '360',
    FORMAT: 'image/jpeg',
  })
  return `https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?${params}`
}

function FieldPhoto({ analysis, geometry }: { analysis: AnalyzeResponse; geometry?: Geometry }) {
  const [failed, setFailed] = useState(false)
  const [locatorFailed, setLocatorFailed] = useState(false)
  const map = fieldMap(analysis, geometry)
  return (
    <figure className="p-hero">
      <div className="p-hero-frame">
        {failed ? (
          <p className="p-hero-off">The field photo needs an internet connection when printing.</p>
        ) : (
          <img src={map.url} alt="Satellite photo of the field and its surroundings" onError={() => setFailed(true)} />
        )}
        <svg className="p-hero-svg" viewBox={`0 0 ${map.width} ${map.height}`} preserveAspectRatio="none" aria-hidden="true">
          <polygon points={map.outline} className="p-outline-halo" />
          <polygon points={map.outline} className="p-outline" />
          <g transform={`translate(28 ${map.height - 34})`}>
            <rect x="-10" y="-30" width={map.scalePx + 20} height="46" rx="3" className="p-scale-bg" />
            <rect x="0" y="0" width={map.scalePx} height="7" className="p-scale" />
            <text x={map.scalePx / 2} y="-9" textAnchor="middle" className="p-scale-text">
              {map.scaleM} m
            </text>
          </g>
        </svg>
        {locatorFailed ? null : (
          <div className="p-locator">
            <img src={locatorMap(analysis)} alt="Where the field is: NASA Blue Marble" onError={() => setLocatorFailed(true)} />
            <span className="p-locator-dot" aria-hidden="true" />
          </div>
        )}
      </div>
      <figcaption>
        The yellow line marks the area SowSmart analyzed{geometry?.type === 'Polygon' ? ' (your drawn field)' : ' (250 m around your point)'}. Photo: Esri World
        Imagery (Maxar, Earthstar Geographics), a cloud-free mosaic. Inset: NASA Blue Marble via NASA GIBS, about 900 km across.
      </figcaption>
    </figure>
  )
}

// --- the NASA chart ------------------------------------------------------------------------------

type Series = { normal: (number | null)[]; source: string; normal_period: string }

function GreenRainChart({ analysis }: { analysis: AnalyzeResponse }) {
  const features = analysis.features as Record<string, Series | undefined>
  const rain = features.rain?.normal.map((v, i) => (v ?? 0) * DAYS[i]) ?? []
  const ndvi = features.ndvi?.normal ?? []
  if (!rain.length && !ndvi.length) return null
  const bare = analysis.bare_months.satellite ?? []
  const W = 720
  const H = 200
  const left = 44
  const right = 44
  const top = 22
  const bottom = 30
  const colW = (W - left - right) / 12
  const plotH = H - top - bottom
  const maxRain = Math.max(100, ...rain)
  const rainTop = Math.ceil(maxRain / 100) * 100
  const nd = ndvi.filter((v): v is number => v != null)
  const nLo = nd.length ? Math.max(0, Math.floor((Math.min(...nd) - 0.1) * 10) / 10) : 0
  const nHi = nd.length ? Math.min(1, Math.ceil((Math.max(...nd) + 0.05) * 10) / 10) : 1
  const yRain = (v: number) => top + plotH - (v / rainTop) * plotH
  const yNdvi = (v: number) => top + plotH - ((v - nLo) / (nHi - nLo)) * plotH
  const line = ndvi
    .map((v, i) => (v == null ? null : `${(left + colW * (i + 0.5)).toFixed(1)},${yNdvi(v).toFixed(1)}`))
    .filter(Boolean)
    .join(' ')
  const flags = analysis.stress_calendar
  return (
    <figure className="p-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Greenness and rain through the year">
        {MONTHS.map((m, i) => (
          <g key={m}>
            {bare.includes(i + 1) ? <rect x={left + colW * i} y={top} width={colW} height={plotH} className="p-c-bare" /> : null}
            {rain.length ? <rect x={left + colW * i + colW * 0.22} y={yRain(rain[i])} width={colW * 0.56} height={top + plotH - yRain(rain[i])} className="p-c-rain" /> : null}
            <text x={left + colW * (i + 0.5)} y={H - 10} textAnchor="middle" className="p-c-month">
              {m}
            </text>
            {(flags.find((f) => f.month === i + 1)?.flags ?? []).map((f, k) => (
              <text key={f} x={left + colW * (i + 0.5) + k * 12} y={top - 7} textAnchor="middle" className={`p-c-flag is-${f}`}>
                {STRESS_LABELS[f]?.icon ?? '!'}
              </text>
            ))}
          </g>
        ))}
        <line x1={left} x2={W - right} y1={top + plotH} y2={top + plotH} className="p-c-axis" />
        {rain.length ? (
          <>
            <text x={left - 6} y={top + 4} textAnchor="end" className="p-c-tick">
              {rainTop}
            </text>
            <text x={left - 6} y={top + plotH} textAnchor="end" className="p-c-tick">
              0
            </text>
            <text x={12} y={top + plotH / 2} className="p-c-unit" transform={`rotate(-90 12 ${top + plotH / 2})`} textAnchor="middle">
              rain, mm/month
            </text>
          </>
        ) : null}
        {line ? (
          <>
            <polyline points={line} className="p-c-ndvi" />
            {ndvi.map((v, i) => (v == null ? null : <circle key={i} cx={left + colW * (i + 0.5)} cy={yNdvi(v)} r="3.2" className="p-c-dot" />))}
            <text x={W - right + 6} y={top + 4} className="p-c-tick">
              {nHi.toFixed(1)}
            </text>
            <text x={W - right + 6} y={top + plotH} className="p-c-tick">
              {nLo.toFixed(1)}
            </text>
            <text x={W - 10} y={top + plotH / 2} className="p-c-unit" transform={`rotate(90 ${W - 10} ${top + plotH / 2})`} textAnchor="middle">
              greenness (NDVI)
            </text>
          </>
        ) : null}
      </svg>
      <figcaption>
        <span className="p-key is-ndvi" /> Greenness, NASA MODIS (NDVI{features.ndvi ? `, ${features.ndvi.normal_period}` : ''}) <span className="p-key is-rain" /> Rain,
        NASA POWER (30-year normal) <span className="p-key is-bare" /> Months the field usually looks bare
        {flags.some((f) => f.flags.length) ? ' · letters on top: weather stress (H heat, D dry, F frost, W very wet)' : ''}
      </figcaption>
    </figure>
  )
}

// --- text helpers --------------------------------------------------------------------------------

/** "FAO-56 Table 22 (Rice) | NASA POWER (Agroclimatology), API v2.10.3" -> ["FAO-56", "NASA POWER"] */
function sourceNames(evidence: Evidence[]): string[] {
  const out = new Set<string>()
  for (const e of evidence) {
    for (const part of e.dataset.split(/ \| | \+ |; /)) {
      const name = part
        .replace(/\s*\(.*$/, '')
        .replace(/ Table \d+.*$/, '')
        .replace(/,? API v[\d.]+.*$/, '')
        .replace(/ v?\d+(\.\d+)?$/, '')
        .trim()
      if (name && /^[A-Z]/.test(name) && !/^(Crop traits|Farmer's|Strategy|Team)/.test(name)) out.add(name)
    }
  }
  return [...out]
}

const label = (s: Strategy, numbers: Record<string, number>) => (s.key === 'current' ? 'Now' : String(numbers[s.key]))
const signed = (x: number) => `${x > 0 ? '+' : ''}${Math.round(x * 10) / 10}`
const capital = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

function scoreTone(score: number) {
  // light green for good, light red for poor: readable in print without color too (the number stays)
  const hue = Math.round((score / 100) * 120)
  return `hsl(${hue} 45% ${92 - (score > 50 ? 0 : 4)}%)`
}

export default function PrintReport({
  analysis,
  language,
  content,
  names,
  title,
  subtitle,
  demo,
  geometry,
}: {
  analysis: AnalyzeResponse
  language: string
  content: Tier1Content | null
  names: Record<string, string>
  title?: string
  subtitle?: string
  demo?: boolean
  geometry?: Geometry
}) {
  const ranked = [...analysis.strategies].sort((a, b) => a.rank - b.rank)
  const textFor = (key: string) => content?.strategies.find((t) => t.key === key)
  const current = ranked.find((s) => s.key === 'current')
  const options = ranked.filter((s) => s.key !== 'current')
  const numbers = optionNumbers(analysis.strategies)
  const best = ranked[0]
  const colors = strategyColors(analysis.strategies)
  const bandFor = (s: Strategy) => {
    const crop = s.rotation.flat().find((c) => c.new)?.crop
    return crop ? colors[crop] : undefined
  }
  const rows = [...(current ? [rowFromStrategy(current, 'Now')] : []), ...options.map((s) => rowFromStrategy(s, label(s, numbers)))]
  const [now] = useState(() => new Date())
  const c = centerOf({ type: 'Point', coordinates: [analysis.field.lon, analysis.field.lat] })
  const componentKeys = Object.keys(ranked[0]?.components ?? {})
  // Gaps every option repeats (coarse weather, national prices...) go once on the limits page.
  const gapLists = options.map((s) => textFor(s.key)?.information_gaps ?? s.gaps)
  const sharedGaps = new Set(gapLists.length > 1 ? gapLists[0].filter((g) => gapLists.every((list) => list.includes(g))) : [])
  const fruit = analysis.fruit_ideas ?? []
  const allSources = sourceNames([
    ...analysis.prefill.flatMap((card) => card.evidence),
    ...analysis.strategies.flatMap((s) => Object.values(s.components).flatMap((comp) => comp.evidence)),
    ...fruit.flatMap((f) => f.evidence),
  ]).sort()
  const nasa = allSources.filter((s) => s.startsWith('NASA'))
  const other = allSources.filter((s) => !s.startsWith('NASA'))
  const bareNow = current ? current.calendar.filter((m) => m.bare >= 0.5).length : 0
  const bareBest = best ? best.calendar.filter((m) => m.bare >= 0.5).length : 0
  const sections = [
    'Summary and what the satellites see',
    'Your year, month by month',
    'Your options, one page each',
    ...(fruit.length ? ["Fruit for the field's edges"] : []),
    'Questions for your local expert',
    'Data sources and limits',
  ]

  return (
    <div className="print-only print-report" lang={language}>
      {/* Cover */}
      <section className="p-page p-cover">
        <header className="p-mast">
          <span className="p-brand">SowSmart</span>
          <p className="cap">
            Crop rotation report · {languageName(language)} · {now.toISOString().slice(0, 10)}
          </p>
        </header>

        <div className="p-title">
          <p className="cap">{demo ? 'Demo farm' : 'Your field'}</p>
          <h1>{title ?? content?.title ?? 'Crop rotation options for your field'}</h1>
          <p className="p-place">
            {subtitle ? `${subtitle} · ` : ''}
            {Math.abs(c.lat).toFixed(3)}° {c.lat >= 0 ? 'N' : 'S'}, {Math.abs(c.lng).toFixed(3)}° {c.lng >= 0 ? 'E' : 'W'}
          </p>
        </div>

        <FieldPhoto analysis={analysis} geometry={geometry} />

        <div className="p-glance">
          {best ? (
            <div className="p-best" style={bandFor(best) ? { borderTopColor: bandFor(best) } : undefined}>
              <p className="cap p-cap-ink">Best match for your goals</p>
              <h2>{names[best.key] ?? best.name}</h2>
              <p className="p-best-score">
                <strong>{best.total}</strong>
                <span>/100</span>
                {current && best.key !== 'current' ? <em>{signed(best.total - current.total)} vs now</em> : null}
              </p>
              <p className="p-small">{textFor(best.key)?.headline ?? best.title}</p>
              {current && best.key !== 'current' ? (
                <p className="p-small">
                  Bare months: <strong>{bareNow}</strong> now → <strong>{bareBest}</strong> with this option.
                </p>
              ) : null}
            </div>
          ) : null}
          <div className="p-cover-side">
            <p className="cap p-cap-ink">{current ? 'All options, best match first' : 'Starting options for this land, best match first'}</p>
            <ol className="p-ranked">
              {ranked.map((s) => (
                <li key={s.key}>
                  <span className="p-chip" style={{ background: s.key === 'current' ? 'var(--line)' : bandFor(s) }} aria-hidden="true" />
                  <span className="p-ranked-name">
                    <strong>{label(s, numbers)}</strong> {names[s.key] ?? s.name}
                  </span>
                  <span className="p-score">{s.total}</span>
                </li>
              ))}
            </ol>
            <p className="p-small">Scores out of 100 from SowSmart's scoring engine, weighted by your goals.</p>
          </div>
        </div>

        <div className="p-disclaimer">
          <p className="cap p-cap-ink">Advice to discuss, not orders</p>
          <p>{content?.disclaimer ?? analysis.disclaimer}</p>
          {language !== 'en' ? <p className="p-small">{analysis.disclaimer}</p> : null}
        </div>

        <ol className="p-contents">
          {sections.map((t, i) => (
            <li key={t}>
              <strong>{i + 1}</strong> {t}
            </li>
          ))}
        </ol>
        {content ? <p className="p-foot">Report text written by AI from SowSmart's results. Scores and the ranking come from SowSmart's scoring engine, not from AI.</p> : null}
      </section>

      {/* 1. Summary and what the satellites see */}
      <section className="p-page">
        <h2>1. Summary</h2>
        <p className="p-lead">
          {content?.summary ??
            `Best match for your goals: ${best?.name} (${best?.title}), ${best?.total} out of 100${current && best?.key !== 'current' ? `, against ${current.total} for what you grow now` : ''}.`}
        </p>
        {content ? <p className="p-ai">Written by AI from SowSmart's results. The ranking comes from SowSmart's scoring engine, not the AI.</p> : null}
        <h2>What the satellites see</h2>
        {content ? <p>{content.what_satellites_see}</p> : null}
        <GreenRainChart analysis={analysis} />
        <table className="p-table p-facts">
          <tbody>
            {analysis.prefill.map((card) => (
              <tr key={card.id}>
                <th>{card.title}</th>
                <td>{card.statement}</td>
                <td className="p-conf">{card.confidence}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* 2. The year and the comparison */}
      <section className="p-page">
        <h2>2. Your year, month by month</h2>
        {content ? <p>{content.bare_and_risky_seasons}</p> : null}
        <div className="p-strip">
          <YearStrip rows={rows} stress={analysis.stress_calendar} colors={colors} caption={current ? '12-month calendar: what you grow now and each option' : '12-month calendar: each starting option'} />
          {analysis.strategies.some((s) => s.rotation.length > 1) ? <p className="p-small">Rotations over two years show year 1 on top and year 2 below.</p> : null}
        </div>
        <h3>How the options compare</h3>
        <table className="p-table p-scores">
          <thead>
            <tr>
              <th>Option</th>
              {componentKeys.map((k) => (
                <th key={k}>{COMPONENT_LABELS[k]?.label ?? k}</th>
              ))}
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {ranked.map((s) => (
              <tr key={s.key} className={s.key === 'current' ? 'is-now' : undefined}>
                <th>
                  <strong>{label(s, numbers)}</strong> {names[s.key] ?? s.name}
                </th>
                {componentKeys.map((k) => (
                  <td key={k} style={{ background: scoreTone(s.components[k].score) }}>
                    {Math.round(s.components[k].score)}
                  </td>
                ))}
                <td className="p-total">{s.total}</td>
              </tr>
            ))}
            <tr className="p-weights">
              <th>Weight from your goals</th>
              {componentKeys.map((k) => (
                <td key={k}>{Math.round((analysis.weights[k] ?? 0) * 100)}%</td>
              ))}
              <td />
            </tr>
          </tbody>
        </table>
        <dl className="p-defs">
          {componentKeys.map((k) => (
            <div key={k}>
              <dt>{COMPONENT_LABELS[k]?.label ?? k}</dt>
              <dd>{COMPONENT_LABELS[k]?.plain}</dd>
            </div>
          ))}
        </dl>
      </section>

      {/* 3. One page per option */}
      {ranked.map((s) => (
        <OptionPage key={s.key} s={s} current={current} name={names[s.key] ?? s.name} t={textFor(s.key)} band={s.key === 'current' ? undefined : bandFor(s)} colors={colors} stress={analysis.stress_calendar} number={numbers[s.key]} last={options.length} shared={sharedGaps} />
      ))}

      {/* 4. Fruit, questions and glossary */}
      <section className="p-page">
        {fruit.length ? <FruitPage ideas={fruit} country={analysis.profile?.country} /> : null}
        <h2>{fruit.length ? '5' : '4'}. Questions for your local expert</h2>
        <ol className="p-numbered">
          {expertQuestions(ranked, (s) => textFor(s.key)).map((q) => (
            <li key={q}>{q}</li>
          ))}
        </ol>
        <h3>Words in plain language</h3>
        <dl className="p-glossary">
          {(content?.glossary.length ? content.glossary : BASE_GLOSSARY).map((g) => (
            <div key={g.term}>
              <dt>{g.term}</dt>
              <dd>{g.meaning}</dd>
            </div>
          ))}
        </dl>
      </section>

      {/* 5. Sources and limits */}
      <section className="p-page">
        <h2>{fruit.length ? '6' : '5'}. Data sources and limits</h2>
        {content?.datasets_line ? <p>{content.datasets_line}</p> : null}
        <div className="p-two">
          <div>
            <h3>NASA Earth observations</h3>
            <ul className="p-small">
              {nasa.map((d) => (
                <li key={d}>{d}</li>
              ))}
              <li>NASA Blue Marble via NASA GIBS (cover inset)</li>
            </ul>
          </div>
          <div>
            <h3>Partner and crop data</h3>
            <ul className="p-small">
              {other.map((d) => (
                <li key={d}>{d}</li>
              ))}
              <li>Esri World Imagery (cover photo)</li>
            </ul>
          </div>
        </div>
        <h3>Limitations</h3>
        <ul>
          {analysis.gaps.map((g) => (
            <li key={g}>{g}</li>
          ))}
          <li>Satellite and weather data are regional averages; your own observations and a soil test are more accurate.</li>
        </ul>
        <div className="p-disclaimer">
          <p className="cap p-cap-ink">Advice to discuss, not orders</p>
          <p>{content?.disclaimer ?? analysis.disclaimer}</p>
        </div>
      </section>
    </div>
  )
}

function OptionPage({
  s,
  current,
  name,
  t,
  band,
  colors,
  stress,
  number,
  last,
  shared,
}: {
  s: Strategy
  current?: Strategy
  name: string
  t?: { name: string; headline: string; why: string; benefits: string[]; risks: string[]; information_gaps: string[]; expert_questions: string[] }
  band?: string
  colors: Record<string, string>
  stress: AnalyzeResponse['stress_calendar']
  /** The option's number among the alternatives (undefined for the current rotation). */
  number?: number
  last: number
  shared: Set<string>
}) {
  const isNow = s.key === 'current'
  const rows = [...(current && !isNow ? [rowFromStrategy(current, 'Now')] : []), { ...rowFromStrategy(s, isNow ? 'Now' : 'This'), highlight: !isNow }]
  const benefits = t?.benefits ?? s.benefits.map(stripScore)
  const risks = t?.risks ?? s.risks
  const own = (t?.information_gaps ?? s.gaps).filter((g) => !shared.has(g))
  const gaps = shared.size && !isNow ? [...own, 'The data limits on the last page apply to this option too.'] : own
  const questions = t?.expert_questions ?? s.expert_questions
  return (
    <section className="p-page p-option">
      <p className="cap">3. Your options, one page each</p>
      <header className="p-option-head" style={band ? { borderTopColor: band } : undefined}>
        <div>
          <p className="cap">{isNow ? 'What you grow now' : `Option ${number} of ${last}${s.rank === 1 ? ' · best match for your goals' : ''}`}</p>
          <h2>{isNow ? (t?.name ?? s.name) : name}</h2>
          <p className="p-sub">{t?.headline ?? s.title}</p>
        </div>
        <div className="p-option-score">
          <strong>{s.total}</strong>
          <span>/100</span>
          {current && !isNow ? <em>{signed(s.total - current.total)} vs now</em> : null}
          <small>{s.confidence} confidence</small>
        </div>
      </header>

      <div className="p-strip">
        <YearStrip rows={rows} stress={stress} colors={colors} caption={`${name}: 12-month calendar`} />
      </div>

      {s.changes.length && !isNow ? (
        <>
          <h3>What changes</h3>
          <ul>
            {s.changes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </>
      ) : null}
      <h3>Why {isNow ? 'it is shown' : 'it was suggested'}</h3>
      <p>{t?.why ?? s.why}</p>

      {benefits.length || risks.length ? (
        <div className="p-two">
          <div>{benefits.length ? <PList title="Benefits" items={benefits} /> : null}</div>
          <div>{risks.length ? <PList title="Risks that need local review" items={risks} risk /> : null}</div>
        </div>
      ) : null}

      <h3>Scores and the evidence behind them</h3>
      <div className="p-bars">
        {Object.entries(s.components).map(([k, comp]) => {
          const was = current && !isNow ? current.components[k]?.score : undefined
          return (
            <div key={k} className="p-bar-row">
              <span className="p-bar-label">{COMPONENT_LABELS[k]?.label ?? k}</span>
              <span className="p-bar-track">
                {was !== undefined ? <i className="p-bar-was" style={{ width: `${was}%` }} /> : null}
                <i className="p-bar-now" style={{ width: `${comp.score}%`, background: band ?? 'var(--ink-soft)' }} />
              </span>
              <span className="p-bar-num">
                {Math.round(comp.score)}
                {was !== undefined && Math.round(comp.score) !== Math.round(was) ? <em>{signed(Math.round(comp.score) - Math.round(was))}</em> : null}
              </span>
              <span className="p-bar-why">{comp.summary}</span>
            </div>
          )
        })}
        <p className="p-small p-bars-key">
          {current && !isNow ? 'Thin gray line: what you grow now. ' : ''}
          Sources: {sourceNames(Object.values(s.components).flatMap((comp) => comp.evidence)).join(', ')}.
        </p>
      </div>

      {gaps.length || questions.length ? (
        <div className="p-two p-small">
          <div>{gaps.length ? <PList title="Information gaps" items={gaps} /> : null}</div>
          <div>{questions.length ? <PList title="Ask a local expert" items={questions} /> : null}</div>
        </div>
      ) : null}
    </section>
  )
}

function FruitPage({ ideas, country }: { ideas: FruitIdea[]; country?: string | null }) {
  return (
    <>
      <h2>4. Fruit for the field's edges</h2>
      <p>
        Long-term ideas, not part of the rotation and not scored with the options. Each one suits this field's weather in every month of the year (FAO EcoCrop
        ranges) and is grown {country ? `in ${country}` : 'in your country'} (FAOSTAT), so plants, know-how and buyers exist nearby.
      </p>
      <div className="p-fruit">
        {ideas.map((f) => (
          <div key={f.crop} className="p-fruit-card">
            <p className="cap">{f.kind === 'tree' ? 'Fruit tree' : 'Fruit plant'}</p>
            <h3>{capital(f.crop)}</h3>
            <p className="p-small">{f.where}.</p>
            <p className="p-small">
              {f.country_area_ha ? `Grown on about ${f.country_area_ha.toLocaleString('en')} ha nationally.` : ''}
              {f.value_usd_ha ? ` Typical harvest worth about ${f.value_usd_ha.toLocaleString('en')} USD per hectare a year before costs (national average).` : ''}
            </p>
          </div>
        ))}
      </div>
    </>
  )
}

function PList({ title, items, risk }: { title: string; items: string[]; risk?: boolean }) {
  if (!items.length) return null
  return (
    <>
      <h3 className={risk ? 'p-risk' : undefined}>{title}</h3>
      <ul>
        {items.map((i) => (
          <li key={i}>{i}</li>
        ))}
      </ul>
    </>
  )
}
