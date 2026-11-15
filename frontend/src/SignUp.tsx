import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import type { Geometry, Polygon } from 'geojson'
import type { Answers, Mode, PrefillResponse } from './api'
import { emptyAnswers, fromDetailed, fromQuick } from './answers'
import DetailedSetup, { createDetailedDraft, type DetailedDraft } from './DetailedSetup'
import LanguageDisclaimer from './LanguageDisclaimer'
import LocateMap from './LocateMap'
import { centerOf } from './mapkit'
import SatelliteCards, { BackButton, type CardAnswers } from './SatelliteCards'
import { isLanguage, translate, type LanguageCode } from './i18n'
import './SignUp.css'

export type UnitSystem = 'imperial' | 'metric'

export type QuestionPath = 'quick' | 'detailed' | 'explore'

export type QuickCrop = {
  crop: string
  planting: string
  harvest: string
}

export type QuickAnswers = {
  notFarming: boolean
  crops: QuickCrop[]
  water: string
  equipment: string
  goal: string
  avoided: string[]
}

/** Everything the wizard collected, ready for POST /analyze (and for saving, when signed in). */
export type SetupResult = {
  geometry: Geometry
  mode: Mode
  answers: Answers
  reportLanguages: LanguageCode[]
  units: UnitSystem
  displayName: string
  prefill: PrefillResponse | null
  questions: QuestionPath
  quick?: QuickAnswers
  detailed?: DetailedDraft
}

type SignUpProps = {
  /** Guests skip the profile name; signed-in users already have an Auth0 account. */
  guest: boolean
  email?: string
  initialName?: string
  initialUnits?: UnitSystem
  onBack: () => void
  onFinish: (result: SetupResult) => void
}

type CropRow = QuickCrop & { id: string }

type QuickDraft = {
  notFarming: boolean
  crops: CropRow[]
  water: string
  equipment: string
  goal: string
  avoided: string[]
  avoidedSkipped: boolean
}

type QuickErrors = {
  crops?: string
  water?: string
  equipment?: string
  goal?: string
}

type Step = 1 | 2 | 3 | 4 | 5 | 6 | 7

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]

const WATER_OPTIONS = [
  { value: 'irrigated', label: 'Irrigated' },
  { value: 'rainfed', label: 'Rain-fed' },
  { value: 'mixed', label: 'Some of each' },
  { value: 'unknown', label: "I don't know" },
]

const EQUIPMENT_OPTIONS = [
  { value: 'hand', label: 'Hand tools' },
  { value: 'animal', label: 'Animal-drawn' },
  { value: 'small-tractor', label: 'Small tractor' },
  { value: 'full', label: 'Full machinery' },
  { value: 'unknown', label: "I don't know" },
]

const GOAL_OPTIONS = [
  { value: 'water', label: 'Save water' },
  { value: 'soil', label: 'Build soil' },
  { value: 'earn', label: 'Earn more' },
  { value: 'feed', label: 'Feed the household' },
  { value: 'survive', label: 'Survive bad years' },
  { value: 'unknown', label: "Not sure: weigh all goals equally" },
]

function blankCrop(): CropRow {
  return { id: crypto.randomUUID(), crop: '', planting: '', harvest: '' }
}

function emptyQuick(): QuickDraft {
  return {
    notFarming: false,
    crops: [blankCrop()],
    water: '',
    equipment: '',
    goal: '',
    avoided: [],
    avoidedSkipped: false,
  }
}

const TITLES: Record<Step, string> = {
  1: 'setup-title',
  2: 'locate-title',
  3: 'confirm-title',
  4: 'questions-title',
  5: 'quick-title',
  6: 'detailed-title',
  7: 'lang-title',
}

