import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent, type RefObject } from 'react'
import DetailedSetup, { createDetailedDraft, slopeEstimate, type DetailedDraft } from './DetailedSetup'
import LanguageDisclaimer from './LanguageDisclaimer'
import { isLanguage, translate, type LanguageCode } from './i18n'
import './SignUp.css'

export type UnitSystem = 'imperial' | 'metric'

export type LandAnswer = 'yes' | 'no' | 'unsure'

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

export type SignUpAccount = {
  username: string
  email: string
  password: string
  units: UnitSystem
  latitude: number
  longitude: number
  confirmation: LandAnswer
  questions: QuestionPath
  language: LanguageCode
  quick?: QuickAnswers
  detailed?: DetailedDraft
}

type SignUpProps = {
  onBack: () => void
  onLogin: () => void
  onCreate: (account: SignUpAccount) => void
}

type FieldErrors = {
  username?: string
  email?: string
  password?: string
  units?: string
}

type Pin = { lat: number; lng: number }

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

type LandDetails = {
  terrain: string
  cover: string
  weather: string
}

type LeafletMarker = { setLatLng: (latlng: [number, number]) => void }

type LeafletMap = {
  setView: (center: [number, number], zoom: number) => LeafletMap
  on: (event: 'click', handler: (event: { latlng: Pin }) => void) => void
  remove: () => void
  invalidateSize: () => void
}

type LeafletLib = {
  map: (element: HTMLElement, options?: object) => LeafletMap
  tileLayer: (url: string, options?: object) => { addTo: (map: LeafletMap) => void }
  marker: (latlng: [number, number], options?: object) => LeafletMarker & { addTo: (map: LeafletMap) => LeafletMarker }
  divIcon: (options: object) => object
}

declare global {
  interface Window {
    L?: LeafletLib
  }
}

const USERNAME_PATTERN = /^[A-Za-z0-9_]{3,24}$/
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PIN_ICON = `<svg viewBox="0 0 24 36" width="24" height="36" aria-hidden="true"><path fill="#1c3d32" d="M12 35.2S23 21.2 23 12A11 11 0 1 0 1 12c0 9.2 11 23.2 11 23.2z"/><circle cx="12" cy="12" r="4.2" fill="#f7f6f1"/></svg>`

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
]

