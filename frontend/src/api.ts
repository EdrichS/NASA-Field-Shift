// The backend API (v1). Types are written by hand from shared/contracts/openapi.json and the
// sample responses next to it; only the fields the app reads are typed strictly.

import type { Geometry } from 'geojson'

export type Evidence = {
  claim: string
  value: unknown
  unit: string
  dataset: string
  native_resolution: string
  period: string
  confidence: string
}

export type CardEdit =
  | { type: 'choice'; options: string[] }
  | { type: 'months' }
  | { type: 'number'; unit?: string }
  | { type: string; options?: string[] }

export type Card = {
  id: string
  title: string
  statement: string
  value: unknown
  confidence: 'high' | 'medium' | 'low' | string
  evidence: Evidence[]
  edit: CardEdit | null
}

export type FieldInfo = { geom_hash: string; lat: number; lon: number; end_month: string }

export type PrefillResponse = {
  field: FieldInfo
  warning: string | null
  cards: Card[]
  gaps: string[]
}

export type Goal = 'save_water' | 'build_soil' | 'earn_more' | 'feed_household' | 'survive_bad_years'

export type Answers = {
  current_crops: { crop: string; plant_month: number; harvest_month: number }[]
  not_farming: boolean
  water: 'irrigated' | 'rainfed' | 'mixed' | 'unknown' | null
  equipment: 'hand_tools' | 'animal' | 'small_tractor' | 'full_machinery' | 'unknown' | null
  top_goal: Goal | null
  ranked_goals: Goal[]
  wont_grow: string[]
  sellable_crops: string[]
  // Detailed mode and card corrections travel as extra keys (the backend keeps them).
  [extra: string]: unknown
}

export type Mode = 'quick' | 'detailed' | 'exploring'

export type AnalyzeRequest = {
  geometry: Geometry
  mode: Mode
  answers: Answers
  report_languages: string[]
}

export type CalendarMonth = {
  month: number
  name: string
  crops: { crop: string; share: number; year: number; new: boolean }[]
  bare: number
  stress: string[]
}

export type Component = { score: number; summary: string; evidence: Evidence[] }

export type Strategy = {
  key: 'current' | 'fill_bare' | 'break_pest' | 'save_water' | string
  name: string
  title: string
  rotation: { crop: string; plant_month: number; harvest_month: number; new: boolean }[][]
  calendar: CalendarMonth[]
  components: Record<string, Component>
  total: number
  rank: number
  confidence: string
  why: string
  changes: string[]
  benefits: string[]
  risks: string[]
  gaps: string[]
  expert_questions: string[]
}

export type StressMonth = { month: number; name: string; flags: string[]; evidence: Evidence[] }

export type StrategyText = {
  key: string
  name: string
  headline: string
  why: string
  benefits: string[]
  risks: string[]
  information_gaps: string[]
  expert_questions: string[]
  rank: number
  engine_name: string
  fallback?: boolean
}

export type Tier1Content = {
  title: string
  summary: string
  what_satellites_see: string
  bare_and_risky_seasons: string
  strategies: StrategyText[]
  idea_to_discuss: string
  idea_label: string
  glossary: { term: string; meaning: string }[]
  datasets_line: string
  disclaimer: string
}

export type Tier2Content = {
  answer: string
  sources: { claim: string; dataset: string; why_it_supports: string }[]
  caveats: string[]
  expert_questions: string[]
}

export type AIReport<C = Tier1Content> = {
  tier: number
  language: string
  language_level: 'farmer' | 'advanced'
  question: string
  ai_generated: boolean
  content: C
  checks: { numbers_ok?: boolean; [k: string]: unknown }
  meta: { model?: string; [k: string]: unknown }
  cached: boolean
}

export type ReportStatus = {
  status: 'ok' | 'cached' | 'skipped' | 'unavailable' | 'limit' | 'failed'
  message: string
}

