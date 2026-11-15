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

// Deep Field crop colors: common crops keep one color everywhere (every strip, the PDF, the deck),
// so a crop never changes color between the overview and an option page.
const KNOWN_CROPS: Record<string, string> = {
  rice: '#4d7a55',
  mungbean: '#c99548',
  sorghum: '#5674a0',
  'sweet potato': '#9b5b4a',
  maize: '#8f8a3e',
  soybean: '#7a6aa0',
  'cereal rye': '#3f7f78',
  peanut: '#8a6440',
  sunflower: '#a35f7a',
  canola: '#b5651d',
}
const PALETTE = ['#4d7a55', '#c99548', '#5674a0', '#9b5b4a', '#7a6aa0', '#8f8a3e', '#3f7f78', '#8a6440']

/** One distinct color per crop, in the order the crops are listed. */
export function cropColors(crops: string[]): Record<string, string> {
  const taken = new Set(crops.map((c) => KNOWN_CROPS[c]).filter(Boolean))
  const free = PALETTE.filter((p) => !taken.has(p))
  let next = 0
  return Object.fromEntries(crops.map((c) => [c, KNOWN_CROPS[c] ?? free[next++ % free.length]]))
}

/** One color per crop across all the strategies, so every strip on a page agrees. */
export function strategyColors(strategies: Strategy[]): Record<string, string> {
  return cropColors([...new Set(strategies.flatMap((s) => s.rotation.flat().map((c) => c.crop)))])
}