const GOAL_OPTIONS = [
  { value: 'water', label: 'Save water' },
  { value: 'soil', label: 'Build soil' },
  { value: 'earn', label: 'Earn more' },
  { value: 'feed', label: 'Feed the household' },
  { value: 'survive', label: 'Survive bad years' },
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

export default function SignUp({ onBack, onLogin, onCreate }: SignUpProps) {
  const formId = useId()
  const mapNode = useRef<HTMLDivElement>(null)
  const mapRef = useRef<LeafletMap | null>(null)
  const markerRef = useRef<LeafletMarker | null>(null)
  const pinRef = useRef<Pin | null>(null)
  const [step, setStep] = useState<1 | 2 | 3 | 4 | 5 | 6 | 7>(1)
  const [reportLanguage, setReportLanguage] = useState<LanguageCode>('en')
  const [languageAccepted, setLanguageAccepted] = useState(false)
  const [answer, setAnswer] = useState<LandAnswer | null>(null)
  const [landEdits, setLandEdits] = useState<LandDetails | null>(null)
  const [landUpdated, setLandUpdated] = useState(false)
  const [questionPath, setQuestionPath] = useState<QuestionPath | null>(null)
  const [quickDraft, setQuickDraft] = useState<QuickDraft>(emptyQuick)
  const [detailedDraft, setDetailedDraft] = useState<DetailedDraft | null>(null)
  const [elevation, setElevation] = useState<{ lat: number; lng: number; meters: number } | null>(null)
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [units, setUnits] = useState<'' | UnitSystem>('')
  const [showPassword, setShowPassword] = useState(false)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [submitted, setSubmitted] = useState(false)
  const [pin, setPin] = useState<Pin | null>(null)
  const [pinError, setPinError] = useState<string>()
  const [locating, setLocating] = useState(false)

  function validate(next: { username: string; email: string; password: string; units: string }): FieldErrors {
    const nextErrors: FieldErrors = {}
    const name = next.username.trim()
    const address = next.email.trim()
    if (!name) nextErrors.username = 'Choose a username.'
    else if (!USERNAME_PATTERN.test(name)) {
      nextErrors.username = 'Use 3–24 letters, numbers, or underscores.'
    }
    if (!address) nextErrors.email = 'Enter your email.'
    else if (!EMAIL_PATTERN.test(address)) nextErrors.email = 'Enter a valid email address.'
    if (!next.password) nextErrors.password = 'Enter a password.'
    else if (next.password.length < 8) nextErrors.password = 'Use at least 8 characters.'
    if (next.units !== 'imperial' && next.units !== 'metric') {
      nextErrors.units = 'Choose a measurement system.'
    }
    return nextErrors
  }

  function update(partial: {
    username?: string
    email?: string
    password?: string
    units?: '' | UnitSystem
  }) {
    const next = {
      username: partial.username ?? username,
      email: partial.email ?? email,
      password: partial.password ?? password,
      units: partial.units ?? units,
    }
    if (partial.username !== undefined) setUsername(partial.username)
    if (partial.email !== undefined) setEmail(partial.email)
    if (partial.password !== undefined) setPassword(partial.password)
    if (partial.units !== undefined) setUnits(partial.units)
    if (submitted) setErrors(validate(next))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors = validate({ username, email, password, units })
    setSubmitted(true)
    setErrors(nextErrors)
    const firstInvalid = (['username', 'email', 'password', 'units'] as const).find((field) => nextErrors[field])
    if (firstInvalid) {
      document.getElementById(`${formId}-${firstInvalid}`)?.focus()
      return
    }
    setStep(2)
  }

  useEffect(() => {
    if ((step !== 2 && step !== 3) || !mapNode.current || !window.L) return
    const L = window.L
    const satellite = step === 3
    const start = pinRef.current
    const map = L.map(mapNode.current, { zoomControl: true, maxZoom: satellite ? 18 : 16 }).setView(
      start ? [start.lat, start.lng] : [20, 0],
      satellite ? 14 : start ? 12 : 2,
    )
    if (satellite) {
      L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        {
          attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics',
          maxZoom: 18,
        },
      ).addTo(map)
    } else {
      L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
        {
          attribution: 'Tiles &copy; Esri',
          maxZoom: 16,
        },
      ).addTo(map)
      L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
        { maxZoom: 16 },
      ).addTo(map)
    }

    const icon = L.divIcon({
      className: 'sow-pin',
      html: PIN_ICON,
      iconSize: [24, 36],
      iconAnchor: [12, 34],
    })

    const place = (lat: number, lng: number) => {
      if (markerRef.current) markerRef.current.setLatLng([lat, lng])
      else markerRef.current = L.marker([lat, lng], { icon, keyboard: false }).addTo(map)
      const next = { lat, lng }
      pinRef.current = next
      setPin(next)
      setPinError(undefined)
    }

    if (start) markerRef.current = L.marker([start.lat, start.lng], { icon, keyboard: false }).addTo(map)

    map.on('click', (event) => place(event.latlng.lat, event.latlng.lng))
    mapRef.current = map
    const timer = window.setTimeout(() => map.invalidateSize(), 50)

    return () => {
      window.clearTimeout(timer)
      map.remove()
      mapRef.current = null
      markerRef.current = null
    }
  }, [step])

  function useMyLocation() {
    if (!navigator.geolocation) {
      setPinError('Location is not available on this device. Tap the map instead.')
      return
    }
    setLocating(true)
    setPinError(undefined)
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const lat = position.coords.latitude
        const lng = position.coords.longitude
        mapRef.current?.setView([lat, lng], 13)
        if (markerRef.current) markerRef.current.setLatLng([lat, lng])
        else if (mapRef.current && window.L) {
          const icon = window.L.divIcon({
            className: 'sow-pin',
            html: PIN_ICON,
            iconSize: [24, 36],
            iconAnchor: [12, 34],
          })
          markerRef.current = window.L.marker([lat, lng], { icon, keyboard: false }).addTo(mapRef.current)
        }
        const next = { lat, lng }
        pinRef.current = next
        setPin(next)
        setLocating(false)
      },
      () => {
        setLocating(false)
        setPinError('We could not read your location. Tap the map instead.')
      },
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 },
    )
  }

  const elevationM =
    pin && elevation && elevation.lat === pin.lat && elevation.lng === pin.lng ? elevation.meters : null

  useEffect(() => {
    if (!pin || (step !== 3 && step !== 6) || elevationM != null) return
    const controller = new AbortController()
    const { lat, lng } = pin
    fetch(`https://api.open-meteo.com/v1/elevation?latitude=${lat}&longitude=${lng}`, {
      signal: controller.signal,
    })
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error('elevation'))))
      .then((data: { elevation?: number[] }) => {
        const value = data.elevation?.[0]
        if (typeof value !== 'number') return
        setElevation({ lat, lng, meters: value })
        setDetailedDraft((current) => {
          if (!current) return current
          let changed = false
          const fields = current.fields.map((field) => {
            if (field.slopeEdited) return field
            const slope = slopeEstimate(value, current.system)
            if (slope === field.slope) return field
            changed = true
            return { ...field, slope }
          })
          return changed ? { ...current, fields } : current
        })
      })
      .catch(() => undefined)
    return () => controller.abort()
  }, [step, pin, elevationM])

  function createAccount() {
    if (!pin) {
      setPinError('Drop a pin on the map, or use your location.')
      return
    }
    setStep(3)
  }

  function finishSetup() {
    if (!pin || !answer) return
    setStep(4)
  }

  function accountBase() {
    return {
      username: username.trim(),
      email: email.trim(),
      password,
      units: units as UnitSystem,
      latitude: pin!.lat,
      longitude: pin!.lng,
      confirmation: answer!,
    }
  }

  function continueQuestions() {
    if (!pin || !answer || !questionPath) return
    if (questionPath === 'quick') {
      setStep(5)
      return
    }
    if (questionPath === 'detailed') {
      const system = units === 'imperial' ? 'imperial' : 'metric'
      setDetailedDraft((current) => current ?? createDetailedDraft(system, pin, elevationM))
      setStep(6)
      return
    }
    openLanguage()
  }

  function openLanguage(preferred?: string) {
    const fromDetailed = detailedDraft && isLanguage(detailedDraft.language) ? detailedDraft.language : null
    const next = preferred && isLanguage(preferred) ? preferred : fromDetailed
    if (next) setReportLanguage(next)
    setLanguageAccepted(false)
    setStep(7)
  }

  function finishLanguage() {
    if (!pin || !answer || !questionPath || !languageAccepted) return
    const crops = quickDraft.notFarming
      ? []
      : quickDraft.crops.map((row) => ({
          crop: row.crop.trim(),
          planting: row.planting,
          harvest: row.harvest,
        }))
    onCreate({
      ...accountBase(),
      questions: questionPath,
      language: reportLanguage,
      quick:
        questionPath === 'quick'
          ? {
              notFarming: quickDraft.notFarming,
              crops,
              water: quickDraft.water,
              equipment: quickDraft.equipment,
              goal: quickDraft.goal,
              avoided: quickDraft.avoided,
            }
          : undefined,
      detailed:
        questionPath === 'detailed' && detailedDraft
          ? { ...detailedDraft, language: reportLanguage }
          : undefined,
    })
  }

  function chooseLanguage(next: LanguageCode) {
    setReportLanguage(next)
    setDetailedDraft((current) => (current ? { ...current, language: next } : current))
  }

  const usernameErrorId = `${formId}-username-error`
  const emailErrorId = `${formId}-email-error`
  const passwordErrorId = `${formId}-password-error`
  const unitsErrorId = `${formId}-units-error`

  return (
    <main className={step === 2 || step === 3 ? 'signup is-locate' : 'signup'} data-testid="signup">
      <div className="signup-column">
        <header className="signup-header">
          <button type="button" className="back" onClick={onBack}>
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path
                d="M10 3L5 8l5 5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            {step === 7 ? translate(reportLanguage, 'back') : 'Back'}
          </button>
          <p className="wordmark">
            <Sprout />
            <span>Sow Smart</span>
          </p>
        </header>

        <section
          className={step === 2 || step === 3 ? 'signup-card is-locate' : 'signup-card'}
          aria-labelledby={
            step === 3
              ? 'confirm-title'
              : step === 4
                ? 'questions-title'
                : step === 5
                  ? 'quick-title'
                  : step === 6
                    ? 'detailed-title'
                    : step === 7
                      ? 'lang-title'
                      : `${formId}-title`
          }
        >
          {step === 1 ? (
            <div className="step-panel" key="account">
              <p className="step">Step 1 of 4</p>
              <h1 id={`${formId}-title`}>Create your account</h1>

              <form className="signup-form" onSubmit={handleSubmit} noValidate>
                <div className="field">
                  <label htmlFor={`${formId}-username`}>Username</label>
                  <input
                    id={`${formId}-username`}
                    className="control"
                    name="username"
                    type="text"
                    autoComplete="username"
                    autoCapitalize="none"
                    autoCorrect="off"
                    spellCheck={false}
                    enterKeyHint="next"
                    placeholder="Choose a username"
                    value={username}
                    aria-invalid={errors.username ? true : undefined}
                    aria-describedby={errors.username ? usernameErrorId : undefined}
                    onChange={(event) => update({ username: event.target.value })}
                  />
                  {errors.username ? (
                    <p id={usernameErrorId} className="field-error" role="alert">
                      {errors.username}
                    </p>
                  ) : null}
                </div>

                <div className="field">
                  <label htmlFor={`${formId}-email`}>Email</label>
                  <input
                    id={`${formId}-email`}
                    className="control"
                    name="email"
                    type="email"
                    autoComplete="email"
                    autoCapitalize="none"
                    autoCorrect="off"
                    spellCheck={false}
                    inputMode="email"
                    enterKeyHint="next"
                    placeholder="Enter your email"
                    value={email}
                    aria-invalid={errors.email ? true : undefined}
                    aria-describedby={errors.email ? emailErrorId : undefined}
                    onChange={(event) => update({ email: event.target.value })}
                  />
                  {errors.email ? (
                    <p id={emailErrorId} className="field-error" role="alert">
                      {errors.email}
                    </p>
                  ) : null}
                </div>

                <div className="field">
                  <label htmlFor={`${formId}-password`}>Password</label>
                  <div className="password-wrap">
                    <input
                      id={`${formId}-password`}
                      className="control"
                      name="password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="new-password"
                      autoCapitalize="none"
                      autoCorrect="off"
                      enterKeyHint="next"
                      placeholder="Create a password"
                      value={password}
                      aria-invalid={errors.password ? true : undefined}
                      aria-describedby={errors.password ? passwordErrorId : undefined}
                      onChange={(event) => update({ password: event.target.value })}
                    />
                    <button
                      type="button"
                      className="peek"
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      aria-pressed={showPassword}
                      onClick={() => setShowPassword((visible) => !visible)}
                    >
                      {showPassword ? <EyeOff /> : <Eye />}
                    </button>
                  </div>
                  {errors.password ? (
                    <p id={passwordErrorId} className="field-error" role="alert">
                      {errors.password}
                    </p>
                  ) : null}
                </div>

                <div className="field">
                  <label htmlFor={`${formId}-units`}>Preferred Measurement System</label>
                  <select
                    id={`${formId}-units`}
                    className={units ? 'control unit-select' : 'control unit-select is-placeholder'}
                    name="units"
                    value={units}
                    aria-invalid={errors.units ? true : undefined}
                    aria-describedby={errors.units ? unitsErrorId : undefined}
                    onChange={(event) => update({ units: event.target.value as '' | UnitSystem })}
                  >
                    <option value="" disabled>
                      Choose a system
                    </option>
                    <option value="imperial">Imperial (inches, °F, fl oz)</option>
                    <option value="metric">Metric (cm, °C, mL)</option>
                  </select>
                  {errors.units ? (
                    <p id={unitsErrorId} className="field-error" role="alert">
                      {errors.units}
                    </p>
                  ) : null}
                </div>

                <button type="submit" className="continue">
                  Next
                </button>
              </form>

              <p className="login-prompt">
                Already have an account?{' '}
                <button type="button" className="login-link" onClick={onLogin}>
                  Log in
                </button>
              </p>
            </div>
          ) : step === 2 ? (
            <div className="step-panel locate-panel" key="location">
              <div className="locate-head">
                <button type="button" className="card-back" onClick={() => setStep(1)} aria-label="Back to account details">
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
                <h1 id={`${formId}-title`} className="where">
                  Where are you?
                </h1>
              </div>

              <div className="map-frame">
                <div ref={mapNode} className="locate-map" role="application" aria-label="Map. Tap to drop a pin." />
                <button type="button" className="locate-me" onClick={useMyLocation} disabled={locating}>
                  {locating ? 'Finding…' : 'Use My Location'}
                </button>
              </div>
              {pinError ? (
                <p className="field-error map-error" role="alert">
                  {pinError}
                </p>
              ) : null}
            </div>
          ) : step === 4 ? (
            <QuestionPath
              selected={questionPath}
              onSelect={setQuestionPath}
              onBack={() => setStep(3)}
              onContinue={continueQuestions}
            />
          ) : step === 5 ? (
            <QuickFive
              draft={quickDraft}
              onDraft={setQuickDraft}
              onBack={() => setStep(4)}
              onFinish={() => openLanguage()}
            />
          ) : step === 6 && detailedDraft ? (
            <DetailedSetup
              draft={detailedDraft}
              elevationM={elevationM}
              onDraft={(profile) => setDetailedDraft(profile)}
              onBack={() => setStep(4)}
              onReset={() => {
                if (!pin) return
                const system = units === 'imperial' ? 'imperial' : 'metric'
                const fresh = createDetailedDraft(system, pin, elevationM)
                setDetailedDraft({
                  ...fresh,
                  notice: 'Removed from this browser. Nothing was stored on a server.',
                })
              }}
              onFinish={(profile) => {
                if (!profile.consent) return
                openLanguage(profile.language)
              }}
            />
          ) : step === 7 ? (
            <LanguageDisclaimer
              language={reportLanguage}
              accepted={languageAccepted}
              onLanguage={chooseLanguage}
              onAccepted={setLanguageAccepted}
              onBack={() => {
                if (questionPath === 'quick') setStep(5)
                else if (questionPath === 'detailed') setStep(6)
                else setStep(4)
              }}
              onContinue={finishLanguage}
            />
          ) : pin ? (
            <ConfirmLand
              pin={pin}
              units={units === 'imperial' ? 'imperial' : 'metric'}
              elevationM={elevationM}
              answer={answer}
              committed={landEdits}
              updated={landUpdated}
              onAnswer={setAnswer}
              onCommit={(details) => {
                setLandEdits(details)
                setLandUpdated(true)
              }}
              onBack={() => setStep(2)}
              onFinish={finishSetup}
              mapNode={mapNode}
              mapRef={mapRef}
            />
          ) : null}
        </section>

        {step === 2 ? (
          <button type="button" className="continue create-account" onClick={createAccount}>
            Create Account
          </button>
        ) : null}
      </div>
    </main>
  )
}

