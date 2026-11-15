import { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  analyze,
  getMe,
  saveAnalysis,
  savedAnalysis,
  serverUp,
  showcaseAnalysis,
  showcaseList,
  updateMe,
  type Alert,
  type AnalyzeRequest,
  type AnalyzeResponse,
  type Me,
  type ShowcaseFarm,
} from './api'
import Analyzing from './Analyzing'
import Landing from './Landing'
import { useSession } from './session'
import type { SetupResult } from './SignUp'

// Map-heavy screens load on demand, so the landing page opens fast on a phone.
const SignUp = lazy(() => import('./SignUp'))
const Results = lazy(() => import('./Results'))
const Dashboard = lazy(() => import('./Dashboard'))

type Screen =
  | { name: 'landing' }
  | { name: 'setup'; guest: boolean }
  | { name: 'analyzing'; setup: SetupResult }
  | { name: 'results'; analysis: AnalyzeResponse; demo?: ShowcaseFarm; offline?: boolean; request?: AnalyzeRequest; fieldName?: string }
  | { name: 'dashboard' }

// A guest who taps Save goes to Auth0 and comes back; the results wait in this tab meanwhile.
const PENDING_SAVE = 'sowsmart.pendingSave'

type PendingSave = { request: AnalyzeRequest; analysis: AnalyzeResponse; fieldName: string }

