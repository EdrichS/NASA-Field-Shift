// Step "Where is your land?": the 4 ways to locate a field (CLAUDE.md section 10).
// Tap a point, use my location, draw the boundary (Terra Draw), or browse NASA GIBS layers.
import { useEffect, useRef, useState } from 'react'
import { TerraDraw, TerraDrawPolygonMode } from 'terra-draw'
import { TerraDrawMapLibreGLAdapter } from 'terra-draw-maplibre-gl-adapter'
import type { Geometry, Polygon } from 'geojson'
import {
  GIBS_LAYERS,
  areaHa,
  baseStyle,
  centerOf,
  defaultLayerDate,
  fitField,
  formatArea,
  maplibregl,
  pinMarker,
  pointGeometry,
  setBasemap,
  setGibsLayer,
  showField,
  type Basemap,
  type LngLat,
} from './mapkit'

export type LocateMode = 'point' | 'locate' | 'draw' | 'browse'

const MAX_FIELD_HA = 2000

const MODES: { id: LocateMode; label: string; hint: string }[] = [
  { id: 'point', label: 'Tap a point', hint: 'Tap your field on the map. We study a circle about 250 m around it.' },
  { id: 'locate', label: 'Use my location', hint: 'Stand in your field and allow location access.' },
  { id: 'draw', label: 'Draw the field', hint: 'Tap each corner of your field. Tap the first corner again to close it.' },
  { id: 'browse', label: 'Browse NASA maps', hint: 'Look at NASA satellite layers for any day, then tap a spot.' },
]

