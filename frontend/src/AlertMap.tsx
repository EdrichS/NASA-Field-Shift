// A small map for one alert: the field pin and the event (storm track, event point or fires).
import { useEffect, useRef } from 'react'
import type { Feature } from 'geojson'
import type { Alert } from './api'
import { baseStyle, collapseAttribution, maplibregl, pinMarker } from './mapkit'

export default function AlertMap({ alert }: { alert: Alert }) {
  const node = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!node.current) return
    const map = new maplibregl.Map({
      container: node.current,
      style: baseStyle('streets'),
      center: [alert.lon, alert.lat],
      zoom: 8,
      attributionControl: { compact: true },
    })
    collapseAttribution(map)
    pinMarker({ lat: alert.lat, lng: alert.lon }).addTo(map)
    map.on('load', () => {
      const features: Feature[] = []
      const g = alert.data.event_geometry
      if (g && g.type === 'MultiPoint') {
        features.push({ type: 'Feature', properties: { kind: 'track' }, geometry: { type: 'LineString', coordinates: g.coordinates } })
        g.coordinates.forEach((c) => features.push({ type: 'Feature', properties: { kind: 'point' }, geometry: { type: 'Point', coordinates: c } }))
      } else if (g) {
        features.push({ type: 'Feature', properties: { kind: 'point' }, geometry: g })
      }
      for (const p of alert.data.points ?? []) {
        features.push({ type: 'Feature', properties: { kind: 'point' }, geometry: { type: 'Point', coordinates: p } })
      }
      map.addSource('event', { type: 'geojson', data: { type: 'FeatureCollection', features } })
      map.addLayer({ id: 'event-line', type: 'line', source: 'event', filter: ['==', ['get', 'kind'], 'track'], paint: { 'line-color': '#a4442a', 'line-width': 2.5, 'line-dasharray': [2, 1] } })
      map.addLayer({ id: 'event-points', type: 'circle', source: 'event', filter: ['==', ['get', 'kind'], 'point'], paint: { 'circle-radius': 6, 'circle-color': '#a4442a', 'circle-stroke-color': '#fff', 'circle-stroke-width': 1.5 } })
      const coords: [number, number][] = [[alert.lon, alert.lat]]
      for (const f of features) {
        if (f.geometry.type === 'Point') coords.push(f.geometry.coordinates as [number, number])
      }
      if (coords.length > 1) {
        const lons = coords.map((c) => c[0])
        const lats = coords.map((c) => c[1])
        map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: 36, maxZoom: 11, duration: 0 })
      }
    })
    return () => map.remove()
  }, [alert])

  return (
    <article className="home-card alert-map-card">
      <div ref={node} className="alert-map" role="img" aria-label={`Map of the alert near ${alert.field_name}`} />
      <p className="helper">Pin: your field. Red: the event{alert.data.event_geometry?.type === 'MultiPoint' ? ' and its track' : ''}.</p>
    </article>
  )
}
