import { useEffect, useState } from 'react'
import { languageName } from './reportText'
// The analyzing list styles live in Landing.css (both screens load eagerly).
import './Landing.css'

/** What the analysis reads, in order. A static list: we get no real progress events. */
const READS = [
  { title: 'Weather and 30-year normals', detail: 'NASA POWER' },
  { title: 'Soil moisture', detail: 'NASA SMAP' },
  { title: 'Greenness, water use and heat', detail: 'NASA MODIS' },
  { title: 'Rain and water storage', detail: 'NASA GPM IMERG · GRACE' },
  { title: 'Slope and soil', detail: 'NASA SRTM · ISRIC SoilGrids' },
  { title: 'Comparing your rotation with 3 options', detail: 'Scores weighted by your goal' },
]

export default function Analyzing({ languages }: { languages: string[] }) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const timer = window.setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => window.clearInterval(timer)
  }, [])
  const names = languages.map(languageName).join(' and ')

  return (
    <main className="analyzing" data-testid="analyzing" aria-busy="true">
      <div className="analyzing-card">
        <div className="analyzing-head">
          <p className="cap">Your field · report in {names}</p>
          <span className="spinner" aria-hidden="true" />
        </div>
        <div role="status" aria-live="polite">
          <h1>Reading your field</h1>
          <p>A new field usually takes under 15 seconds.</p>
        </div>
        <ul className="analyzing-steps" aria-label="What we read">
          {READS.map((item) => (
            <li key={item.title}>
              <div>
                <strong>{item.title}</strong>
                <span>{item.detail}</span>
              </div>
            </li>
          ))}
          <li>
            <div>
              <strong>Writing your report</strong>
              <span>In {names}</span>
            </div>
          </li>
        </ul>
        <p className="analyzing-elapsed" aria-hidden="true">
          {seconds}s
        </p>
      </div>
    </main>
  )
}
