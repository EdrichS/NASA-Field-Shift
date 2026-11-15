// Results: the Tier 1 report per language, the 12-month calendar, and the current rotation vs.
// 3 alternatives with scores, confidence, gaps, risks and questions for a local expert.
// Tier 2 (detailed follow-up with sources) only runs when the farmer asks.
import { useMemo, useState } from 'react'
import {
  ApiError,
  followup,
  type AIReport,
  type AnalyzeResponse,
  type Strategy,
  type StrategyText,
  type Tier2Content,
} from './api'
import PrintReport from './PrintReport'
import { BASE_GLOSSARY, COMPONENT_LABELS, expertQuestions, languageName, stripScore } from './reportText'
import RotationCalendar from './RotationCalendar'
import './Results.css'

export type ResultsProps = {
  analysis: AnalyzeResponse
  title?: string
  subtitle?: string
  demo?: boolean
  offline?: boolean
  canSave?: boolean
  saved?: boolean
  saveLabel?: string
  onSave?: () => void
  onBack: () => void
  getToken?: () => Promise<string | null>
}

export default function Results({ analysis, title, subtitle, demo, offline, canSave, saved, saveLabel = 'Save', onSave, onBack, getToken }: ResultsProps) {
  const languages = Object.keys(analysis.reports_tier1)
  const [language, setLanguage] = useState(languages[0] ?? 'en')
  const report = analysis.reports_tier1[language] ?? null
  const status = analysis.report_status[language]
  const content = report?.content ?? null
  const ranked = useMemo(() => [...analysis.strategies].sort((a, b) => a.rank - b.rank), [analysis.strategies])
  const textFor = (s: Strategy): StrategyText | undefined => content?.strategies.find((t) => t.key === s.key)
  const names = Object.fromEntries(analysis.strategies.map((s) => [s.key, textFor(s)?.name ?? s.name]))
  const top = ranked[0]
  const current = analysis.strategies.find((s) => s.key === 'current')

  function print() {
    window.print()
  }

  return (
    <main className="results" data-testid="results">
      <div className="results-column">
        <header className="results-bar no-print">
          <button type="button" className="back" onClick={onBack}>
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M10 3L5 8l5 5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Home
          </button>
          <div className="results-actions">
            {canSave ? (
              <button type="button" className="secondary" onClick={onSave} disabled={saved}>
                {saved ? 'Saved ✓' : saveLabel}
              </button>
            ) : null}
            <button type="button" className="secondary" onClick={print}>
              Download PDF
            </button>
          </div>
        </header>

        <div className="screen-only">
          <p className="results-kicker">{demo ? 'Demo farm' : 'Your results'}{subtitle ? ` · ${subtitle}` : ''}</p>
          <h1 className="results-title">{content?.title ?? title ?? 'Your rotation options'}</h1>

          <aside className="disclaimer" role="note">
            <strong>Advice to discuss, not orders.</strong> {content?.disclaimer ?? analysis.disclaimer}
          </aside>

          {offline ? (
            <p className="notice">You are viewing a saved copy of this demo farm. Live analysis needs the SowSmart server.</p>
          ) : null}
          {analysis.warning ? <p className="notice">{analysis.warning}</p> : null}

          {languages.length > 1 ? (
            <div className="lang-tabs" role="tablist" aria-label="Report language">
              {languages.map((code) => (
                <button
                  key={code}
                  type="button"
                  role="tab"
                  aria-selected={language === code}
                  className={language === code ? 'lang-tab is-on' : 'lang-tab'}
                  onClick={() => setLanguage(code)}
                >
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

          <section className="r-card summary-card" aria-labelledby="sum-h">
            <div className="r-head">
              <h2 id="sum-h">Summary</h2>
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
            <details className="more">
              <summary>Where the data comes from</summary>
              {content?.datasets_line ? <p className="datasets">{content.datasets_line}</p> : <DatasetsLine analysis={analysis} />}
            </details>
          </section>

          <section className="r-card" aria-labelledby="sat-h">
            <h2 id="sat-h">What the satellites see</h2>
            {content ? <p>{content.what_satellites_see}</p> : null}
            <ul className="mini-cards">
              {analysis.prefill.map((card) => (
                <li key={card.id}>
                  <strong>{card.title}</strong>
                  <span>{card.statement}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="r-card" aria-labelledby="cal-h">
            <h2 id="cal-h">Your year, month by month</h2>
            {content ? <p>{content.bare_and_risky_seasons}</p> : null}
            <RotationCalendar strategies={analysis.strategies} stress={analysis.stress_calendar} names={names} />
          </section>

          <h2 className="section-title">Your options, best match first</h2>
          <p className="helper">
            Scores come from SowSmart's scoring engine, weighted by your goals. The AI only explains them in plain words.
          </p>
          <ol className="strategy-list">
            {ranked.map((s) => (
              <StrategyCard key={s.key} strategy={s} text={textFor(s)} weights={analysis.weights} current={current} />
            ))}
          </ol>

          <section className="r-card" aria-labelledby="q-h">
            <h2 id="q-h">Questions for your local expert</h2>
            <ul className="questions">
              {expertQuestions(ranked, textFor).map((q) => (
                <li key={q}>{q}</li>
              ))}
            </ul>
          </section>

          <FollowUp analysis={analysis} language={language} getToken={getToken} demo={demo} offline={offline} />

          {content?.glossary.length ? (
            <section className="r-card" aria-labelledby="g-h">
              <h2 id="g-h">Words in plain language</h2>
              <dl className="glossary">
                {content.glossary.map((g) => (
                  <div key={g.term}>
                    <dt>{g.term}</dt>
                    <dd>{g.meaning}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ) : (
            <BaseGlossary />
          )}

          <section className="r-card" aria-labelledby="lim-h">
            <h2 id="lim-h">Limits of this analysis</h2>
            <ul>
              {analysis.gaps.map((g) => (
                <li key={g}>{g}</li>
              ))}
            </ul>
          </section>

          <aside className="disclaimer" role="note">
            {content?.disclaimer ?? analysis.disclaimer}
          </aside>
        </div>

        <PrintReport analysis={analysis} language={language} content={content} names={names} title={title} subtitle={subtitle} />
      </div>
    </main>
  )
}

function AiBadge({ report }: { report: AIReport }) {
  return (
    <span className="ai-badge" title={`Model: ${report.meta.model ?? 'AI'}. Every number was checked against SowSmart's data.`}>
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

function StrategyCard({
  strategy: s,
  text,
  weights,
  current,
}: {
  strategy: Strategy
  text?: StrategyText
  weights: Record<string, number>
  current?: Strategy
}) {
  const benefits = text?.benefits ?? s.benefits.map(stripScore)
  const risks = text?.risks ?? s.risks
  const gaps = text?.information_gaps ?? s.gaps
  const isCurrent = s.key === 'current'
  return (
    <li className={isCurrent ? 'strategy is-current' : 'strategy'}>
      <div className="strategy-head">
        <span className="rank" aria-label={`Rank ${s.rank}`}>#{s.rank}</span>
        <div className="strategy-names">
          <h3>{text?.name ?? s.name}</h3>
          <p className="strategy-title">{text?.headline ?? s.title}</p>
        </div>
        <div className="score" aria-label={`Score ${s.total} out of 100`}>
          <strong>{s.total}</strong>
          <span>/100</span>
        </div>
      </div>
      {!isCurrent && current ? (
        <p className="strategy-meta">{s.total > current.total ? 'Scores better than what you grow now' : s.total < current.total ? 'Scores lower than what you grow now' : 'Scores the same as what you grow now'}</p>
      ) : null}

      {s.changes.length && !isCurrent ? (
        <div className="changes">
          <strong>What changes:</strong> {s.changes.join('; ')}
        </div>
      ) : null}
      <p className="why"><strong>Why it was suggested:</strong> {text?.why ?? s.why}</p>

      {benefits.length ? <ListBlock title="Benefits" items={benefits} tone="good" /> : null}
      {risks.length ? <ListBlock title="Risks to check locally" items={risks} tone="risk" /> : null}
      {gaps.length ? <ListBlock title="What we don't know yet" items={gaps} tone="gap" /> : null}

      <details className="breakdown">
        <summary>More details</summary>
        <p className="bar-summary">
          How sure we are: {s.confidence}.
          {!isCurrent && current ? ` Score ${s.total} vs. ${current.total} for what you grow now.` : ''}
          {text?.fallback ? ' (Plain text from the engine: the AI skipped this option.)' : ''}
        </p>
        <ul className="bars">
          {Object.entries(s.components).map(([key, c]) => (
            <li key={key}>
              <div className="bar-label">
                <span title={COMPONENT_LABELS[key]?.plain}>{COMPONENT_LABELS[key]?.label ?? key}</span>
                <span className="bar-weight">weight {Math.round((weights[key] ?? 0) * 100)}%</span>
                <span>{Math.round(c.score)}</span>
              </div>
              <div className="bar"><span style={{ width: `${Math.max(0, Math.min(100, c.score))}%` }} /></div>
              <p className="bar-summary">{c.summary}</p>
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
      </details>
    </li>
  )
}

function ListBlock({ title, items, tone }: { title: string; items: string[]; tone: 'good' | 'risk' | 'gap' }) {
  return (
    <div className={`list-block tone-${tone}`}>
      <strong>{title}</strong>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
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
    <section className="r-card followup" aria-labelledby="f-h">
      <div className="r-head">
        <h2 id="f-h">Go deeper</h2>
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
          <div className="segmented" role="radiogroup" aria-label="Language level">
            {(['farmer', 'advanced'] as const).map((l) => (
              <button key={l} type="button" role="radio" aria-checked={level === l} className={level === l ? 'is-on' : ''} onClick={() => setLevel(l)}>
                {l === 'farmer' ? 'Plain words' : 'Advanced'}
              </button>
            ))}
          </div>
          <label className="lang-label" htmlFor="followup-q">Your question (optional)</label>
          <textarea
            id="followup-q"
            className="control"
            rows={2}
            maxLength={500}
            placeholder={demo ? 'e.g., Why is mungbean better than sorghum here?' : 'e.g., Why is this option first?'}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <button type="button" className="continue" onClick={ask} disabled={busy}>
            {busy ? 'Writing your answer…' : 'Ask'}
          </button>
          {error ? <p className="field-error" role="alert">{error}</p> : null}
          {answers.map((a, i) => (
            <article key={i} className="answer">
              {a.question ? <p className="answer-q">“{a.question}”</p> : null}
              <AiBadge report={a as unknown as AIReport} />
              <p>{a.content.answer}</p>
              {a.content.sources.length ? (
                <>
                  <h3>Where each claim comes from</h3>
                  <ul className="sources">
                    {a.content.sources.map((s, j) => (
                      <li key={j}>
                        <strong>{s.claim}</strong>
                        <span className="ev-src">{s.dataset}</span>
                        <span>{s.why_it_supports}</span>
                      </li>
                    ))}
                  </ul>
                </>
              ) : null}
              {a.content.caveats.length ? <ListBlock title="Keep in mind" items={a.content.caveats} tone="gap" /> : null}
              {a.content.expert_questions.length ? <ListBlock title="Ask your local expert" items={a.content.expert_questions} tone="good" /> : null}
            </article>
          ))}
        </>
      ) : null}
    </section>
  )
}

function BaseGlossary() {
  return (
    <section className="r-card" aria-labelledby="g-h">
      <h2 id="g-h">Words in plain language</h2>
      <dl className="glossary">
        {BASE_GLOSSARY.map((g) => (
          <div key={g.term}>
            <dt>{g.term}</dt>
            <dd>{g.meaning}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

