import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { LANGUAGES } from './i18n'
import type { UnitSystem } from './SignUp'
import './DetailedSetup.css'

type LatLng = { lat: number; lng: number }

type Removable = { remove: () => void }

type DrawMap = {
  setView: (center: [number, number], zoom: number) => DrawMap
  on: (event: 'click', handler: (event: { latlng: LatLng }) => void) => void
  remove: () => void
  invalidateSize: () => void
}

type LeafletDraw = {
  map: (element: HTMLElement, options?: object) => DrawMap
  tileLayer: (url: string, options?: object) => { addTo: (map: object) => void }
  marker: (latlng: [number, number], options?: object) => Removable & { addTo: (map: object) => Removable }
  polygon: (latlngs: [number, number][], options?: object) => Removable & { addTo: (map: object) => Removable }
  polyline: (latlngs: [number, number][], options?: object) => Removable & { addTo: (map: object) => Removable }
  divIcon: (options: object) => object
}

export type FieldPlot = {
  id: string
  name: string
  size: string
  sizeEdited: boolean
  areaHa: number | null
  drawMode: boolean
  boundaryClosed: boolean
  point: LatLng
  polygon: LatLng[]
  slope: string
  slopeEdited: boolean
  confirmed: boolean
}

export type RotationRow = { id: string; crop: string; planting: string; harvest: string }

const SECTION_IDS = [
  'account',
  'fields',
  'practice',
  'water',
  'soil',
  'resources',
  'market',
  'pests',
  'priorities',
  'privacy',
] as const

export type SectionId = (typeof SECTION_IDS)[number]

const SECTION_TITLES: Record<SectionId, string> = {
  account: 'Account & preferences',
  fields: 'Farm & fields',
  practice: 'What they do now',
  water: 'Water',
  soil: 'Soil',
  resources: 'Resources & limits',
  market: 'Market & household',
  pests: 'Pests & history',
  priorities: 'Priorities & risk',
  privacy: 'Privacy & consent',
}

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]

const SHORT_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const GOALS = [
  'Save water',
  'Build soil',
  'Reduce erosion',
  'Cut fertilizer costs',
  'Earn more',
  'Feed the household',
  'Feed livestock',
  'Less labor',
  'Survive bad years',
]

const PIN_ICON = `<svg viewBox="0 0 24 36" width="24" height="36" aria-hidden="true"><path fill="#1c3d32" d="M12 35.2S23 21.2 23 12A11 11 0 1 0 1 12c0 9.2 11 23.2 11 23.2z"/><circle cx="12" cy="12" r="4.2" fill="#f7f6f1"/></svg>`

export type DetailedDraft = {
  notice: string
  showAdvanced: boolean
  openSection: SectionId
  skipped: SectionId[]
  language: string
  areaUnit: 'hectares' | 'acres'
  system: UnitSystem
  displayName: string
  fields: FieldPlot[]
  activeField: string
  rotation: RotationRow[]
  emptyMonths: string[]
  tillage: string
  leftovers: string
  coverCrops: string[]
  livestock: string[]
  yields: string
  waterType: string
  irrigation: string
  waterSource: string
  reliability: string
  waterLimits: string
  drainage: string[]
  soilProblems: string[]
  soilFeel: string
  soilTestOpen: boolean
  ph: string
  organic: string
  n: string
  p: string
  k: string
  testYear: string
  equipment: string
  budget: string
  labor: string
  seedAccess: string
  fertilizerAccess: string
  storage: string
  road: string
  marketDistance: string
  sellCrops: string[]
  wontGrow: string[]
  eatenShare: number
  extraIncome: string[]
  contracts: string
  pests: string[]
  events: string[]
  eventNote: string
  goals: string[]
  risk: string
  riskCustom: string
  timeFrame: string
  consent: boolean
  shareRegional: boolean
}

export function slopeEstimate(meters: number | null, system: UnitSystem) {
  if (meters == null) return ''
  const height =
    system === 'imperial'
      ? `${Math.round(meters * 3.28084).toLocaleString('en-US')} ft`
      : `${Math.round(meters).toLocaleString('en-US')} m`
  return `Elevation about ${height}. Slope is not measured from one pin yet.`
}

function blankField(point: LatLng, slope: string): FieldPlot {
  return {
    id: crypto.randomUUID(),
    name: '',
    size: '',
    sizeEdited: false,
    areaHa: null,
    drawMode: false,
    boundaryClosed: false,
    point: { ...point },
    polygon: [],
    slope,
    slopeEdited: false,
    confirmed: false,
  }
}

function blankRotation(): RotationRow {
  return { id: crypto.randomUUID(), crop: '', planting: '', harvest: '' }
}

