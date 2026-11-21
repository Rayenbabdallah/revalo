import type { SheetAnalysis } from '../../lib/api'

/** Visual thickness: the real thickness, but never thinner than a readable slab. */
export function visualThickness(sheet: SheetAnalysis, thicknessMm: number | null) {
  const longest = Math.max(sheet.width, sheet.height)
  const real = thicknessMm ?? 3
  const shown = Math.max(real, longest * 0.004)
  return { shown, exaggeration: shown / real }
}
