import { useEffect, useId } from 'react'
import { LANGUAGES, translate, type LanguageCode } from './i18n'

type LanguageDisclaimerProps = {
  language: LanguageCode
  accepted: boolean
  onLanguage: (language: LanguageCode) => void
  onAccepted: (accepted: boolean) => void
  onBack: () => void
  onContinue: () => void
}

export default function LanguageDisclaimer({
  language,
  accepted,
  onLanguage,
  onAccepted,
  onBack,
  onContinue,
}: LanguageDisclaimerProps) {
  const fieldId = useId()
  const copy = (key: Parameters<typeof translate>[1]) => translate(language, key)

  useEffect(() => {
    document.documentElement.lang = language
    return () => {
      document.documentElement.lang = 'en'
    }
  }, [language])

  return (
    <div className="step-panel lang-panel" data-testid="language-disclaimer">
      <div className="locate-head">
        <button type="button" className="card-back" onClick={onBack} aria-label={copy('back')}>
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
        <h1 id="lang-title">{copy('disclaimerTitle')}</h1>
      </div>

      <label className="lang-label" htmlFor={fieldId}>
        {copy('languageLabel')}
      </label>
      <select
        id={fieldId}
        className="control unit-select"
        value={language}
        onChange={(event) => onLanguage(event.target.value as LanguageCode)}
      >
        {LANGUAGES.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>

      <div className="lang-callout">
        <strong>{copy('noticeTitle')}</strong>
        <p>{copy('noticeBody')}</p>
        {language !== 'en' ? <p>{copy('reportWarning')}</p> : null}
      </div>

      <label className="lang-ack">
        <input
          type="checkbox"
          checked={accepted}
          onChange={(event) => onAccepted(event.target.checked)}
        />
        <span>{copy('acknowledge')}</span>
      </label>

      <button type="button" className="continue" disabled={!accepted} onClick={onContinue}>
        {copy('continue')}
      </button>
    </div>
  )
}
