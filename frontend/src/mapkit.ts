// Shared MapLibre setup: basemaps, NASA GIBS browse layers, the field pin and field outline.
import * as maplibregl from 'maplibre-gl'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import turfArea from '@turf/area'
import turfCircle from '@turf/circle'
import type { Feature, Geometry, Point, Polygon } from 'geojson'

// MapLibre looks for its worker next to its own module, which breaks once Vite pre-bundles it.
maplibregl.setWorkerUrl(maplibreWorkerUrl)

export { maplibregl }

export type LngLat = { lat: number; lng: number }

/** The backend buffers a point by this much (backend/app/data/geometry.py FIELD_BUFFER_M). */
export const FIELD_BUFFER_M = 250

const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services'

// Layer IDs, tile matrix sets and formats checked against the GIBS WMTS GetCapabilities
// (epsg3857/best) on Nov 15, 2026.
const GIBS = 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best'

export type GibsLayer = {
  id: string
  label: string
  matrix: string
  maxzoom: number
  ext: 'jpeg' | 'png'
  step: 'day' | 'month'
  lagDays: number
  note: string
}

export const GIBS_LAYERS: GibsLayer[] = [
  {
    id: 'MODIS_Terra_CorrectedReflectance_TrueColor',
    label: 'True color (MODIS)',
    matrix: 'GoogleMapsCompatible_Level9',
    maxzoom: 9,
    ext: 'jpeg',
    step: 'day',
    lagDays: 1,
    note: 'NASA MODIS Terra true-color image for the chosen day (250 m).',
  },
  {
    id: 'HLS_S30_Nadir_BRDF_Adjusted_Reflectance',
    label: 'Field detail (HLS 30 m)',
    matrix: 'GoogleMapsCompatible_Level12',
    maxzoom: 12,
    ext: 'png',
    step: 'day',
    lagDays: 10,
    note: 'NASA Harmonized Landsat Sentinel-2, 30 m. Only days with a clear pass show an image.',
  },
  {
    id: 'MODIS_Terra_NDVI_8Day',
    label: 'Greenness (NDVI)',
    matrix: 'GoogleMapsCompatible_Level9',
    maxzoom: 9,
    ext: 'png',
    step: 'day',
    lagDays: 3,
    note: 'NASA MODIS 8-day greenness. Darker green = more growing plants.',
  },
  {
    id: 'SMAP_L4_Analyzed_Root_Zone_Soil_Moisture',
    label: 'Soil moisture (SMAP)',
    matrix: 'GoogleMapsCompatible_Level6',
    maxzoom: 6,
    ext: 'png',
    step: 'day',
    lagDays: 6,
    note: 'NASA SMAP root-zone soil moisture, 9 km. Blue = wetter.',
  },
  {
    id: 'IMERG_Precipitation_Rate',
    label: 'Rain (GPM IMERG)',
    matrix: 'GoogleMapsCompatible_Level6',
    maxzoom: 6,
    ext: 'png',
    step: 'day',
    lagDays: 2,
    note: 'NASA GPM IMERG daily rain rate, about 11 km.',
  },
]

export function isoDay(date: Date) {
  return date.toISOString().slice(0, 10)
}

export function defaultLayerDate(layer: GibsLayer) {
  return isoDay(new Date(Date.now() - layer.lagDays * 86_400_000))
}

export function gibsTiles(layer: GibsLayer, date: string) {
  return `${GIBS}/${layer.id}/default/${date}/${layer.matrix}/{z}/{y}/{x}.${layer.ext}`
}

export type Basemap = 'imagery' | 'streets'

/** A style with Esri imagery and a light street map, plus an empty slot for a NASA layer. */
export function baseStyle(basemap: Basemap): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: {
      imagery: {
        type: 'raster',
        tiles: [`${ESRI}/World_Imagery/MapServer/tile/{z}/{y}/{x}`],
        tileSize: 256,
        maxzoom: 18,
        attribution: 'Imagery © Esri, Maxar, Earthstar Geographics',
      },
      gray: {
        type: 'raster',
        tiles: [`${ESRI}/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}`],
        tileSize: 256,
        maxzoom: 16,
        attribution: 'Tiles © Esri',
      },
      labels: {
        type: 'raster',
        tiles: [`${ESRI}/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}`],
        tileSize: 256,
        maxzoom: 16,
      },
    },
    layers: [
      { id: 'imagery', type: 'raster', source: 'imagery', layout: { visibility: basemap === 'imagery' ? 'visible' : 'none' } },
      { id: 'gray', type: 'raster', source: 'gray', layout: { visibility: basemap === 'streets' ? 'visible' : 'none' } },
      { id: 'labels', type: 'raster', source: 'labels', layout: { visibility: basemap === 'streets' ? 'visible' : 'none' } },
    ],
  }
}

export function setBasemap(map: maplibregl.Map, basemap: Basemap) {
  map.setLayoutProperty('imagery', 'visibility', basemap === 'imagery' ? 'visible' : 'none')
  map.setLayoutProperty('gray', 'visibility', basemap === 'streets' ? 'visible' : 'none')
  map.setLayoutProperty('labels', 'visibility', basemap === 'streets' ? 'visible' : 'none')
}

