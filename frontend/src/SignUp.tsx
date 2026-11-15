import { useEffect, useId, useRef, useState, type FormEvent, type RefObject } from 'react'
import './SignUp.css'

export type UnitSystem = 'imperial' | 'metric'

export type LandAnswer = 'yes' | 'no' | 'unsure'

export type SignUpAccount = {
  username: string
  email: string
  password: string
  units: UnitSystem
  latitude: number
  longitude: number
  confirmation: LandAnswer
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

export default function SignUp({ onBack, onLogin, onCreate }: SignUpProps) {
  const formId = useId()
  const mapNode = useRef<HTMLDivElement>(null)
  const mapRef = useRef<LeafletMap | null>(null)
  const markerRef = useRef<LeafletMarker | null>(null)
  const pinRef = useRef<Pin | null>(null)
  const [step, setStep] = useState<1 | 2 | 3>(1)
  const [answer, setAnswer] = useState<LandAnswer | null>(null)
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

  useEffect(() => {
    if (step !== 3 || !pin) return
    const controller = new AbortController()
    const { lat, lng } = pin
    fetch(`https://api.open-meteo.com/v1/elevation?latitude=${lat}&longitude=${lng}`, {
      signal: controller.signal,
    })
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error('elevation'))))
      .then((data: { elevation?: number[] }) => {
        const value = data.elevation?.[0]
        if (typeof value === 'number') setElevation({ lat, lng, meters: value })
      })
      .catch(() => undefined)
    return () => controller.abort()
  }, [step, pin])

  const elevationM =
    pin && elevation && elevation.lat === pin.lat && elevation.lng === pin.lng ? elevation.meters : null

  function createAccount() {
    if (!pin) {
      setPinError('Drop a pin on the map, or use your location.')
      return
    }
    setStep(3)
  }

  function finishSetup() {
    if (!pin || !answer) return
    onCreate({
      username: username.trim(),
      email: email.trim(),
      password,
      units: units as UnitSystem,
      latitude: pin.lat,
      longitude: pin.lng,
      confirmation: answer,
    })
  }

  const usernameErrorId = `${formId}-username-error`
  const emailErrorId = `${formId}-email-error`
  const passwordErrorId = `${formId}-password-error`
  const unitsErrorId = `${formId}-units-error`

  return (
    <main className={step === 1 ? 'signup' : 'signup is-locate'} data-testid="signup">
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
            Back
          </button>
          <p className="wordmark">
            <Sprout />
            <span>Sow Smart</span>
          </p>
        </header>

        <section
          className={step === 1 ? 'signup-card' : 'signup-card is-locate'}
          aria-labelledby={step === 3 ? 'confirm-title' : `${formId}-title`}
        >
          {step === 1 ? (
            <div className="step-panel" key="account">
              <p className="step">Step 1 of 3</p>
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
          ) : pin ? (
            <ConfirmLand
              pin={pin}
              units={units === 'imperial' ? 'imperial' : 'metric'}
              elevationM={elevationM}
              answer={answer}
              onAnswer={setAnswer}
              onBack={() => setStep(2)}
              onFinish={finishSetup}
              mapNode={mapNode}
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
  onAnswer,
  onBack,
  onFinish,
  mapNode,
}: {
  pin: Pin
  units: UnitSystem
  elevationM: number | null
  answer: LandAnswer | null
  onAnswer: (answer: LandAnswer) => void
  onBack: () => void
  onFinish: () => void
  mapNode: RefObject<HTMLDivElement | null>
}) {
  const preview = landPreview(pin.lat, elevationM, units)
  const choices: { id: LandAnswer; label: string }[] = [
    { id: 'yes', label: 'Yes' },
    { id: 'no', label: 'No' },
    { id: 'unsure', label: "I don't know" },
  ]

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

      <dl className="land-summary">
        <div>
          <dt>Terrain & elevation</dt>
          <dd>{preview.terrain}</dd>
        </div>
        <div>
          <dt>Land cover / soil appearance</dt>
          <dd>{preview.cover}</dd>
        </div>
        <div>
          <dt>Typical weather pattern</dt>
          <dd>{preview.weather}</dd>
        </div>
      </dl>

      <div className="choices" role="radiogroup" aria-label="Does this look like your land?">
        {choices.map((choice) => (
          <button
            key={choice.id}
            type="button"
            className={answer === choice.id ? 'choice is-selected' : 'choice'}
            role="radio"
            aria-checked={answer === choice.id}
            onClick={() => onAnswer(choice.id)}
          >
            {choice.label}
          </button>
        ))}
      </div>

      {answer === 'no' ? (
        <p className="adjust-pin">Tap the satellite view below to move your pin, or use the arrow to choose again.</p>
      ) : null}

      <div className="sat-block">
        <p className="sat-badge">NASA Satellite & Earth View</p>
        <div className="map-frame">
          <div ref={mapNode} className="locate-map" role="application" aria-label="Satellite view of your pin. Tap to move it." />
        </div>
      </div>

      <button type="button" className="continue" disabled={!answer} onClick={onFinish}>
        Finish Setup
      </button>
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