function demoIdFromHash() {
  const match = window.location.hash.match(/^#\/demo\/([\w-]+)/)
  return match ? match[1] : null
}

function requestOf(setup: SetupResult): AnalyzeRequest {
  return { geometry: setup.geometry, mode: setup.mode, answers: setup.answers, report_languages: setup.reportLanguages }
}

function inputMode(request: AnalyzeRequest) {
  return request.geometry.type === 'Polygon' ? 'polygon' : 'point'
}

function readPending(): PendingSave | null {
  try {
    const raw = sessionStorage.getItem(PENDING_SAVE)
    return raw ? (JSON.parse(raw) as PendingSave) : null
  } catch {
    return null
  }
}

function Screens() {
  const session = useSession()
  const [screen, setScreen] = useState<Screen>({ name: 'landing' })
  const [farms, setFarms] = useState<ShowcaseFarm[]>([])
  const [offline, setOffline] = useState(false)
  const [error, setError] = useState<string>()
  const [notice, setNotice] = useState<string>()
  const [me, setMe] = useState<Me | null>(null)
  const [savedId, setSavedId] = useState<string | null>(null)
  const [live, setLive] = useState<boolean | null>(null)
  const started = useRef(false)

  useEffect(() => {
    void serverUp().then(setLive)
  }, [])

  useEffect(() => {
    showcaseList()
      .then(({ farms: list, offline: off }) => {
        setFarms(list.filter((f) => f.available))
        setOffline(off)
      })
      .catch(() => setFarms([]))
  }, [])

  const refreshMe = useCallback(async () => {
    const token = await session.token()
    if (!token) return null
    try {
      const profile = await getMe(token)
      setMe(profile)
      return profile
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not load your account.')
      return null
    }
  }, [session])

  // After signing in: finish a pending save, then go to the dashboard (or set up a first field).
  useEffect(() => {
    if (session.loading || !session.signedIn || started.current) return
    started.current = true
    void (async () => {
      const pending = readPending()
      if (pending) {
        sessionStorage.removeItem(PENDING_SAVE)
        const token = await session.token()
        if (token) {
          try {
            const saved = await saveAnalysis(token, pending.request, pending.analysis, pending.fieldName, inputMode(pending.request))
            setNotice(`Saved "${pending.fieldName}" to your account.`)
            setSavedId(saved.analysis_id)
          } catch (e) {
            setError(e instanceof ApiError ? e.message : 'Saving failed. Please try again.')
          }
        }
      }
      const profile = await refreshMe()
      if (demoIdFromHash()) return
      if (profile && profile.fields.length === 0 && !pending) setScreen({ name: 'setup', guest: false })
      else setScreen({ name: 'dashboard' })
    })()
  }, [session, refreshMe])

  const openDemo = useCallback(async (id: string) => {
    setError(undefined)
    try {
      const analysis = await showcaseAnalysis(id)
      const list = farms.length ? farms : (await showcaseList()).farms
      const farm = list.find((f) => f.id === id)
      if (window.location.hash !== `#/demo/${id}`) window.history.pushState(null, '', `#/demo/${id}`)
      setScreen({ name: 'results', analysis, demo: farm, offline })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'This demo farm could not be opened.')
      setScreen({ name: 'landing' })
    }
  }, [farms, offline])

  // Deep links: #/demo/<farm-id> opens a showcase farm directly (handy for judges).
  useEffect(() => {
    const sync = () => {
      const id = demoIdFromHash()
      if (id) void openDemo(id)
      else setScreen((s) => (s.name === 'results' && s.demo ? { name: session.signedIn ? 'dashboard' : 'landing' } : s))
    }
    sync()
    window.addEventListener('popstate', sync)
    return () => window.removeEventListener('popstate', sync)
    // Only on first load and back/forward.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function goHome() {
    if (window.location.hash) window.history.pushState(null, '', window.location.pathname)
    setSavedId(null)
    setScreen(session.signedIn ? { name: 'dashboard' } : { name: 'landing' })
    if (session.signedIn) void refreshMe()
  }

  async function runAnalysis(setup: SetupResult) {
    setScreen({ name: 'analyzing', setup })
    setError(undefined)
    setSavedId(null)
    const request = requestOf(setup)
    const fieldName = setup.detailed?.fields[0]?.name?.trim() || `Field ${(me?.fields.length ?? 0) + 1}`
    try {
      const analysis = await analyze(request)
      setScreen({ name: 'results', analysis, request, fieldName })
      const token = await session.token()
      if (token) {
        // Signed in: results are kept automatically (CLAUDE.md section 5).
        try {
          await updateMe(token, { display_name: setup.displayName || me?.display_name || null, language: setup.reportLanguages[0], units: setup.units })
          const saved = await saveAnalysis(token, request, analysis, fieldName, inputMode(request))
          setSavedId(saved.analysis_id)
          setScreen({ name: 'results', analysis: { ...analysis, analysis_id: saved.analysis_id }, request, fieldName })
          void refreshMe()
        } catch (e) {
          setError(e instanceof ApiError ? `Your results are here, but saving failed: ${e.message}` : 'Saving failed.')
        }
      }
    } catch (e) {
      setError(`${e instanceof ApiError ? e.message : 'The analysis could not finish.'} Your answers are kept: tap "Generate my report" to try again.`)
      setScreen({ name: 'setup', guest: !session.signedIn })
    }
  }

  async function save(analysis: AnalyzeResponse, request: AnalyzeRequest, fieldName: string) {
    const token = await session.token()
    if (!token) {
      try {
        sessionStorage.setItem(PENDING_SAVE, JSON.stringify({ request, analysis, fieldName } satisfies PendingSave))
      } catch {
        setError('Your browser blocked saving for later. Sign up first, then run the analysis again.')
        return
      }
      session.login({ signup: true, returnTo: 'save' })
      return
    }
    try {
      const saved = await saveAnalysis(token, request, analysis, fieldName, inputMode(request))
      setSavedId(saved.analysis_id)
      setNotice(`Saved "${fieldName}" to your account.`)
      void refreshMe()
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Saving failed. Please try again.')
    }
  }

  async function openSaved(id: string) {
    const token = await session.token()
    if (!token) return
    try {
      const analysis = await savedAnalysis(token, id)
      setSavedId(id)
      setScreen({ name: 'results', analysis })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not open this plan.')
    }
  }

  const banners = (
    <>
      {error ? <Banner kind="error" message={error} onClose={() => setError(undefined)} /> : null}
      {notice ? <Banner kind="ok" message={notice} onClose={() => setNotice(undefined)} /> : null}
    </>
  )

  if (import.meta.env.DEV && window.location.hash.startsWith('#/dev/dashboard')) {
    // Dev-only layout preview with sample data (no sign-in, nothing is called).
    const sample: Me = {
      display_name: 'Ana', language: 'tl', units: 'metric', has_email: true,
      fields: [{ id: 'f1', name: 'Buclad paddy', area_ha: 19.63, input_mode: 'point', lat: 7.4945, lon: 125.7513,
        analysis_id: 'a1', top_strategy: 'break_pest', analyzed_at: null, created_at: null,
        alert_types: ['natural_event', 'fire', 'heavy_rain', 'drought', 'pest_risk', 'new_findings'], email: true, push: true, unread: 2 }],
    }
    return (
      <Dashboard me={sample} email="ana@example.org" name="Ana" onRefresh={() => undefined}
        onOpenPlan={() => undefined} onNewAnalysis={() => undefined}
        onLogout={() => undefined} onError={setError} onNotice={setNotice} getToken={async () => null}
        initialTab={window.location.hash.endsWith('/alerts') ? 'alerts' : 'home'} initialAlerts={SAMPLE_ALERTS} />
    )
  }

  if (session.loading && !demoIdFromHash()) {
    return (
      <main className="analyzing" aria-busy="true">
        <span className="spinner big" aria-hidden="true" />
      </main>
    )
  }

  if (screen.name === 'setup' || screen.name === 'analyzing') {
    // The wizard stays mounted while the analysis runs, so a failure returns the farmer to their
    // filled-in answers instead of an empty form.
    const analyzing = screen.name === 'analyzing'
    const guest = screen.name === 'setup' ? screen.guest : !session.signedIn
    return (
      <>
        {banners}
        <div style={{ display: analyzing ? 'none' : 'contents' }}>
          <SignUp
            guest={guest}
            email={session.email}
            initialName={me?.display_name ?? session.name ?? ''}
            initialUnits={me?.units === 'imperial' ? 'imperial' : me?.units === 'metric' ? 'metric' : undefined}
            onBack={goHome}
            onFinish={(setup) => void runAnalysis(setup)}
          />
        </div>
        {screen.name === 'analyzing' ? <Analyzing languages={screen.setup.reportLanguages} /> : null}
      </>
    )
  }

  if (screen.name === 'results') {
    const farm = screen.demo
    const { request, fieldName } = screen
    return (
      <>
        {banners}
        <Results
          analysis={screen.analysis}
          demo={!!farm}
          offline={screen.offline}
          title={farm?.name}
          subtitle={farm ? `${farm.place}, ${farm.country}` : undefined}
          canSave={!farm && !!request}
          saved={!!savedId || !!screen.analysis.analysis_id}
          saveLabel={session.signedIn ? 'Save' : 'Sign up to save'}
          onSave={request ? () => void save(screen.analysis, request, fieldName ?? 'My field') : undefined}
          onBack={goHome}
          getToken={session.token}
        />
      </>
    )
  }

  if (screen.name === 'dashboard' && session.signedIn) {
    return (
      <>
        {banners}
        <Dashboard
          me={me}
          email={session.email}
          name={me?.display_name || session.name || ''}
          onRefresh={() => void refreshMe()}
          onOpenPlan={(id) => void openSaved(id)}
          onNewAnalysis={() => setScreen({ name: 'setup', guest: false })}
          onLogout={session.logout}
          onError={setError}
          onNotice={setNotice}
          getToken={session.token}
        />
      </>
    )
  }

  return (
    <>
      {banners}
      <Landing
        farms={farms}
        live={live !== false}
        onDemo={(id) => void openDemo(id)}
        onLogin={() => session.login()}
        onSignUp={() => session.login({ signup: true })}
        onGuest={() => setScreen({ name: 'setup', guest: true })}
      />
    </>
  )
}

function Banner({ kind, message, onClose }: { kind: 'error' | 'ok'; message: string; onClose: () => void }) {
  return (
    <div className={kind === 'error' ? 'error-banner' : 'error-banner ok-banner'} role={kind === 'error' ? 'alert' : 'status'}>
      <span>{message}</span>
      <button type="button" onClick={onClose} aria-label="Dismiss">
        ×
      </button>
    </div>
  )
}

function Loading() {
  return (
    <main className="analyzing" aria-busy="true">
      <span className="spinner big" aria-hidden="true" />
    </main>
  )
}

export default function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Screens />
    </Suspense>
  )
}