export function createDetailedDraft(units: UnitSystem, pin: LatLng, elevationM: number | null): DetailedDraft {
  const field = blankField(pin, slopeEstimate(elevationM, units))
  field.confirmed = true
  return {
    notice: '',
    showAdvanced: false,
    openSection: 'account',
    skipped: [],
    language: 'en',
    areaUnit: units === 'imperial' ? 'acres' : 'hectares',
    system: units,
    displayName: '',
    fields: [field],
    activeField: field.id,
    rotation: [blankRotation()],
    emptyMonths: [],
    tillage: '',
    leftovers: '',
    coverCrops: [],
    livestock: [],
    yields: '',
    waterType: '',
    irrigation: '',
    waterSource: '',
    reliability: '',
    waterLimits: '',
    drainage: [],
    soilProblems: [],
    soilFeel: '',
    soilTestOpen: false,
    ph: '',
    organic: '',
    n: '',
    p: '',
    k: '',
    testYear: '',
    equipment: '',
    budget: '',
    labor: '',
    seedAccess: '',
    fertilizerAccess: '',
    storage: '',
    road: '',
    marketDistance: '',
    sellCrops: [],
    wontGrow: [],
    eatenShare: 50,
    extraIncome: [],
    contracts: '',
    pests: [],
    events: [],
    eventNote: '',
    goals: [...GOALS],
    risk: '',
    riskCustom: '',
    timeFrame: '',
    consent: false,
    shareRegional: false,
  }
}

function polygonAreaHa(ring: LatLng[]) {
  if (ring.length < 3) return 0
  const radius = 6378137
  const lat0 = (ring[0].lat * Math.PI) / 180
  const points = ring.map((point) => ({
    x: radius * ((point.lng * Math.PI) / 180) * Math.cos(lat0),
    y: radius * ((point.lat * Math.PI) / 180),
  }))
  let sum = 0
  for (let index = 0; index < points.length; index += 1) {
    const next = points[(index + 1) % points.length]
    sum += points[index].x * next.y - next.x * points[index].y
  }
  return Math.abs(sum) / 2 / 10000
}

function formatArea(hectares: number, unit: 'hectares' | 'acres') {
  if (hectares <= 0) return ''
  const value = unit === 'acres' ? hectares * 2.47105 : hectares
  const digits = value < 10 ? 2 : 1
  return `${value.toFixed(digits)} ${unit === 'acres' ? 'acres' : 'ha'}`
}

function sectionReady(id: SectionId, draft: DetailedDraft) {
  if (draft.skipped.includes(id)) return true
  const rotationReady = draft.rotation.some((row) => row.crop.trim() && row.planting && row.harvest)
  switch (id) {
    case 'account':
      return true
    case 'fields':
      return draft.fields.some((field) => field.confirmed || field.name.trim() !== '' || field.boundaryClosed)
    case 'practice':
      return rotationReady && draft.emptyMonths.length > 0
    case 'water':
      return draft.waterType !== ''
    case 'soil':
      return draft.soilProblems.length > 0
    case 'resources':
      return draft.equipment !== '' && draft.budget !== ''
    case 'market':
      return draft.sellCrops.length > 0 && draft.wontGrow.length > 0
    case 'pests':
      return draft.pests.length > 0 || draft.events.length > 0 || draft.eventNote.trim() !== ''
    case 'priorities':
      return draft.risk !== '' || draft.riskCustom.trim() !== ''
    case 'privacy':
      return draft.consent
    default:
      return false
  }
}