export type AnalyzeResponse = {
  analysis_id: string | null
  field: FieldInfo
  warning: string | null
  prefill: Card[]
  features: unknown
  static: Record<string, unknown>
  profile: { mode: string; water: string; equipment: string; goals: string[]; wont_grow: string[]; rotation_source: string }
  weights: Record<string, number>
  bare_months: { satellite: number[]; current_rotation?: number[]; [k: string]: unknown }
  stress_calendar: StressMonth[]
  strategies: Strategy[]
  gaps: string[]
  disclaimer: string
  reports_tier1: Record<string, AIReport | null>
  report_status: Record<string, ReportStatus>
  timings_ms?: Record<string, number>
}

export type ShowcaseFarm = {
  id: string
  name: string
  persona: string
  country: string
  place: string
  story: string
  geometry: Geometry
  report_languages: string[]
  available: boolean
  generated_at: string | null
  model: string | null
}

/** Where the API lives. Empty = "/api" on this origin (the Vite dev server forwards it). */
const API = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') || '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function detailText(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => (d && typeof d === 'object' && 'msg' in d ? String(d.msg) : String(d))).join('; ')
  }
  return ''
}

async function call<T>(path: string, init?: RequestInit & { token?: string | null; empty?: boolean }): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (init?.body) headers['Content-Type'] = 'application/json'
  if (init?.token) headers.Authorization = `Bearer ${init.token}`
  let response: Response
  try {
    const { token: _token, empty: _empty, ...rest } = init ?? {}
    void _token
    void _empty
    response = await fetch(`${API}${path}`, { ...rest, headers: { ...headers, ...(init?.headers ?? {}) } })
  } catch {
    throw new ApiError(0, 'Could not reach the SowSmart server. Check your connection and try again.')
  }
  if (!response.ok) {
    let message = ''
    try {
      message = detailText((await response.json()).detail)
    } catch {
      /* not JSON */
    }
    if (response.status === 429) message = message || 'Too many requests for now. Please try again later.'
    throw new ApiError(response.status, message || `The server answered ${response.status}.`)
  }
  if (init?.empty || response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function prefill(geometry: Geometry, signal?: AbortSignal) {
  return call<PrefillResponse>('/prefill', { method: 'POST', body: JSON.stringify({ geometry }), signal })
}

export function analyze(body: AnalyzeRequest, token?: string | null) {
  return call<AnalyzeResponse>('/analyze', { method: 'POST', body: JSON.stringify(body), token })
}

export function followup(
  analysis: AnalyzeResponse,
  language: string,
  level: 'farmer' | 'advanced',
  question: string,
  token?: string | null,
) {
  // Saved analyses (signed in) send only their id; the answer is stored with them.
  const source = analysis.analysis_id && token ? { analysis_id: analysis.analysis_id } : { analysis_payload: analysis }
  return call<AIReport<Tier2Content>>('/reports/followup', {
    method: 'POST',
    body: JSON.stringify({ ...source, language, language_level: level, question: question.trim() || null }),
    token,
  })
}

// --- Signed-in (Auth0 token required) -------------------------------------------------

export type FieldSummary = {
  id: string
  name: string
  area_ha: number | null
  input_mode: string
  lat: number
  lon: number
  analysis_id: string | null
  top_strategy: string | null
  analyzed_at: string | null
  created_at: string | null
  alert_types: string[]
  email: boolean
  push: boolean
  unread: number
}

export type Me = {
  display_name: string | null
  language: string
  units: 'metric' | 'imperial' | string
  has_email: boolean
  fields: FieldSummary[]
}

export function getMe(token: string) {
  return call<Me>('/me', { token })
}

export function updateMe(token: string, profile: { display_name: string | null; language: string; units: string }) {
  return call<void>('/me', { method: 'PUT', body: JSON.stringify(profile), token, empty: true })
}

export function deleteMe(token: string) {
  return call<void>('/me', { method: 'DELETE', token, empty: true })
}

export function saveAnalysis(
  token: string,
  request: AnalyzeRequest,
  analysis: AnalyzeResponse,
  fieldName: string,
  inputMode: 'geolocation' | 'point' | 'polygon' | 'browse',
) {
  return call<{ analysis_id: string; field_id: string; new_findings: boolean }>('/analyses/save', {
    method: 'POST',
    body: JSON.stringify({ request, analysis, field_name: fieldName, input_mode: inputMode }),
    token,
  })
}

export function savedAnalysis(token: string, id: string) {
  return call<AnalyzeResponse>(`/analyses/${encodeURIComponent(id)}`, { token })
}

export function renameField(token: string, id: string, name: string) {
  return call<void>(`/fields/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ name }), token, empty: true })
}

export function deleteField(token: string, id: string) {
  return call<void>(`/fields/${encodeURIComponent(id)}`, { method: 'DELETE', token, empty: true })
}

// Showcase farms: from the API when it is up, else from the copies bundled with the app
// (public/demo/, made by `make bundle-demo`), so the demo link keeps working without a server.
const DEMO = `${import.meta.env.BASE_URL}demo`

export async function showcaseList(): Promise<{ farms: ShowcaseFarm[]; offline: boolean }> {
  try {
    return { farms: await call<ShowcaseFarm[]>('/showcase'), offline: false }
  } catch {
    const response = await fetch(`${DEMO}/index.json`)
    if (!response.ok) throw new ApiError(0, 'The demo farms are not available right now.')
    return { farms: (await response.json()) as ShowcaseFarm[], offline: true }
  }
}

export async function showcaseAnalysis(id: string): Promise<AnalyzeResponse> {
  try {
    return await call<AnalyzeResponse>(`/showcase/${encodeURIComponent(id)}`)
  } catch {
    const response = await fetch(`${DEMO}/${encodeURIComponent(id)}.json`)
    if (!response.ok) throw new ApiError(404, 'This demo farm is not available right now.')
    const stored = (await response.json()) as { analysis: AnalyzeResponse }
    return stored.analysis
  }
}

/** True when the SowSmart API answers. A static host (e.g. Cloudflare Pages) answers /api/health
 *  with the app's HTML, so the JSON body is checked, not only the status. */
export async function serverUp(): Promise<boolean> {
  try {
    const response = await fetch(`${API}/health`, { headers: { Accept: 'application/json' } })
    if (!response.ok) return false
    const body = (await response.json()) as { status?: string }
    return body.status === 'ok'
  } catch {
    return false
  }
}

// --- Alerts (signed in) ----------------------------------------------------------------

export type AlertType = 'natural_event' | 'fire' | 'heavy_rain' | 'drought' | 'pest_risk' | 'new_findings'

export type Alert = {
  id: string
  field_id: string
  field_name: string
  type: AlertType
  severity: 'info' | 'watch' | 'warning'
  message: string
  source: string
  data: { event_geometry?: Geometry; points?: [number, number][]; url?: string; [k: string]: unknown }
  triggered_at: string
  read_at: string | null
  lat: number
  lon: number
}

export function getAlerts(token: string) {
  return call<Alert[]>('/alerts', { token })
}

export function checkAlerts(token: string, force = false) {
  return call<{ checked: boolean; new: number; last_check: string; alerts: Alert[] }>('/alerts/check', {
    method: 'POST',
    body: JSON.stringify({ force }),
    token,
  })
}

export function readAlert(token: string, id: string) {
  return call<void>(`/alerts/${encodeURIComponent(id)}/read`, { method: 'POST', token, empty: true })
}

export function setAlertPreferences(token: string, fieldId: string, alertTypes: AlertType[], email: boolean, push: boolean) {
  return call<void>('/alerts/preferences', {
    method: 'PUT',
    body: JSON.stringify({ field_id: fieldId, alert_types: alertTypes, email, push }),
    token,
    empty: true,
  })
}

export function pushKey() {
  return call<{ public_key: string | null }>('/alerts/push-key')
}

export function savePushSubscription(token: string, subscription: PushSubscriptionJSON) {
  return call<void>('/alerts/push-subscription', {
    method: 'POST',
    body: JSON.stringify({ endpoint: subscription.endpoint, keys: subscription.keys }),
    token,
    empty: true,
  })
}