function ConfirmLand({
  pin,
  units,
  elevationM,
  answer,
  committed,
  updated,
  onAnswer,
  onCommit,
  onBack,
  onFinish,
  mapNode,
  mapRef,
}: {
  pin: Pin
  units: UnitSystem
  elevationM: number | null
  answer: LandAnswer | null
  committed: LandDetails | null
  updated: boolean
  onAnswer: (answer: LandAnswer) => void
  onCommit: (details: LandDetails) => void
  onBack: () => void
  onFinish: () => void
  mapNode: RefObject<HTMLDivElement | null>
  mapRef: RefObject<LeafletMap | null>
}) {
  const fieldId = useId()
  const terrainRef = useRef<HTMLTextAreaElement>(null)
  const finishRef = useRef<HTMLButtonElement>(null)
  const preview = landPreview(pin.lat, elevationM, units)
  const [draft, setDraft] = useState<LandDetails>(committed ?? preview)
  const [editing, setEditing] = useState(false)
  const view = committed ?? preview
  const draftReady = draft.terrain.trim() !== '' && draft.cover.trim() !== '' && draft.weather.trim() !== ''
  const canFinish = answer === 'yes' || answer === 'unsure' || (answer === 'no' && updated && !editing)
  const choices: { id: LandAnswer; label: string }[] = [
    { id: 'yes', label: 'Yes' },
    { id: 'no', label: 'No' },
    { id: 'unsure', label: "I don't know" },
  ]

  useEffect(() => {
    if (!editing) return
    terrainRef.current?.focus()
  }, [editing])

  useEffect(() => {
    const timer = window.setTimeout(() => mapRef.current?.invalidateSize(), 260)
    return () => window.clearTimeout(timer)
  }, [editing, mapRef])

  function choose(id: LandAnswer) {
    if (id === 'no') {
      if (!editing) setDraft(committed ?? preview)
      setEditing(true)
    } else {
      setEditing(false)
    }
    onAnswer(id)
  }

  function saveEdits(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next = {
      terrain: draft.terrain.trim(),
      cover: draft.cover.trim(),
      weather: draft.weather.trim(),
    }
    if (!next.terrain || !next.cover || !next.weather) return
    onCommit(next)
    setDraft(next)
    setEditing(false)
    window.setTimeout(() => finishRef.current?.focus(), 220)
  }

  return (
    <div className="step-panel locate-panel confirm-panel" key="confirm">
      <div className="locate-head">
        <button type="button" className="card-back" onClick={onBack} aria-label="Back to location">
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
        <h1 id="confirm-title" className="where">
          Does this look like your land?
        </h1>
      </div>
      <p className="pin-coords">{formatCoord(pin)}</p>

      <div className="land-summary">
        <div className="summary-head">
          <h2>Location details</h2>
          {updated && !editing ? <span className="updated-badge">Updated</span> : null}
        </div>
        <div className="summary-swap">
          <div className={editing ? 'swap-pane' : 'swap-pane is-open'} inert={editing}>
            <div className="swap-inner">
              <dl className="land-read">
                <div>
                  <dt>Terrain & elevation</dt>
                  <dd>{view.terrain}</dd>
                </div>
                <div>
                  <dt>Land cover / soil appearance</dt>
                  <dd>{view.cover}</dd>
                </div>
                <div>
                  <dt>Typical weather pattern</dt>
                  <dd>{view.weather}</dd>
                </div>
              </dl>
            </div>
          </div>
          <div className={editing ? 'swap-pane is-open' : 'swap-pane'} inert={!editing}>
            <div className="swap-inner">
              <form className="land-edit" onSubmit={saveEdits}>
                <div className="field">
                  <label htmlFor={`${fieldId}-terrain`}>Terrain & elevation</label>
                  <textarea
                    ref={terrainRef}
                    id={`${fieldId}-terrain`}
                    className="control land-input"
                    name="terrain"
                    rows={2}
                    autoComplete="off"
                    enterKeyHint="next"
                    value={draft.terrain}
                    onChange={(event) => setDraft((current) => ({ ...current, terrain: event.target.value }))}
                  />
                </div>
                <div className="field">
                  <label htmlFor={`${fieldId}-cover`}>Land cover / soil appearance</label>
                  <textarea
                    id={`${fieldId}-cover`}
                    className="control land-input"
                    name="cover"
                    rows={2}
                    autoComplete="off"
                    enterKeyHint="next"
                    value={draft.cover}
                    onChange={(event) => setDraft((current) => ({ ...current, cover: event.target.value }))}
                  />
                </div>
                <div className="field">
                  <label htmlFor={`${fieldId}-weather`}>Typical weather pattern</label>
                  <textarea
                    id={`${fieldId}-weather`}
                    className="control land-input"
                    name="weather"
                    rows={2}
                    autoComplete="off"
                    enterKeyHint="done"
                    value={draft.weather}
                    onChange={(event) => setDraft((current) => ({ ...current, weather: event.target.value }))}
                  />
                </div>
                <button type="submit" className="continue done-edit" disabled={!draftReady}>
                  Done
                </button>
              </form>
            </div>
          </div>
        </div>
      </div>

      <div className="choices" role="radiogroup" aria-label="Does this look like your land?">
        {choices.map((choice) => (
          <button
            key={choice.id}
            type="button"
            className={answer === choice.id ? 'choice is-selected' : 'choice'}
            role="radio"
            aria-checked={answer === choice.id}
            onClick={() => choose(choice.id)}
          >
            {choice.label}
          </button>
        ))}
      </div>

      <div className="sat-block">
        <p className="sat-badge">NASA Satellite & Earth View</p>
        <div className="map-frame">
          <div ref={mapNode} className="locate-map" role="application" aria-label="Satellite view of your pin. Tap to move it." />
        </div>
      </div>

      <button ref={finishRef} type="button" className="continue" disabled={!canFinish} onClick={onFinish}>
        Finish Setup
      </button>
    </div>
  )
}

