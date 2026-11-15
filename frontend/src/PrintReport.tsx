// The printable report (PDF = the browser's "Save as PDF"). Hidden on screen.
// Sections follow CLAUDE.md section 12: cover with disclaimer, 1 summary, 2 what the satellites
// see, 3 the Year Strip and score table, 4 one page per option, 5 expert questions, 6 glossary,
// 7 data sources and limits.
import { useState } from 'react'
import type { AnalyzeResponse, Strategy, Tier1Content } from './api'
import { centerOf } from './mapkit'
import { BASE_GLOSSARY, COMPONENT_LABELS, expertQuestions, languageName, strategyColors, stripScore } from './reportText'
import YearStrip, { rowFromStrategy } from './YearStrip'

const CONTENTS = [
  'Summary',
  'What the satellites see',
  'Your year, month by month',
  'Your options, one page each',
  'Questions for your local expert',
  'Words in plain language',
  'Data sources and limits',
]

function gibsMap(analysis: AnalyzeResponse, now: Date) {
  // NASA GIBS WMS GetMap: MODIS Terra true color around the field (WMS 1.3.0 EPSG:4326 = lat,lon order).
  const { lat, lon } = analysis.field
  const d = 0.2
  const day = new Date(now.getTime() - 5 * 86_400_000).toISOString().slice(0, 10)
  const params = new URLSearchParams({
    SERVICE: 'WMS',
    REQUEST: 'GetMap',
    VERSION: '1.3.0',
    LAYERS: 'MODIS_Terra_CorrectedReflectance_TrueColor',
    STYLES: '',
    CRS: 'EPSG:4326',
    BBOX: [lat - d, lon - d, lat + d, lon + d].map((x) => x.toFixed(4)).join(','),
    WIDTH: '640',
    HEIGHT: '640',
    FORMAT: 'image/jpeg',
    TIME: day,
  })
  return { url: `https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?${params}`, day }
}

const label = (s: Strategy) => (s.key === 'current' ? 'Now' : String(s.rank))