export default function DetailedSetup({
  draft,
  elevationM,
  onDraft,
  onBack,
  onReset,
  onFinish,
}: {
  draft: DetailedDraft
  elevationM: number | null
  onDraft: (draft: DetailedDraft) => void
  onBack: () => void
  onReset: () => void
  onFinish: (draft: DetailedDraft) => void
}) {
  const readyCount = SECTION_IDS.filter((id) => sectionReady(id, draft)).length
  const active = draft.fields.find((field) => field.id === draft.activeField) ?? draft.fields[0]

  function edit(partial: Partial<DetailedDraft>) {
    onDraft({ ...draft, ...partial, notice: '' })
  }

  function skip(id: SectionId) {
    edit({ skipped: draft.skipped.includes(id) ? draft.skipped : [...draft.skipped, id] })
  }

  function updateField(id: string, partial: Partial<FieldPlot>) {
    edit({
      fields: draft.fields.map((field) => (field.id === id ? { ...field, ...partial } : field)),
    })
  }

  function setAreaUnit(areaUnit: 'hectares' | 'acres') {
    edit({
      areaUnit,
      fields: draft.fields.map((field) =>
        field.sizeEdited || field.areaHa == null ? field : { ...field, size: formatArea(field.areaHa, areaUnit) },
      ),
    })
  }

  function setSystem(system: UnitSystem) {
    edit({
      system,
      fields: draft.fields.map((field) =>
        field.slopeEdited ? field : { ...field, slope: slopeEstimate(elevationM, system) },
      ),
    })
  }

  return (
    <div className="step-panel questions-panel detailed-panel">
      <div className="ask-head">
        <button type="button" className="card-back" onClick={onBack} aria-label="Back to question options">
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
        <div className="quick-titles">
          <h1 id="detailed-title" className="ask">
            Detailed Farm Profile
          </h1>
          <p className="ask-sub">Essential fields are marked. Skip anything you do not know.</p>
        </div>
      </div>

      <label className={draft.showAdvanced ? 'farm-toggle is-on advanced-toggle' : 'farm-toggle advanced-toggle'}>
        <input
          type="checkbox"
          checked={draft.showAdvanced}
          onChange={(event) => edit({ showAdvanced: event.target.checked })}
        />
        <span>Show all advanced fields</span>
      </label>

      {draft.notice ? <p className="cleared-note">{draft.notice}</p> : null}

      <div className="section-list">
        {SECTION_IDS.map((id, index) => {
          const open = draft.openSection === id
          const ready = sectionReady(id, draft)
          return (
            <section key={id} className={open ? 'detail-section is-open' : 'detail-section'}>
              <button
                type="button"
                className="section-head"
                aria-expanded={open}
                onClick={() => edit({ openSection: open ? draft.openSection : id })}
              >
                <span className="q-num">{index + 1}</span>
                <span className="section-title">{SECTION_TITLES[id]}</span>
                {ready ? <span className="section-done">Ready</span> : null}
              </button>
              {open ? (
                <div className="section-body">
                  {id === 'account' ? (
                    <AccountSection draft={draft} edit={edit} setAreaUnit={setAreaUnit} setSystem={setSystem} />
                  ) : null}
                  {id === 'fields' && active ? (
                    <FieldsSection
                      draft={draft}
                      active={active}
                      edit={edit}
                      updateField={updateField}
                      onAdd={() => {
                        const field = blankField(active.point, slopeEstimate(elevationM, draft.system))
                        edit({ fields: [...draft.fields, field], activeField: field.id })
                      }}
                    />
                  ) : null}
                  {id === 'practice' ? <PracticeSection draft={draft} edit={edit} /> : null}
                  {id === 'water' ? <WaterSection draft={draft} edit={edit} /> : null}
                  {id === 'soil' ? <SoilSection draft={draft} edit={edit} /> : null}
                  {id === 'resources' ? <ResourcesSection draft={draft} edit={edit} /> : null}
                  {id === 'market' ? <MarketSection draft={draft} edit={edit} /> : null}
                  {id === 'pests' ? <PestsSection draft={draft} edit={edit} /> : null}
                  {id === 'priorities' ? <PrioritiesSection draft={draft} edit={edit} /> : null}
                  {id === 'privacy' ? (
                    <PrivacySection
                      draft={draft}
                      edit={edit}
                      onReset={() => {
                        onReset()
                      }}
                    />
                  ) : null}
                  {id !== 'privacy' ? (
                    <button type="button" className="skip-link section-skip" onClick={() => skip(id)}>
                      {draft.skipped.includes(id) ? 'Section skipped' : 'Skip this section'}
                    </button>
                  ) : null}
                </div>
              ) : null}
            </section>
          )
        })}
      </div>

      <div className="plan-footer">
        <p className="progress-label">{readyCount} of 10 sections ready</p>
        <div
          className="progress-track"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={10}
          aria-valuenow={readyCount}
          aria-label="Sections ready"
        >
          <span style={{ width: `${(readyCount / 10) * 100}%` }} />
        </div>
        <button type="button" className="continue" disabled={!draft.consent} onClick={() => onFinish(draft)}>
          Save & Generate Farm Plan
        </button>
        {draft.consent ? null : <p className="footer-hint">Consent is required before SowSmart can keep this profile.</p>}
      </div>
    </div>
  )
}

function AccountSection({
  draft,
  edit,
  setAreaUnit,
  setSystem,
}: {
  draft: DetailedDraft
  edit: (partial: Partial<DetailedDraft>) => void
  setAreaUnit: (unit: 'hectares' | 'acres') => void
  setSystem: (system: UnitSystem) => void
}) {
  return (
    <>
      <FieldLabel essential htmlFor="detail-language">
        Language
      </FieldLabel>
      <select
        id="detail-language"
        className="control unit-select"
        value={draft.language}
        onChange={(event) => edit({ language: event.target.value })}
      >
        {LANGUAGES.map((language) => (
          <option key={language.value} value={language.value}>
            {language.label}
          </option>
        ))}
      </select>
      {draft.language !== 'en' ? (
        <p className="helper">
          Reports are most reliable in English. In other languages the quality may be lower, and some words will stay in
          English when there is no common local word for them.
        </p>
      ) : null}
      <FieldLabel essential>Units</FieldLabel>
      <p className="helper">Pre-filled from the measurement system you chose earlier.</p>
      <div className="unit-stack">
        <Segment
          label="Area"
          value={draft.areaUnit}
          options={[
            { value: 'hectares', label: 'Hectares' },
            { value: 'acres', label: 'Acres' },
          ]}
          onChange={setAreaUnit}
        />
        <Segment
          label="System"
          value={draft.system}
          options={[
            { value: 'metric', label: 'Metric' },
            { value: 'imperial', label: 'Imperial' },
          ]}
          onChange={setSystem}
        />
      </div>
      {draft.showAdvanced ? (
        <div className="field">
          <FieldLabel htmlFor="detail-name">Display name</FieldLabel>
          <input
            id="detail-name"
            className="control"
            value={draft.displayName}
            autoComplete="nickname"
            placeholder="Optional"
            onChange={(event) => edit({ displayName: event.target.value })}
          />
          <p className="helper">Collects minimal personal info.</p>
        </div>
      ) : null}
    </>
  )
}