const QUESTION_PATHS: { id: QuestionPath; title: string; detail: string }[] = [
  { id: 'quick', title: 'Quick 5', detail: '5 fast questions to get started right away' },
  { id: 'detailed', title: 'Detailed', detail: 'In-depth setup for tailored planting & soil advice' },
  { id: 'explore', title: 'Just exploring', detail: 'Skip the questions for now and browse freely' },
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
    const missing = draft.crops.length === 0 || draft.crops.some((row) => !row.crop.trim() || !row.planting || !row.harvest)
    if (missing) errors.crops = 'Add a crop with both months, or mark that you are not farming this land yet.'
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

function formatCoord(pin: Pin) {
  const ns = pin.lat >= 0 ? 'N' : 'S'
  const ew = pin.lng >= 0 ? 'E' : 'W'
  return `${Math.abs(pin.lat).toFixed(2)}° ${ns}, ${Math.abs(pin.lng).toFixed(2)}° ${ew}`
}

function landPreview(lat: number, elevationM: number | null, units: UnitSystem) {
  const abs = Math.abs(lat)
  const high = elevationM !== null && elevationM >= 800
  const low = elevationM !== null && elevationM < 40
  const height = elevationM === null ? '' : elevationPhrase(elevationM, units)

  if (abs < 12) {
    return {
      terrain: `${high ? 'Highland tropical ground' : low ? 'Low, nearly flat tropical ground' : 'Slightly raised tropical ground'}${height}`,
      cover: high ? 'Thinner vegetation with more open soil' : 'Dense vegetation and cropland, with small patches of open soil',
      weather: 'Warm and humid through the year, with heavy rainfall',
    }
  }
  if (abs < 25) {
    return {
      terrain: `${high ? 'Highland tropical terrain' : low ? 'Lowland tropical terrain' : 'Slightly raised / rolling terrain'}${height}`,
      cover: 'Mixed vegetation with patches of open or bare soil',
      weather: 'Tropical seasonal climate, a wet season and a drier season',
    }
  }
  if (abs < 35) {
    return {
      terrain: `${high ? 'Highland, rolling terrain' : 'Gently rolling terrain'}${height}`,
      cover: 'Mixed cropland, grass, and patches of open soil',
      weather: 'Warm summers, mild winters, and moderate rainfall',
    }
  }
  if (abs < 55) {
    return {
      terrain: `${high ? 'Higher, rolling terrain' : 'Gently rolling terrain'}${height}`,
      cover: 'Mixed vegetation with seasonal bare soil',
      weather: 'Temperate seasonal climate, moderate rainfall, warm summers',
    }
  }
  if (abs < 66) {
    return {
      terrain: `${high ? 'Cool highland ground' : 'Cool, gently rolling ground'}${height}`,
      cover: 'Forest, grass, and open soil',
      weather: 'Short summers, cold winters, and moderate precipitation',
    }
  }
  return {
    terrain: `Open, cold ground${height}`,
    cover: 'Sparse vegetation and bare soil',
    weather: 'A cold climate with a short growing season',
  }
}

function elevationPhrase(meters: number, units: UnitSystem) {
  if (units === 'imperial') {
    const feet = Math.round(meters * 3.28084)
    return `, ~${feet.toLocaleString('en-US')} ft elevation`
  }
  return `, ~${Math.round(meters).toLocaleString('en-US')} m elevation`
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

function Eye() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <circle cx="12" cy="12" r="2.6" fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}

function EyeOff() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M4 5l16 14M9.5 9.7A3.2 3.2 0 0 0 12 15.2c.7 0 1.3-.2 1.8-.6M6.2 7.8C4.2 9.2 2.8 11 2 12c0 0 3.5 6 10 6 1.6 0 3-.3 4.3-.9M10.2 6.3A11 11 0 0 1 12 6c6.5 0 10 6 10 6a17 17 0 0 1-3.2 3.4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  )
}
