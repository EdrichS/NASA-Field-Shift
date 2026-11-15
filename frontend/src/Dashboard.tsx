// Signed-in home: saved fields and plans, alerts (bell + list + map + per-field toggles),
// account settings and "delete my data". Design system v1: index cards, ruled rows, docked tab bar.
import { useCallback, useEffect, useRef, useState } from 'react'
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
import { LANGUAGES } from './i18n'
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
  add_income: 'Add a cash crop',
}

/** "Fires nearby (NASA FIRMS)" -> ["Fires nearby", "NASA FIRMS"], for a name line and a source line. */
function splitLabel(label: string): [string, string] {
  const match = /^(.*) \((.*)\)$/.exec(label)
  return match ? [match[1], match[2]] : [label, '']
}

function plural(count: number, word: string) {
  return `${count} ${word}${count === 1 ? '' : 's'}`
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
  const latestUnread = alerts.find((a) => !a.read_at)
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

  const checkLabel = checking ? 'Checking…' : 'Check now'

  return (
    <main className="home" data-testid="dashboard">
      <div className="home-column">
        {tab === 'home' ? (
          <div className="home-stack">
            <header className="home-bar">
              <p className="wordmark">SowSmart</p>
              <button type="button" className={unread ? 'bell has-unread' : 'bell'} onClick={() => setTab('alerts')} aria-label={`Alerts: ${unread} unread`}>
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 3a6 6 0 0 0-6 6v3.6L4.5 16h15L18 12.6V9a6 6 0 0 0-6-6zm-2 15a2 2 0 0 0 4 0" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                {unread ? <span className="bell-count">{unread}</span> : null}
              </button>
            </header>

            <div className="page-head is-welcome">
              <p className="cap">{email ? `Signed in as ${email}` : 'Signed in'}</p>
              <h1>Welcome{name ? `, ${name}` : ''}</h1>
            </div>

            <section className={unread ? 'index-card band-risk home-alerts' : 'index-card band-quiet home-alerts'} aria-labelledby="home-alerts-title">
              <h2 id="home-alerts-title" className="cap">
                {unread ? plural(unread, 'new alert') : 'Alerts'}
              </h2>
              <p className="home-alerts-msg">{latestUnread ? latestUnread.message : 'No unread alerts.'}</p>
              {lastCheck ? <p className="home-meta">Last checked {new Date(lastCheck).toLocaleString()}.</p> : null}
              <div className="home-actions">
                <button type="button" className="link-button" onClick={() => setTab('alerts')}>
                  See alerts <span aria-hidden="true">›</span>
                </button>
                <button type="button" className="secondary" onClick={() => void runCheck(true)} disabled={checking || !fields.length}>
                  {checkLabel}
                </button>
              </div>
            </section>

            <section className="home-section" aria-labelledby="home-plans-title">
              <h2 id="home-plans-title">Your plans</h2>
              {fields.length === 0 ? <p className="home-empty">No saved fields yet. Analyze a field to get your first plan.</p> : null}
              {fields.length ? (
                <ul className="plan-list">
                  {fields.map((f) => (
                    <li key={f.id} className="index-card plan-card">
                      <h3>{f.name}</h3>
                      <p className="home-meta">
                        {f.top_strategy
                          ? `${f.analyzed_at ? `Analyzed ${new Date(f.analyzed_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })} · ` : ''}Best match: ${STRATEGY_NAMES[f.top_strategy] ?? f.top_strategy}`
                          : 'Not analyzed yet'}
                      </p>
                      <div className="field-actions">
                        {f.analysis_id ? (
                          <button type="button" className="link-button" onClick={() => onOpenPlan(f.analysis_id!)}>
                            Open plan <span aria-hidden="true">›</span>
                          </button>
                        ) : null}
                        <button type="button" className="link-button is-quiet" onClick={() => setTab('fields')} aria-label={`Rename or delete ${f.name}`}>
                          Rename / delete
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>

            <button type="button" className="tag-btn is-block" onClick={onNewAnalysis}>
              Plan a new field
            </button>
          </div>
        ) : null}

        {tab === 'fields' ? (
          <div className="home-stack">
            <div className="page-head">
              <h1>Your fields</h1>
              <p className="cap">{fields.length} saved</p>
            </div>
            {fields.length === 0 ? (
              <section className="index-card band-quiet">
                <p className="home-empty">No saved fields yet.</p>
              </section>
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
            <button type="button" className="link-button home-add" onClick={onNewAnalysis}>
              + Analyze another field
            </button>
            <PushOptIn getToken={getToken} onNotice={onNotice} onError={onError} />
          </div>
        ) : null}

        {tab === 'alerts' ? (
          <AlertsPanel
            alerts={alerts}
            fields={fields}
            checkLabel={checkLabel}
            checking={checking}
            lastCheck={lastCheck}
            onCheck={() => void runCheck(true)}
            onRead={(a) => void markRead(a)}
          />
        ) : null}

        {tab === 'account' ? (
          <AccountPanel me={me} email={email} getToken={getToken} onLogout={onLogout} onError={onError} />
        ) : null}
      </div>

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
            {item === 'alerts' && unread ? (
              <>
                {` · ${unread}`}
                <span className="visually-hidden"> unread</span>
              </>
            ) : null}
          </button>
        ))}
      </nav>
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
  const [renaming, setRenaming] = useState(false)
  const [types, setTypes] = useState<AlertType[]>(field.alert_types as AlertType[])
  const [email, setEmail] = useState(field.email)
  const [pushOn, setPushOn] = useState(field.push)
  const nameInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (renaming) nameInput.current?.focus()
  }, [renaming])

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

  const meta = [field.area_ha ? `About ${formatArea(field.area_ha, units)}` : '', field.unread ? plural(field.unread, 'unread alert') : '']
    .filter(Boolean)
    .join(' · ')

  return (
    <article className="index-card field-card">
      <h2>{field.name}</h2>
      {meta ? <p className="home-meta">{meta}</p> : null}
      {renaming ? (
        <label className="field-name">
          <span>Field name</span>
          <input
            ref={nameInput}
            className="control"
            value={name}
            maxLength={60}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') e.currentTarget.blur()
            }}
            onBlur={() => {
              setRenaming(false)
              void rename()
            }}
          />
        </label>
      ) : null}
      <div className="field-actions">
        {field.analysis_id ? (
          <button type="button" className="link-button" onClick={() => onOpenPlan(field.analysis_id!)}>
            Open plan
          </button>
        ) : null}
        <button type="button" className="link-button" onClick={() => setRenaming(true)}>
          Rename
        </button>
        <button type="button" className="link-button danger" onClick={() => void remove()}>
          Delete this field
        </button>
      </div>
      <details className="alert-prefs">
        <summary>Alerts for this field</summary>
        {(Object.keys(ALERT_LABELS) as AlertType[]).map((t) => {
          const [title, source] = splitLabel(ALERT_LABELS[t])
          return (
            <label key={t} className="toggle-row">
              <input
                type="checkbox"
                checked={types.includes(t)}
                onChange={(e) => void save({ types: e.target.checked ? [...types, t] : types.filter((x) => x !== t) })}
              />
              <span className="toggle-text">
                <span>{title}</span>
                {source ? <span className="toggle-source">{source}</span> : null}
              </span>
            </label>
          )
        })}
        <p className="helper">Alerts always show in the app. Also send them by:</p>
        <label className="toggle-row">
          <input type="checkbox" checked={email} onChange={(e) => void save({ email: e.target.checked })} />
          <span className="toggle-text">Email</span>
        </label>
        <label className="toggle-row">
          <input type="checkbox" checked={pushOn} onChange={(e) => void save({ push: e.target.checked })} />
          <span className="toggle-text">Phone or browser notification</span>
        </label>
      </details>
    </article>
  )
}

