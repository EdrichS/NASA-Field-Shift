// Turn the form drafts (Quick 5, Detailed) into the backend's Answers shape.
import type { Answers, Goal } from './api'
import type { DetailedDraft } from './DetailedSetup'
import type { CardAnswers } from './SatelliteCards'
import type { QuickAnswers } from './SignUp'

const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

export function monthNumber(value: string): number | null {
  const key = value.trim().slice(0, 3).toLowerCase()
  const i = MONTHS.indexOf(key)
  if (i >= 0) return i + 1
  const n = Number(value)
  return Number.isInteger(n) && n >= 1 && n <= 12 ? n : null
}

// The engine knows 5 goals (backend/app/engine/answers.py). Detailed mode offers 9, so each extra
// goal maps to the engine goal that scores what it asks for.
const GOAL_MAP: Record<string, Goal> = {
  'save water': 'save_water',
  water: 'save_water',
  'build soil': 'build_soil',
  soil: 'build_soil',
  'reduce erosion': 'build_soil',
  'cut fertilizer costs': 'build_soil',
  'earn more': 'earn_more',
  earn: 'earn_more',
  'less labor': 'earn_more',
  'feed the household': 'feed_household',
  feed: 'feed_household',
  'feed livestock': 'feed_household',
  'survive bad years': 'survive_bad_years',
  survive: 'survive_bad_years',
}

function goal(label: string): Goal | null {
  return GOAL_MAP[label.trim().toLowerCase()] ?? null
}

const WATER: Record<string, Answers['water']> = {
  irrigated: 'irrigated',
  rainfed: 'rainfed',
  'rain-fed': 'rainfed',
  mixed: 'mixed',
  'some of each': 'mixed',
  unknown: 'unknown',
  "i don't know": 'unknown',
}

const EQUIPMENT: Record<string, Answers['equipment']> = {
  hand: 'hand_tools',
  'hand tools': 'hand_tools',
  animal: 'animal',
  'animal-drawn': 'animal',
  'small-tractor': 'small_tractor',
  'small tractor': 'small_tractor',
  full: 'full_machinery',
  'full machinery': 'full_machinery',
}

// The same planting and harvest month is a 12-month crop (cassava, sugarcane), so it is kept.
function crops(rows: { crop: string; planting: string; harvest: string }[]) {
  return rows
    .map((r) => ({ crop: r.crop.trim(), plant_month: monthNumber(r.planting), harvest_month: monthNumber(r.harvest) }))
    .filter((r): r is { crop: string; plant_month: number; harvest_month: number } =>
      !!r.crop && r.plant_month !== null && r.harvest_month !== null)
    .slice(0, 6)
}

function corrections(cards: CardAnswers) {
  return Object.fromEntries(Object.entries(cards).map(([id, a]) => [id, a.value === undefined ? { status: a.status } : a]))
}

export function emptyAnswers(cards: CardAnswers = {}): Answers {
  return {
    current_crops: [],
    not_farming: false,
    water: null,
    equipment: null,
    top_goal: null,
    ranked_goals: [],
    wont_grow: [],
    sellable_crops: [],
    confirmed_prefill: corrections(cards),
  }
}

export function fromQuick(quick: QuickAnswers, cards: CardAnswers): Answers {
  const top = goal(quick.goal)
  return {
    ...emptyAnswers(cards),
    not_farming: quick.notFarming,
    current_crops: quick.notFarming ? [] : crops(quick.crops),
    water: WATER[quick.water.toLowerCase()] ?? null,
    equipment: EQUIPMENT[quick.equipment.toLowerCase()] ?? null,
    top_goal: top,
    ranked_goals: top ? [top] : [],
    wont_grow: quick.avoided.slice(0, 30),
  }
}

export function fromDetailed(d: DetailedDraft, cards: CardAnswers): Answers {
  // The starting goal order is not an answer: until the farmer reorders or confirms it, no
  // ranking is sent and the engine weighs all goals equally (like Quick 5's "Not sure").
  const ranked: Goal[] = []
  for (const label of d.goalsTouched ? d.goals : []) {
    const g = goal(label)
    if (g && !ranked.includes(g)) ranked.push(g)
    if (ranked.length === 3) break
  }
  const field = d.fields.find((f) => f.id === d.activeField) ?? d.fields[0]
  return {
    ...emptyAnswers(cards),
    current_crops: crops(d.rotation),
    water: WATER[d.waterType.toLowerCase()] ?? null,
    equipment: EQUIPMENT[d.equipment.toLowerCase()] ?? null,
    top_goal: ranked[0] ?? null,
    ranked_goals: ranked,
    wont_grow: d.wontGrow.slice(0, 30),
    sellable_crops: d.sellCrops.slice(0, 30),
    // Detailed sections the engine does not score yet are kept with the analysis (and shown
    // as information the farmer gave), never sent to the AI as raw text.
    detailed: {
      empty_months: d.emptyMonths,
      tillage: d.tillage,
      residue: d.leftovers,
      cover_crops: d.coverCrops,
      livestock: d.livestock,
      irrigation_method: d.irrigation,
      water_source: d.waterSource,
      water_reliability: d.reliability,
      drainage: d.drainage,
      soil_problems: d.soilProblems,
      soil_feel: d.soilFeel,
      soil_test: d.ph || d.organic ? { ph: d.ph, organic_matter_pct: d.organic, n: d.n, p: d.p, k: d.k, year: d.testYear } : null,
      budget: d.budget,
      labor: d.labor,
      seed_access: d.seedAccess,
      fertilizer_access: d.fertilizerAccess,
      market_distance: d.marketDistance,
      eaten_share_pct: d.eatenShare,
      pests: d.pests,
      recent_events: d.events,
      risk_share: d.risk === 'custom' ? d.riskCustom : d.risk,
      time_frame: d.timeFrame,
      field_slope: field?.slopeEdited ? field.slope : null,
    },
  }
}
