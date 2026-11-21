import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { SlidersHorizontal } from 'lucide-react'
import type { ReactNode } from 'react'

import { getMachines, getMaterials, type AnalysisOptions } from '../../lib/api'
import { processLabel } from '../../lib/format'

interface SettingsPanelProps {
  value: AnalysisOptions
  onChange: (value: AnalysisOptions) => void
  footer?: ReactNode
  className?: string
}

const fieldClass =
  'w-full rounded-lg border border-ink-700 bg-ink-950/60 px-3 py-2.5 font-mono text-sm text-ink-100 placeholder:text-ink-500 transition focus:border-brand-500 focus:outline-none'

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-baseline justify-between text-[13px] font-medium text-ink-200">
        {label}
        {hint && <span className="font-mono text-[10px] font-normal text-ink-500">{hint}</span>}
      </span>
      {children}
    </label>
  )
}

const num = (v: string) => (v === '' ? undefined : Number(v))

export function SettingsPanel({ value, onChange, footer, className }: SettingsPanelProps) {
  const catalog = useQuery({ queryKey: ['materials'], queryFn: getMaterials, staleTime: Infinity })
  const set = (patch: Partial<AnalysisOptions>) => onChange({ ...value, ...patch })
  const machines = useQuery({ queryKey: ['machines'], queryFn: () => getMachines() })
  const applyMachine = (id: string) => {
    const m = machines.data?.machines.find((x) => x.id === id)
    if (!m) return
    onChange({
      material: m.material_code ?? undefined,
      process: m.process,
      thickness_mm: m.thickness_mm ?? undefined,
      kerf_mm: m.kerf_mm ?? undefined,
      sheet_width_mm: m.sheet_width_mm ?? undefined,
      sheet_height_mm: m.sheet_height_mm ?? undefined,
      min_side_mm: m.min_side_mm ?? undefined,
    })
  }
  const families = ['metal', 'wood', 'plastic'] as const

  return (
    <section className={clsx('panel p-6', className)}>
      <header className="flex items-center gap-2.5">
        <SlidersHorizontal className="size-4 text-brand-400" />
        <h2 className="font-display text-lg font-semibold">Machine settings</h2>
      </header>
      <p className="mt-1.5 text-[13px] leading-relaxed text-ink-400">
        Leave on auto: Revalo reads material, thickness and sheet size from the file. Set them here
        when the file does not say.
      </p>

      <div className="mt-5 grid grid-cols-2 gap-4">
        {!!machines.data?.machines.length && (
          <div className="col-span-2">
            <Field label="Machine preset">
              <select className={fieldClass} defaultValue="" onChange={(e) => applyMachine(e.target.value)}>
                <option value="">None</option>
                {machines.data.machines.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        )}
        <div className="col-span-2">
          <Field label="Material">
            <select
              className={fieldClass}
              value={value.material ?? ''}
              onChange={(e) => set({ material: e.target.value || undefined })}
            >
              <option value="">Auto-detect</option>
              {families.map((family) => (
                <optgroup key={family} label={family[0].toUpperCase() + family.slice(1)}>
                  {catalog.data?.materials
                    .filter((m) => m.family === family)
                    .map((m) => (
                      <option key={m.code} value={m.code}>
                        {m.name.en}
                      </option>
                    ))}
                </optgroup>
              ))}
            </select>
          </Field>
        </div>
        <Field label="Thickness" hint="mm">
          <input
            className={fieldClass}
            inputMode="decimal"
            placeholder="auto"
            value={value.thickness_mm ?? ''}
            onChange={(e) => set({ thickness_mm: num(e.target.value) })}
          />
        </Field>
        <Field label="Process">
          <select
            className={fieldClass}
            value={value.process ?? ''}
            onChange={(e) => set({ process: e.target.value || undefined })}
          >
            <option value="">Auto</option>
            {catalog.data?.processes.map((p) => (
              <option key={p.code} value={p.code}>
                {processLabel(p.code)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Sheet width" hint="mm">
          <input
            className={fieldClass}
            inputMode="numeric"
            placeholder="auto"
            value={value.sheet_width_mm ?? ''}
            onChange={(e) => set({ sheet_width_mm: num(e.target.value) })}
          />
        </Field>
        <Field label="Sheet height" hint="mm">
          <input
            className={fieldClass}
            inputMode="numeric"
            placeholder="auto"
            value={value.sheet_height_mm ?? ''}
            onChange={(e) => set({ sheet_height_mm: num(e.target.value) })}
          />
        </Field>
        <Field label="Cut width" hint="mm">
          <input
            className={fieldClass}
            inputMode="decimal"
            placeholder="auto"
            value={value.kerf_mm ?? ''}
            onChange={(e) => set({ kerf_mm: num(e.target.value) })}
          />
        </Field>
        <Field label="Smallest useful side" hint="mm">
          <input
            className={fieldClass}
            inputMode="numeric"
            placeholder="auto"
            value={value.min_side_mm ?? ''}
            onChange={(e) => set({ min_side_mm: num(e.target.value) })}
          />
        </Field>
      </div>
      {footer && <div className="mt-6">{footer}</div>}
    </section>
  )
}
