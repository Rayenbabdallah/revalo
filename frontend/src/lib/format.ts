import { intlLocale, t } from './i18n'

const nf = (digits: number) =>
  new Intl.NumberFormat(intlLocale(), { minimumFractionDigits: digits, maximumFractionDigits: digits })

export const fmtMm = (v: number) => nf(0).format(v)
export const fmtKg = (v: number | null | undefined, digits = 1) =>
  v === null || v === undefined ? '—' : nf(digits).format(v)
export const fmtM2 = (v: number, digits = 2) => nf(digits).format(v)
export const fmtPct = (v: number) => `${nf(1).format(v * 100)}`

export function fmtBytes(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${nf(0).format(size / 1024)} KB`
  return `${nf(1).format(size / 1024 / 1024)} MB`
}

const SOURCE_LABEL: Record<string, string> = {
  given: t('set by you'),
  file_name: t('from file name'),
  file_content: t('from file'),
  file_type: t('from file type'),
  unknown: t('not found'),
}
export const sourceLabel = (source: string) => SOURCE_LABEL[source] ?? source

const PROCESS_LABEL: Record<string, string> = {
  fiber_laser: t('Fibre laser'),
  co2_laser: t('CO₂ laser'),
  plasma: t('Plasma'),
  waterjet: t('Waterjet'),
  router: t('CNC router'),
  panel_saw: t('Panel saw'),
}
export const processLabel = (code: string | null) => (code ? (PROCESS_LABEL[code] ?? code) : t('Unknown'))

const FORMAT_LABEL = { dxf: t('DXF nest'), gcode: 'G-code', cutlist: t('Cut list'), manual: t('Existing stock') } as const
export const formatLabel = (f: keyof typeof FORMAT_LABEL) => FORMAT_LABEL[f]

export function fmtDate(iso: string) {
  return new Intl.DateTimeFormat(intlLocale(), { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(iso))
}

export function fmtDateTime(iso: string) {
  return new Intl.DateTimeFormat(intlLocale(), {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso))
}

const MATERIAL_LABEL: Record<string, string> = {
  steel_mild: t('Mild steel'),
  steel_galvanized: t('Galvanized steel'),
  stainless_304: t('Stainless 304'),
  stainless_316: t('Stainless 316'),
  aluminium: t('Aluminium'),
  copper: t('Copper'),
  brass: t('Brass'),
  mdf: t('MDF'),
  hdf: t('HDF'),
  plywood: t('Plywood'),
  particleboard: t('Particleboard'),
  melamine_board: t('Melamine board'),
  osb: t('OSB'),
  solid_pine: t('Solid pine'),
  solid_beech: t('Solid beech'),
  pmma: t('Acrylic'),
}
export const materialLabel = (code: string | null) => (code ? (MATERIAL_LABEL[code] ?? code) : t('Unknown material'))

const STATUS_LABEL: Record<string, string> = {
  draft: t('To review'),
  rejected: t('Rejected'),
  in_stock: t('In stock'),
  reserved: t('Reserved'),
  reused: t('Reused'),
  sold: t('Sold'),
  recycled: t('Recycled'),
  approved: t('Approved'),
  open: t('On sale'),
  withdrawn: t('Withdrawn'),
  requested: t('Requested'),
  scheduled: t('Scheduled'),
  collected: t('Collected'),
  cancelled: t('Cancelled'),
}
export const statusLabel = (status: string) => STATUS_LABEL[status] ?? status

export const fmtTnd = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined ? '—' : `${nf(digits).format(v)} TND`

const ACTION_LABEL = { reuse: t('Reuse'), sell: t('Sell'), recycle: t('Recycle') } as const
export const actionLabel = (a: keyof typeof ACTION_LABEL) => ACTION_LABEL[a]
