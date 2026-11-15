import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { LANGUAGES } from './i18n'
import { MAX_FIELD_HA, areaHa, baseStyle, maplibregl, pinMarker } from './mapkit'
import type { Feature } from 'geojson'
import type { UnitSystem } from './SignUp'
import './DetailedSetup.css'

type LatLng = { lat: number; lng: number }

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
  /** True once the farmer reorders or confirms the goals; until then no ranking is sent. */
  goalsTouched: boolean
  risk: string
  riskCustom: string
  timeFrame: string
  consent: boolean
  shareRegional: boolean
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

/** slopeText: the NASA SRTM slope card from /prefill ("The land is gently sloping (about 2°)").
 *  polygon: the boundary drawn on the locate step, if any. */
export function createDetailedDraft(units: UnitSystem, pin: LatLng, slopeText: string, polygon: LatLng[] = []): DetailedDraft {
  const field = blankField(pin, slopeText)
  field.confirmed = true
  if (polygon.length >= 3) {
    field.polygon = polygon
    field.boundaryClosed = true
    field.drawMode = true
    field.areaHa = polygonAreaHa(polygon)
    field.size = formatArea(field.areaHa, units === 'imperial' ? 'acres' : 'hectares')
  }
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
    goalsTouched: false,
    risk: '',
    riskCustom: '',
    timeFrame: '',
    consent: false,
    shareRegional: false,
  }
}