export default function SignUp({ guest, email, initialName = '', initialUnits, onBack, onFinish }: SignUpProps) {
  const formId = useId()
  const [step, setStep] = useState<Step>(1)
  const [displayName, setDisplayName] = useState(initialName)
  const [units, setUnits] = useState<'' | UnitSystem>(initialUnits ?? '')
  const [unitsError, setUnitsError] = useState<string>()
  const [geometry, setGeometry] = useState<Geometry | null>(null)
  const [prefillData, setPrefillData] = useState<PrefillResponse | null>(null)
  const [cardAnswers, setCardAnswers] = useState<CardAnswers>({})
  const [questionPath, setQuestionPath] = useState<QuestionPath | null>(null)
  const [quickDraft, setQuickDraft] = useState<QuickDraft>(emptyQuick)
  const [detailedDraft, setDetailedDraft] = useState<DetailedDraft | null>(null)
  const [languages, setLanguages] = useState<LanguageCode[]>(['en'])
  const [languageAccepted, setLanguageAccepted] = useState(false)
  const system: UnitSystem = units === 'imperial' ? 'imperial' : 'metric'

  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [step])

  function submitPreferences(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (units !== 'imperial' && units !== 'metric') {
      setUnitsError('Choose a measurement system.')
      document.getElementById(`${formId}-units`)?.focus()
      return
    }
    setStep(2)
  }

  function chooseGeometry(next: Geometry | null) {
    setGeometry(next)
    setPrefillData(null)
    setCardAnswers({})
  }

  const slopeText = prefillData?.cards.find((c) => c.id === 'slope')?.statement ?? ''

  function continueQuestions() {
    if (!geometry || !questionPath) return
    if (questionPath === 'quick') {
      setStep(5)
      return
    }
    if (questionPath === 'detailed') {
      const at = centerOf(geometry)
      const ring = geometry.type === 'Polygon'
        ? (geometry as Polygon).coordinates[0].slice(0, -1).map(([lng, lat]) => ({ lat, lng }))
        : []
      setDetailedDraft((current) => current ?? { ...createDetailedDraft(system, at, slopeText, ring), displayName })
      setStep(6)
      return
    }
    openLanguage()
  }

  function openLanguage(preferred?: string) {
    if (preferred && isLanguage(preferred)) setLanguages((current) => [preferred, ...current.filter((l) => l !== preferred)].slice(0, 2))
    setLanguageAccepted(false)
    setStep(7)
  }

  function finish() {
    if (!geometry || !questionPath || !languageAccepted) return
    const quick: QuickAnswers = {
      notFarming: quickDraft.notFarming,
      crops: quickDraft.notFarming
        ? []
        : quickDraft.crops.map((row) => ({ crop: row.crop.trim(), planting: row.planting, harvest: row.harvest })),
      water: quickDraft.water,
      equipment: quickDraft.equipment,
      goal: quickDraft.goal,
      avoided: quickDraft.avoided,
    }
    const answers =
      questionPath === 'quick'
        ? fromQuick(quick, cardAnswers)
        : questionPath === 'detailed' && detailedDraft
          ? fromDetailed(detailedDraft, cardAnswers)
          : emptyAnswers(cardAnswers)
    onFinish({
      geometry,
      mode: questionPath === 'explore' ? 'exploring' : questionPath,
      answers,
      reportLanguages: languages,
      units: system,
      displayName: (detailedDraft?.displayName || displayName).trim(),
      prefill: prefillData,
      questions: questionPath,
      quick: questionPath === 'quick' ? quick : undefined,
      detailed: questionPath === 'detailed' && detailedDraft ? detailedDraft : undefined,
    })
  }

  const wide = step === 2

  return (
    <main className={wide ? 'signup is-locate' : 'signup'} data-testid="signup">
      <div className="signup-column">
        <header className="signup-header">
          <button type="button" className="back" onClick={onBack}>
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M10 3L5 8l5 5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {step === 7 ? translate(languages[0], 'back') : 'Home'}
          </button>
          <p className="wordmark">
            <Sprout />
            <span>Sow Smart</span>
          </p>
        </header>

        <section className={wide ? 'signup-card is-locate' : 'signup-card'} aria-labelledby={TITLES[step]}>
          {step === 1 ? (
            <div className="step-panel" key="setup">
              <p className="step">{guest ? 'Guest · nothing is saved' : 'Your account'}</p>
              <h1 id="setup-title">{guest ? 'Before we start' : 'Set up your profile'}</h1>
              {!guest && email ? <p className="signed-in-as">Signed in as {email}</p> : null}

              <form className="signup-form" onSubmit={submitPreferences} noValidate>
                {!guest ? (
                  <div className="field">
                    <label htmlFor={`${formId}-name`}>Display name (optional)</label>
                    <input
                      id={`${formId}-name`}
                      className="control"
                      name="displayName"
                      type="text"
                      autoComplete="nickname"
                      maxLength={40}
                      placeholder="What should we call you?"
                      value={displayName}
                      onChange={(event) => setDisplayName(event.target.value)}
                    />
                  </div>
                ) : null}

                <div className="field">
                  <label htmlFor={`${formId}-units`}>Preferred measurement system</label>
                  <select
                    id={`${formId}-units`}
                    className={units ? 'control unit-select' : 'control unit-select is-placeholder'}
                    name="units"
                    value={units}
                    aria-invalid={unitsError ? true : undefined}
                    aria-describedby={unitsError ? `${formId}-units-error` : undefined}
                    onChange={(event) => {
                      setUnits(event.target.value as '' | UnitSystem)
                      setUnitsError(undefined)
                    }}
                  >
                    <option value="" disabled>
                      Choose a system
                    </option>
                    <option value="metric">Metric (hectares, mm, °C)</option>
                    <option value="imperial">Imperial (acres, inches, °F)</option>
                  </select>
                  {unitsError ? (
                    <p id={`${formId}-units-error`} className="field-error" role="alert">
                      {unitsError}
                    </p>
                  ) : null}
                </div>

                <p className="helper">
                  SowSmart supports your own judgment and local agricultural expertise. It never replaces them.
                </p>

                <button type="submit" className="continue">
                  Next
                </button>
              </form>
            </div>
          ) : step === 2 ? (
            <div className="step-panel locate-panel" key="location">
              <div className="locate-head">
                <BackButton onClick={() => setStep(1)} label="Back" />
                <h1 id="locate-title" className="where">
                  Where is your land?
                </h1>
              </div>
              <LocateMap geometry={geometry} onGeometry={chooseGeometry} units={system} />
              <button type="button" className="continue create-account" disabled={!geometry} onClick={() => setStep(3)}>
                See what the satellites see
              </button>
            </div>
          ) : step === 3 && geometry ? (
            <SatelliteCards
              geometry={geometry}
              data={prefillData}
              onData={setPrefillData}
              answers={cardAnswers}
              onAnswers={setCardAnswers}
              onBack={() => setStep(2)}
              onContinue={() => setStep(4)}
            />
          ) : step === 4 ? (
            <QuestionPath
              selected={questionPath}
              onSelect={setQuestionPath}
              onBack={() => setStep(3)}
              onContinue={continueQuestions}
            />
          ) : step === 5 ? (
            <QuickFive draft={quickDraft} onDraft={setQuickDraft} onBack={() => setStep(4)} onFinish={() => openLanguage()} />
          ) : step === 6 && detailedDraft && geometry ? (
            <DetailedSetup
              draft={detailedDraft}
              slopeText={slopeText}
              onDraft={(profile) => setDetailedDraft(profile)}
              onBack={() => setStep(4)}
              onReset={() => {
                const fresh = createDetailedDraft(system, centerOf(geometry), slopeText)
                setDetailedDraft({ ...fresh, notice: 'Removed from this browser. Nothing was stored on a server.' })
              }}
              onFinish={(profile) => {
                if (!profile.consent) return
                openLanguage(profile.language)
              }}
            />
          ) : step === 7 ? (
            <LanguageDisclaimer
              languages={languages}
              accepted={languageAccepted}
              onLanguages={(next) => {
                setLanguages(next)
                setDetailedDraft((current) => (current ? { ...current, language: next[0] } : current))
              }}
              onAccepted={setLanguageAccepted}
              onBack={() => {
                if (questionPath === 'quick') setStep(5)
                else if (questionPath === 'detailed') setStep(6)
                else setStep(4)
              }}
              onContinue={finish}
            />
          ) : null}
        </section>
      </div>
    </main>
  )
}

