// Signed-in home: saved fields and plans, alerts (bell + list + map + per-field toggles),
// account settings and "delete my data". Built on the teammate's Dashboard styles.
import { useCallback, useEffect, useState } from 'react'
import {
  ApiError,
  checkAlerts,
  deleteField,
  deleteMe,
  readAlert,
  renameField,
  setAlertPreferences,
  type Alert,
  type AlertType,
  type FieldSummary,
  type Me,
} from './api'
import AlertMap from './AlertMap'
import { formatArea } from './mapkit'
import { enablePush, pushStatus } from './push'
import './Dashboard.css'

export type Tab = 'home' | 'fields' | 'alerts' | 'account'

const TAB_LABELS: Record<Tab, string> = { home: 'Home', fields: 'Fields', alerts: 'Alerts', account: 'Account' }

export const ALERT_LABELS: Record<AlertType, string> = {
  natural_event: 'Storms, floods & other natural events (NASA EONET)',
  fire: 'Fires nearby (NASA FIRMS)',
  heavy_rain: 'Heavy rain (JAXA GSMaP)',
  drought: 'Dry soil (NASA SMAP)',
  pest_risk: 'Pest-risk weather',
  new_findings: 'New findings in my plan',
}

const STRATEGY_NAMES: Record<string, string> = {
  current: 'Keep the current rotation',
  fill_bare: 'Fill the bare gap',
  break_pest: 'Break the pest cycle',
  save_water: 'Save water',
}

type DashboardProps = {
  me: Me | null
  email?: string
  name: string
  onRefresh: () => void
  onOpenPlan: (analysisId: string) => void
  onNewAnalysis: () => void
  onLogout: () => void
  onError: (message: string) => void
  onNotice: (message: string) => void
  getToken: () => Promise<string | null>
  /** Dev preview only: sample alerts and the tab to open. */
  initialAlerts?: Alert[]
  initialTab?: Tab
}

