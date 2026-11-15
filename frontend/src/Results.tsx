// Results: one option per page. An Overview tab (disclaimer, the Year Strip for every rotation,
// the ranked list, the Tier 1 report per language) and one tab per option plus "Now" (the current
// rotation), each with its score, reasons, risks and gaps. Tier 2 (detailed follow-up with
// sources) only runs when the farmer asks.
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import type { Geometry } from 'geojson'
import {
  ApiError,
  followup,
  type AIReport,
  type AnalyzeResponse,
  type FruitIdea,
  type ReportStatus,
  type Strategy,
  type StrategyText,
  type Tier1Content,
  type Tier2Content,
} from './api'
import PlotName from './PlotName'
import PrintReport from './PrintReport'
import { BASE_GLOSSARY, COMPONENT_LABELS, expertQuestions, languageName, strategyColors, stripScore } from './reportText'
import YearStrip, { rowFromStrategy } from './YearStrip'
import './Results.css'

export type ResultsProps = {
  analysis: AnalyzeResponse
  title?: string
  subtitle?: string
  /** The farmer's name for this plot or field; shown with Rename when onRename is set. */
  name?: string
  onRename?: (name: string) => void
  /** The analyzed point or drawn field, for the field photo in the PDF. */
  geometry?: Geometry
  demo?: boolean
  offline?: boolean
  canSave?: boolean
  saved?: boolean
  saveLabel?: string
  onSave?: () => void
  onBack: () => void
  getToken?: () => Promise<string | null>
}

const OVERVIEW = 'overview'

/** The short label of a rotation in tabs and Year Strip rows: its rank, or "Now". */
function rankLabel(s: Strategy) {
  return s.key === 'current' ? 'Now' : String(s.rank)
}

/** The longer name used in links: "Option 2", "What you grow now" or "Overview". */
function tabName(key: string, strategies: Strategy[]) {
  if (key === OVERVIEW) return 'Overview'
  if (key === 'current') return 'What you grow now'
  return `Option ${strategies.find((s) => s.key === key)?.rank ?? ''}`
}

function compareWords(s: Strategy, current?: Strategy) {
  if (!current || s.key === 'current') return null
  if (s.total > current.total) return 'Scores better than what you grow now'
  if (s.total < current.total) return 'Scores lower than what you grow now'
  return 'Scores the same as what you grow now'
}

function isMultiYear(strategies: Strategy[]) {
  return strategies.some((s) => s.rotation.length > 1)
}

/** The option's first new crop, in the same color the Year Strips give it. */
function newCropColor(colors: Record<string, string>, s: Strategy) {
  const crop = s.rotation.flat().find((c) => c.new)?.crop
  return crop ? colors[crop] : undefined
}

