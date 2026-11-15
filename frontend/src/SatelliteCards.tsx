// Step "What the satellites see": the backend's /prefill cards (NASA data) with
// "Is this right?" so the farmer can confirm or correct each one (CLAUDE.md section 3, step 3).
import { useEffect, useRef, useState } from 'react'
import type { Geometry } from 'geojson'
import { ApiError, prefill, type Card, type PrefillResponse } from './api'
import { baseStyle, collapseAttribution, centerOf, fitField, maplibregl, pinMarker, showField } from './mapkit'

export type CardAnswer = { status: 'confirmed' | 'corrected' | 'unsure'; value?: unknown }
export type CardAnswers = Record<string, CardAnswer>

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export default function SatelliteCards({
  geometry,
  data,
  onData,
  answers,
  onAnswers,
  onBack,
  onContinue,
}: {
  geometry: Geometry
  data: PrefillResponse | null
  onData: (data: PrefillResponse | null) => void
  answers: CardAnswers
  onAnswers: (answers: CardAnswers) => void
  onBack: () => void
  onContinue: () => void
}) {
  const [error, setError] = useState<string>()
  const [attempt, setAttempt] = useState(0)
  const loading = !data && !error

  useEffect(() => {
    if (data) return
    const controller = new AbortController()
    setError(undefined)
    prefill(geometry, controller.signal)
      .then(onData)
      .catch((e: unknown) => {
        if (controller.signal.aborted) return
        setError(e instanceof ApiError ? e.message : 'Something went wrong. Please try again.')
      })
    return () => controller.abort()
    // Re-run only for a new place or a retry.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geometry, attempt])

  const blocked = !!data && data.cards.length === 0
  const set = (id: string, answer: CardAnswer) => onAnswers({ ...answers, [id]: answer })

  return (
    <div className="step-panel locate-panel confirm-panel" key="confirm">
      <div className="locate-head">
        <BackButton onClick={onBack} label="Back to the map" />
        <h1 id="confirm-title" className="where">What the satellites see</h1>
      </div>
      <p className="cards-intro">
        NASA satellites have watched this spot for years. Check each card: you know your land best, and your
        answer replaces our estimate.
      </p>

      <FieldPreview geometry={geometry} />

      {loading ? (
        <div className="cards-loading" role="status">
          <span className="spinner" aria-hidden="true" />
          <div>
            <strong>Reading NASA data for this field…</strong>
            <p>Weather, soil moisture, greenness, rain and slope. The first look at a new place can take up to a minute.</p>
          </div>
        </div>
      ) : null}

      {error ? (
        <div className="notice notice-error" role="alert">
          <p>{error}</p>
          <button type="button" className="secondary" onClick={() => setAttempt((n) => n + 1)}>Try again</button>
        </div>
      ) : null}

      {data?.warning ? (
        <div className={blocked ? 'notice notice-error' : 'notice'} role="status">
          <p>{data.warning}</p>
          {blocked ? <button type="button" className="secondary" onClick={onBack}>Move the pin</button> : null}
        </div>
      ) : null}

      {data && !blocked ? (
        <ol className="sat-cards">
          {data.cards.map((card) => (
            <SatCard key={card.id} card={card} answer={answers[card.id]} onAnswer={(a) => set(card.id, a)} />
          ))}
        </ol>
      ) : null}

      {data && data.gaps.length ? (
        <details className="gaps">
          <summary>What we could not see ({data.gaps.length})</summary>
          <ul>{data.gaps.map((g) => <li key={g}>{g}</li>)}</ul>
        </details>
      ) : null}

      <button type="button" className="continue" disabled={!data || blocked} onClick={onContinue}>
        Continue
      </button>
    </div>
  )
}

function SatCard({ card, answer, onAnswer }: { card: Card; answer?: CardAnswer; onAnswer: (a: CardAnswer) => void }) {
  const [editing, setEditing] = useState(false)
  const edit = card.edit
  const status = answer?.status

  return (
    <li className={`sat-card${status ? ` is-${status}` : ''}`}>
      <div className="sat-card-head">
        <h3>{card.title}</h3>
      </div>
      <p className="sat-statement">{card.statement}</p>
      {status === 'corrected' ? <p className="sat-correction">Your answer: {describe(answer?.value)}</p> : null}

      <div className="sat-ask" role="group" aria-label={`Is this right? ${card.title}`}>
        <span>Is this right?</span>
        <button type="button" className={status === 'confirmed' ? 'pick is-on' : 'pick'} onClick={() => { setEditing(false); onAnswer({ status: 'confirmed' }) }}>Yes</button>
        {edit ? (
          <button type="button" className={editing || status === 'corrected' ? 'pick is-on' : 'pick'} onClick={() => setEditing((v) => !v)}>Not quite</button>
        ) : null}
        <button type="button" className={status === 'unsure' ? 'pick is-on' : 'pick'} onClick={() => { setEditing(false); onAnswer({ status: 'unsure' }) }}>I don't know</button>
      </div>

      {editing && edit ? (
        <CardEditor card={card} onSave={(value) => { onAnswer({ status: 'corrected', value }); setEditing(false) }} />
      ) : null}

      <details className="sat-sources">
        <summary>More details</summary>
        <p>How sure we are: {card.confidence}. Sources:</p>
        <ul>
          {dedupe(card.evidence.map((e) => `${e.dataset} · ${e.native_resolution} · ${e.period}`)).map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </details>
    </li>
  )
}

function CardEditor({ card, onSave }: { card: Card; onSave: (value: unknown) => void }) {
  const edit = card.edit!
  const initialMonths = Array.isArray(card.value) && card.value.every((v) => typeof v === 'number' && v >= 1 && v <= 12)
    ? (card.value as number[])
    : []
  const [months, setMonths] = useState<number[]>(initialMonths)

  if (edit.type === 'months') {
    return (
      <div className="card-editor">
        <p>Which months are right?</p>
        <div className="month-grid">
          {MONTHS.map((m, i) => (
            <button
              key={m}
              type="button"
              className={months.includes(i + 1) ? 'pick is-on' : 'pick'}
              aria-pressed={months.includes(i + 1)}
              onClick={() => setMonths((cur) => (cur.includes(i + 1) ? cur.filter((x) => x !== i + 1) : [...cur, i + 1].sort((a, b) => a - b)))}
            >
              {m}
            </button>
          ))}
        </div>
        <button type="button" className="secondary" onClick={() => onSave(months)}>Save</button>
      </div>
    )
  }
  if ('options' in edit && edit.options?.length) {
    return (
      <div className="card-editor">
        <p>What fits better?</p>
        <div className="option-row">
          {edit.options.map((option) => (
            <button key={option} type="button" className="pick" onClick={() => onSave(option)}>{option}</button>
          ))}
        </div>
      </div>
    )
  }
  return null
}

function FieldPreview({ geometry }: { geometry: Geometry }) {
  const node = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!node.current) return
    const c = centerOf(geometry)
    const map = new maplibregl.Map({
      container: node.current,
      style: baseStyle('imagery'),
      center: [c.lng, c.lat],
      zoom: 15,
      interactive: false,
      attributionControl: { compact: true },
    })
    collapseAttribution(map)
    map.on('load', () => {
      showField(map, geometry)
      fitField(map, geometry, 16)
    })
    pinMarker(c).addTo(map)
    return () => map.remove()
  }, [geometry])
  return (
    <div className="sat-block">
      <p className="sat-badge">Satellite view of your field</p>
      <div className="map-frame">
        <div ref={node} className="locate-map preview-map" aria-label="Satellite image of the field" role="img" />
      </div>
    </div>
  )
}

export function BackButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button type="button" className="card-back" onClick={onClick} aria-label={label}>
      <svg viewBox="0 0 16 16" aria-hidden="true">
        <path d="M10 3L5 8l5 5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  )
}

function describe(value: unknown) {
  if (Array.isArray(value)) {
    return value.length ? value.map((m) => (typeof m === 'number' ? MONTHS[m - 1] : String(m))).join(', ') : 'none'
  }
  return String(value ?? '')
}

function dedupe(items: string[]) {
  return [...new Set(items)]
}
