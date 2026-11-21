const nf = (digits: number) =>
  new Intl.NumberFormat('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })

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
  given: 'set by you',
  file_name: 'from file name',
  file_content: 'from file',
  file_type: 'from file type',
  unknown: 'not found',
}
export const sourceLabel = (source: string) => SOURCE_LABEL[source] ?? source

const PROCESS_LABEL: Record<string, string> = {
  fiber_laser: 'Fibre laser',
  co2_laser: 'CO₂ laser',
  plasma: 'Plasma',
  waterjet: 'Waterjet',
  router: 'CNC router',
  panel_saw: 'Panel saw',
}
export const processLabel = (code: string | null) => (code ? (PROCESS_LABEL[code] ?? code) : 'Unknown')

const FORMAT_LABEL = { dxf: 'DXF nest', gcode: 'G-code', cutlist: 'Cut list' } as const
export const formatLabel = (f: keyof typeof FORMAT_LABEL) => FORMAT_LABEL[f]

export function fmtDate(iso: string) {
  return new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(iso))
}

export function fmtDateTime(iso: string) {
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso))
}

const MATERIAL_LABEL: Record<string, string> = {
  steel_mild: 'Mild steel',
  steel_galvanized: 'Galvanized steel',
  stainless_304: 'Stainless 304',
  stainless_316: 'Stainless 316',
  aluminium: 'Aluminium',
  copper: 'Copper',
  brass: 'Brass',
  mdf: 'MDF',
  hdf: 'HDF',
  plywood: 'Plywood',
  particleboard: 'Particleboard',
  melamine_board: 'Melamine board',
  osb: 'OSB',
  solid_pine: 'Solid pine',
  solid_beech: 'Solid beech',
  pmma: 'Acrylic',
}
export const materialLabel = (code: string | null) => (code ? (MATERIAL_LABEL[code] ?? code) : 'Unknown material')

const STATUS_LABEL: Record<string, string> = {
  draft: 'To review',
  rejected: 'Rejected',
  in_stock: 'In stock',
  reserved: 'Reserved',
  reused: 'Reused',
  sold: 'Sold',
  recycled: 'Recycled',
  approved: 'Approved',
}
export const statusLabel = (status: string) => STATUS_LABEL[status] ?? status