/** Show one NASA GIBS layer for one date (or none), above the basemap and below the field. */
export function setGibsLayer(map: maplibregl.Map, layer: GibsLayer | null, date: string, opacity = 0.85) {
  if (map.getLayer('gibs')) map.removeLayer('gibs')
  if (map.getSource('gibs')) map.removeSource('gibs')
  if (!layer) return
  map.addSource('gibs', {
    type: 'raster',
    tiles: [gibsTiles(layer, date)],
    tileSize: 256,
    maxzoom: layer.maxzoom,
    attribution: 'NASA GIBS / ESDIS',
  })
  const before = map.getLayer('field-fill') ? 'field-fill' : undefined
  map.addLayer({ id: 'gibs', type: 'raster', source: 'gibs', paint: { 'raster-opacity': opacity } }, before)
}

export const PIN_SVG = `<svg viewBox="0 0 24 36" width="24" height="36" aria-hidden="true"><path fill="#1c3d32" d="M12 35.2S23 21.2 23 12A11 11 0 1 0 1 12c0 9.2 11 23.2 11 23.2z"/><circle cx="12" cy="12" r="4.2" fill="#f7f6f1"/></svg>`

export function pinMarker(at: LngLat) {
  const el = document.createElement('div')
  el.className = 'sow-pin'
  el.innerHTML = PIN_SVG
  return new maplibregl.Marker({ element: el, anchor: 'bottom' }).setLngLat([at.lng, at.lat])
}

export function pointGeometry(at: LngLat): Point {
  return { type: 'Point', coordinates: [round6(at.lng), round6(at.lat)] }
}

function round6(x: number) {
  return Math.round(x * 1e6) / 1e6
}

/** The area the backend analyzes for a point: a circle of FIELD_BUFFER_M. For display only. */
export function bufferCircle(at: LngLat): Feature<Polygon> {
  return turfCircle([at.lng, at.lat], FIELD_BUFFER_M / 1000, { steps: 48, units: 'kilometers' })
}

export function areaHa(geometry: Geometry) {
  return turfArea(geometry) / 10_000
}

export function centerOf(geometry: Geometry): LngLat {
  if (geometry.type === 'Point') return { lng: geometry.coordinates[0], lat: geometry.coordinates[1] }
  if (geometry.type === 'Polygon') {
    const ring = geometry.coordinates[0].slice(0, -1)
    const lng = ring.reduce((s, c) => s + c[0], 0) / ring.length
    const lat = ring.reduce((s, c) => s + c[1], 0) / ring.length
    return { lng, lat }
  }
  return { lng: 0, lat: 0 }
}

/** Draw (or replace) the field outline: the drawn polygon, or the circle around a point. */
export function showField(map: maplibregl.Map, geometry: Geometry | null) {
  const shape: Feature<Polygon> | null = !geometry
    ? null
    : geometry.type === 'Point'
      ? bufferCircle({ lng: geometry.coordinates[0], lat: geometry.coordinates[1] })
      : geometry.type === 'Polygon'
        ? { type: 'Feature', properties: {}, geometry }
        : null
  const data = { type: 'FeatureCollection' as const, features: shape ? [shape] : [] }
  const source = map.getSource('field') as maplibregl.GeoJSONSource | undefined
  if (source) {
    source.setData(data)
    return
  }
  map.addSource('field', { type: 'geojson', data })
  map.addLayer({ id: 'field-fill', type: 'fill', source: 'field', paint: { 'fill-color': '#f2c14e', 'fill-opacity': 0.18 } })
  map.addLayer({ id: 'field-line', type: 'line', source: 'field', paint: { 'line-color': '#f2c14e', 'line-width': 2 } })
}

export function fitField(map: maplibregl.Map, geometry: Geometry, maxZoom = 16) {
  const shape = geometry.type === 'Point' ? bufferCircle(centerOf(geometry)).geometry : geometry
  if (shape.type !== 'Polygon') return
  const lngs = shape.coordinates[0].map((c) => c[0])
  const lats = shape.coordinates[0].map((c) => c[1])
  map.fitBounds(
    [
      [Math.min(...lngs), Math.min(...lats)],
      [Math.max(...lngs), Math.max(...lats)],
    ],
    { padding: 40, maxZoom, duration: 0 },
  )
}

export function formatCoord(at: LngLat) {
  const ns = at.lat >= 0 ? 'N' : 'S'
  const ew = at.lng >= 0 ? 'E' : 'W'
  return `${Math.abs(at.lat).toFixed(2)}° ${ns}, ${Math.abs(at.lng).toFixed(2)}° ${ew}`
}

export function formatArea(ha: number, units: 'metric' | 'imperial') {
  if (units === 'imperial') return `${(ha * 2.47105).toFixed(ha * 2.47105 < 10 ? 1 : 0)} acres`
  return `${ha.toFixed(ha < 10 ? 2 : 1)} ha`
}

/** Start with the compact attribution collapsed to its (i) button, so it doesn't cover small
 *  maps; tapping (i) shows the credits. */
export function collapseAttribution(map: maplibregl.Map) {
  map.once('load', () => {
    map.getContainer().querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show')
  })
}
