// A plot's name with a Rename link (Results header), and the box that renames it (also used on
// the start screen's plot list): Enter or leaving the box saves, Escape cancels.
import { useEffect, useRef, useState, type RefObject } from 'react'

export function NameInput({
  value,
  onSave,
  onCancel,
  returnFocus,
}: {
  value: string
  onSave: (name: string) => void
  onCancel: () => void
  /** Where the keyboard focus goes back to after Enter or Escape (the Rename link). */
  returnFocus?: RefObject<HTMLElement | null>
}) {
  const [text, setText] = useState(value)
  const input = useRef<HTMLInputElement>(null)
  const done = useRef(false)

  useEffect(() => {
    input.current?.focus()
    input.current?.select()
  }, [])

  function finish(save: boolean, byKey: boolean) {
    if (done.current) return
    done.current = true
    const name = text.trim()
    if (save && name && name !== value) onSave(name)
    else onCancel()
    if (byKey) requestAnimationFrame(() => returnFocus?.current?.focus())
  }

  return (
    <label className="name-edit">
      <span className="cap">Plot name</span>
      <input
        ref={input}
        value={text}
        maxLength={60}
        enterKeyHint="done"
        autoComplete="off"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key !== 'Enter' && e.key !== 'Escape') return
          e.preventDefault()
          finish(e.key === 'Enter', true)
        }}
        onBlur={() => finish(true, false)}
      />
    </label>
  )
}

export default function PlotName({ name, onRename }: { name: string; onRename?: (name: string) => void }) {
  const [editing, setEditing] = useState(false)
  const renameButton = useRef<HTMLButtonElement>(null)

  if (editing && onRename) {
    return (
      <NameInput
        value={name}
        returnFocus={renameButton}
        onSave={(next) => {
          setEditing(false)
          onRename(next)
        }}
        onCancel={() => setEditing(false)}
      />
    )
  }
  return (
    <p className="plot-name">
      <strong>{name}</strong>
      {onRename ? (
        <button ref={renameButton} type="button" className="link-button" onClick={() => setEditing(true)} aria-label={`Rename ${name}`}>
          Rename
        </button>
      ) : null}
    </p>
  )
}