function FieldsSection({
  draft,
  active,
  edit,
  updateField,
  onAdd,
}: {
  draft: DetailedDraft
  active: FieldPlot
  edit: (partial: Partial<DetailedDraft>) => void
  updateField: (id: string, partial: Partial<FieldPlot>) => void
  onAdd: () => void
}) {
  return (
    <>
      <div className="field-tabs">
        {draft.fields.map((field, index) => (
          <button
            key={field.id}
            type="button"
            className={field.id === active.id ? 'field-tab is-on' : 'field-tab'}
            onClick={() => edit({ activeField: field.id })}
          >
            {field.name.trim() || `Field ${index + 1}`}
          </button>
        ))}
        <button type="button" className="field-tab" onClick={onAdd}>
          + Add another field
        </button>
      </div>
      <FieldLabel essential>Location & field boundary</FieldLabel>
      <div className="mode-row" role="radiogroup" aria-label="How to mark the field">
        <button
          type="button"
          className={active.drawMode ? 'mini-pill' : 'mini-pill is-on'}
          aria-pressed={!active.drawMode}
          onClick={() => updateField(active.id, { drawMode: false })}
        >
          Drop a pin
        </button>
        <button
          type="button"
          className={active.drawMode ? 'mini-pill is-on' : 'mini-pill'}
          aria-pressed={active.drawMode}
          onClick={() => updateField(active.id, { drawMode: true })}
        >
          Draw a boundary
        </button>
      </div>
      <FieldMap
        field={active}
        onPoint={(point) => updateField(active.id, { point, confirmed: true })}
        onVertex={(point) => updateField(active.id, { polygon: [...active.polygon, point], boundaryClosed: false })}
      />
      <div className="map-actions">
        <button type="button" className="text-action" onClick={() => updateField(active.id, { confirmed: true })}>
          Confirm this pin
        </button>
        {active.drawMode ? (
          <>
            <button
              type="button"
              className="text-action"
              disabled={active.polygon.length === 0}
              onClick={() => updateField(active.id, { polygon: active.polygon.slice(0, -1), boundaryClosed: false, areaHa: null })}
            >
              Undo point
            </button>
            <button
              type="button"
              className="text-action"
              disabled={active.polygon.length < 3}
              onClick={() => {
                const areaHa = polygonAreaHa(active.polygon)
                updateField(active.id, {
                  boundaryClosed: true,
                  confirmed: true,
                  areaHa,
                  size: active.sizeEdited ? active.size : formatArea(areaHa, draft.areaUnit),
                })
              }}
            >
              Close shape
            </button>
            <button
              type="button"
              className="text-action"
              onClick={() =>
                updateField(active.id, {
                  polygon: [],
                  boundaryClosed: false,
                  areaHa: null,
                  size: active.sizeEdited ? active.size : '',
                })
              }
            >
              Clear
            </button>
          </>
        ) : null}
      </div>
      <div className="month-pair">
        <div className="field">
          <FieldLabel essential htmlFor={`field-name-${active.id}`}>
            Field name
          </FieldLabel>
          <input
            id={`field-name-${active.id}`}
            className="control"
            value={active.name}
            placeholder="e.g., North paddy"
            onChange={(event) => updateField(active.id, { name: event.target.value, confirmed: true })}
          />
        </div>
        <div className="field">
          <FieldLabel essential htmlFor={`field-size-${active.id}`}>
            Size
          </FieldLabel>
          <input
            id={`field-size-${active.id}`}
            className="control"
            value={active.size}
            placeholder={draft.areaUnit === 'acres' ? 'acres' : 'hectares'}
            onChange={(event) => updateField(active.id, { size: event.target.value, sizeEdited: true })}
          />
        </div>
      </div>
      <p className="helper">Size fills in after you close a drawn boundary. You can type it instead.</p>
      {draft.showAdvanced ? (
        <div className="field">
          <div className="q-head">
            <FieldLabel htmlFor={`field-slope-${active.id}`}>Slope</FieldLabel>
            <button
              type="button"
              className="skip-link"
              onClick={() => updateField(active.id, { slopeEdited: !active.slopeEdited })}
            >
              {active.slopeEdited ? 'Done' : 'Edit / Correct'}
            </button>
          </div>
          <input
            id={`field-slope-${active.id}`}
            className="control"
            readOnly={!active.slopeEdited}
            value={active.slope}
            onChange={(event) => updateField(active.id, { slope: event.target.value, slopeEdited: true })}
          />
        </div>
      ) : null}
    </>
  )
}

