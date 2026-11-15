import type { ShowcaseFarm } from './api'
import './Landing.css'

type LandingProps = {
  farms: ShowcaseFarm[]
  /** False on a static copy with no server (e.g. Cloudflare Pages after the event). */
  live: boolean
  onDemo: (id: string) => void
  onLogin: () => void
  onSignUp: () => void
  onGuest: () => void
}

export default function Landing({ farms, live, onDemo, onLogin, onSignUp, onGuest }: LandingProps) {
  return (
    <main className="landing" data-testid="landing">
      <div className="landing-cluster">
        <h1 className="brand">
          <Sprout />
          <span>Sow Smart</span>
        </h1>
        <p className="tagline">Compare crop rotations for your field with NASA satellite data.</p>

        {!live ? (
          <p className="notice">
            This copy of SowSmart shows the demo farms. Live analysis, sign-in and alerts run on the team's server during the
            event.
          </p>
        ) : null}

        {live ? (
        <>
        <div className="actions">
          <button type="button" className="pill pill-login" onClick={onLogin}>
            Login
          </button>
          <button type="button" className="pill pill-signup" onClick={onSignUp}>
            Sign Up
          </button>
        </div>

        <p className="or">
          <span>or</span>
        </p>

        <button type="button" className="guest" onClick={onGuest}>
          <span className="guest-label">Continue as Guest</span>
          <svg className="guest-arrow" viewBox="0 0 16 16" aria-hidden="true">
            <path
              d="M3 8h10M9 4l4 4-4 4"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        </>
        ) : null}

        {farms.length ? (
          <section className="demo-farms" aria-labelledby="demo-h">
            <h2 id="demo-h">Try a demo farm</h2>
            {farms.map((farm) => (
              <button key={farm.id} type="button" className="demo-farm" onClick={() => onDemo(farm.id)}>
                <strong>{farm.name}</strong>
                <span>{farm.place}, {farm.country}</span>
                <span className="demo-story">{farm.persona}</span>
              </button>
            ))}
          </section>
        ) : null}

        <p className="landing-note">
          SowSmart supports your judgment and local expertise. It never replaces them.
        </p>
      </div>
    </main>
  )
}

function Sprout() {
  return (
    <svg className="sprout" viewBox="0 0 36 36" aria-hidden="true">
      <path
        d="M18 33.5V18.2"
        fill="none"
        stroke="#1c3d32"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <path
        d="M17.6 22.8c-1.4-4.2-5.2-7.3-10.4-8.2 2.2 4.6 6 7.4 10.4 8.2z"
        fill="#4d7a5e"
      />
      <path
        d="M18.3 16.6c2.2-5.6 7.4-9.4 13.2-9.8-2.4 5.6-7.6 9.4-13.2 9.8z"
        fill="#1c3d32"
      />
    </svg>
  )
}