function polygonAreaHa(ring: LatLng[]) {
  if (ring.length < 3) return 0
  const coords = ring.map((p) => [p.lng, p.lat])
  return areaHa({ type: 'Polygon', coordinates: [[...coords, coords[0]]] })
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
  slopeText,
  onDraft,
  onBack,
  onReset,
  onFinish,
}: {
  draft: DetailedDraft
  slopeText: string
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
    const skipped = draft.skipped.includes(id) ? draft.skipped : [...draft.skipped, id]
    // Skipping priorities means "not sure": all goals then count the same.
    edit(id === 'priorities' ? { skipped, goalsTouched: false } : { skipped })
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
    edit({ system })
  }

  return (
    <div className="step-panel questions-panel detailed-panel">
      <div className="detailed-top">
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
      </div>
      <div className="detailed-head">
        <h1 id="detailed-title" className="detailed-title">
          Detailed setup
        </h1>
        <p className="cap detailed-count">{readyCount} of 10 ready</p>
      </div>
      <p className="detailed-note">Every section is optional: skip anything you don't know. Only the consent at the end is needed to save.</p>

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
        {SECTION_IDS.map((id) => {
          const open = draft.openSection === id
          const ready = sectionReady(id, draft)
          const classes = ['detail-section', open ? 'index-card is-open' : '', ready ? 'is-ready' : ''].filter(Boolean).join(' ')
          return (
            <section key={id} className={classes}>
              <div className="section-row">
                <h2 className="section-heading">
                  <button
                    type="button"
                    className="section-head"
                    aria-expanded={open}
                    onClick={() => edit({ openSection: open ? draft.openSection : id })}
                  >
                    <span className="section-title">{SECTION_TITLES[id]}</span>
                    {open ? null : ready ? (
                      <span className="cap section-done">
                        Ready <span aria-hidden="true">✓</span>
                      </span>
                    ) : (
                      <span className="section-plus" aria-hidden="true">
                        +
                      </span>
                    )}
                  </button>
                </h2>
                {open && id !== 'privacy' ? (
                  <button type="button" className="skip-link section-skip" onClick={() => skip(id)}>
                    {draft.skipped.includes(id) ? 'Section skipped' : 'Skip this section'}
                  </button>
                ) : null}
              </div>
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
                        const field = blankField(active.point, slopeText)
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
            { value: 'metric', label: 'Metric · km' },
            { value: 'imperial', label: 'Imperial · miles' },
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
            maxLength={40}
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
  const [message, setMessage] = useState<string>()
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
        <button type="button" className="field-tab is-add" onClick={onAdd}>
          + Add another field
        </button>
      </div>
      <FieldLabel essential>Location & field boundary</FieldLabel>
      <div className="mode-row" role="radiogroup" aria-label="How to mark the field">
        <button
          type="button"
          className={active.drawMode ? 'pick' : 'pick is-on'}
          aria-pressed={!active.drawMode}
          onClick={() => updateField(active.id, { drawMode: false })}
        >
          Drop a pin
        </button>
        <button
          type="button"
          className={active.drawMode ? 'pick is-on' : 'pick'}
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
              onClick={() => {
                setMessage(undefined)
                updateField(active.id, { polygon: active.polygon.slice(0, -1), boundaryClosed: false, areaHa: null })
              }}
            >
              Undo point
            </button>
            <button
              type="button"
              className="text-action"
              disabled={active.polygon.length < 3}
              onClick={() => {
                const areaHa = polygonAreaHa(active.polygon)
                // Same limit as the locate step: one field, not a whole district.
                if (areaHa > MAX_FIELD_HA) {
                  setMessage(`That outline is about ${Math.round(areaHa).toLocaleString()} ha. Please draw one field (under ${MAX_FIELD_HA.toLocaleString()} ha).`)
                  return
                }
                setMessage(undefined)
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
              onClick={() => {
                setMessage(undefined)
                updateField(active.id, {
                  polygon: [],
                  boundaryClosed: false,
                  areaHa: null,
                  size: active.sizeEdited ? active.size : '',
                })
              }}
            >
              Clear
            </button>
          </>
        ) : null}
      </div>
      {message ? <p className="field-error map-error" role="alert">{message}</p> : null}
      <div className="month-pair">
        <div className="field">
          <FieldLabel essential htmlFor={`field-name-${active.id}`}>
            Field name
          </FieldLabel>
          <input
            id={`field-name-${active.id}`}
            className="control"
            value={active.name}
            maxLength={60}
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
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markerRef = useRef<maplibregl.Marker | null>(null)
  const [loaded, setLoaded] = useState(false)
  const fieldRef = useRef(field)
  const onPointRef = useRef(onPoint)
  const onVertexRef = useRef(onVertex)

  useEffect(() => {
    fieldRef.current = field
    onPointRef.current = onPoint
    onVertexRef.current = onVertex
  })

  useEffect(() => {
    if (!node.current) return
    const start = fieldRef.current.point
    const map = new maplibregl.Map({
      container: node.current,
      style: baseStyle('imagery'),
      center: [start.lng, start.lat],
      zoom: 15,
      maxZoom: 18,
      attributionControl: { compact: true },
    })
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.on('load', () => {
      map.addSource('plot', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      map.addLayer({ id: 'plot-fill', type: 'fill', source: 'plot', filter: ['==', ['geometry-type'], 'Polygon'], paint: { 'fill-color': '#183323', 'fill-opacity': 0.28 } })
      map.addLayer({ id: 'plot-line', type: 'line', source: 'plot', paint: { 'line-color': '#d9a93a', 'line-width': 3 } })
      setLoaded(true)
    })
    map.on('click', (event) => {
      const current = fieldRef.current
      const point = { lat: event.lngLat.lat, lng: event.lngLat.lng }
      if (current.drawMode && !current.boundaryClosed) onVertexRef.current(point)
      else if (!current.drawMode) onPointRef.current(point)
    })
    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
      markerRef.current = null
      setLoaded(false)
    }
  }, [field.id])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !loaded) return
    markerRef.current?.remove()
    markerRef.current = pinMarker(field.point).addTo(map)
    const ring = field.polygon.map((p) => [p.lng, p.lat])
    const features: Feature[] = []
    if (field.boundaryClosed && ring.length >= 3) {
      features.push({ type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [[...ring, ring[0]]] } })
    } else if (ring.length >= 2) {
      features.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: ring } })
    }
    ;(map.getSource('plot') as maplibregl.GeoJSONSource | undefined)?.setData({ type: 'FeatureCollection', features })
  }, [loaded, field.boundaryClosed, field.id, field.point, field.polygon])

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
              maxLength={60}
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
    edit({ goals, goalsTouched: true })
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
      {/* The starting order is only a list: it counts once the farmer reorders or confirms it. */}
      {draft.goalsTouched ? (
        <button type="button" className="text-action" onClick={() => edit({ goalsTouched: false })}>
          Weigh all goals equally instead
        </button>
      ) : (
        <>
          <p className="helper">Not ranked yet: all goals count the same until you reorder or confirm the list.</p>
          <button type="button" className="text-action" onClick={() => edit({ goalsTouched: true })}>
            Use this order
          </button>
        </>
      )}
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
            className={on ? 'pick is-on' : 'pick'}
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
            className={value === option.value ? 'pick is-on' : 'pick'}
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