export default function PrintReport({
  analysis,
  language,
  content,
  names,
  title,
  subtitle,
  demo,
}: {
  analysis: AnalyzeResponse
  language: string
  content: Tier1Content | null
  names: Record<string, string>
  title?: string
  subtitle?: string
  demo?: boolean
}) {
  const ranked = [...analysis.strategies].sort((a, b) => a.rank - b.rank)
  const textFor = (key: string) => content?.strategies.find((t) => t.key === key)
  const current = ranked.find((s) => s.key === 'current')
  const rows = [...(current ? [rowFromStrategy(current, 'Now')] : []), ...ranked.filter((s) => s.key !== 'current').map((s) => rowFromStrategy(s, label(s)))]
  // Same colors as the strip on page 3, so each option page's band matches its new crop there.
  const colors = strategyColors(analysis.strategies)
  const bandFor = (s: Strategy) => {
    const crop = s.rotation.flat().find((c) => c.new)?.crop
    return crop ? colors[crop] : undefined
  }
  const [now] = useState(() => new Date())
  const map = gibsMap(analysis, now)
  const c = centerOf({ type: 'Point', coordinates: [analysis.field.lon, analysis.field.lat] })
  const datasets = [...new Set([
    ...analysis.prefill.flatMap((card) => card.evidence.map((e) => `${e.dataset} (${e.native_resolution}, ${e.period})`)),
    ...analysis.strategies.flatMap((s) => Object.values(s.components).flatMap((comp) => comp.evidence.map((e) => `${e.dataset} (${e.native_resolution}, ${e.period})`))),
  ])].sort()

  return (
    <div className="print-only print-report" lang={language}>
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

        <div className="p-cover-grid">
          <figure className="p-map">
            <div className="p-map-frame">
              <img src={map.url} alt="NASA MODIS true-color image around the field" />
              <span className="p-map-pin" aria-hidden="true" />
            </div>
            <figcaption>NASA MODIS Terra true color (via NASA GIBS), {map.day}, about 44 km across. The circle marks the field.</figcaption>
          </figure>
          <div className="p-cover-side">
            <h2>Your options, best match first</h2>
            <ol className="p-ranked">
              {ranked.map((s) => (
                <li key={s.key}>
                  <span>
                    <strong>{label(s)}</strong> {names[s.key] ?? s.name}
                  </span>
                  <span className="p-score">{s.total}</span>
                </li>
              ))}
            </ol>
            <p className="p-small">Scores out of 100, from SowSmart's scoring engine.</p>
          </div>
        </div>

        <div className="p-disclaimer">
          <p className="cap p-cap-ink">Advice to discuss, not orders</p>
          <p>{content?.disclaimer ?? analysis.disclaimer}</p>
          {language !== 'en' ? <p className="p-small">{analysis.disclaimer}</p> : null}
        </div>

        <ol className="p-contents">
          {CONTENTS.map((t, i) => (
            <li key={t}>
              <strong>{i + 1}</strong> {t}
            </li>
          ))}
        </ol>

        {content ? (
          <p className="p-foot">The report text is written by AI from SowSmart's results. Scores and the ranking come from SowSmart's scoring engine, not from AI.</p>
        ) : null}
      </section>

      <section className="p-page">
        <h2>1. Summary</h2>
        <p>{content?.summary ?? `Best match for your goals: ${ranked[0]?.name} (${ranked[0]?.title}), ${ranked[0]?.total} out of 100.`}</p>
        {content ? <p className="p-ai">Written by AI from SowSmart's results. The ranking comes from SowSmart's scoring engine, not the AI.</p> : null}
        <h2>2. What the satellites see</h2>
        {content ? <p>{content.what_satellites_see}</p> : null}
        <table className="p-table">
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

      <section className="p-page">
        <h2>3. Your year, month by month</h2>
        {content ? <p>{content.bare_and_risky_seasons}</p> : null}
        <div className="p-strip">
          <YearStrip rows={rows} stress={analysis.stress_calendar} colors={colors} caption="12-month calendar: what you grow now and each option" />
          {analysis.strategies.some((s) => s.rotation.length > 1) ? <p className="p-small">Rotations over two years show year 1 on top and year 2 below.</p> : null}
        </div>
        <h3>How the options compare</h3>
        <table className="p-table p-scores">
          <thead>
            <tr>
              <th>Option</th>
              {Object.keys(ranked[0]?.components ?? {}).map((k) => (
                <th key={k}>{COMPONENT_LABELS[k]?.label ?? k}</th>
              ))}
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {ranked.map((s) => (
              <tr key={s.key}>
                <th>
                  <strong>{label(s)}</strong> {names[s.key] ?? s.name}
                </th>
                {Object.values(s.components).map((comp, i) => (
                  <td key={i}>{Math.round(comp.score)}</td>
                ))}
                <td className="p-total">{s.total}</td>
              </tr>
            ))}
            <tr className="p-weights">
              <th>Weight from your goals</th>
              {Object.keys(ranked[0]?.components ?? {}).map((k) => (
                <td key={k}>{Math.round((analysis.weights[k] ?? 0) * 100)}%</td>
              ))}
              <td />
            </tr>
          </tbody>
        </table>
      </section>

      {ranked.map((s) => {
        const t = textFor(s.key)
        const band = s.key === 'current' ? undefined : bandFor(s)
        return (
          <section key={s.key} className="p-page p-option">
            <p className="cap">4. Your options, one page each</p>
            <h2 className="p-option-title" style={band ? { borderTopColor: band } : undefined}>
              {s.key === 'current' ? (t?.name ?? s.name) : `Option ${s.rank}: ${t?.name ?? s.name}`}
            </h2>
            <p className="p-sub">
              {t?.headline ?? s.title} · score {s.total}/100 · {s.confidence} confidence
            </p>
            {s.changes.length && s.key !== 'current' ? (
              <p>
                <strong>What changes:</strong> {s.changes.join('; ')}
              </p>
            ) : null}
            <p>
              <strong>Why it was suggested:</strong> {t?.why ?? s.why}
            </p>
            <PList title="Benefits" items={t?.benefits ?? s.benefits.map(stripScore)} />
            <PList title="Risks that need local review" items={t?.risks ?? s.risks} risk />
            <PList title="Information gaps" items={t?.information_gaps ?? s.gaps} />
            <h3>Evidence</h3>
            <ul className="p-evidence">
              {Object.entries(s.components).map(([k, comp]) => (
                <li key={k}>
                  <strong>
                    {COMPONENT_LABELS[k]?.label ?? k} ({Math.round(comp.score)}):
                  </strong>{' '}
                  {comp.summary}
                  <span> — {[...new Set(comp.evidence.map((e) => e.dataset))].join('; ')}</span>
                </li>
              ))}
            </ul>
          </section>
        )
      })}

      <section className="p-page">
        <h2>5. Questions for your local expert</h2>
        <ol className="p-numbered">
          {expertQuestions(ranked, (s) => textFor(s.key)).map((q) => (
            <li key={q}>{q}</li>
          ))}
        </ol>
        <h2>6. Words in plain language</h2>
        <dl className="p-glossary">
          {(content?.glossary.length ? content.glossary : BASE_GLOSSARY).map((g) => (
            <div key={g.term}>
              <dt>{g.term}</dt>
              <dd>{g.meaning}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="p-page">
        <h2>7. Data sources and limits</h2>
        {content?.datasets_line ? <p>{content.datasets_line}</p> : null}
        <ul className="p-small">
          {datasets.map((d) => (
            <li key={d}>{d}</li>
          ))}
          <li>Base map image: NASA GIBS (ESDIS). Field imagery in the app: Esri World Imagery.</li>
        </ul>
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