export default function Results({ analysis, title, subtitle, name, onRename, geometry, demo, offline, canSave, saved, saveLabel = 'Save', onSave, onBack, getToken }: ResultsProps) {
  const languages = Object.keys(analysis.reports_tier1)
  const [language, setLanguage] = useState(languages[0] ?? 'en')
  const report = analysis.reports_tier1[language] ?? null
  const status = analysis.report_status[language]
  const content = report?.content ?? null
  const ranked = useMemo(() => [...analysis.strategies].sort((a, b) => a.rank - b.rank), [analysis.strategies])
  const textFor = (s: Strategy): StrategyText | undefined => content?.strategies.find((t) => t.key === s.key)
  const names = Object.fromEntries(analysis.strategies.map((s) => [s.key, textFor(s)?.name ?? s.name]))
  const current = analysis.strategies.find((s) => s.key === 'current')
  const options = ranked.filter((s) => s.key !== 'current')
  const lastRank = Math.max(0, ...options.map((s) => s.rank))

  const tabs = [OVERVIEW, ...options.map((s) => s.key), ...(current ? ['current'] : [])]
  const [tab, setTab] = useState(OVERVIEW)
  const active = tabs.includes(tab) ? tab : OVERVIEW
  const tabsRef = useRef<HTMLDivElement>(null)
  const pendingScroll = useRef(false)

  useEffect(() => {
    if (!pendingScroll.current) return
    pendingScroll.current = false
    const bar = tabsRef.current
    if (bar && bar.getBoundingClientRect().top < 0) bar.scrollIntoView({ block: 'start' })
  }, [active])

  function select(key: string, focusTab = false) {
    pendingScroll.current = true
    setTab(key)
    if (focusTab) document.getElementById(`rtab-${key}`)?.focus({ preventScroll: true })
  }

  function onTabKey(e: KeyboardEvent<HTMLDivElement>) {
    const i = tabs.indexOf(active)
    const next =
      e.key === 'ArrowRight' ? (i + 1) % tabs.length
      : e.key === 'ArrowLeft' ? (i - 1 + tabs.length) % tabs.length
      : e.key === 'Home' ? 0
      : e.key === 'End' ? tabs.length - 1
      : -1
    if (next < 0) return
    e.preventDefault()
    select(tabs[next], true)
  }

  function print() {
    window.print()
  }

  return (
    <main className="results" data-testid="results">
      <div className="results-column">
        <header className="results-bar no-print">
          <button type="button" className="results-back" onClick={onBack}>
            <span aria-hidden="true">‹</span> Home
          </button>
          <div className="results-actions">
            {canSave ? (
              <button type="button" className="link-button results-save" onClick={onSave} disabled={saved}>
                {saved ? 'Saved ✓' : saveLabel}
              </button>
            ) : null}
            <button type="button" className="secondary" onClick={print} aria-label="Download PDF" title="Download PDF">
              PDF
            </button>
          </div>
        </header>

        <div className="screen-only">
          <div className="results-head">
            <p className="cap">{demo ? 'Demo farm' : 'Your results'}{subtitle ? ` · ${subtitle}` : ''}</p>
            <h1 className="results-title">{content?.title ?? title ?? 'Your rotation options'}</h1>
            {!demo && name ? <PlotName name={name} onRename={onRename} /> : null}
          </div>

          <div ref={tabsRef} className="rtabs" role="tablist" aria-label="Overview and options" onKeyDown={onTabKey}>
            {tabs.map((key) => {
              const s = analysis.strategies.find((x) => x.key === key)
              const on = key === active
              const label = s ? rankLabel(s) : 'Overview'
              return (
                <button
                  key={key}
                  id={`rtab-${key}`}
                  type="button"
                  role="tab"
                  aria-selected={on}
                  aria-controls={`rpanel-${key}`}
                  aria-label={s ? `${tabName(key, analysis.strategies)}: ${names[key]}` : undefined}
                  title={s ? names[key] : undefined}
                  tabIndex={on ? 0 : -1}
                  className={`rtab${key === OVERVIEW ? ' is-wide' : key === 'current' ? ' is-now' : ''}`}
                  onClick={() => select(key)}
                >
                  {label}
                </button>
              )
            })}
          </div>

          <div id={`rpanel-${OVERVIEW}`} className="rpanel" role="tabpanel" aria-labelledby={`rtab-${OVERVIEW}`} tabIndex={0} hidden={active !== OVERVIEW}>
            <Overview
              analysis={analysis}
              report={report}
              content={content}
              status={status}
              language={language}
              languages={languages}
              onLanguage={setLanguage}
              ranked={ranked}
              current={current}
              textFor={textFor}
              onPick={(key) => select(key, true)}
              getToken={getToken}
              demo={demo}
              offline={offline}
            />
          </div>

          {tabs
            .filter((key) => key !== OVERVIEW)
            .map((key) => {
              const s = analysis.strategies.find((x) => x.key === key)
              if (!s) return null
              const i = tabs.indexOf(key)
              const prev = tabs[i - 1]
              const next = tabs[i + 1]
              return (
                <div key={key} id={`rpanel-${key}`} className="rpanel" role="tabpanel" aria-labelledby={`rtab-${key}`} tabIndex={0} hidden={active !== key}>
                  <OptionPage
                    strategy={s}
                    text={textFor(s)}
                    current={current}
                    weights={analysis.weights}
                    stress={analysis.stress_calendar}
                    colors={strategyColors(analysis.strategies)}
                    lastRank={lastRank}
                    prev={prev ? { key: prev, label: tabName(prev, analysis.strategies) } : undefined}
                    next={next ? { key: next, label: tabName(next, analysis.strategies) } : undefined}
                    onPick={(k) => select(k, true)}
                  />
                </div>
              )
            })}
        </div>

        <PrintReport analysis={analysis} language={language} content={content} names={names} title={title ?? name} subtitle={subtitle} demo={demo} geometry={geometry} />
      </div>
    </main>
  )
}