// Dev preview only: the shape of two alerts the live check produced on Nov 15 (simulated storm,
// pest-risk weather), so the alerts screen can be reviewed without signing in.
const SAMPLE_ALERTS: Alert[] = [
  {
    id: 's1', field_id: 'f1', field_name: 'Buclad paddy', type: 'natural_event', severity: 'warning',
    message: '(Simulation for the demo) Simulated Typhoon Amihan is 75 km from Buclad paddy and moving closer. Follow local warnings and get ready.',
    source: 'NASA EONET (simulated)', triggered_at: '2026-11-15T06:15:00Z', read_at: null, lat: 7.4945, lon: 125.7513,
    data: { event_geometry: { type: 'MultiPoint', coordinates: [[129.84, 7.4945], [128.477, 7.6945], [127.205, 7.8945], [126.296, 8.0945]] } },
  },
  {
    id: 's2', field_id: 'f1', field_name: 'Buclad paddy', type: 'pest_risk', severity: 'watch',
    message: 'Weather at Buclad paddy favors bacterial leaf blight on rice: 25-34 °C and humidity above 70% for 2+ days in a row. Conditions favor it; check your field. This is not a confirmed outbreak.',
    source: 'NASA POWER daily weather + team pest rules', triggered_at: '2026-11-15T06:15:00Z', read_at: null, lat: 7.4945, lon: 125.7513,
    data: {},
  },
]
