import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import type { Geometry, Polygon } from 'geojson'
import type { Answers, Mode, PrefillResponse } from './api'
import { emptyAnswers, fromDetailed, fromQuick } from './answers'
import DetailedSetup, { createDetailedDraft, type DetailedDraft } from './DetailedSetup'
import LanguageDisclaimer from './LanguageDisclaimer'
import LocateMap from './LocateMap'
import { centerOf } from './mapkit'
import SatelliteCards, { type CardAnswers } from './SatelliteCards'
import YearStrip, { rowFromBareMonths, rowFromCrops, stressFromCards, type StripRow } from './YearStrip'
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

/** The 4 steps the farmer sees; the internal steps 4-6 are all "Your farm". */
const STAGES = ['Your land', 'Satellite check', 'Your farm', 'Report']
const STAGE_OF: Record<Step, number> = { 1: 0, 2: 1, 3: 2, 4: 3, 5: 3, 6: 3, 7: 4 }

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

  function back() {
    if (step === 7) {
      if (questionPath === 'quick') setStep(5)
      else if (questionPath === 'detailed') setStep(6)
      else setStep(4)
    } else if (step === 5 || step === 6) setStep(4)
    else if (step > 1) setStep((step - 1) as Step)
  }

  const backLabel: Record<Step, string> = {
    1: 'Back',
    2: 'Back',
    3: 'Back to the map',
    4: 'Back to the satellite check',
    5: 'Back to question options',
    6: 'Back to question options',
    7: translate(languages[0], 'back'),
  }

  // The pinned Year Strip: what the satellites saw (with the farmer's corrections), plus the
  // crops typed in Quick 5. Hidden until there is something to draw.
  const stripCards = (prefillData?.cards ?? []).map((card) => {
    const answer = cardAnswers[card.id]
    return answer?.status === 'corrected' && Array.isArray(answer.value) ? { ...card, value: answer.value } : card
  })
  const bareValue = stripCards.find((card) => card.id === 'bare_months')?.value
  const bareMonths = Array.isArray(bareValue) ? bareValue.filter((m): m is number => typeof m === 'number') : null
  const typedCrops =
    questionPath === 'quick' && (step === 5 || step === 7) && !quickDraft.notFarming
      ? quickDraft.crops
          .filter((row) => row.crop.trim() && row.planting && row.harvest)
          .map((row) => ({
            crop: row.crop.trim(),
            plant_month: MONTHS.indexOf(row.planting) + 1,
            harvest_month: MONTHS.indexOf(row.harvest) + 1,
          }))
      : []
  const stripRows: StripRow[] = [
    ...(bareMonths ? [rowFromBareMonths(bareMonths, 'Field')] : []),
    ...(typedCrops.length ? [{ ...rowFromCrops(typedCrops, 'You'), highlight: true }] : []),
  ]
  const stress = stressFromCards(stripCards)
  const showStrip = (step === 3 || step === 4 || step === 5 || step === 7) && stripRows.length > 0

  return (
    <main className="signup" data-testid="signup">
      <div className="signup-column">
        {step === 1 ? (
          <header className="signup-header">
            <button type="button" className="step-back" onClick={onBack}>
              <span aria-hidden="true">‹</span> Back
            </button>
            <p className="wordmark">SowSmart</p>
          </header>
        ) : (
          <header className="stepper">
            <div className="stepper-row">
              <button type="button" className="step-back" onClick={back} aria-label={backLabel[step]}>
                <span aria-hidden="true">‹</span> {step === 7 ? translate(languages[0], 'back') : 'Back'}
              </button>
              <p className="cap">
                Step {STAGE_OF[step]} of {STAGES.length} · {STAGES[STAGE_OF[step] - 1]}
              </p>
            </div>
            <div className="stepper-bar" aria-hidden="true">
              {STAGES.map((name, i) => (
                <span key={name} className={i < STAGE_OF[step] ? 'is-done' : undefined} />
              ))}
            </div>
          </header>
        )}

        {showStrip ? (
          <div className="setup-strip">
            <div className="setup-strip-head">
              <p className="cap">Your year so far</p>
              <p className="cap setup-strip-key">Dotted: bare</p>
            </div>
            <YearStrip
              rows={stripRows}
              stress={stress.some((m) => m.flags.length) ? stress : undefined}
              legend={false}
              caption="Your year so far"
            />
          </div>
        ) : null}

        <section className="signup-card" aria-labelledby={TITLES[step]}>
          {step === 1 ? (
            <div className="step-panel" key="setup">
              <div className="step-title is-ruled">
                {!guest ? <p className="cap">Your account</p> : null}
                <h1 id="setup-title">{guest ? 'Before we start' : 'Set up your profile'}</h1>
                <p className="step-sub">
                  {guest ? 'One quick setting before we find your field.' : 'Two quick settings before we find your field.'}
                </p>
              </div>
              {!guest && email ? <p className="signed-in-as">Signed in as {email}</p> : null}

              <form className="signup-form" onSubmit={submitPreferences} noValidate>
                {!guest ? (
                  <div className="field">
                    <label htmlFor={`${formId}-name`}>
                      What should we call you? <span className="optional">(optional)</span>
                    </label>
                    <input
                      id={`${formId}-name`}
                      className="control"
                      name="displayName"
                      type="text"
                      autoComplete="nickname"
                      maxLength={40}
                      placeholder="Your name"
                      value={displayName}
                      onChange={(event) => setDisplayName(event.target.value)}
                    />
                  </div>
                ) : null}

                <div className="field">
                  <p className="field-label" id={`${formId}-units-label`}>
                    Measurement system
                  </p>
                  <div
                    className="pick-row"
                    role="group"
                    aria-labelledby={`${formId}-units-label`}
                    aria-describedby={unitsError ? `${formId}-units-error` : undefined}
                  >
                    {UNIT_OPTIONS.map((option, index) => (
                      <button
                        key={option.value}
                        id={index === 0 ? `${formId}-units` : undefined}
                        type="button"
                        className={units === option.value ? 'pick is-on' : 'pick'}
                        aria-pressed={units === option.value}
                        onClick={() => {
                          setUnits(option.value)
                          setUnitsError(undefined)
                        }}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                  {unitsError ? (
                    <p id={`${formId}-units-error`} className="field-error" role="alert">
                      {unitsError}
                    </p>
                  ) : null}
                </div>

                {guest ? (
                  <div className="index-card guest-note">
                    <p className="cap">Using SowSmart as a guest</p>
                    <p>You can do everything except save your plan. To keep it, sign up from the results.</p>
                  </div>
                ) : null}

                <p className="helper">
                  SowSmart supports your own judgment and local agricultural expertise. It never replaces them.
                </p>

                <button type="submit" className="tag-btn is-block step-cta">
                  Continue
                </button>
              </form>
            </div>
          ) : step === 2 ? (
            <div className="step-panel locate-panel" key="location">
              <div className="step-title">
                <h1 id="locate-title">Where is your land?</h1>
              </div>
              <LocateMap geometry={geometry} onGeometry={chooseGeometry} units={system} />
              <button type="button" className="tag-btn is-block step-cta" disabled={!geometry} onClick={() => setStep(3)}>
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
            <QuestionPath selected={questionPath} onSelect={setQuestionPath} onContinue={continueQuestions} />
          ) : step === 5 ? (
            <QuickFive draft={quickDraft} onDraft={setQuickDraft} onFinish={() => openLanguage()} />
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
              onContinue={finish}
            />
          ) : null}
        </section>
      </div>
    </main>
  )
}

const UNIT_OPTIONS: { value: UnitSystem; label: string }[] = [
  { value: 'metric', label: 'Metric · ha, mm, °C' },
  { value: 'imperial', label: 'Imperial · ac, in, °F' },
]

const QUESTION_PATHS: { id: QuestionPath; title: string; detail: string }[] = [
  { id: 'quick', title: 'Quick 5', detail: '5 fast questions to get started right away.' },
  { id: 'detailed', title: 'Detailed', detail: 'In-depth setup for tailored planting and soil advice.' },
  { id: 'explore', title: 'Just exploring', detail: 'No farm details: see what this land and its climate suggest.' },
]

function QuestionPath({
  selected,
  onSelect,
  onContinue,
}: {
  selected: QuestionPath | null
  onSelect: (path: QuestionPath) => void
  onContinue: () => void
}) {
  return (
    <div className="step-panel questions-panel" key="questions">
      <div className="step-title">
        <h1 id="questions-title">How much do you want to tell us?</h1>
        <p className="step-sub">More detail makes the comparison fit your farm better.</p>
      </div>

      <div className="path-list" role="radiogroup" aria-labelledby="questions-title">
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
                <svg viewBox="0 0 24 24">
                  <path d="M4 12l5 5L20 6" fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="square" />
                </svg>
              </span>
            </button>
          )
        })}
      </div>

      <button type="button" className="tag-btn is-block step-cta" disabled={!selected} onClick={onContinue}>
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
  onFinish,
}: {
  draft: QuickDraft
  onDraft: (draft: QuickDraft) => void
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

  const cropsBlank = !draft.notFarming && draft.crops.every((row) => !row.crop.trim() && !row.planting && !row.harvest)

  function dontKnowCrops() {
    update({ ...draft, notFarming: false, crops: [blankCrop()] })
  }

  return (
    <div className="step-panel questions-panel quick-panel">
      <div className="step-title">
        <h1 id="quick-title">Quick 5</h1>
        <p className="step-sub">Tell us a bit about your land. Only the starred questions are needed.</p>
      </div>

      <form className="quick-form" onSubmit={submit} noValidate>
        <fieldset className="q-block">
          <legend className="q-label">
            <span className="cap q-count">Question 1 of 5</span>
            What do you grow now, and in which months?
            <span className="q-star" aria-hidden="true">
              *
            </span>
          </legend>
          <div className={draft.notFarming ? 'crop-slot is-closed' : 'crop-slot'} inert={draft.notFarming}>
            <div className="crop-slot-inner">
              {draft.crops.map((row, index) => {
                const cropMissing = submitted && !!errors.crops && !row.crop.trim()
                const plantMissing = submitted && !!errors.crops && !row.planting
                const harvestMissing = submitted && !!errors.crops && !row.harvest
                return (
                  <div className="crop-row" key={row.id}>
                    <div className="crop-row-head">
                      <p className="cap">Crop {index + 1}</p>
                      {index > 0 ? (
                        <button
                          type="button"
                          className="crop-remove"
                          aria-label={`Remove crop ${index + 1}`}
                          onClick={() => removeCrop(row.id)}
                        >
                          Remove
                        </button>
                      ) : null}
                    </div>
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
                        <label htmlFor={`plant-${row.id}`}>Planting month</label>
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
                        <label htmlFor={`harvest-${row.id}`}>Harvest month</label>
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
                + Add another crop
              </button>
              {errors.crops ? (
                <p id="quick-crops-error" className="field-error" role="alert">
                  {errors.crops}
                </p>
              ) : null}
            </div>
          </div>
          {!draft.notFarming ? (
            <p className="helper">Not sure? Leave it blank and we'll estimate your crop months from when the field looks green from space.</p>
          ) : null}
          <div className="pick-row" role="group" aria-label="Other answers">
            <button
              id="quick-not-farming"
              type="button"
              className={draft.notFarming ? 'pick is-on' : 'pick'}
              aria-pressed={draft.notFarming}
              onClick={() => update({ ...draft, notFarming: !draft.notFarming })}
            >
              Not farming it yet
            </button>
            <button
              type="button"
              className={cropsBlank ? 'pick is-on' : 'pick'}
              aria-pressed={cropsBlank}
              onClick={dontKnowCrops}
            >
              I don't know
            </button>
          </div>
        </fieldset>

        <div className="q-block">
          <label className="q-label" htmlFor="quick-water">
            <span className="cap q-count">Question 2 of 5</span>
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
            <span className="cap q-count">Question 3 of 5</span>
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
            <span className="cap q-count">Question 4 of 5</span>
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
              <span className="cap q-count">Question 5 of 5 · optional</span>
              Crops you won't grow
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

        <button type="submit" className="tag-btn is-block step-cta">
          Continue
        </button>
      </form>
    </div>
  )
}
