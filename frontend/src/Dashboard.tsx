import { useEffect, useState } from 'react'
import { LANGUAGES, languageLabel, translate, type LanguageCode } from './i18n'
import type { QuestionPath } from './SignUp'
import './Dashboard.css'

type DashboardProps = {
  language: LanguageCode
  username: string
  latitude: number
  longitude: number
  path: QuestionPath
  onLanguage: (language: LanguageCode) => void
}

type Tab = 'home' | 'fields' | 'plan' | 'alerts'

const TABS: Tab[] = ['home', 'fields', 'plan', 'alerts']

export default function Dashboard({ language, username, latitude, longitude, path, onLanguage }: DashboardProps) {
  const [tab, setTab] = useState<Tab>('home')
  const copy = (key: Parameters<typeof translate>[1], vars?: Record<string, string>) =>
    translate(language, key, vars)

  useEffect(() => {
    document.documentElement.lang = language
  }, [language])

  const pathLabel =
    path === 'quick' ? copy('pathQuick') : path === 'detailed' ? copy('pathDetailed') : copy('pathExplore')

  return (
    <main className="home" data-testid="dashboard">
      <div className="home-column">
        <header className="home-bar">
          <p className="wordmark">
            <Sprout />
            <span>Sow Smart</span>
          </p>
          <label className="home-lang">
            <span>{copy('languageLabel')}</span>
            <select
              value={language}
              aria-label={copy('languageLabel')}
              onChange={(event) => onLanguage(event.target.value as LanguageCode)}
            >
              {LANGUAGES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        </header>

        <p className="home-kicker">{copy('showing', { language: languageLabel(language) })}</p>
        <h1>{copy('welcome', { name: username })}</h1>
        <p className="home-farm">{copy('yourFarm')}</p>

        {tab === 'home' ? (
          <div className="home-stack" key="home">
            <article className="home-card">
              <h2>{copy('planTitle')}</h2>
              <p>{copy('planBody')}</p>
            </article>
            <article className="home-card">
              <h2>{copy('fieldTitle')}</h2>
              <p className="pin-line">
                <span>{copy('coordinates')}</span>
                {formatPin(latitude, longitude)}
              </p>
            </article>
            <article className="home-card">
              <h2>{copy('setupTitle')}</h2>
              <p>{pathLabel}</p>
            </article>
            <article className="home-card">
              <h2>{copy('nextTitle')}</h2>
              <ul>
                <li>{copy('nextCompare')}</li>
                <li>{copy('nextWater')}</li>
                <li>{copy('nextExpert')}</li>
              </ul>
            </article>
          </div>
        ) : null}

        {tab === 'fields' ? (
          <article className="home-card home-panel" key="fields">
            <h2>{copy('fieldTitle')}</h2>
            <p className="pin-line">
              <span>{copy('coordinates')}</span>
              {formatPin(latitude, longitude)}
            </p>
            <p>{copy('fieldsHint')}</p>
          </article>
        ) : null}

        {tab === 'plan' ? (
          <article className="home-card home-panel" key="plan">
            <h2>{copy('planTitle')}</h2>
            <p>{copy('planHint')}</p>
          </article>
        ) : null}

        {tab === 'alerts' ? (
          <article className="home-card home-panel" key="alerts">
            <h2>{copy('alerts')}</h2>
            <p>{copy('alertsEmpty')}</p>
          </article>
        ) : null}

        <nav className="home-nav" aria-label={copy('home')}>
          {TABS.map((item) => (
            <button
              key={item}
              type="button"
              className={tab === item ? 'is-on' : undefined}
              aria-current={tab === item ? 'page' : undefined}
              onClick={() => setTab(item)}
            >
              {copy(item)}
            </button>
          ))}
        </nav>
      </div>
    </main>
  )
}

function formatPin(latitude: number, longitude: number) {
  const ns = latitude >= 0 ? 'N' : 'S'
  const ew = longitude >= 0 ? 'E' : 'W'
  return `${Math.abs(latitude).toFixed(2)}°${ns}, ${Math.abs(longitude).toFixed(2)}°${ew}`
}

function Sprout() {
  return (
    <svg className="wordmark-sprout" viewBox="0 0 36 36" aria-hidden="true">
      <path d="M18 33.5V18.2" fill="none" stroke="#1c3d32" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M17.6 22.8c-1.4-4.2-5.2-7.3-10.4-8.2 2.2 4.6 6 7.4 10.4 8.2z" fill="#4d7a5e" />
      <path d="M18.3 16.6c2.2-5.6 7.4-9.4 13.2-9.8-2.4 5.6-7.6 9.4-13.2 9.8z" fill="#1c3d32" />
    </svg>
  )
}
