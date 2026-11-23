import type { IntakeRow } from './api'

export const EMPTY_ROW: IntakeRow = { material: '', thickness_mm: 0, width_mm: null, height_mm: null, quantity: 1, location: '', kind: 'remnant', weight_kg: null }

/** Column names a workshop list may use, in English or French. */
const HEADERS: Record<string, keyof IntakeRow> = {
  material: 'material', materiau: 'material', matiere: 'material',
  thickness: 'thickness_mm', epaisseur: 'thickness_mm', ep: 'thickness_mm',
  width: 'width_mm', largeur: 'width_mm', length: 'width_mm', longueur: 'width_mm',
  height: 'height_mm', hauteur: 'height_mm',
  quantity: 'quantity', qty: 'quantity', quantite: 'quantity', qte: 'quantity',
  location: 'location', rack: 'location', emplacement: 'location',
  kind: 'kind', type: 'kind',
  weight: 'weight_kg', poids: 'weight_kg',
}

const normalize = (h: string) =>
  h.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/\(.*\)|[^a-z]/g, '')

export const num = (v: string) => {
  const n = Number(v.replace(/\s/g, '').replace(',', '.'))
  return Number.isFinite(n) && n > 0 ? n : null
}

/** Reads a spreadsheet export: comma, semicolon or tab, decimal commas welcome. */
export function parseList(text: string): IntakeRow[] {
  const lines = text.replace(/^﻿/, '').split(/\r?\n/).filter((l) => l.trim())
  if (lines.length < 2) return []
  const sep = [';', '\t', ','].find((s) => lines[0].includes(s)) ?? ','
  const columns = lines[0].split(sep).map((h) => HEADERS[normalize(h)])
  return lines.slice(1).map((line) => {
    const row: IntakeRow = { ...EMPTY_ROW }
    line.split(sep).forEach((cell, i) => {
      const key = columns[i]
      const value = cell.trim().replace(/^"|"$/g, '')
      if (!key || !value) return
      if (key === 'material' || key === 'location') row[key] = value
      else if (key === 'kind') row.kind = /scrap|ferraille|chute.*lot/i.test(value) ? 'scrap' : 'remnant'
      else if (key === 'quantity') row.quantity = Math.max(1, Math.round(num(value) ?? 1))
      else if (key === 'thickness_mm') row.thickness_mm = num(value) ?? 0
      else row[key] = num(value)
    })
    return row
  })
}