const QUESTION_PATHS: { id: QuestionPath; title: string; detail: string }[] = [
  { id: 'quick', title: 'Quick 5', detail: '5 fast questions to get started right away' },
  { id: 'detailed', title: 'Detailed', detail: 'In-depth setup for tailored planting & soil advice' },
  { id: 'explore', title: 'Just exploring', detail: 'No farm details: see what this land and its climate suggest' },
]

function QuestionPath({
  selected,
  onSelect,
  onBack,
  onContinue,
}: {
  selected: QuestionPath | null
  onSelect: (path: QuestionPath) => void
  onBack: () => void
  onContinue: () => void
}) {
  return (
    <div className="step-panel questions-panel" key="questions">
      <div className="ask-head">
        <button type="button" className="card-back" onClick={onBack} aria-label="Back to location details">
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <path
              d="M10 3L5 8l5 5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        <h1 id="questions-title" className="ask">
          Which options for questions?
        </h1>
      </div>

      <div className="path-list" role="radiogroup" aria-label="Which options for questions?">
        {QUESTION_PATHS.map((path) => {
          const isSelected = selected === path.id
          return (
            <button
              key={path.id}
              type="button"
              className={isSelected ? 'path-option is-selected' : 'path-option'}
              role="radio"
              aria-checked={isSelected}
              onClick={() => onSelect(path.id)}
            >
              <span className="path-copy">
                <strong>{path.title}</strong>
                <span>{path.detail}</span>
              </span>
              <span className="path-check" aria-hidden="true">
                <svg viewBox="0 0 16 16">
                  <path
                    d="M3.5 8.2 6.5 11.2 12.5 4.8"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
            </button>
          )
        })}
      </div>

      <button type="button" className="continue" disabled={!selected} onClick={onContinue}>
        Continue
      </button>
    </div>
  )
}