export default function LocateMap({
  geometry,
  onGeometry,
  units,
}: {
  geometry: Geometry | null
  onGeometry: (geometry: Geometry | null) => void
  units: 'metric' | 'imperial'
}) {
  const node = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const drawRef = useRef<TerraDraw | null>(null)
  const markerRef = useRef<maplibregl.Marker | null>(null)
  const modeRef = useRef<LocateMode>('point')
  const geometryRef = useRef<Geometry | null>(geometry)
  const [mode, setMode] = useState<LocateMode>('point')
  const [basemap, setBase] = useState<Basemap>('streets')
  const [layerId, setLayerId] = useState(GIBS_LAYERS[0].id)
  const [date, setDate] = useState(defaultLayerDate(GIBS_LAYERS[0]))
  const [message, setMessage] = useState<string>()
  const [busy, setBusy] = useState(false)
  const [ready, setReady] = useState(false)
  const layer = GIBS_LAYERS.find((l) => l.id === layerId) ?? GIBS_LAYERS[0]

  geometryRef.current = geometry

  function place(next: Geometry | null) {
    const map = mapRef.current
    geometryRef.current = next
    onGeometry(next)
    if (!map) return
    showField(map, next)
    markerRef.current?.remove()
    markerRef.current = null
    if (next) markerRef.current = pinMarker(centerOf(next)).addTo(map)
  }

  useEffect(() => {
    if (!node.current) return
    const start = geometryRef.current
    const map = new maplibregl.Map({
      container: node.current,
      style: baseStyle('streets'),
      center: start ? [centerOf(start).lng, centerOf(start).lat] : [10, 20],
      zoom: start ? 14 : 1.4,
      attributionControl: { compact: true },
    })
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    mapRef.current = map
    if (import.meta.env.DEV) {
      // Dev-only test hook: drop a pin at exact coordinates from the browser console.
      ;(window as unknown as { __sowMap?: maplibregl.Map }).__sowMap = map
      ;(window as unknown as { __sowLocate?: (lat: number, lng: number) => void }).__sowLocate = (lat, lng) => {
        place(pointGeometry({ lat, lng }))
        map.jumpTo({ center: [lng, lat], zoom: 15 })
      }
    }

    map.on('load', () => {
      const draw = new TerraDraw({
        adapter: new TerraDrawMapLibreGLAdapter({ map }),
        modes: [
          new TerraDrawPolygonMode({
            styles: {
              fillColor: '#f2c14e',
              fillOpacity: 0.25,
              outlineColor: '#f2c14e',
              outlineWidth: 2,
              closingPointColor: '#1c3d32',
              closingPointWidth: 6,
              closingPointOutlineColor: '#ffffff',
              closingPointOutlineWidth: 2,
            },
          }),
        ],
      })
      draw.start()
      draw.on('finish', (id) => {
        const feature = draw.getSnapshotFeature(id)
        draw.clear()
        if (!feature || feature.geometry.type !== 'Polygon') return
        const polygon = feature.geometry as Polygon
        const ha = areaHa(polygon)
        if (ha > MAX_FIELD_HA) {
          setMessage(`That outline is about ${Math.round(ha).toLocaleString()} ha. Please draw one field (under ${MAX_FIELD_HA.toLocaleString()} ha).`)
          return
        }
        setMessage(undefined)
        place(polygon)
        fitField(map, polygon)
      })
      drawRef.current = draw
      if (start) {
        showField(map, start)
        markerRef.current = pinMarker(centerOf(start)).addTo(map)
      }
      setReady(true)
    })

    map.on('click', (event) => {
      if (modeRef.current === 'draw') return
      setMessage(undefined)
      place(pointGeometry({ lat: event.lngLat.lat, lng: event.lngLat.lng }))
    })

    return () => {
      drawRef.current?.stop()
      drawRef.current = null
      map.remove()
      mapRef.current = null
      markerRef.current = null
    }
    // The map is created once; place() reads the latest props through refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Draw mode on/off.
  useEffect(() => {
    modeRef.current = mode
    const draw = drawRef.current
    if (!draw || !ready) return
    if (mode === 'draw') {
      draw.setMode('polygon')
      if (basemap === 'streets') changeBasemap('imagery')
    } else {
      draw.setMode('static')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, ready])

  // NASA layer for browse mode.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready) return
    setGibsLayer(map, mode === 'browse' ? layer : null, date)
    if (mode === 'browse' && map.getZoom() > layer.maxzoom + 2) map.setZoom(layer.maxzoom + 1)
  }, [mode, layer, date, ready])

  function changeBasemap(next: Basemap) {
    setBase(next)
    if (mapRef.current && ready) setBasemap(mapRef.current, next)
  }

  function chooseMode(next: LocateMode) {
    setMessage(undefined)
    setMode(next)
    if (next === 'locate') locateMe()
  }

  function locateMe() {
    if (!navigator.geolocation) {
      setMessage('Location is not available on this device. Tap the map instead.')
      setMode('point')
      return
    }
    setBusy(true)
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setBusy(false)
        const at: LngLat = { lat: position.coords.latitude, lng: position.coords.longitude }
        const point = pointGeometry(at)
        place(point)
        mapRef.current?.flyTo({ center: [at.lng, at.lat], zoom: 15, duration: 900 })
        changeBasemap('imagery')
        setMode('point')
      },
      () => {
        setBusy(false)
        setMessage('We could not read your location. Tap the map instead.')
        setMode('point')
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    )
  }

  const hint = MODES.find((m) => m.id === mode)?.hint
  const ha = geometry ? (geometry.type === 'Polygon' ? areaHa(geometry) : null) : null

  return (
    <div className="locate-tool">
      <div className="mode-tabs" role="tablist" aria-label="How to find your land">
        {MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            role="tab"
            aria-selected={mode === m.id}
            className={mode === m.id ? 'mode-tab is-on' : 'mode-tab'}
            onClick={() => chooseMode(m.id)}
            disabled={busy && m.id === 'locate'}
          >
            {m.id === 'locate' && busy ? 'Finding…' : m.label}
          </button>
        ))}
      </div>
      <p className="mode-hint">{hint}</p>

      {mode === 'browse' ? (
        <div className="browse-bar">
          <label>
            <span>NASA layer</span>
            <select className="control" value={layerId} onChange={(e) => {
              const next = GIBS_LAYERS.find((l) => l.id === e.target.value) ?? GIBS_LAYERS[0]
              setLayerId(next.id)
              setDate(defaultLayerDate(next))
            }}>
              {GIBS_LAYERS.map((l) => (
                <option key={l.id} value={l.id}>{l.label}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Date</span>
            <input
              className="control"
              type="date"
              value={date}
              min="2015-04-01"
              max={defaultLayerDate({ ...layer, lagDays: 0 })}
              onChange={(e) => e.target.value && setDate(e.target.value)}
            />
          </label>
          <p className="browse-note">{layer.note}</p>
        </div>
      ) : null}

      <div className="map-frame locate-frame">
        <div ref={node} className="locate-map" role="application" aria-label="Map. Tap to choose your field." />
        <div className="base-toggle" role="group" aria-label="Base map">
          <button type="button" className={basemap === 'streets' ? 'is-on' : ''} onClick={() => changeBasemap('streets')}>Map</button>
          <button type="button" className={basemap === 'imagery' ? 'is-on' : ''} onClick={() => changeBasemap('imagery')}>Satellite</button>
        </div>
      </div>

      {message ? <p className="field-error map-error" role="alert">{message}</p> : null}
      {geometry ? (
        <p className="pin-coords">
          {geometry.type === 'Polygon'
            ? `Field outline: about ${formatArea(ha ?? 0, units)}`
            : `Point ${centerLabel(geometry)} · we look at a circle about ${units === 'imperial' ? '820 ft' : '250 m'} around it`}
          {' · '}
          <button type="button" className="link-button" onClick={() => place(null)}>Clear</button>
        </p>
      ) : null}
    </div>
  )
}

function centerLabel(geometry: Geometry) {
  const c = centerOf(geometry)
  return `${Math.abs(c.lat).toFixed(4)}° ${c.lat >= 0 ? 'N' : 'S'}, ${Math.abs(c.lng).toFixed(4)}° ${c.lng >= 0 ? 'E' : 'W'}`
}