export default function Dashboard(props: DashboardProps) {
  const { me, email, name, onRefresh, onOpenPlan, onNewAnalysis, onLogout, onError, onNotice, getToken } = props
  const [tab, setTab] = useState<Tab>(props.initialTab ?? 'home')
  const [alerts, setAlerts] = useState<Alert[]>(props.initialAlerts ?? [])
  const [checking, setChecking] = useState(false)
  const [lastCheck, setLastCheck] = useState<string | null>(null)
  const unread = alerts.filter((a) => !a.read_at).length
  const fields = me?.fields ?? []
  const units = me?.units === 'imperial' ? 'imperial' : 'metric'

  const fail = useCallback((e: unknown, fallback: string) => onError(e instanceof ApiError ? e.message : fallback), [onError])

  const runCheck = useCallback(
    async (force: boolean) => {
      const token = await getToken()
      if (!token) return
      setChecking(true)
      try {
        const result = await checkAlerts(token, force)
        setAlerts(result.alerts)
        setLastCheck(result.last_check)
        if (force) onNotice(result.new ? `${result.new} new alert(s).` : 'Checked: no new alerts for your fields.')
      } catch (e) {
        fail(e, 'Could not check alerts right now.')
      } finally {
        setChecking(false)
      }
    },
    [getToken, onNotice, fail],
  )

  // Opening the app runs the check (the server caches it for ~6 hours).
  useEffect(() => {
    if (fields.length) void runCheck(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fields.length])

  async function markRead(alert: Alert) {
    if (alert.read_at) return
    const token = await getToken()
    if (!token) return
    try {
      await readAlert(token, alert.id)
      setAlerts((list) => list.map((a) => (a.id === alert.id ? { ...a, read_at: new Date().toISOString() } : a)))
      onRefresh()
    } catch (e) {
      fail(e, 'Could not update the alert.')
    }
  }

  return (
    <main className="home" data-testid="dashboard">
      <div className="home-column">
        <header className="home-bar">
          <p className="wordmark">
            <Sprout />
            <span>Sow Smart</span>
          </p>
          <button type="button" className={unread ? 'bell has-unread' : 'bell'} onClick={() => setTab('alerts')} aria-label={`Alerts: ${unread} unread`}>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 3a6 6 0 0 0-6 6v3.6L4.5 16h15L18 12.6V9a6 6 0 0 0-6-6zm-2 15a2 2 0 0 0 4 0" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {unread ? <span className="bell-count">{unread}</span> : null}
          </button>
        </header>

        <p className="home-kicker">{email ? `Signed in as ${email}` : 'Signed in'}</p>
        <h1>Welcome{name ? `, ${name}` : ''}</h1>

        {tab === 'home' ? (
          <div className="home-stack">
            <article className="home-card">
              <h2>Your plans</h2>
              {fields.length === 0 ? <p>No saved fields yet. Analyze a field to get your first plan.</p> : null}
              <ul className="field-list">
                {fields.map((f) => (
                  <li key={f.id}>
                    <div>
                      <strong>{f.name}</strong>
                      <span>{f.top_strategy ? `Best match: ${STRATEGY_NAMES[f.top_strategy] ?? f.top_strategy}` : 'Not analyzed yet'}</span>
                    </div>
                    {f.analysis_id ? (
                      <button type="button" className="secondary" onClick={() => onOpenPlan(f.analysis_id!)}>
                        Open plan
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
              <div className="plan-buttons">
                <button type="button" className="secondary" onClick={onNewAnalysis}>
                  + Analyze a field
                </button>
              </div>
            </article>

            <article className="home-card">
              <h2>Alerts</h2>
              <p>
                {unread ? `${unread} unread alert(s).` : 'No unread alerts.'}{' '}
                {lastCheck ? `Last checked ${new Date(lastCheck).toLocaleString()}.` : ''}
              </p>
              <div className="plan-buttons">
                <button type="button" className="secondary" onClick={() => setTab('alerts')}>
                  See alerts
                </button>
                <button type="button" className="secondary" onClick={() => void runCheck(true)} disabled={checking || !fields.length}>
                  {checking ? 'Checking…' : 'Check now'}
                </button>
              </div>
            </article>

          </div>
        ) : null}

        {tab === 'fields' ? (
          <div className="home-stack">
            {fields.length === 0 ? (
              <article className="home-card">
                <p>No saved fields yet.</p>
              </article>
            ) : null}
            {fields.map((f) => (
              <FieldCard
                key={f.id}
                field={f}
                units={units}
                getToken={getToken}
                onChanged={onRefresh}
                onOpenPlan={onOpenPlan}
                onError={(e) => fail(e, 'Could not update the field.')}
              />
            ))}
            <button type="button" className="secondary" onClick={onNewAnalysis}>
              + Analyze another field
            </button>
          </div>
        ) : null}

        {tab === 'alerts' ? (
          <AlertsPanel
            alerts={alerts}
            fields={fields}
            checking={checking}
            lastCheck={lastCheck}
            onCheck={() => void runCheck(true)}
            onRead={(a) => void markRead(a)}
            getToken={getToken}
            onNotice={onNotice}
            onError={onError}
          />
        ) : null}

        {tab === 'account' ? (
          <AccountPanel me={me} email={email} getToken={getToken} onLogout={onLogout} onError={onError} />
        ) : null}

        <nav className="home-nav" aria-label="Sections">
          {(Object.keys(TAB_LABELS) as Tab[]).map((item) => (
            <button
              key={item}
              type="button"
              className={tab === item ? 'is-on' : undefined}
              aria-current={tab === item ? 'page' : undefined}
              onClick={() => setTab(item)}
            >
              {TAB_LABELS[item]}
              {item === 'alerts' && unread ? ` (${unread})` : ''}
            </button>
          ))}
        </nav>
      </div>
    </main>
  )
}

function FieldCard({
  field,
  units,
  getToken,
  onChanged,
  onOpenPlan,
  onError,
}: {
  field: FieldSummary
  units: 'metric' | 'imperial'
  getToken: () => Promise<string | null>
  onChanged: () => void
  onOpenPlan: (id: string) => void
  onError: (e: unknown) => void
}) {
  const [name, setName] = useState(field.name)
  const [types, setTypes] = useState<AlertType[]>(field.alert_types as AlertType[])
  const [email, setEmail] = useState(field.email)
  const [pushOn, setPushOn] = useState(field.push)

  async function save(next: { types?: AlertType[]; email?: boolean; push?: boolean }) {
    const token = await getToken()
    if (!token) return
    const t = next.types ?? types
    const e = next.email ?? email
    const p = next.push ?? pushOn
    setTypes(t)
    setEmail(e)
    setPushOn(p)
    try {
      await setAlertPreferences(token, field.id, t, e, p)
    } catch (err) {
      onError(err)
    }
  }

  async function rename() {
    const token = await getToken()
    if (!token || !name.trim() || name.trim() === field.name) return
    try {
      await renameField(token, field.id, name.trim())
      onChanged()
    } catch (err) {
      onError(err)
    }
  }

  async function remove() {
    if (!window.confirm(`Delete "${field.name}" and its saved plans and alerts? This cannot be undone.`)) return
    const token = await getToken()
    if (!token) return
    try {
      await deleteField(token, field.id)
      onChanged()
    } catch (err) {
      onError(err)
    }
  }

  return (
    <article className="home-card field-card">
      <label className="field-name">
        <span>Field name</span>
        <input className="control" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} onBlur={() => void rename()} />
      </label>
      <p className="pin-line">
        {field.area_ha ? `About ${formatArea(field.area_ha, units)}` : ''}
        {field.unread ? ` · ${field.unread} unread alert(s)` : ''}
      </p>
      <div className="plan-buttons">
        {field.analysis_id ? (
          <button type="button" className="secondary" onClick={() => onOpenPlan(field.analysis_id!)}>
            Open plan
          </button>
        ) : null}
      </div>
      <details className="alert-prefs">
        <summary>Alerts for this field</summary>
        {(Object.keys(ALERT_LABELS) as AlertType[]).map((t) => (
          <label key={t} className="toggle-row">
            <input
              type="checkbox"
              checked={types.includes(t)}
              onChange={(e) => void save({ types: e.target.checked ? [...types, t] : types.filter((x) => x !== t) })}
            />
            <span>{ALERT_LABELS[t]}</span>
          </label>
        ))}
        <p className="helper">Alerts always show in the app. Also send them by:</p>
        <label className="toggle-row">
          <input type="checkbox" checked={email} onChange={(e) => void save({ email: e.target.checked })} />
          <span>Email</span>
        </label>
        <label className="toggle-row">
          <input type="checkbox" checked={pushOn} onChange={(e) => void save({ push: e.target.checked })} />
          <span>Phone or browser notification</span>
        </label>
      </details>
      <button type="button" className="link-button danger" onClick={() => void remove()}>
        Delete this field
      </button>
    </article>
  )
}

function AlertsPanel({
  alerts,
  fields,
  checking,
  lastCheck,
  onCheck,
  onRead,
  getToken,
  onNotice,
  onError,
}: {
  alerts: Alert[]
  fields: FieldSummary[]
  checking: boolean
  lastCheck: string | null
  onCheck: () => void
  onRead: (a: Alert) => void
  getToken: () => Promise<string | null>
  onNotice: (m: string) => void
  onError: (m: string) => void
}) {
  const [selected, setSelected] = useState<string | null>(null)
  const [push, setPush] = useState<'unsupported' | 'denied' | 'on' | 'off'>('off')

  useEffect(() => {
    void pushStatus().then(setPush)
  }, [])

  async function turnOnPush() {
    const token = await getToken()
    if (!token) return
    try {
      const problem = await enablePush(token)
      if (problem) onError(problem)
      else {
        setPush('on')
        onNotice('Notifications are on for this device.')
      }
    } catch {
      onError('Could not turn on notifications on this device.')
    }
  }

  const focus = alerts.find((a) => a.id === selected) ?? alerts[0]

  return (
    <div className="home-stack">
      <article className="home-card">
        <div className="alerts-head">
          <h2>Alerts</h2>
          <button type="button" className="secondary" onClick={onCheck} disabled={checking || !fields.length}>
            {checking ? 'Checking…' : 'Check now'}
          </button>
        </div>
        <p className="helper">
          We check NASA EONET, NASA FIRMS, JAXA GSMaP, NASA SMAP and pest-risk weather for your saved fields when you open the app,
          when you tap Check now, and every 6 hours.{lastCheck ? ` Last check: ${new Date(lastCheck).toLocaleString()}.` : ''}
        </p>
        {push === 'off' ? (
          <button type="button" className="secondary" onClick={() => void turnOnPush()}>
            Get notifications on this device
          </button>
        ) : push === 'on' ? (
          <p className="helper">Notifications are on for this device.</p>
        ) : push === 'denied' ? (
          <p className="helper">Notifications are blocked in this browser's settings.</p>
        ) : (
          <p className="helper">This browser can't show notifications. On iPhone, add SowSmart to your Home Screen first.</p>
        )}
      </article>

      {focus ? <AlertMap alert={focus} /> : null}

      {alerts.length === 0 ? (
        <article className="home-card">
          <p>No alerts for your fields. That's good news.</p>
        </article>
      ) : null}
      <ul className="alert-list">
        {alerts.map((a) => (
          <li key={a.id} className={`alert-item sev-${a.severity}${a.read_at ? ' is-read' : ''}${focus?.id === a.id ? ' is-focus' : ''}`}>
            <button
              type="button"
              onClick={() => {
                setSelected(a.id)
                onRead(a)
              }}
            >
              <span className="alert-top">
                <strong>{ALERT_LABELS[a.type]?.split(' (')[0] ?? a.type}</strong>
                <span className={`sev sev-${a.severity}`}>{a.severity}</span>
              </span>
              <span className="alert-msg">{a.message}</span>
              <span className="alert-meta">
                {a.field_name} · {a.source} · {new Date(a.triggered_at).toLocaleString()}
                {a.read_at ? '' : ' · new'}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <p className="helper">Pest alerts mean the weather favors a pest or disease. Check your field: they are not confirmed outbreaks.</p>
    </div>
  )
}

function AccountPanel({
  me,
  email,
  getToken,
  onLogout,
  onError,
}: {
  me: Me | null
  email?: string
  getToken: () => Promise<string | null>
  onLogout: () => void
  onError: (m: string) => void
}) {
  async function deleteAll() {
    if (!window.confirm('Delete your SowSmart data: profile, fields, plans, reports and alerts? This cannot be undone.')) return
    const token = await getToken()
    if (!token) return
    try {
      await deleteMe(token)
      onLogout()
    } catch (e) {
      onError(e instanceof ApiError ? e.message : 'Could not delete your data.')
    }
  }
  return (
    <div className="home-stack">
      <article className="home-card">
        <h2>Account</h2>
        <p className="pin-line">
          <span>Email</span> {email ?? 'unknown'}
        </p>
        <p className="pin-line">
          <span>Units</span> {me?.units ?? 'metric'} · <span>Report language</span> {me?.language ?? 'en'}
        </p>
        <p className="helper">
          {me?.has_email ? 'Alert emails go to your verified email address.' : 'Verify your email with Auth0 to also get alerts by email.'}
        </p>
        <div className="plan-buttons">
          <button type="button" className="secondary" onClick={onLogout}>
            Log out
          </button>
        </div>
      </article>
      <article className="home-card">
        <h2>Privacy</h2>
        <p>Your field locations are private: only you can see them. Region-wide alerts are matched on our server.</p>
        <button type="button" className="link-button danger" onClick={() => void deleteAll()}>
          Delete my data
        </button>
      </article>
    </div>
  )
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