function FieldMap({
  field,
  onPoint,
  onVertex,
}: {
  field: FieldPlot
  onPoint: (point: LatLng) => void
  onVertex: (point: LatLng) => void
}) {
  const node = useRef<HTMLDivElement>(null)
  const mapRef = useRef<DrawMap | null>(null)
  const layers = useRef<{ marker?: Removable; shape?: Removable }>({})
  const fieldRef = useRef(field)
  const onPointRef = useRef(onPoint)
  const onVertexRef = useRef(onVertex)

  useEffect(() => {
    fieldRef.current = field
    onPointRef.current = onPoint
    onVertexRef.current = onVertex
  })

  useEffect(() => {
    const L = window.L as unknown as LeafletDraw | undefined
    if (!node.current || !L) return
    const start = fieldRef.current.point
    const map = L.map(node.current, { zoomControl: true, maxZoom: 18 }).setView([start.lat, start.lng], 14)
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      attribution: 'Imagery &copy; Esri, Maxar, Earthstar Geographics',
      maxZoom: 18,
    }).addTo(map)
    map.on('click', (event) => {
      const current = fieldRef.current
      if (current.drawMode && !current.boundaryClosed) onVertexRef.current(event.latlng)
      else if (!current.drawMode) onPointRef.current(event.latlng)
    })
    mapRef.current = map
    const timer = window.setTimeout(() => map.invalidateSize(), 80)
    return () => {
      window.clearTimeout(timer)
      map.remove()
      mapRef.current = null
    }
  }, [field.id])

  useEffect(() => {
    const L = window.L as unknown as LeafletDraw | undefined
    const map = mapRef.current
    if (!L || !map) return
    layers.current.marker?.remove()
    layers.current.shape?.remove()
    const icon = L.divIcon({ className: 'sow-pin', html: PIN_ICON, iconSize: [24, 36], iconAnchor: [12, 34] })
    layers.current.marker = L.marker([field.point.lat, field.point.lng], { icon, keyboard: false }).addTo(map)
    if (field.polygon.length >= 2) {
      const ring = field.polygon.map((point) => [point.lat, point.lng] as [number, number])
      layers.current.shape =
        field.boundaryClosed && field.polygon.length >= 3
          ? L.polygon(ring, { color: '#1c3d32', weight: 2, fillColor: '#1c3d32', fillOpacity: 0.28 }).addTo(map)
          : L.polyline(ring, { color: '#f7f6f1', weight: 3 }).addTo(map)
    }
  }, [field.boundaryClosed, field.id, field.point, field.polygon])

  return (
    <div className="detailed-map-frame">
      <div ref={node} className="detailed-map" role="application" aria-label="Field map. Tap to place a pin or add a boundary point." />
    </div>
  )
}

function PracticeSection({ draft, edit }: { draft: DetailedDraft; edit: (partial: Partial<DetailedDraft>) => void }) {
  function setRow(id: string, partial: Partial<RotationRow>) {
    edit({ rotation: draft.rotation.map((row) => (row.id === id ? { ...row, ...partial } : row)) })
  }
  return (
    <>
      <FieldLabel essential>Current rotation</FieldLabel>
      {draft.rotation.map((row, index) => (
        <div className="crop-row" key={row.id}>
          {index > 0 ? (
            <button
              type="button"
              className="crop-remove"
              aria-label={`Remove crop ${index + 1}`}
              onClick={() => edit({ rotation: draft.rotation.filter((item) => item.id !== row.id) })}
            >
              ×
            </button>
          ) : null}
          <div className="field">
            <label htmlFor={`rot-crop-${row.id}`}>Crop</label>
            <input
              id={`rot-crop-${row.id}`}
              className="control"
              value={row.crop}
              placeholder="e.g., Rice"
              onChange={(event) => setRow(row.id, { crop: event.target.value })}
            />
          </div>
          <div className="month-pair">
            <MonthSelect id={`rot-plant-${row.id}`} label="Planting month" value={row.planting} onChange={(planting) => setRow(row.id, { planting })} />
            <MonthSelect id={`rot-harvest-${row.id}`} label="Harvest month" value={row.harvest} onChange={(harvest) => setRow(row.id, { harvest })} />
          </div>
        </div>
      ))}
      <button type="button" className="add-crop" onClick={() => edit({ rotation: [...draft.rotation, blankRotation()] })}>
        + Add crop to rotation
      </button>
      <FieldLabel essential>Months the field sits empty</FieldLabel>
      <p className="helper">Cross-checks satellite bare-field data.</p>
      <Pills
        options={[...SHORT_MONTHS, 'No empty months']}
        value={draft.emptyMonths}
        onChange={(emptyMonths) => edit({ emptyMonths })}
      />
      {draft.showAdvanced ? (
        <>
          <Choice id="detail-tillage" label="Tillage" value={draft.tillage} options={['Plowing', 'Reduced tillage', 'No-till']} onChange={(tillage) => edit({ tillage })} />
          <Choice id="detail-leftovers" label="Crop leftovers" value={draft.leftovers} options={['Removed', 'Burned', 'Left on the field']} onChange={(leftovers) => edit({ leftovers })} />
          <FieldLabel>Cover crops used</FieldLabel>
          <Chips value={draft.coverCrops} placeholder="e.g., Sunn hemp" onChange={(coverCrops) => edit({ coverCrops })} />
          <FieldLabel>Livestock on farm</FieldLabel>
          <p className="helper">Helps with feed and manure.</p>
          <Pills options={['None', 'Cattle', 'Goats/Sheep', 'Poultry', 'Pigs', 'Draft animals']} value={draft.livestock} onChange={(livestock) => edit({ livestock })} />
          <div className="field">
            <FieldLabel htmlFor="detail-yields">Typical yields</FieldLabel>
            <input id="detail-yields" className="control" value={draft.yields} placeholder="Optional, with units" onChange={(event) => edit({ yields: event.target.value })} />
          </div>
        </>
      ) : null}
    </>
  )
}

