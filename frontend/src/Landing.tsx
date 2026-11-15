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

/** The mark under the wordmark: a year of 12 months, green when growing, outlined when bare. */
const YEAR_MARK = [1, 1, 1, 0, 0, 1, 1, 1, 1, 0, 0, 1]

export default function Landing({ farms, live, onDemo, onLogin, onSignUp, onGuest }: LandingProps) {
  return (
    <main className="landing" data-testid="landing">
      <div className="landing-cluster">
        <div className="brand">
          <p className="brand-name">SowSmart</p>
          <span className="brand-mark" aria-hidden="true">
            {YEAR_MARK.map((on, i) => (
              <i key={i} className={on ? 'is-on' : undefined} />
            ))}
          </span>
        </div>

        <div className="landing-intro">
          <h1>Compare crop rotations for your field</h1>
          <p className="tagline">Using NASA satellite data, your answers and your goals.</p>
        </div>

        {!live ? (
          <p className="notice">
            This copy of SowSmart shows the demo farms. Live analysis, sign-in and alerts run on the team's server during the
            event.
          </p>
        ) : null}

        {live ? (
          <div className="landing-actions">
            <button type="button" className="tag-btn is-block" onClick={onGuest}>
              Continue as guest
            </button>
            <p className="landing-account cap">To save your plans</p>
            <div className="landing-auth">
              <button type="button" className="tag-btn is-quiet" onClick={onLogin}>
                Log in
              </button>
              <button type="button" className="tag-btn is-quiet" onClick={onSignUp}>
                Sign up
              </button>
            </div>
          </div>
        ) : null}

        {farms.length ? (
          <section className="demo-farms" aria-labelledby="demo-h">
            <h2 id="demo-h">{live ? 'Or open a demo farm' : 'Open a demo farm'}</h2>
            {farms.map((farm) => (
              <button key={farm.id} type="button" className="demo-farm" onClick={() => onDemo(farm.id)}>
                <strong>{farm.name}</strong>
                <span>
                  {farm.place}, {farm.country}
                </span>
                <span className="demo-story">{farm.persona}</span>
              </button>
            ))}
          </section>
        ) : null}

        <p className="landing-note">SowSmart supports your judgment and local expertise. It never replaces them.</p>
      </div>
    </main>
  )
}
