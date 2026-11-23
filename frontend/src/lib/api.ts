/** Typed client for the Revalo API. All calls go through the /api dev proxy. */

import { getLocale, t } from './i18n'

const BASE = import.meta.env.VITE_API_URL ?? '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, { credentials: 'include', ...init, headers: { 'Accept-Language': getLocale(), ...init?.headers } })
  } catch {
    throw new ApiError(0, t('The Revalo server cannot be reached.'))
  }
  if (!response.ok) {
    let message = response.statusText
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join('; ')
    } catch {
      /* keep status text */
    }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export interface Health {
  status: string
  version: string
}

export const getHealth = () => request<Health>('/health')

/* ---------- Materials ---------- */

export type MaterialFamily = 'metal' | 'wood' | 'plastic'

export interface MaterialInfo {
  code: string
  name: { en: string; fr: string }
  family: MaterialFamily
  density_kg_m3: number
}

export interface ProcessInfo {
  code: string
  kerf_mm: number
  families: MaterialFamily[]
}

export const getMaterials = () =>
  request<{ materials: MaterialInfo[]; processes: ProcessInfo[] }>('/v1/materials')

/* ---------- Samples ---------- */

export interface Sample {
  id: string
  name: string
  collection: 'synthetic' | 'public'
  title: string
  process: string | null
  licence: string | null
  source: string | null
  size: number
}

export const getSamples = () => request<{ samples: Sample[] }>('/v1/samples')

export async function fetchSampleFile(sample: Sample): Promise<File> {
  const response = await fetch(`${BASE}/v1/samples/${encodeURIComponent(sample.id)}`)
  if (!response.ok) throw new ApiError(response.status, 'Sample not found.')
  return new File([await response.blob()], sample.name)
}

/* ---------- Analysis ---------- */

export interface PolygonJson {
  exterior: [number, number][]
  holes: [number, number][][]
}

export interface Remnant {
  id: string
  x: number
  y: number
  width: number
  height: number
  area_m2: number
  weight_kg: number | null
}

export interface SheetAnalysis {
  index: number
  width: number
  height: number
  sheet_detected: boolean
  part_count: number
  utilization: number
  area_m2: number
  parts_area_m2: number
  kerf_area_m2: number
  scrap_area_m2: number
  sheet_weight_kg: number | null
  parts_weight_kg: number | null
  scrap_weight_kg: number | null
  remnants: Remnant[]
  geometry?: {
    outline: PolygonJson
    parts: PolygonJson[]
    scrap: PolygonJson[]
  }
}

export interface Analysis {
  source: { name: string; format: 'dxf' | 'gcode' | 'cutlist'; layout_estimated: boolean }
  material: {
    code: string
    name: { en: string; fr: string }
    family: MaterialFamily
    density_kg_m3: number
    source: string
  } | null
  thickness_mm: number | null
  thickness_source: string
  process: string | null
  process_source: string
  kerf_mm: number
  min_side_mm: number
  totals: {
    sheet_area_m2: number
    parts_area_m2: number
    remnant_area_m2: number
    scrap_area_m2: number
    kerf_area_m2: number
    remnant_count: number
    remnant_weight_kg: number | null
    scrap_weight_kg: number | null
    sheet_weight_kg: number | null
  }
  sheets: SheetAnalysis[]
  warnings: string[]
}

export interface AnalysisOptions {
  material?: string
  thickness_mm?: number
  kerf_mm?: number
  process?: string
  sheet_width_mm?: number
  sheet_height_mm?: number
  min_side_mm?: number
}

export function analyzeFile(file: File, options: AnalysisOptions = {}): Promise<Analysis> {
  const form = new FormData()
  form.append('file', file)
  for (const [key, value] of Object.entries(options)) {
    if (value !== undefined && value !== '' && !Number.isNaN(value)) form.append(key, String(value))
  }
  return request<Analysis>('/v1/analyze', { method: 'POST', body: form })
}

/* ---------- Jobs and pieces ---------- */

export type DecisionAction = 'reuse' | 'sell' | 'recycle'