function WaterSection({ draft, edit }: { draft: DetailedDraft; edit: (partial: Partial<DetailedDraft>) => void }) {
  return (
    <>
      <Choice
        essential
        id="detail-water"
        label="Water source type"
        value={draft.waterType}
        options={['Irrigated', 'Rain-fed', 'Some of each', "I don't know"]}
        onChange={(waterType) => edit({ waterType })}
      />
      {draft.showAdvanced ? (
        <>
          <Choice id="detail-irrigation" label="Irrigation method" value={draft.irrigation} options={['Flood', 'Furrow', 'Sprinkler', 'Drip', 'None']} onChange={(irrigation) => edit({ irrigation })} />
          <Choice id="detail-source" label="Water source" value={draft.waterSource} options={['Well', 'Canal', 'River', 'Pond', 'Rain only']} onChange={(waterSource) => edit({ waterSource })} />
          <Choice id="detail-reliability" label="Seasonal reliability" value={draft.reliability} options={['Reliable year-round', 'Seasonal shortages', 'Unreliable']} onChange={(reliability) => edit({ reliability })} />
          <div className="field">
            <FieldLabel htmlFor="detail-limits">Water limits or costs</FieldLabel>
            <input id="detail-limits" className="control" value={draft.waterLimits} placeholder="Optional" onChange={(event) => edit({ waterLimits: event.target.value })} />
          </div>
          <FieldLabel>Drainage problems</FieldLabel>
          <Pills options={['None', 'Poor drainage', 'Waterlogging', 'Seasonal flooding']} value={draft.drainage} onChange={(drainage) => edit({ drainage })} />
        </>
      ) : null}
    </>
  )
}

function SoilSection({ draft, edit }: { draft: DetailedDraft; edit: (partial: Partial<DetailedDraft>) => void }) {
  return (
    <>
      <p className="helper soil-note">What you know overrides satellite and model estimates.</p>
      <FieldLabel essential>Known soil problems</FieldLabel>
      <Pills
        options={['None', 'Erosion', 'Compaction', 'Salty soil', 'Acidic soil', 'Low fertility', 'Surface crusting']}
        value={draft.soilProblems}
        onChange={(soilProblems) => edit({ soilProblems })}
      />
      {draft.showAdvanced ? (
        <>
          <FieldLabel>How the soil feels</FieldLabel>
          <Pills single options={['Sandy', 'Loamy', 'Clay']} value={draft.soilFeel ? [draft.soilFeel] : []} onChange={(value) => edit({ soilFeel: value[0] ?? '' })} />
          <button type="button" className="add-crop" onClick={() => edit({ soilTestOpen: !draft.soilTestOpen })}>
            {draft.soilTestOpen ? 'Hide soil test' : 'Soil test results (optional)'}
          </button>
          {draft.soilTestOpen ? (
            <div className="test-grid">
              <MiniInput id="soil-ph" label="pH" value={draft.ph} onChange={(ph) => edit({ ph })} />
              <MiniInput id="soil-om" label="Organic matter %" value={draft.organic} onChange={(organic) => edit({ organic })} />
              <MiniInput id="soil-n" label="N" value={draft.n} onChange={(n) => edit({ n })} />
              <MiniInput id="soil-p" label="P" value={draft.p} onChange={(p) => edit({ p })} />
              <MiniInput id="soil-k" label="K" value={draft.k} onChange={(k) => edit({ k })} />
              <MiniInput id="soil-year" label="Year tested" value={draft.testYear} onChange={(testYear) => edit({ testYear })} />
            </div>
          ) : null}
        </>
      ) : null}
    </>
  )
}

function ResourcesSection({ draft, edit }: { draft: DetailedDraft; edit: (partial: Partial<DetailedDraft>) => void }) {
  return (
    <>
      <Choice essential id="detail-equipment" label="Equipment" value={draft.equipment} options={['Hand tools', 'Animal-drawn', 'Small tractor', 'Full machinery']} onChange={(equipment) => edit({ equipment })} />
      <FieldLabel essential>Budget for seed & supplies</FieldLabel>
      <Pills single options={['Low', 'Medium', 'High']} value={draft.budget ? [draft.budget] : []} onChange={(value) => edit({ budget: value[0] ?? '' })} />
      {draft.showAdvanced ? (
        <>
          <Choice id="detail-labor" label="Labor" value={draft.labor} options={['Family only', 'Hired', 'Seasonal']} onChange={(labor) => edit({ labor })} />
          <FieldLabel>Access to seed</FieldLabel>
          <Pills single options={['Easy access', 'Limited / Expensive', 'No access']} value={draft.seedAccess ? [draft.seedAccess] : []} onChange={(value) => edit({ seedAccess: value[0] ?? '' })} />
          <FieldLabel>Access to fertilizer</FieldLabel>
          <Pills single options={['Easy access', 'Limited / Expensive', 'No access']} value={draft.fertilizerAccess ? [draft.fertilizerAccess] : []} onChange={(value) => edit({ fertilizerAccess: value[0] ?? '' })} />
          <Choice id="detail-storage" label="Storage & drying space" value={draft.storage} options={['None', 'Basic / On-farm', 'Dedicated dry storage']} onChange={(storage) => edit({ storage })} />
          <Choice id="detail-road" label="Road access" value={draft.road} options={['Paved', 'Unpaved / Seasonal', 'Footpath only']} onChange={(road) => edit({ road })} />
          <div className="field">
            <FieldLabel htmlFor="detail-market">Distance to market</FieldLabel>
            <input
              id="detail-market"
              className="control"
              value={draft.marketDistance}
              placeholder={draft.system === 'imperial' ? 'miles' : 'km'}
              onChange={(event) => edit({ marketDistance: event.target.value })}
            />
          </div>
        </>
      ) : null}
    </>
  )
}

