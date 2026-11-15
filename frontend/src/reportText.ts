// Shared labels and text helpers for the results screen, calendar and printable report.
import type { Strategy, StrategyText } from './api'
import { LANGUAGES } from './i18n'

export const COMPONENT_LABELS: Record<string, { label: string; plain: string }> = {
  water: { label: 'Water', plain: 'How much water the crops need beyond rain' },
  soil: { label: 'Soil building', plain: 'Nitrogen from legumes, root depth and how long the soil is covered' },
  erosion: { label: 'Erosion protection', plain: 'Slope × months the soil is bare' },
  pest_cycle: { label: 'Pest-cycle break', plain: 'Changing plant family so pests lose their host' },
  climate_risk: { label: 'Weather risk', plain: 'Frost, heat, dry spells or very wet months during the crops' },
  income: { label: 'Income fit', plain: 'Harvests to sell or eat, and fit with your market' },
  labor: { label: 'Labor fit', plain: 'Work needed compared with your equipment' },
}

export function languageName(code: string) {
  return LANGUAGES.find((l) => l.value === code)?.label ?? code
}

export function stripScore(text: string) {
  return text.replace(/\s*\([+-]\d+(\.\d+)?\)\s*$/, '')
}

export function expertQuestions(ranked: Strategy[], textFor: (s: Strategy) => StrategyText | undefined) {
  const out: string[] = []
  for (const s of ranked) {
    for (const q of textFor(s)?.expert_questions ?? s.expert_questions) if (!out.includes(q)) out.push(q)
  }
  return out.slice(0, 10)
}

export const BASE_GLOSSARY: { term: string; meaning: string }[] = [
  { term: 'Evapotranspiration', meaning: 'Water that leaves the field through plant leaves and from the soil surface.' },
  { term: 'NDVI', meaning: 'A satellite number for how green and leafy the plants are. Low values mean bare or dry land.' },
  { term: 'Soil moisture anomaly', meaning: 'How much wetter or drier the soil is than normal for that month.' },
  { term: 'Frost risk', meaning: 'The chance that nights get cold enough (0 °C or below) to damage crops.' },
  { term: 'Legume', meaning: 'Plants of the bean family (beans, peas, mungbean, cowpea) that add nitrogen to the soil.' },
  { term: 'Cover crop', meaning: 'A crop grown to protect and feed the soil between main crops, not mainly to harvest.' },
]

export const STRESS_LABELS: Record<string, { label: string; icon: string; plain: string }> = {
  heat: { label: 'Heat', icon: 'H', plain: 'Hot spells often reach 35 °C or more' },
  dry: { label: 'Dry', icon: 'D', plain: 'Little rain falls' },
  frost: { label: 'Frost', icon: 'F', plain: 'Nights can freeze (0 °C or below)' },
  very_wet: { label: 'Very wet', icon: 'W', plain: 'Very heavy rain: flooding or waterlogging risk' },
}

const PALETTE = ['#4d7a5e', '#c9893b', '#5b84b1', '#a65d57', '#8a7bb0', '#b3a247', '#3f8f8a', '#9a6b43']

/** One distinct color per crop, in the order the crops are listed. */
export function cropColors(crops: string[]): Record<string, string> {
  return Object.fromEntries(crops.map((c, i) => [c, PALETTE[i % PALETTE.length]]))
}