export interface DecisionOption {
  action: DecisionAction
  available: boolean
  value_tnd: number | null
  co2_kg: number | null
  note: string
}

export interface Decision {
  recommended: DecisionAction | null
  /** new: just recorded · review: past one review period · overdue: past two */
  stage: 'new' | 'review' | 'overdue'
  reasons: string[]
  options: DecisionOption[]
}

export interface Recovered {
  value_tnd: number
  co2_kg: number
  priced_pieces: number
  pieces: number
}

export type PieceStatus = 'draft' | 'rejected' | 'in_stock' | 'reserved' | 'reused' | 'sold' | 'recycled'

export interface Piece {
  id: string
  code: string
  job_id: string
  kind: 'remnant' | 'scrap'
  status: PieceStatus
  label: string
  sheet_index: number
  material_code: string | null
  thickness_mm: number | null
  x_mm: number | null
  y_mm: number | null
  width_mm: number | null
  height_mm: number | null
  area_m2: number
  weight_est_kg: number | null
  weight_actual_kg: number | null
  weight_kg: number | null
  condition_note: string | null
  location: string | null
  review_date: string | null
  /** In stock and past its review date: score it again. */
  due_for_review: boolean
  label_url: string
  updated_at: string
  decision: Decision
  listing: { id: string; status: ListingStatus; price_tnd: number } | null
}

export interface PieceEvent {
  at: string
  actor: string
  action: string
  data: Record<string, unknown>
}

export interface PieceWithHistory extends Piece {
  events: PieceEvent[]
}

export interface JobSummary {
  id: string
  file_name: string
  file_format: 'dxf' | 'gcode' | 'cutlist'
  material_code: string | null
  thickness_mm: number | null
  process: string | null
  machine_id: string | null
  status: 'draft' | 'approved'
  sheet_count: number
  part_count: number
  remnant_count: number
  remnant_weight_kg: number | null
  scrap_weight_kg: number | null
  recovered: Recovered
  created_at: string
  approved_at: string | null
  approved_by: string | null
}

export interface JobDetail extends JobSummary {
  analysis: Analysis
  pieces: Piece[]
}

export function createJob(
  file: File,
  options: AnalysisOptions = {},
  machineId?: string,
): Promise<JobDetail> {
  const form = new FormData()
  form.append('file', file)
  if (machineId) form.append('machine_id', machineId)
  for (const [key, value] of Object.entries(options)) {
    if (value !== undefined && value !== '' && !Number.isNaN(value)) form.append(key, String(value))
  }
  return request<JobDetail>('/v1/jobs', { method: 'POST', body: form })
}

export const listJobs = () => request<{ jobs: JobSummary[] }>('/v1/jobs')
export const getJob = (id: string) => request<JobDetail>(`/v1/jobs/${encodeURIComponent(id)}`)

export interface PiecePatch {
  weight_actual_kg?: number
  clear_weight?: boolean
  width_mm?: number
  height_mm?: number
  condition_note?: string
  location?: string
  rejected?: boolean
}

