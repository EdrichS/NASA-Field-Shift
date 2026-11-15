import { useEffect, useId } from 'react'
import { LANGUAGES, translate, type LanguageCode } from './i18n'

type LanguageDisclaimerProps = {
  /** Report languages: the first is the main one; at most 2 (each is its own AI call). */
  languages: LanguageCode[]
  accepted: boolean
  onLanguages: (languages: LanguageCode[]) => void
  onAccepted: (accepted: boolean) => void
  onBack: () => void
  onContinue: () => void
}

export default function LanguageDisclaimer({
  languages,
  accepted,
  onLanguages,
  onAccepted,
  onBack,
  onContinue,
}: LanguageDisclaimerProps) {
  const fieldId = useId()
  const main = languages[0] ?? 'en'
  const second = languages[1] ?? ''
  const copy = (key: Parameters<typeof translate>[1]) => translate(main, key)
  const nonEnglish = languages.some((l) => l !== 'en')

  useEffect(() => {
    document.documentElement.lang = main
    return () => {
      document.documentElement.lang = 'en'
    }
  }, [main])

  return (
    <div className="step-panel lang-panel" data-testid="language-disclaimer">
      <div className="locate-head">
        <button type="button" className="card-back" onClick={onBack} aria-label={copy('back')}>
          <svg viewBox="0 0 16 16" aria-hidden="true">
            <path d="M10 3L5 8l5 5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
        <h1 id="lang-title">Report language</h1>
      </div>

      <label className="lang-label" htmlFor={`${fieldId}-main`}>
        Write my report in
      </label>
      <select
        id={`${fieldId}-main`}
        className="control unit-select"
        value={main}
        onChange={(event) => {
          const next = event.target.value as LanguageCode
          onLanguages(second && second !== next ? [next, second as LanguageCode] : [next])
        }}
      >
        {LANGUAGES.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>

      <label className="lang-label" htmlFor={`${fieldId}-second`}>
        Also in (optional, up to 2 languages)
      </label>
      <select
        id={`${fieldId}-second`}
        className={second ? 'control unit-select' : 'control unit-select is-placeholder'}
        value={second}
        onChange={(event) => {
          const next = event.target.value as LanguageCode | ''
          onLanguages(next ? [main, next] : [main])
        }}
      >
        <option value="">No second language</option>
        {LANGUAGES.filter((item) => item.value !== main).map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>

      <div className="lang-callout">
        <strong>{copy('noticeTitle')}</strong>
        {nonEnglish ? (
          <p>
            Reports are most reliable in English. In other languages the quality may be lower, and some words will stay
            in English when there's no common local word for them.
          </p>
        ) : null}
        {main !== 'en' ? <p>{copy('reportWarning')}</p> : null}
        <p>{copy('noticeBody')}</p>
        <p className="helper">The app's buttons and menus stay in English for now; your report uses the language(s) above.</p>
      </div>

      <label className="lang-ack">
        <input type="checkbox" checked={accepted} onChange={(event) => onAccepted(event.target.checked)} />
        <span>{copy('acknowledge')}</span>
      </label>

      <button type="button" className="continue" disabled={!accepted} onClick={onContinue}>
        Generate my report
      </button>
    </div>
  )
}