function validateQuick(draft: QuickDraft): QuickErrors {
  const errors: QuickErrors = {}
  if (!draft.notFarming) {
    // Blank rows are fine ("I don't know": the engine estimates the rotation from when the field
    // looks green). A row that is only partly filled needs finishing.
    const partial = draft.crops.some((row) => {
      const filled = [row.crop.trim(), row.planting, row.harvest].filter(Boolean).length
      return filled > 0 && filled < 3
    })
    if (partial) errors.crops = 'Finish the crop row (name and both months), or clear it if you are not sure.'
  }
  if (!draft.water) errors.water = 'Choose how the field is watered.'
  if (!draft.equipment) errors.equipment = 'Choose the equipment you use.'
  if (!draft.goal) errors.goal = 'Choose your top goal.'
  return errors
}

function QuickFive({
  draft,
  onDraft,
  onBack,
  onFinish,
}: {
  draft: QuickDraft
  onDraft: (draft: QuickDraft) => void
  onBack: () => void
  onFinish: (draft: QuickDraft) => void
}) {
  const [chipText, setChipText] = useState('')
  const [errors, setErrors] = useState<QuickErrors>({})
  const [submitted, setSubmitted] = useState(false)
  const pendingFocus = useRef<string | null>(null)

  useEffect(() => {
    const id = pendingFocus.current
    if (!id) return
    pendingFocus.current = null
    document.getElementById(`crop-${id}`)?.focus()
  }, [draft.crops])

  function update(next: QuickDraft) {
    onDraft(next)
    if (submitted) setErrors(validateQuick(next))
  }

  function setRow(id: string, partial: Partial<CropRow>) {
    update({
      ...draft,
      crops: draft.crops.map((row) => (row.id === id ? { ...row, ...partial } : row)),
    })
  }

  function addCrop() {
    const row = blankCrop()
    pendingFocus.current = row.id
    update({ ...draft, crops: [...draft.crops, row] })
  }

  function removeCrop(id: string) {
    update({ ...draft, crops: draft.crops.filter((row) => row.id !== id) })
  }

  function addChip(raw: string) {
    const name = raw.trim().replace(/,+$/, '')
    if (!name) {
      setChipText('')
      return draft
    }
    const exists = draft.avoided.some((item) => item.toLowerCase() === name.toLowerCase())
    const next = {
      ...draft,
      avoided: exists ? draft.avoided : [...draft.avoided, name],
      avoidedSkipped: false,
    }
    update(next)
    setChipText('')
    return next
  }

  function onChipKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault()
      addChip(chipText)
      return
    }
    if (event.key === 'Backspace' && chipText === '' && draft.avoided.length > 0) {
      update({ ...draft, avoided: draft.avoided.slice(0, -1), avoidedSkipped: false })
    }
  }

  function skipAvoided() {
    setChipText('')
    update({ ...draft, avoided: [], avoidedSkipped: true })
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next = chipText.trim() ? addChip(chipText) : draft
    const nextErrors = validateQuick(next)
    setSubmitted(true)
    setErrors(nextErrors)
    if (nextErrors.crops) {
      const row = next.crops.find((item) => !item.crop.trim() || !item.planting || !item.harvest)
      const field = row
        ? !row.crop.trim()
          ? `crop-${row.id}`
          : !row.planting
            ? `plant-${row.id}`
            : `harvest-${row.id}`
        : 'quick-not-farming'
      document.getElementById(field)?.focus()
      return
    }
    if (nextErrors.water) {
      document.getElementById('quick-water')?.focus()
      return
    }
    if (nextErrors.equipment) {
      document.getElementById('quick-equipment')?.focus()
      return
    }
    if (nextErrors.goal) {
      document.getElementById('quick-goal')?.focus()
      return
    }
    onFinish(next)
  }

  return (
    <div className="step-panel questions-panel quick-panel">
      <div className="ask-head quick-top">
        <button type="button" className="card-back" onClick={onBack} aria-label="Back to question options">
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <path
              d="M10 3L5 8l5 5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        <div className="quick-titles">
          <h1 id="quick-title" className="ask">
            Quick 5 Setup
          </h1>
          <p className="ask-sub">Tell us a bit about your land</p>
        </div>
      </div>

      <form className="quick-form" onSubmit={submit} noValidate>
        <fieldset className="q-block">
          <legend className="q-label">
            <span className="q-num">1</span>
            What do you grow now, and in which months?
            <span className="q-star" aria-hidden="true">
              *
            </span>
          </legend>
          <label className={draft.notFarming ? 'farm-toggle is-on' : 'farm-toggle'}>
            <input
              id="quick-not-farming"
              type="checkbox"
              checked={draft.notFarming}
              onChange={(event) => update({ ...draft, notFarming: event.target.checked })}
            />
            <span>I'm not farming this land yet</span>
          </label>
          {!draft.notFarming ? (
            <p className="helper">Not sure? Leave it blank and we'll estimate your crop months from when the field looks green from space.</p>
          ) : null}
          <div className={draft.notFarming ? 'crop-slot is-closed' : 'crop-slot'} inert={draft.notFarming}>
            <div className="crop-slot-inner">
              {draft.crops.map((row, index) => {
                const cropMissing = submitted && !!errors.crops && !row.crop.trim()
                const plantMissing = submitted && !!errors.crops && !row.planting
                const harvestMissing = submitted && !!errors.crops && !row.harvest
                return (
                  <div className="crop-row" key={row.id}>
                    {index > 0 ? (
                      <button
                        type="button"
                        className="crop-remove"
                        aria-label={`Remove crop ${index + 1}`}
                        onClick={() => removeCrop(row.id)}
                      >
                        ×
                      </button>
                    ) : null}
                    <div className="field">
                      <label htmlFor={`crop-${row.id}`}>Crop</label>
                      <input
                        id={`crop-${row.id}`}
                        className="control"
                        name="crop"
                        type="text"
                        autoComplete="off"
                        placeholder="e.g., Corn, Tomatoes"
                        value={row.crop}
                        aria-invalid={cropMissing || undefined}
                        aria-describedby={errors.crops ? 'quick-crops-error' : undefined}
                        onChange={(event) => setRow(row.id, { crop: event.target.value })}
                      />
                    </div>
                    <div className="month-pair">
                      <div className="field">
                        <label htmlFor={`plant-${row.id}`}>Planting Month</label>
                        <select
                          id={`plant-${row.id}`}
                          className={row.planting ? 'control unit-select' : 'control unit-select is-placeholder'}
                          value={row.planting}
                          aria-invalid={plantMissing || undefined}
                          aria-describedby={errors.crops ? 'quick-crops-error' : undefined}
                          onChange={(event) => setRow(row.id, { planting: event.target.value })}
                        >
                          <option value="">Month</option>
                          {MONTHS.map((month) => (
                            <option key={month} value={month}>
                              {month}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="field">
                        <label htmlFor={`harvest-${row.id}`}>Harvest Month</label>
                        <select
                          id={`harvest-${row.id}`}
                          className={row.harvest ? 'control unit-select' : 'control unit-select is-placeholder'}
                          value={row.harvest}
                          aria-invalid={harvestMissing || undefined}
                          aria-describedby={errors.crops ? 'quick-crops-error' : undefined}
                          onChange={(event) => setRow(row.id, { harvest: event.target.value })}
                        >
                          <option value="">Month</option>
                          {MONTHS.map((month) => (
                            <option key={month} value={month}>
                              {month}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>
                )
              })}
              <button type="button" className="add-crop" onClick={addCrop}>
                + Add more crops
              </button>
              {errors.crops ? (
                <p id="quick-crops-error" className="field-error" role="alert">
                  {errors.crops}
                </p>
              ) : null}
            </div>
          </div>
        </fieldset>

        <div className="q-block">
          <label className="q-label" htmlFor="quick-water">
            <span className="q-num">2</span>
            Is it irrigated or rain-fed?
            <span className="q-star" aria-hidden="true">
              *
            </span>
          </label>
          <select
            id="quick-water"
            className={draft.water ? 'control unit-select' : 'control unit-select is-placeholder'}
            name="water"
            value={draft.water}
            aria-invalid={errors.water ? true : undefined}
            aria-describedby={errors.water ? 'quick-water-error' : undefined}
            onChange={(event) => update({ ...draft, water: event.target.value })}
          >
            <option value="">Choose one</option>
            {WATER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {errors.water ? (
            <p id="quick-water-error" className="field-error" role="alert">
              {errors.water}
            </p>
          ) : null}
        </div>

        <div className="q-block">
          <label className="q-label" htmlFor="quick-equipment">
            <span className="q-num">3</span>
            What equipment do you use?
            <span className="q-star" aria-hidden="true">
              *
            </span>
          </label>
          <select
            id="quick-equipment"
            className={draft.equipment ? 'control unit-select' : 'control unit-select is-placeholder'}
            name="equipment"
            value={draft.equipment}
            aria-invalid={errors.equipment ? true : undefined}
            aria-describedby={errors.equipment ? 'quick-equipment-error' : undefined}
            onChange={(event) => update({ ...draft, equipment: event.target.value })}
          >
            <option value="">Choose one</option>
            {EQUIPMENT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {errors.equipment ? (
            <p id="quick-equipment-error" className="field-error" role="alert">
              {errors.equipment}
            </p>
          ) : null}
        </div>

        <div className="q-block">
          <label className="q-label" htmlFor="quick-goal">
            <span className="q-num">4</span>
            Your top goal (pick one)
            <span className="q-star" aria-hidden="true">
              *
            </span>
          </label>
          <select
            id="quick-goal"
            className={draft.goal ? 'control unit-select' : 'control unit-select is-placeholder'}
            name="goal"
            value={draft.goal}
            aria-invalid={errors.goal ? true : undefined}
            aria-describedby={errors.goal ? 'quick-goal-error' : undefined}
            onChange={(event) => update({ ...draft, goal: event.target.value })}
          >
            <option value="">Choose one</option>
            {GOAL_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {errors.goal ? (
            <p id="quick-goal-error" className="field-error" role="alert">
              {errors.goal}
            </p>
          ) : null}
        </div>

        <div className="q-block">
          <div className="q-head">
            <label className="q-label" htmlFor="quick-avoided">
              <span className="q-num">5</span>
              Crops you won't grow
              <span className="q-optional">optional</span>
            </label>
            <button type="button" className="skip-link" onClick={skipAvoided}>
              Skip
            </button>
          </div>
          <div className="chip-box">
            {draft.avoided.map((crop) => (
              <span className="chip" key={crop}>
                {crop}
                <button
                  type="button"
                  aria-label={`Remove ${crop}`}
                  onClick={() =>
                    update({
                      ...draft,
                      avoided: draft.avoided.filter((item) => item !== crop),
                      avoidedSkipped: false,
                    })
                  }
                >
                  ×
                </button>
              </span>
            ))}
            <input
              id="quick-avoided"
              name="avoided"
              type="text"
              autoComplete="off"
              enterKeyHint="done"
              placeholder={draft.avoided.length === 0 ? 'e.g., Soybeans, Cotton (optional)' : 'Add another'}
              value={chipText}
              onChange={(event) => setChipText(event.target.value)}
              onKeyDown={onChipKey}
              onBlur={() => {
                if (chipText.trim()) addChip(chipText)
              }}
            />
          </div>
          {draft.avoidedSkipped && draft.avoided.length === 0 ? <p className="skipped-note">Skipped for now</p> : null}
        </div>

        <button type="submit" className="continue">
          Finish & View My Plan
        </button>
      </form>
    </div>
  )
}


function Sprout() {
  return (
    <svg className="wordmark-sprout" viewBox="0 0 36 36" aria-hidden="true">
      <path
        d="M18 33.5V18.2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <path d="M17.6 22.8c-1.4-4.2-5.2-7.3-10.4-8.2 2.2 4.6 6 7.4 10.4 8.2z" fill="#4d7a5e" />
      <path d="M18.3 16.6c2.2-5.6 7.4-9.4 13.2-9.8-2.4 5.6-7.6 9.4-13.2 9.8z" fill="currentColor" />
    </svg>
  )
}