function Overview({
  analysis,
  report,
  content,
  status,
  language,
  languages,
  onLanguage,
  ranked,
  current,
  textFor,
  onPick,
  getToken,
  demo,
  offline,
}: {
  analysis: AnalyzeResponse
  report: AIReport | null
  content: Tier1Content | null
  status?: ReportStatus
  language: string
  languages: string[]
  onLanguage: (code: string) => void
  ranked: Strategy[]
  current?: Strategy
  textFor: (s: Strategy) => StrategyText | undefined
  onPick: (key: string) => void
  getToken?: () => Promise<string | null>
  demo?: boolean
  offline?: boolean
}) {
  const top = ranked[0]
  const rows = [
    ...(current ? [rowFromStrategy(current, 'Now')] : []),
    ...ranked.filter((s) => s.key !== 'current').map((s) => rowFromStrategy(s, rankLabel(s))),
  ]
  const goals = (analysis.profile?.goals ?? []).map((g) => g.replace(/_/g, ' '))

  return (
    <>
      <aside className="rule-note" role="note">
        <p className="cap rule-note-title">Advice to discuss, not orders</p>
        <p>{content?.disclaimer ?? analysis.disclaimer}</p>
      </aside>

      {offline ? <p className="notice">You are viewing a saved copy of this demo farm. Live analysis needs the SowSmart server.</p> : null}
      {analysis.warning ? <p className="notice">{analysis.warning}</p> : null}

      {languages.length > 1 || (language !== 'en' && content) ? (
        <div className="lang-switch">
          {languages.length > 1 ? (
            <div role="group" aria-label="Report language" className="lang-options">
              <span className="cap" aria-hidden="true">Report in</span>
              {languages.map((code) => (
                <button key={code} type="button" aria-pressed={language === code} className="lang-opt" onClick={() => onLanguage(code)}>
                  {languageName(code)}
                </button>
              ))}
            </div>
          ) : null}
          {language !== 'en' && content ? (
            <p className="helper">
              Reports are most reliable in English. In other languages the quality may be lower, and some words stay in English.
            </p>
          ) : null}
        </div>
      ) : null}

      <section className="r-sec" aria-labelledby="cal-h">
        <h2 id="cal-h" className="r-h2">Your year, month by month</h2>
        <YearStrip rows={rows} stress={analysis.stress_calendar} colors={strategyColors(analysis.strategies)} caption="12-month calendar: what you grow now and each option" />
        {isMultiYear(analysis.strategies) ? <p className="helper">Rotations over two years show year 1 on top and year 2 below.</p> : null}
        {content ? <p>{content.bare_and_risky_seasons}</p> : null}
      </section>

      <section className="r-sec" aria-labelledby="rank-h">
        <h2 id="rank-h" className="r-h2">Your options, best match first</h2>
        <p className="helper">
          {goals.length ? `Ranked for your goals: ${goals.join(', ')}. ` : ''}
          Scores come from SowSmart's scoring engine, weighted by your goals. The AI only explains them in plain words.
        </p>
        <ol className="rank-list">
          {ranked.map((s) => {
            const t = textFor(s)
            return (
              <li key={s.key}>
                <button type="button" className={s.key === 'current' ? 'rank-row is-now' : 'rank-row'} onClick={() => onPick(s.key)}>
                  <span className="rank-num" aria-hidden="true">{rankLabel(s)}</span>
                  <span className="visually-hidden">{s.key === 'current' ? `What you grow now, ranked ${s.rank}:` : `Option ${s.rank}:`}</span>
                  <span className="rank-text">
                    <span className="rank-name">{t?.name ?? s.name}</span>
                    <span className="rank-detail">{t?.headline ?? s.title}</span>
                  </span>
                  <span className="rank-score">
                    <span className="visually-hidden">score </span>
                    {s.total}
                  </span>
                  <span className="rank-go" aria-hidden="true">›</span>
                </button>
              </li>
            )
          })}
        </ol>
      </section>

      {analysis.fruit_ideas?.length ? <FruitIdeas ideas={analysis.fruit_ideas} country={analysis.profile?.country} /> : null}

      <section className="index-card band-ai r-card" aria-labelledby="sum-h">
        <div className="card-head">
          <h2 id="sum-h" className="card-h">Summary</h2>
          {report ? <AiBadge report={report} /> : null}
        </div>
        {content ? (
          <p className="lead">{content.summary}</p>
        ) : (
          <>
            <ReportMissing status={status?.status} message={status?.message} />
            {top ? (
              <p className="lead">
                Best match for your goals: <strong>{top.name}</strong> ({top.title}), scoring {top.total} out of 100
                {current && top.key !== 'current' ? ` compared with ${current.total} for your current rotation` : ''}.
              </p>
            ) : null}
          </>
        )}
        <details className="disclosure is-small">
          <summary>Where the data comes from</summary>
          <div className="disclosure-body">
            {content?.datasets_line ? <p className="datasets">{content.datasets_line}</p> : <DatasetsLine analysis={analysis} />}
          </div>
        </details>
      </section>

      <section className="r-sec" aria-labelledby="sat-h">
        <h2 id="sat-h" className="r-h2">What the satellites see</h2>
        {content ? <p>{content.what_satellites_see}</p> : null}
        <ul className="ruled fact-list">
          {analysis.prefill.map((card) => (
            <li key={card.id}>
              <strong>{card.title}</strong>
              <span>{card.statement}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="r-sec" aria-labelledby="q-h">
        <h2 id="q-h" className="r-h2">Questions for your local expert</h2>
        <ol className="ruled numbered">
          {expertQuestions(ranked, textFor).map((q) => (
            <li key={q}>{q}</li>
          ))}
        </ol>
      </section>

      <FollowUp analysis={analysis} language={language} getToken={getToken} demo={demo} offline={offline} />

      <Glossary items={content?.glossary.length ? content.glossary : BASE_GLOSSARY} />

      <section className="r-sec" aria-labelledby="lim-h">
        <h2 id="lim-h" className="r-h2">Limits of this analysis</h2>
        <ul className="ruled">
          {analysis.gaps.map((g) => (
            <li key={g}>{g}</li>
          ))}
        </ul>
      </section>

      <aside className="rule-note" role="note">
        <p>{content?.disclaimer ?? analysis.disclaimer}</p>
      </aside>
    </>
  )
}

/** Fruit trees and plants for bunds or field edges: long-term ideas the engine does not score. */
function FruitIdeas({ ideas, country }: { ideas: FruitIdea[]; country?: string | null }) {
  return (
    <section className="r-sec" aria-labelledby="fruit-h">
      <h2 id="fruit-h" className="r-h2">Beyond the rotation: fruit for the field's edges</h2>
      <p className="helper">
        Long-term ideas, not scored with the options above. Each one suits this field's weather in every month (FAO EcoCrop) and is grown
        {country ? ` in ${country}` : ' in your country'} (FAOSTAT), so plants, know-how and buyers exist.
      </p>
      <ul className="ruled fact-list">
        {ideas.map((f) => (
          <li key={f.crop}>
            <strong>
              {f.crop.charAt(0).toUpperCase() + f.crop.slice(1)} <span className="cap">{f.kind === 'tree' ? 'tree' : 'fruit plant'}</span>
            </strong>
            <span>
              {f.where}.
              {f.country_area_ha ? ` Grown on about ${f.country_area_ha.toLocaleString('en')} ha nationally` : ''}
              {f.value_usd_ha ? `; typical harvest worth about ${f.value_usd_ha.toLocaleString('en')} USD per hectare a year before costs (national average).` : f.country_area_ha ? '.' : ''}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function AiBadge({ report }: { report: AIReport }) {
  return (
    <span className="cap ai-badge" title={`Model: ${report.meta.model ?? 'AI'}`}>
      Written by AI from SowSmart's results
    </span>
  )
}

function ReportMissing({ status, message }: { status?: string; message?: string }) {
  if (!status || status === 'skipped') return null
  return <p className="notice">{message || 'The plain-language report is not available right now. The comparison below is complete.'}</p>
}

function DatasetsLine({ analysis }: { analysis: AnalyzeResponse }) {
  const sets = [...new Set(analysis.prefill.flatMap((c) => c.evidence.map((e) => e.dataset.split(' (')[0])))]
  return <p className="datasets">Based on {sets.join(', ')}.</p>
}

function OptionPage({
  strategy: s,
  text,
  current,
  weights,
  stress,
  colors,
  lastRank,
  prev,
  next,
  onPick,
}: {
  strategy: Strategy
  text?: StrategyText
  current?: Strategy
  weights: Record<string, number>
  stress: AnalyzeResponse['stress_calendar']
  colors: Record<string, string>
  lastRank: number
  prev?: { key: string; label: string }
  next?: { key: string; label: string }
  onPick: (key: string) => void
}) {
  const isCurrent = s.key === 'current'
  const benefits = text?.benefits ?? s.benefits.map(stripScore)
  const risks = text?.risks ?? s.risks
  const gaps = text?.information_gaps ?? s.gaps
  const rows = isCurrent || !current ? [rowFromStrategy(s, rankLabel(s))] : [rowFromStrategy(current, 'Now'), rowFromStrategy(s, rankLabel(s))]
  const band = isCurrent ? undefined : newCropColor(colors, s)
  const words = compareWords(s, current)
  const id = `opt-${s.key}`

  return (
    <>
      <div className="opt-head">
        <p className="cap">
          {isCurrent ? 'What you grow now' : `Option ${s.rank} of ${lastRank}${s.rank === 1 ? ' · best match for your goals' : ''}`}
        </p>
        <h2 className="opt-title">{text?.name ?? s.name}</h2>
        <p className="opt-headline">{text?.headline ?? s.title}</p>
      </div>

      <div className="r-sec">
        <YearStrip
          rows={rows}
          stress={stress}
          colors={colors}
          caption={isCurrent ? '12-month calendar: what you grow now' : '12-month calendar: what you grow now and this option'}
        />
        {s.rotation.length > 1 || (!isCurrent && current && current.rotation.length > 1) ? (
          <p className="helper">Rotations over two years show year 1 on top and year 2 below.</p>
        ) : null}
      </div>

      <div className="opt-score">
        <span className="opt-total">{s.total}</span>
        <span className="opt-score-words">
          <span className="cap">Score out of 100</span>
          <span>{words ?? 'The options are compared with this score.'}</span>
        </span>
      </div>

      {s.changes.length && !isCurrent ? (
        <section className="r-sec" aria-labelledby={`${id}-ch`}>
          <h3 id={`${id}-ch`} className="r-h3">What changes</h3>
          <ul className="sq-list">
            {s.changes.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="index-card r-card" style={band ? { borderTopColor: band } : undefined} aria-labelledby={`${id}-why`}>
        <h3 id={`${id}-why`} className="card-h">{isCurrent ? 'The starting point' : 'Why it was suggested'}</h3>
        <p>{text?.why ?? s.why}</p>
      </section>

      {benefits.length ? <ListSection id={`${id}-ben`} title="Benefits" items={benefits} /> : null}

      {risks.length ? (
        <section className="index-card band-risk r-card" aria-labelledby={`${id}-risk`}>
          <h3 id={`${id}-risk`} className="cap risk-h">Check locally</h3>
          <ul className="sq-list">
            {risks.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {gaps.length ? <ListSection id={`${id}-gap`} title="What we don't know yet" items={gaps} /> : null}

      <details className="disclosure">
        <summary>More details</summary>
        <div className="disclosure-body">
          <p className="confidence">Confidence: {s.confidence}</p>
          {!isCurrent && current ? <p>Score {s.total} vs. {current.total} for what you grow now.</p> : null}
          {text?.fallback ? <p className="helper">Plain text from the engine: the AI skipped this option.</p> : null}
          <ul className="comp-list">
            {Object.entries(s.components).map(([key, c]) => (
              <li key={key}>
                <div className="comp-row">
                  <span className="comp-name" title={COMPONENT_LABELS[key]?.plain}>
                    {COMPONENT_LABELS[key]?.label ?? key} <span className="comp-weight">· weight {Math.round((weights[key] ?? 0) * 100)}%</span>
                  </span>
                  <span className="comp-track" aria-hidden="true">
                    <span style={{ width: `${Math.max(0, Math.min(100, c.score))}%` }} />
                  </span>
                  <span className="comp-val">
                    <span className="visually-hidden">score </span>
                    {Math.round(c.score)}
                  </span>
                </div>
                <p className="comp-summary">{c.summary}</p>
                <ul className="evidence">
                  {c.evidence.slice(0, 4).map((e, i) => (
                    <li key={i}>
                      {e.claim}
                      {typeof e.value === 'number' || typeof e.value === 'string' ? `: ${e.value}${e.unit ? ` ${e.unit}` : ''}` : ''}
                      <span className="ev-src"> — {e.dataset}, {e.native_resolution}, {e.period} ({e.confidence} confidence)</span>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      </details>

      <nav className="opt-nav" aria-label="Previous and next">
        {prev ? (
          <button type="button" className="link-button" onClick={() => onPick(prev.key)}>
            <span aria-hidden="true">‹ </span>
            {prev.label}
          </button>
        ) : null}
        {next ? (
          <button type="button" className="link-button is-next" onClick={() => onPick(next.key)}>
            {next.label}
            <span aria-hidden="true"> ›</span>
          </button>
        ) : null}
      </nav>
    </>
  )
}

function ListSection({ id, title, items }: { id: string; title: string; items: string[] }) {
  return (
    <section className="r-sec" aria-labelledby={id}>
      <h3 id={id} className="r-h3">{title}</h3>
      <ul className="sq-list">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  )
}

function FollowUp({
  analysis,
  language,
  getToken,
  demo,
  offline,
}: {
  analysis: AnalyzeResponse
  language: string
  getToken?: () => Promise<string | null>
  demo?: boolean
  offline?: boolean
}) {
  const [open, setOpen] = useState(false)
  const [level, setLevel] = useState<'farmer' | 'advanced'>('farmer')
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const [answers, setAnswers] = useState<AIReport<Tier2Content>[]>([])

  async function ask() {
    setBusy(true)
    setError(undefined)
    try {
      const token = getToken ? await getToken() : null
      const result = await followup(analysis, language, level, question, token)
      setAnswers((cur) => [result, ...cur])
      setQuestion('')
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="r-sec followup" aria-labelledby="f-h">
      <div className="fu-head">
        <h2 id="f-h" className="r-h2">Go deeper</h2>
        {!open ? (
          <button type="button" className="secondary" onClick={() => setOpen(true)} disabled={offline}>
            Show details and sources
          </button>
        ) : null}
      </div>
      <p className="helper">
        {offline
          ? 'Detailed answers need the SowSmart server, which is offline for this saved demo.'
          : 'A longer explanation with the dataset behind every claim. Ask your own question, or leave it empty for a full walk-through.'}
      </p>
      {open ? (
        <>
          <div className="fu-level" role="group" aria-label="Wording">
            {(['farmer', 'advanced'] as const).map((l) => (
              <button key={l} type="button" aria-pressed={level === l} className={level === l ? 'pick is-on' : 'pick'} onClick={() => setLevel(l)}>
                {l === 'farmer' ? 'Plain words' : 'Advanced'}
              </button>
            ))}
          </div>
          <label className="fu-label" htmlFor="followup-q">Your question (optional)</label>
          <textarea
            id="followup-q"
            className="fu-input"
            rows={3}
            maxLength={500}
            placeholder={demo ? 'e.g., Why is mungbean better than sorghum here?' : 'e.g., Why is this option first?'}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <button type="button" className="tag-btn is-block" onClick={ask} disabled={busy}>
            {busy ? 'Writing your answer…' : 'Ask'}
          </button>
          {error ? <p className="field-error" role="alert">{error}</p> : null}
          {answers.map((a, i) => (
            <article key={i} className="index-card band-ai r-card fu-answer">
              <AiBadge report={a as unknown as AIReport} />
              {a.question ? <h3 className="card-h">“{a.question}”</h3> : null}
              <p>{a.content.answer}</p>
              {a.content.sources.length ? (
                <>
                  <h4 className="cap">Where each claim comes from</h4>
                  <ol className="ruled numbered sources">
                    {a.content.sources.map((s, j) => (
                      <li key={j}>
                        <span className="src-body">
                          <strong>{s.claim}</strong>
                          <span className="ev-src">{s.dataset}</span>
                          <span>{s.why_it_supports}</span>
                        </span>
                      </li>
                    ))}
                  </ol>
                </>
              ) : null}
              {a.content.caveats.length ? <AnswerList title="Keep in mind" items={a.content.caveats} /> : null}
              {a.content.expert_questions.length ? <AnswerList title="Ask your local expert" items={a.content.expert_questions} /> : null}
            </article>
          ))}
        </>
      ) : null}
    </section>
  )
}

function AnswerList({ title, items }: { title: string; items: string[] }) {
  return (
    <>
      <h4 className="cap">{title}</h4>
      <ul className="sq-list">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </>
  )
}

function Glossary({ items }: { items: { term: string; meaning: string }[] }) {
  return (
    <section className="r-sec" aria-labelledby="g-h">
      <h2 id="g-h" className="r-h2">Words in plain language</h2>
      <dl className="ruled glossary">
        {items.map((g) => (
          <div key={g.term}>
            <dt>{g.term}</dt>
            <dd>{g.meaning}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
