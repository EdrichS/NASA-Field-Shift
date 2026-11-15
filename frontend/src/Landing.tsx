import { useRef, useState } from 'react'
import type { ShowcaseFarm } from './api'
import { NameInput } from './PlotName'
import { bestMatch, type Plot } from './plots'
import './Landing.css'

type LandingProps = {
  farms: ShowcaseFarm[]
  /** False on a static copy with no server (e.g. Cloudflare Pages after the event). */
  live: boolean
  onDemo: (id: string) => void
  onLogin: () => void
  onSignUp: () => void
  onGuest: () => void
  /** Guest analyses kept on this device, newest first. */
  plots: Plot[]
  onOpenPlot: (id: string) => void
  onRenamePlot: (id: string, name: string) => void
  onDeletePlot: (id: string) => void
}

/** The mark under the wordmark: a year of 12 months, green when growing, outlined when bare. */
const YEAR_MARK = [1, 1, 1, 0, 0, 1, 1, 1, 1, 0, 0, 1]

export default function Landing({ farms, live, onDemo, onLogin, onSignUp, onGuest, plots, onOpenPlot, onRenamePlot, onDeletePlot }: LandingProps) {
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

        {plots.length ? (
          <section className="my-plots" aria-labelledby="plots-h">
            <h2 id="plots-h" className="cap">
              Your plots on this device
            </h2>
            <ul className="plot-list">
              {plots.map((plot) => (
                <PlotRow
                  key={plot.id}
                  plot={plot}
                  onOpen={() => onOpenPlot(plot.id)}
                  onRename={(name) => onRenamePlot(plot.id, name)}
                  onDelete={() => onDeletePlot(plot.id)}
                />
              ))}
            </ul>
          </section>
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

function PlotRow({ plot, onOpen, onRename, onDelete }: { plot: Plot; onOpen: () => void; onRename: (name: string) => void; onDelete: () => void }) {
  const [renaming, setRenaming] = useState(false)
  const renameButton = useRef<HTMLButtonElement>(null)
  const top = bestMatch(plot)
  const date = new Date(plot.createdAt).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })

  function remove() {
    if (window.confirm(`Delete "${plot.name}"? This only removes it from this device.`)) onDelete()
  }

  return (
    <li className="index-card plot-row">
      {renaming ? (
        <NameInput
          value={plot.name}
          returnFocus={renameButton}
          onSave={(name) => {
            setRenaming(false)
            onRename(name)
          }}
          onCancel={() => setRenaming(false)}
        />
      ) : (
        <h3>{plot.name}</h3>
      )}
      <p className="plot-meta">
        Analyzed {date}
        {top ? ` · Best match: ${top}` : ''}
      </p>
      {renaming ? null : (
        <div className="plot-actions">
          <button type="button" className="link-button" onClick={onOpen} aria-label={`Open ${plot.name}`}>
            Open
          </button>
          <button ref={renameButton} type="button" className="link-button" onClick={() => setRenaming(true)} aria-label={`Rename ${plot.name}`}>
            Rename
          </button>
          <button type="button" className="link-button danger" onClick={remove} aria-label={`Delete ${plot.name}`}>
            Delete
          </button>
        </div>
      )}
    </li>
  )
}