/** Turns on notifications for this device (the per-field toggle decides which fields send them). */
function PushOptIn({
  getToken,
  onNotice,
  onError,
}: {
  getToken: () => Promise<string | null>
  onNotice: (m: string) => void
  onError: (m: string) => void
}) {
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

  if (push === 'off') {
    return (
      <button type="button" className="tag-btn is-quiet is-block" onClick={() => void turnOnPush()}>
        Get notifications on this device
      </button>
    )
  }
  return (
    <p className="home-meta">
      {push === 'on'
        ? 'Notifications are on for this device.'
        : push === 'denied'
          ? "Notifications are blocked in this browser's settings."
          : "This browser can't show notifications. On iPhone, add SowSmart to your Home Screen first."}
    </p>
  )
}

function AlertsPanel({
  alerts,
  fields,
  checkLabel,
  checking,
  lastCheck,
  onCheck,
  onRead,
}: {
  alerts: Alert[]
  fields: FieldSummary[]
  checkLabel: string
  checking: boolean
  lastCheck: string | null
  onCheck: () => void
  onRead: (a: Alert) => void
}) {
  const [selected, setSelected] = useState<string | null>(null)
  const focus = alerts.find((a) => a.id === selected) ?? alerts[0]

  return (
    <div className="home-stack">
      <div className="page-head has-action">
        <h1>Alerts</h1>
        <button type="button" className="secondary" onClick={onCheck} disabled={checking || !fields.length}>
          {checkLabel}
        </button>
      </div>
      <p className="home-meta">
        We check NASA EONET, NASA FIRMS, JAXA GSMaP, NASA SMAP and pest-risk weather for your saved fields when you open the app,
        when you tap Check now, and every 6 hours.{lastCheck ? ` Last check: ${new Date(lastCheck).toLocaleString()}.` : ''}
      </p>

      {focus ? <AlertMap alert={focus} /> : null}

      {alerts.length === 0 ? (
        <section className="index-card band-quiet">
          <p className="home-empty">No alerts for your fields. That's good news.</p>
        </section>
      ) : null}
      {alerts.length ? (
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
                  <span className="alert-kind">
                    {ALERT_LABELS[a.type] ? splitLabel(ALERT_LABELS[a.type])[0] : a.type} ·{' '}
                    <span className={`sev sev-${a.severity}`}>{a.severity}</span>
                  </span>
                  {a.read_at ? null : <span className="alert-new">New</span>}
                </span>
                <span className="alert-msg">{a.message}</span>
                <span className="alert-meta">
                  {a.field_name} · {a.source} · {new Date(a.triggered_at).toLocaleString()}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <p className="home-meta">Pest alerts mean the weather favors a pest or disease. Check your field: they are not confirmed outbreaks.</p>
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
  const unitsName = me?.units ?? 'metric'
  const languageCode = me?.language ?? 'en'
  const languageName = LANGUAGES.find((l) => l.value === languageCode)?.label ?? languageCode
  return (
    <div className="home-stack">
      <div className="page-head">
        <h1>Account</h1>
      </div>
      <dl className="settings-list">
        <div className="setting-row">
          <dt className="cap">Email</dt>
          <dd>{email ?? 'unknown'}</dd>
        </div>
        <div className="setting-row">
          <dt className="cap">Units</dt>
          <dd>{unitsName.charAt(0).toUpperCase() + unitsName.slice(1)}</dd>
        </div>
        <div className="setting-row">
          <dt className="cap">Report language</dt>
          <dd>{languageName}</dd>
        </div>
        <div className="setting-row">
          <dt className="cap">Alert emails</dt>
          <dd className="is-note">
            {me?.has_email ? 'Alert emails go to your verified email address.' : 'Verify your email with Auth0 to also get alerts by email.'}
          </dd>
        </div>
      </dl>
      <section className="index-card band-risk privacy-card" aria-labelledby="privacy-title">
        <h2 id="privacy-title">Privacy</h2>
        <p>Your field locations are private: only you can see them. Region-wide alerts are matched on our server.</p>
        <p>Deleting your data removes your profile, fields, plans, reports and alerts. It can't be undone.</p>
        <button type="button" className="tag-btn is-block is-danger" onClick={() => void deleteAll()}>
          Delete my data
        </button>
      </section>
      <button type="button" className="link-button sign-out" onClick={onLogout}>
        Log out
      </button>
    </div>
  )
}
