import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import Dashboard from './Dashboard'
import Landing from './Landing'
import SignUp, { type SignUpAccount } from './SignUp'
import type { LanguageCode } from './i18n'

// MapLibre looks for its worker next to its own module, which breaks once Vite pre-bundles it.
// Point it at the (self-contained) worker file explicitly; works in dev and in the build.
maplibregl.setWorkerUrl(maplibreWorkerUrl)

// NASA GIBS Blue Marble basemap: no API key needed.
// Layer ID, tile matrix set and format come from the GIBS WMTS GetCapabilities (EPSG:3857, "best").
const GIBS_BLUE_MARBLE =
  'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg'

export default function App() {
  const [screen, setScreen] = useState<'landing' | 'signup' | 'dashboard' | 'map'>('landing')
  const [place, setPlace] = useState<[number, number] | null>(null)
  const [account, setAccount] = useState<SignUpAccount | null>(null)
  const [language, setLanguage] = useState<LanguageCode>('en')

  if (screen === 'signup') {
    return (
      <SignUp
        onBack={() => setScreen('landing')}
        onLogin={() => setScreen('landing')}
        onCreate={(next) => {
          // The account stays in the browser. Auth0, saving, and the farm plan come later.
          setAccount(next)
          setLanguage(next.language)
          setPlace([next.longitude, next.latitude])
          setScreen('dashboard')
        }}
      />
    )
  }

  if (screen === 'dashboard' && account) {
    return (
      <Dashboard
        language={language}
        username={account.username}
        latitude={account.latitude}
        longitude={account.longitude}
        path={account.questions}
        onLanguage={setLanguage}
      />
    )
  }

  if (screen === 'landing') {
    return (
      <Landing
        onLogin={() => {
          // Auth0 sign-in is step 3.4. The button is ready; it does not log anyone in yet.
        }}
        onSignUp={() => setScreen('signup')}
        onGuest={() => {
          setPlace(null)
          setScreen('map')
        }}
      />
    )
  }

  return <MapScreen center={place} />
}

function MapScreen({ center }: { center: [number, number] | null }) {
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
      center: center ?? [0, 20],
      zoom: center ? 8 : 1.5,
    })
    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    if (center) new maplibregl.Marker({ color: '#1c3d32' }).setLngLat(center).addTo(map)
    return () => map.remove()
  }, [center])

  return <div ref={container} className="map" data-testid="map" />
}
