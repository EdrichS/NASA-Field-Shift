import { useEffect, useState } from 'react'
import { languageName } from './reportText'

const STAGES = [
  { after: 0, text: 'Reading NASA weather, soil moisture, greenness and rain for your field…' },
  { after: 6, text: 'Finding the months your field is bare and the risky seasons…' },
  { after: 10, text: 'Comparing your rotation with 3 alternatives…' },
  { after: 14, text: 'Writing your plain-language report…' },
]

export default function Analyzing({ languages }: { languages: string[] }) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const timer = window.setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => window.clearInterval(timer)
  }, [])
  const stage = [...STAGES].reverse().find((s) => seconds >= s.after) ?? STAGES[0]

  return (
    <main className="analyzing" data-testid="analyzing" aria-busy="true">
      <div className="analyzing-card" role="status" aria-live="polite">
        <span className="spinner big" aria-hidden="true" />
        <h1>Building your plan</h1>
        <p>{stage.text}</p>
        <p className="helper">
          Report in {languages.map(languageName).join(' and ')} · {seconds}s
        </p>
        <p className="helper">A new place can take up to a minute. Places we have seen before take a few seconds.</p>
      </div>
    </main>
  )
}
