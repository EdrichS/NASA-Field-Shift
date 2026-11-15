import { useId, useState, type FormEvent } from 'react'
import './SignUp.css'

export type UnitSystem = 'imperial' | 'metric'

export type SignUpStepOne = {
  username: string
  password: string
  units: UnitSystem
}

type SignUpProps = {
  onBack: () => void
  onLogin: () => void
  onContinue: (values: SignUpStepOne) => void
}

type FieldErrors = {
  username?: string
  password?: string
  units?: string
}

const USERNAME_PATTERN = /^[A-Za-z0-9_]{3,24}$/

export default function SignUp({ onBack, onLogin, onContinue }: SignUpProps) {
  const formId = useId()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [units, setUnits] = useState<'' | UnitSystem>('')
  const [showPassword, setShowPassword] = useState(false)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [submitted, setSubmitted] = useState(false)

  function validate(next: { username: string; password: string; units: string }): FieldErrors {
    const nextErrors: FieldErrors = {}
    const name = next.username.trim()
    if (!name) nextErrors.username = 'Choose a username.'
    else if (!USERNAME_PATTERN.test(name)) {
      nextErrors.username = 'Use 3–24 letters, numbers, or underscores.'
    }
    if (!next.password) nextErrors.password = 'Enter a password.'
    else if (next.password.length < 8) nextErrors.password = 'Use at least 8 characters.'
    if (next.units !== 'imperial' && next.units !== 'metric') {
      nextErrors.units = 'Choose a measurement system.'
    }
    return nextErrors
  }

  function update(partial: { username?: string; password?: string; units?: '' | UnitSystem }) {
    const next = {
      username: partial.username ?? username,
      password: partial.password ?? password,
      units: partial.units ?? units,
    }
    if (partial.username !== undefined) setUsername(partial.username)
    if (partial.password !== undefined) setPassword(partial.password)
    if (partial.units !== undefined) setUnits(partial.units)
    if (submitted) setErrors(validate(next))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors = validate({ username, password, units })
    setSubmitted(true)
    setErrors(nextErrors)
    const firstInvalid = (['username', 'password', 'units'] as const).find((field) => nextErrors[field])
    if (firstInvalid) {
      document.getElementById(`${formId}-${firstInvalid}`)?.focus()
      return
    }
    onContinue({
      username: username.trim(),
      password,
      units: units as UnitSystem,
    })
  }

  const usernameErrorId = `${formId}-username-error`
  const passwordErrorId = `${formId}-password-error`
  const unitsErrorId = `${formId}-units-error`

  return (
    <main className="signup" data-testid="signup">
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

        <section className="signup-card" aria-labelledby={`${formId}-title`}>
          <p className="step">Step 1 of 2</p>
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
              Continue
            </button>
          </form>

          <p className="login-prompt">
            Already have an account?{' '}
            <button type="button" className="login-link" onClick={onLogin}>
              Log in
            </button>
          </p>
        </section>
      </div>
    </main>
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