function MarketSection({ draft, edit }: { draft: DetailedDraft; edit: (partial: Partial<DetailedDraft>) => void }) {
  const sold = draft.eatenShare
  return (
    <>
      <FieldLabel essential>Crops you can sell locally</FieldLabel>
      <Chips value={draft.sellCrops} placeholder="e.g., Rice" onChange={(sellCrops) => edit({ sellCrops })} />
      <FieldLabel essential>Crops you won't grow</FieldLabel>
      <p className="helper">Cultural, religious, dietary, or no buyer.</p>
      <Chips value={draft.wontGrow} placeholder="e.g., Cotton" onChange={(wontGrow) => edit({ wontGrow })} />
      {draft.showAdvanced ? (
        <>
          <FieldLabel htmlFor="detail-split">Household use vs. sales</FieldLabel>
          <input
            id="detail-split"
            className="split-range"
            type="range"
            min={0}
            max={100}
            value={sold}
            onChange={(event) => edit({ eatenShare: Number(event.target.value) })}
          />
          <p className="helper">
            Eaten by household {100 - sold}% · Sold {sold}%
          </p>
          <FieldLabel>Interest in extra income</FieldLabel>
          <Pills options={['Animal feed', 'Specialty crops', 'Seed production']} value={draft.extraIncome} onChange={(extraIncome) => edit({ extraIncome })} />
          <div className="field">
            <FieldLabel htmlFor="detail-contracts">Contracts or programs</FieldLabel>
            <input id="detail-contracts" className="control" value={draft.contracts} placeholder="Optional" onChange={(event) => edit({ contracts: event.target.value })} />
          </div>
        </>
      ) : null}
    </>
  )
}

function PestsSection({ draft, edit }: { draft: DetailedDraft; edit: (partial: Partial<DetailedDraft>) => void }) {
  if (!draft.showAdvanced) {
    return <p className="helper">Pest history is optional. Turn on advanced fields to add it.</p>
  }
  return (
    <>
      <FieldLabel>Recurring pests, diseases & weeds</FieldLabel>
      <Chips value={draft.pests} placeholder="e.g., Stem borer on rice" onChange={(pests) => edit({ pests })} />
      <FieldLabel>Recent extreme events</FieldLabel>
      <Pills options={['Drought', 'Flood', 'Typhoon / High wind', 'Frost', 'Extreme heat']} value={draft.events} onChange={(events) => edit({ events })} />
      <div className="field">
        <FieldLabel htmlFor="detail-losses">Notes on crop losses</FieldLabel>
        <textarea id="detail-losses" className="control land-input" rows={2} value={draft.eventNote} onChange={(event) => edit({ eventNote: event.target.value })} />
      </div>
    </>
  )
}

function PrioritiesSection({ draft, edit }: { draft: DetailedDraft; edit: (partial: Partial<DetailedDraft>) => void }) {
  function move(index: number, direction: -1 | 1) {
    const nextIndex = index + direction
    if (nextIndex < 0 || nextIndex >= draft.goals.length) return
    const goals = [...draft.goals]
    const [item] = goals.splice(index, 1)
    goals.splice(nextIndex, 0, item)
    edit({ goals })
  }
  return (
    <>
      <FieldLabel essential>Rank your goals</FieldLabel>
      <p className="helper">Top of the list matters most. Use the arrows to reorder.</p>
      <ol className="goal-list">
        {draft.goals.map((goal, index) => (
          <li key={goal}>
            <span>{goal}</span>
            <span className="goal-moves">
              <button type="button" aria-label={`Move ${goal} up`} disabled={index === 0} onClick={() => move(index, -1)}>
                ↑
              </button>
              <button
                type="button"
                aria-label={`Move ${goal} down`}
                disabled={index === draft.goals.length - 1}
                onClick={() => move(index, 1)}
              >
                ↓
              </button>
            </span>
          </li>
        ))}
      </ol>
      <FieldLabel essential>Land risked on a new crop</FieldLabel>
      <Pills
        single
        options={['One small test plot', '10% of land', '25% of land', '50%+']}
        value={draft.risk ? [draft.risk] : []}
        onChange={(value) => edit({ risk: value[0] ?? '', riskCustom: '' })}
      />
      <input
        className="control"
        value={draft.riskCustom}
        placeholder="Or type your own share"
        onChange={(event) => edit({ riskCustom: event.target.value, risk: '' })}
      />
      {draft.showAdvanced ? (
        <>
          <FieldLabel>Time frame</FieldLabel>
          <Pills
            single
            options={['Results this season', 'Over 3–5 years']}
            value={draft.timeFrame ? [draft.timeFrame] : []}
            onChange={(value) => edit({ timeFrame: value[0] ?? '' })}
          />
        </>
      ) : null}
    </>
  )
}

