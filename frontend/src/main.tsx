import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'maplibre-gl/dist/maplibre-gl.css'
import './index.css'
import './app.css'
import App from './App.tsx'
import { SessionProvider } from './session'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SessionProvider onReturn={() => undefined}>
      <App />
    </SessionProvider>
  </StrictMode>,
)
