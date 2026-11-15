import { useEffect, useId } from 'react'
import { LANGUAGES, translate, type LanguageCode } from './i18n'

type LanguageDisclaimerProps = {
  /** Report languages: the first is the main one; at most 2 (each is its own AI call). */
  languages: LanguageCode[]
  accepted: boolean
  onLanguages: (languages: LanguageCode[]) => void
  onAccepted: (accepted: boolean) => void
  onContinue: () => void
}

/** Tap a language to add it (a third replaces the second); tap a chosen one to remove it.
 *  There is always at least one, and the first chosen is the main one. */
function toggle(languages: LanguageCode[], code: LanguageCode): LanguageCode[] {
  if (languages.includes(code)) {
    const rest = languages.filter((l) => l !== code)
    return rest.length ? rest : languages
  }
  if (languages.length === 0) return [code]
  return [languages[0], code]
}

export default function LanguageDisclaimer({
  languages,
  accepted,
  onLanguages,
  onAccepted,
  onContinue,
}: LanguageDisclaimerProps) {
  const fieldId = useId()
  const main = languages[0] ?? 'en'
  const copy = (key: Parameters<typeof translate>[1]) => translate(main, key)
  const others = languages.filter((l) => l !== 'en')
  const nonEnglish = others.length > 0
  const label = (code: LanguageCode) => LANGUAGES.find((item) => item.value === code)?.label ?? code

  useEffect(() => {
    document.documentElement.lang = main
    return () => {
      document.documentElement.lang = 'en'
    }
  }, [main])

  return (
    <div className="step-panel lang-panel" data-testid="language-disclaimer">
      <div className="step-title is-ruled">
        <h1 id="lang-title">Which languages should your report use?</h1>
        <p className="step-sub">
          Pick up to two. The first is the main one. The app's buttons and menus stay in English; your report uses the
          languages you pick.
        </p>
      </div>

      <div className="lang-grid" role="group" aria-labelledby="lang-title" aria-describedby={`${fieldId}-count`}>
        {LANGUAGES.map((item) => {
          const at = languages.indexOf(item.value)
          return (
            <button
              key={item.value}
              type="button"
              className={at >= 0 ? 'pick lang-pick is-on' : 'pick lang-pick'}
              aria-pressed={at >= 0}
              onClick={() => onLanguages(toggle(languages, item.value))}
            >
              <span lang={item.value}>{item.label}</span>
              {at >= 0 ? <span className="lang-order">{at === 0 ? '1st' : '2nd'}</span> : null}
            </button>
          )
        })}
      </div>
      <p id={`${fieldId}-count`} className="cap lang-count" aria-live="polite">
        {languages.length} of 2 chosen
      </p>

      {nonEnglish ? (
        <div className="index-card band-risk lang-risk">
          <p className="cap">About {others.map(label).join(' and ')}</p>
          <p>
            Reports are most reliable in English. In other languages the quality may be lower, and some words will stay in
            English when there's no common local word for them.
          </p>
          {main !== 'en' ? <p lang={main}>{copy('reportWarning')}</p> : null}
        </div>
      ) : null}

      <div className="index-card band-quiet lang-notice">
        <p className="cap" lang={main}>
          {copy('noticeTitle')}
        </p>
        <p lang={main}>{copy('noticeBody')}</p>
        <label className="lang-ack">
          <input type="checkbox" checked={accepted} onChange={(event) => onAccepted(event.target.checked)} />
          <span lang={main}>{copy('acknowledge')}</span>
        </label>
      </div>

      <button type="button" className="tag-btn is-block step-cta" disabled={!accepted} onClick={onContinue}>
        Generate my report
      </button>
    </div>
  )
}