function PrivacySection({
  draft,
  edit,
  onReset,
}: {
  draft: DetailedDraft
  edit: (partial: Partial<DetailedDraft>) => void
  onReset: () => void
}) {
  return (
    <>
      <label className="consent-row">
        <input type="checkbox" checked={draft.consent} onChange={(event) => edit({ consent: event.target.checked })} />
        <span>
          <Essential /> I consent to SowSmart storing my farm data to generate recommendations.
        </span>
      </label>
      <button type="button" className="text-action delete-data" onClick={onReset}>
        Delete my data
      </button>
      {draft.showAdvanced ? (
        <label className="consent-row">
          <input
            type="checkbox"
            checked={draft.shareRegional}
            onChange={(event) => edit({ shareRegional: event.target.checked })}
          />
          <span>Opt in to share anonymized farm data to help power regional insights.</span>
        </label>
      ) : null}
    </>
  )
}

function FieldLabel({
  children,
  essential,
  htmlFor,
}: {
  children: string
  essential?: boolean
  htmlFor?: string
}) {
  const content = (
    <>
      {essential ? <Essential /> : null}
      {children}
    </>
  )
  if (htmlFor) {
    return (
      <label className="detail-label" htmlFor={htmlFor}>
        {content}
      </label>
    )
  }
  return <p className="detail-label">{content}</p>
}

function Essential() {
  return <span className="essential">Essential</span>
}

function Choice({
  id,
  label,
  value,
  options,
  onChange,
  essential,
}: {
  id: string
  label: string
  value: string
  options: string[]
  onChange: (value: string) => void
  essential?: boolean
}) {
  return (
    <div className="field">
      <FieldLabel essential={essential} htmlFor={id}>
        {label}
      </FieldLabel>
      <select
        id={id}
        className={value ? 'control unit-select' : 'control unit-select is-placeholder'}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Choose one</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  )
}

function MonthSelect({ id, label, value, onChange }: { id: string; label: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        className={value ? 'control unit-select' : 'control unit-select is-placeholder'}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Month</option>
        {MONTHS.map((month) => (
          <option key={month} value={month}>
            {month}
          </option>
        ))}
      </select>
    </div>
  )
}

function Pills({
  options,
  value,
  onChange,
  single,
}: {
  options: string[]
  value: string[]
  onChange: (value: string[]) => void
  single?: boolean
}) {
  return (
    <div className="pill-row" role={single ? 'radiogroup' : 'group'}>
      {options.map((option) => {
        const on = value.includes(option)
        return (
          <button
            key={option}
            type="button"
            className={on ? 'mini-pill is-on' : 'mini-pill'}
            aria-pressed={on}
            onClick={() => {
              if (single) {
                onChange(on ? [] : [option])
                return
              }
              if (option === 'None' || option === 'No empty months') {
                onChange(on ? [] : [option])
                return
              }
              onChange(on ? value.filter((item) => item !== option) : [...value.filter((item) => item !== 'None' && item !== 'No empty months'), option])
            }}
          >
            {option}
          </button>
        )
      })}
    </div>
  )
}

function Segment<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
}) {
  return (
    <div className="segment">
      <span>{label}</span>
      <div role="radiogroup" aria-label={label}>
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            className={value === option.value ? 'mini-pill is-on' : 'mini-pill'}
            aria-pressed={value === option.value}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function Chips({ value, onChange, placeholder }: { value: string[]; onChange: (value: string[]) => void; placeholder: string }) {
  const [text, setText] = useState('')
  function add(raw: string) {
    const name = raw.trim().replace(/,+$/, '')
    setText('')
    if (!name || value.some((item) => item.toLowerCase() === name.toLowerCase())) return
    onChange([...value, name])
  }
  function onKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter' || event.key === ',') {
      event.preventDefault()
      add(text)
    } else if (event.key === 'Backspace' && text === '' && value.length > 0) {
      onChange(value.slice(0, -1))
    }
  }
  return (
    <div className="chip-box">
      {value.map((item) => (
        <span className="chip" key={item}>
          {item}
          <button type="button" aria-label={`Remove ${item}`} onClick={() => onChange(value.filter((chip) => chip !== item))}>
            ×
          </button>
        </span>
      ))}
      <input
        value={text}
        placeholder={value.length === 0 ? placeholder : 'Add another'}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKey}
        onBlur={() => {
          if (text.trim()) add(text)
        }}
      />
    </div>
  )
}

function MiniInput({ id, label, value, onChange }: { id: string; label: string; value: string; onChange: (value: string) => void }) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input id={id} className="control" value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  )
}
