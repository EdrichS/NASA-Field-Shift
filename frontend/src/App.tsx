import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import Landing from './Landing'

// MapLibre looks for its worker next to its own module, which breaks once Vite pre-bundles it.
// Point it at the (self-contained) worker file explicitly; works in dev and in the build.
maplibregl.setWorkerUrl(maplibreWorkerUrl)

// NASA GIBS Blue Marble basemap: no API key needed.
// Layer ID, tile matrix set and format come from the GIBS WMTS GetCapabilities (EPSG:3857, "best").
const GIBS_BLUE_MARBLE =
  'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg'

export default function App() {
  const [entered, setEntered] = useState(false)

  if (!entered) {
    return (
      <Landing
        onLogin={() => {
          // Auth0 sign-in is step 3.4. The button is ready; it does not log anyone in yet.
        }}
        onSignUp={() => {
          // Auth0 sign-up is step 3.4. The button is ready; it does not create an account yet.
        }}
        onGuest={() => setEntered(true)}
      />
    )
  }

  return <MapScreen />
}

function MapScreen() {
  const container = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!container.current) return
    const map = new maplibregl.Map({
      container: container.current,
      style: {
        version: 8,
        sources: {
          gibs: {
            type: 'raster',
            tiles: [GIBS_BLUE_MARBLE],
            tileSize: 256,
            maxzoom: 8,
            attribution: 'Imagery: NASA GIBS / ESDIS',
          },
        },
        layers: [{ id: 'gibs-blue-marble', type: 'raster', source: 'gibs' }],
      },
      center: [0, 20],
      zoom: 1.5,
    })
    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    return () => map.remove()
  }, [])

  return <div ref={container} className="map" data-testid="map" />
}