const json = (body: unknown): RequestInit => ({
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const patchPiece = (id: string, patch: PiecePatch) =>
  request<PieceWithHistory>(`/v1/pieces/${encodeURIComponent(id)}`, { method: 'PATCH', ...json(patch) })

export const approveJob = (id: string) =>
  request<JobDetail>(`/v1/jobs/${encodeURIComponent(id)}/approve`, { method: 'POST' })

export const getPieceByCode = (code: string) =>
  request<PieceWithHistory & { job: { id: string; file_name: string; status: string } }>(
    `/v1/codes/${encodeURIComponent(code)}`,
  )

export interface StockSummaryRow {
  material_code: string | null
  remnant_count: number
  remnant_area_m2: number
  remnant_weight_kg: number
  scrap_lots: number
  scrap_weight_kg: number
  unweighed: number
  due_for_review: number
  value_tnd: number
  co2_kg: number
}

export const getStock = (kind?: 'remnant' | 'scrap') =>
  request<{ pieces: Piece[] }>(`/v1/stock${kind ? `?kind=${kind}` : ''}`)

export const getStockSummary = () =>
  request<{
    materials: StockSummaryRow[]
    totals: Omit<StockSummaryRow, 'material_code' | 'unweighed'>
    actions: Record<DecisionAction, { count: number; value_tnd: number }>
  }>('/v1/stock/summary')

/* ---------- Price book ---------- */

export interface PriceRow {
  material_code: string
  name: { en: string; fr: string }
  family: MaterialFamily
  new_tnd_per_kg: number | null
  scrap_tnd_per_kg: number | null
  resale_factor: number | null
  source: string | null
  custom: boolean
  updated_at: string | null
  updated_by: string | null
  co2_primary_kg_per_kg: number | null
  co2_recycling_saves_kg_per_kg: number | null
  co2_source: string | null
}

export interface PriceUpdate {
  new_tnd_per_kg: number
  scrap_tnd_per_kg: number
  resale_factor: number
  source?: string
}

export const getPrices = () => request<{ prices: PriceRow[] }>('/v1/prices')

export const putPrice = (code: string, body: PriceUpdate) =>
  request<PriceRow>(`/v1/prices/${encodeURIComponent(code)}`, { method: 'PUT', ...json(body) })

export const resetPrice = (code: string) =>
  request<PriceRow>(`/v1/prices/${encodeURIComponent(code)}`, { method: 'DELETE' })

/* ---------- Marketplace ---------- */

export type ListingStatus = 'open' | 'reserved' | 'sold' | 'withdrawn'
export type BuyerKind = 'reuse' | 'recycler'

export interface BuyerRequest {
  id: string
  kind: BuyerKind
  name: string
  organization: string | null
  phone: string
  governorate: string
  materials: string[]
  thickness_min_mm: number | null
  thickness_max_mm: number | null
  min_length_mm: number | null
  min_width_mm: number | null
  max_price_tnd_per_kg: number | null
  offered_tnd_per_kg: number | null
  min_lot_kg: number | null
  pickup_note: string | null
  note: string | null
  active: boolean
  created_at: string
  match_count?: number
}

export interface BuyerMatch {
  request: BuyerRequest
  score: number
  distance_km: number | null
  reasons: string[]
  whatsapp_url: string
}

export interface PublicListing {
  id: string
  status: ListingStatus
  price_tnd: number
  price_tnd_per_kg: number | null
  piece: {
    code: string
    kind: 'remnant' | 'scrap'
    material_code: string | null
    material_name: { en: string; fr: string } | null
    family: MaterialFamily | null
    thickness_mm: number | null
    width_mm: number | null
    height_mm: number | null
    area_m2: number
    weight_kg: number | null
    condition_note: string | null
  }
  governorate: string | null
  created_at: string
  contact_url?: string | null
}

export interface WorkshopListing extends PublicListing {
  piece_id: string
  buyer: BuyerRequest | null
  sold_price_tnd: number | null
  fee_tnd: number | null
  updated_at: string
  closed_at: string | null
  match_count?: number
  top_matches?: BuyerMatch[]
}

export interface MarketSummary {
  open: number
  reserved: number
  sold: number
  sales_tnd: number
  fees_tnd: number
  open_value_tnd: number
  active_requests: number
}

export type ListingAction = 'reprice' | 'reserve' | 'reopen' | 'sell' | 'withdraw'

export const createListing = (pieceId: string, priceTnd?: number) =>
  request<WorkshopListing>(`/v1/pieces/${encodeURIComponent(pieceId)}/listing`, {
    method: 'POST',
    ...json({ price_tnd: priceTnd }),
  })

export const actOnListing = (
  id: string,
  body: { action: ListingAction; price_tnd?: number; buyer_request_id?: string },
) => request<WorkshopListing>(`/v1/listings/${encodeURIComponent(id)}`, { method: 'PATCH', ...json(body) })

export const getListings = () =>
  request<{ listings: WorkshopListing[]; summary: MarketSummary }>('/v1/listings')

export const getListingMatches = (id: string) =>
  request<{ listing: WorkshopListing; matches: BuyerMatch[] }>(`/v1/listings/${encodeURIComponent(id)}/matches`)

export const getMarket = () => request<{ listings: PublicListing[] }>('/v1/market')

export interface BuyerRequestInput {
  kind: BuyerKind
  name: string
  organization?: string
  phone: string
  governorate: string
  materials: string[]
  thickness_min_mm?: number
  thickness_max_mm?: number
  min_length_mm?: number
  min_width_mm?: number
  max_price_tnd_per_kg?: number
  offered_tnd_per_kg?: number
  min_lot_kg?: number
  pickup_note?: string
  note?: string
}

export const postBuyerRequest = (body: BuyerRequestInput) =>
  request<BuyerRequest & { matching_listings: PublicListing[] }>('/v1/buyer-requests', {
    method: 'POST',
    ...json(body),
  })

export const getBuyerRequests = () => request<{ requests: BuyerRequest[] }>('/v1/buyer-requests')

export const toggleBuyerRequest = (id: string, active: boolean) =>
  request<BuyerRequest>(`/v1/buyer-requests/${encodeURIComponent(id)}`, { method: 'PATCH', ...json({ active }) })

export const getGovernorates = () => request<{ governorates: string[] }>('/v1/geo/governorates')

/* ---------- Machines ---------- */

export interface Machine {
  id: string
  name: string
  process: string
  material_code: string | null
  material_name: { en: string; fr: string } | null
  thickness_mm: number | null
  kerf_mm: number | null
  sheet_width_mm: number | null
  sheet_height_mm: number | null
  min_side_mm: number | null
  active: boolean
}

export type MachineInput = Omit<Machine, 'id' | 'material_name' | 'active'>

export const getMachines = (includeInactive = false) =>
  request<{ machines: Machine[] }>(`/v1/machines${includeInactive ? '?include_inactive=true' : ''}`)

export const saveMachine = (body: MachineInput & { active?: boolean }, id?: string) =>
  request<Machine>(id ? `/v1/machines/${encodeURIComponent(id)}` : '/v1/machines', {
    method: id ? 'PUT' : 'POST',
    ...json(id ? { active: true, ...body } : body),
  })

/* ---------- Check stock before cutting ---------- */

export interface FitUse {
  piece: { id: string; code: string; width_mm: number; height_mm: number; location: string | null }
  fill: number
  placements: { label: string; x: number; y: number; width: number; height: number }[]
}

export interface FitPlan {
  material_code: string
  material_name: { en: string; fr: string }
  thickness_mm: number
  kerf_mm: number
  part_count: number
  placed_count: number
  candidates: number
  saved_kg: number
  saved_tnd: number | null
  uses: FitUse[]
  unplaced: { label: string; length: number; width: number }[]
}

export function checkFit(input: {
  file?: File
  material?: string
  thickness_mm?: number
  parts?: { length: number; width: number; qty: number; label?: string }[]
}): Promise<FitPlan> {
  const form = new FormData()
  if (input.file) form.append('file', input.file)
  if (input.material) form.append('material', input.material)
  if (input.thickness_mm) form.append('thickness_mm', String(input.thickness_mm))
  if (input.parts?.length) form.append('parts', JSON.stringify(input.parts))
  return request<FitPlan>('/v1/stock/fit', { method: 'POST', body: form })
}

export const reuseRemnants = (pieceIds: string[], jobName: string) =>
  request<{ pieces: Piece[] }>('/v1/stock/fit/reuse', {
    method: 'POST',
    ...json({ piece_ids: pieceIds, job_name: jobName }),
  })

/* ---------- Recycler pickups ---------- */

export interface RecyclerOption {
  recycler: BuyerRequest
  distance_km: number | null
  lot_ok: boolean
  estimated_tnd: number | null
}

export interface RecycleGroup {
  material_code: string | null
  material_name: { en: string; fr: string } | null
  total_kg: number
  pieces: {
    id: string
    code: string
    kind: 'remnant' | 'scrap'
    label: string
    width_mm: number | null
    height_mm: number | null
    thickness_mm: number | null
    weight_kg: number | null
  }[]
  recyclers: RecyclerOption[]
}

export type PickupStatus = 'requested' | 'scheduled' | 'collected' | 'cancelled'

export interface Pickup {
  id: string
  status: PickupStatus
  recycler: BuyerRequest
  scheduled_for: string | null
  estimated_kg: number
  weighed_kg: number | null
  paid_tnd: number | null
  created_by: string
  created_at: string
  closed_at: string | null
  pieces: { id: string; code: string; kind: string; material_code: string | null; thickness_mm: number | null; weight_kg: number | null }[]
  whatsapp_url: string
}

export const getRecycleQueue = () => request<{ groups: RecycleGroup[] }>('/v1/pickups/queue')
export const getPickups = () => request<{ pickups: Pickup[] }>('/v1/pickups')

export const createPickup = (recyclerId: string, pieceIds: string[]) =>
  request<Pickup>('/v1/pickups', { method: 'POST', ...json({ recycler_id: recyclerId, piece_ids: pieceIds }) })

export const actOnPickup = (
  id: string,
  body: { action: 'schedule' | 'collect' | 'cancel'; scheduled_for?: string; weighed_kg?: number; paid_tnd?: number },
) => request<Pickup>(`/v1/pickups/${encodeURIComponent(id)}`, { method: 'PATCH', ...json(body) })

/* ---------- Reports ---------- */

export interface MonthlyReport {
  month: string
  workshop: string
  generated_at: string
  production: { jobs: number; sheets: number; parts: number; remnant_kg: number; scrap_kg: number }
  outcomes: {
    reused: { pieces: number; kg: number; tnd: number }
    sold: { pieces: number; kg: number; tnd: number; fees_tnd: number }
    recycled: { pickups: number; kg: number; tnd: number }
  }
  recovered_tnd: number
  diverted_kg: number
  co2_avoided_kg: number
  plan_tnd: number
  return_on_plan: number | null
  stock: { value_tnd: number; remnant_count: number; remnant_kg: number; scrap_kg: number; due_for_review: number }
}

export const getMonthlyReport = (month: string) =>
  request<MonthlyReport>(`/v1/reports/monthly?month=${encodeURIComponent(month)}`)

export const stockExportUrl = `${BASE}/v1/stock/export.csv`

/* ---------- Alerts ---------- */

export interface Alert {
  kind: 'review' | 'due' | 'match' | 'recycle' | 'pickup' | 'buyer'
  title: string
  detail: string
  link: string
}

export const getAlerts = () => request<{ alerts: Alert[] }>('/v1/alerts')

/* ---------- Accounts ---------- */

export type Role = 'operator' | 'manager' | 'owner'

export interface User {
  id: string
  email: string
  name: string
  role: Role
  active: boolean
  created_at: string
  last_login_at: string | null
}

export interface Me {
  user: User | null
  setup_required: boolean
  workshop: { name: string; governorate: string | null }
}

export const getMe = () => request<Me>('/v1/auth/me')

export const signIn = (email: string, password: string) =>
  request<Me>('/v1/auth/login', { method: 'POST', ...json({ email, password }) })

export const setupWorkshop = (body: { workshop_name?: string; name: string; email: string; password: string }) =>
  request<Me>('/v1/auth/setup', { method: 'POST', ...json(body) })

export const signOut = () => request<void>('/v1/auth/logout', { method: 'POST' })

export const changePassword = (current: string, next: string) =>
  request<void>('/v1/auth/password', { method: 'POST', ...json({ current, new: next }) })

export const listUsers = () => request<{ users: User[] }>('/v1/users')

export const addUser = (body: { email: string; name: string; role: Role; password: string }) =>
  request<User>('/v1/users', { method: 'POST', ...json(body) })

export const updateUser = (
  id: string,
  body: { name?: string; role?: Role; active?: boolean; password?: string },
) => request<User>(`/v1/users/${encodeURIComponent(id)}`, { method: 'PATCH', ...json(body) })
