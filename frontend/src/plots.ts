// Guest plots: finished analyses kept on this device (localStorage), newest first, so a guest
// can reopen, rename or delete them from the start screen. Signed-in users keep theirs on the
// server instead. Every read and write is guarded: blocked storage just means no list.
import type { AnalyzeRequest, AnalyzeResponse } from './api'

export type Plot = {
  id: string
  name: string
  createdAt: string
  updatedAt: string
  request: AnalyzeRequest
  analysis: AnalyzeResponse
}

const KEY = 'sowsmart.plots.v1'
/** An analysis is ~90 KB of JSON, so only the newest few fit next to everything else. */
const MAX_PLOTS = 15

function isPlot(value: unknown): value is Plot {
  const p = value as Plot | null
  return (
    !!p &&
    typeof p.id === 'string' &&
    typeof p.name === 'string' &&
    !Number.isNaN(Date.parse(p.createdAt)) &&
    !!p.request?.geometry &&
    Array.isArray(p.analysis?.strategies)
  )
}

function isQuotaError(e: unknown) {
  return e instanceof DOMException && (e.name === 'QuotaExceededError' || e.name === 'NS_ERROR_DOM_QUOTA_REACHED')
}

function read(): Plot[] {
  try {
    const list: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    return Array.isArray(list) ? list.filter(isPlot) : []
  } catch {
    return []
  }
}

/** Stores the list, dropping the oldest plots while the browser says it is full.
 *  Returns what was kept, or null when nothing could be written. */
function write(list: Plot[]): Plot[] | null {
  let kept = list.slice(0, MAX_PLOTS)
  for (;;) {
    try {
      localStorage.setItem(KEY, JSON.stringify(kept))
      return kept
    } catch (e) {
      if (!isQuotaError(e) || kept.length <= 1) return null
      kept = kept.slice(0, -1)
    }
  }
}

export function listPlots(): Plot[] {
  return read()
}

export function getPlot(id: string): Plot | undefined {
  return read().find((p) => p.id === id)
}

/** Keeps a finished analysis. Returns null when this browser can't store it. */
export function addPlot(request: AnalyzeRequest, analysis: AnalyzeResponse, name: string): Plot | null {
  const now = new Date().toISOString()
  const id = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
  const plot: Plot = { id, name, createdAt: now, updatedAt: now, request, analysis }
  return write([plot, ...read()]) ? plot : null
}

/** Each change returns the list as stored afterwards. */
export function renamePlot(id: string, name: string): Plot[] {
  const now = new Date().toISOString()
  return write(read().map((p) => (p.id === id ? { ...p, name, updatedAt: now } : p))) ?? read()
}

export function removePlot(id: string): Plot[] {
  return write(read().filter((p) => p.id !== id)) ?? read()
}

/** "Plot near 7.49° N, 125.75° E", from the field's center point. */
export function defaultPlotName(analysis: AnalyzeResponse) {
  const lat = analysis.field?.lat
  const lon = analysis.field?.lon
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return 'My plot'
  return `Plot near ${Math.abs(lat).toFixed(2)}° ${lat < 0 ? 'S' : 'N'}, ${Math.abs(lon).toFixed(2)}° ${lon < 0 ? 'W' : 'E'}`
}

/** The name of the option ranked first, e.g. "Fill the bare gap". */
export function bestMatch(plot: Plot) {
  return [...plot.analysis.strategies].sort((a, b) => a.rank - b.rank)[0]?.name
}
