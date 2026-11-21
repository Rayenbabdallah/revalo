import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Cpu, Pencil, Plus } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'

import { getMachines, getMaterials, saveMachine, type Machine, type MachineInput } from '../../lib/api'
import { materialLabel, processLabel } from '../../lib/format'

const field =
  'w-full rounded-xl border border-ink-700 bg-ink-900 px-3 py-2.5 text-[14px] text-ink-50 focus:border-brand-500 focus:outline-none'

function Label({ text, children }: { text: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[12.5px] font-medium text-ink-300">{text}</span>
      {children}
    </label>
  )
}

const num = (v: FormDataEntryValue | null) => {
  const s = String(v ?? '').trim().replace(',', '.')
  return s === '' ? null : Number(s)
}

function MachineForm({ machine, onDone }: { machine?: Machine; onDone: () => void }) {
  const queryClient = useQueryClient()
  const catalog = useQuery({ queryKey: ['materials'], queryFn: getMaterials, staleTime: Infinity })
  const save = useMutation({
    mutationFn: (body: MachineInput & { active?: boolean }) => saveMachine(body, machine?.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['machines'] })
      onDone()
    },
  })
  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    save.mutate({
      name: String(f.get('name') ?? ''),
      process: String(f.get('process') ?? ''),
      material_code: String(f.get('material') ?? '') || null,
      thickness_mm: num(f.get('thickness')),
      kerf_mm: num(f.get('kerf')),
      sheet_width_mm: num(f.get('sw')),
      sheet_height_mm: num(f.get('sh')),
      min_side_mm: num(f.get('min')),
      active: true,
    })
  }
  return (
    <form onSubmit={submit} className="grid gap-3 sm:grid-cols-4">
      <div className="sm:col-span-2">
        <Label text="Name">
          <input name="name" required defaultValue={machine?.name} placeholder="Fibre laser 3 kW" className={field} />
        </Label>
      </div>
      <Label text="Process">
        <select name="process" required defaultValue={machine?.process ?? 'fiber_laser'} className={field}>
          {catalog.data?.processes.map((p) => (
            <option key={p.code} value={p.code}>
              {processLabel(p.code)}
            </option>
          ))}
        </select>
      </Label>
      <Label text="Usual material">
        <select name="material" defaultValue={machine?.material_code ?? ''} className={field}>
          <option value="">Varies</option>
          {catalog.data?.materials.map((m) => (
            <option key={m.code} value={m.code}>
              {m.name.en}
            </option>
          ))}
        </select>
      </Label>
      <Label text="Usual thickness (mm)">
        <input name="thickness" inputMode="decimal" defaultValue={machine?.thickness_mm ?? ''} className={field} />
      </Label>
      <Label text="Cut width (mm)">
        <input name="kerf" inputMode="decimal" defaultValue={machine?.kerf_mm ?? ''} placeholder="from process" className={field} />
      </Label>
      <Label text="Sheet width (mm)">
        <input name="sw" inputMode="numeric" defaultValue={machine?.sheet_width_mm ?? ''} className={field} />
      </Label>
      <Label text="Sheet height (mm)">
        <input name="sh" inputMode="numeric" defaultValue={machine?.sheet_height_mm ?? ''} className={field} />
      </Label>
      <Label text="Smallest useful side (mm)">
        <input name="min" inputMode="numeric" defaultValue={machine?.min_side_mm ?? ''} placeholder="auto" className={field} />
      </Label>
      <div className="flex items-end gap-2 sm:col-span-3">
        <button type="submit" disabled={save.isPending} className="rounded-xl bg-brand-500 px-5 py-2.5 text-[14px] font-semibold text-ink-950 hover:bg-brand-400 disabled:opacity-60">
          Save machine
        </button>
        <button type="button" onClick={onDone} className="rounded-xl border border-ink-700 px-4 py-2.5 text-[14px] text-ink-300">
          Cancel
        </button>
        {save.isError && <span className="text-[13px] text-alarm-400">{save.error.message}</span>}
      </div>
    </form>
  )
}

export function MachinesPanel() {
  const queryClient = useQueryClient()
  const machines = useQuery({ queryKey: ['machines', 'all'], queryFn: () => getMachines(true) })
  const [editing, setEditing] = useState<string | 'new' | null>(null)
  const retire = useMutation({
    mutationFn: (m: Machine) => saveMachine({ ...m, active: !m.active }, m.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['machines'] }),
  })
  const list = machines.data?.machines ?? []

  return (
    <div className="space-y-3">
      <p className="max-w-2xl text-[14.5px] leading-relaxed text-ink-400">
        Save each machine's usual settings once. Operators then pick the machine and the file, and nothing needs typing.
        Anything the file says itself still wins.
      </p>
      {list.map((m) => (
        <div key={m.id} className="panel p-5">
          {editing === m.id ? (
            <MachineForm machine={m} onDone={() => setEditing(null)} />
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className="grid size-10 place-items-center rounded-xl bg-ink-800">
                  <Cpu className="size-5 text-brand-500" />
                </span>
                <div>
                  <p className="font-display text-[16px] font-semibold text-ink-50">
                    {m.name} {!m.active && <span className="text-[12px] font-normal text-ink-500">· retired</span>}
                  </p>
                  <p className="text-[13px] text-ink-400">
                    {processLabel(m.process)}
                    {m.material_code && ` · ${materialLabel(m.material_code)}`}
                    {m.thickness_mm && ` ${m.thickness_mm} mm`}
                    {m.kerf_mm !== null && ` · cut ${m.kerf_mm} mm`}
                    {m.sheet_width_mm && ` · sheet ${m.sheet_width_mm} × ${m.sheet_height_mm}`}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <button type="button" onClick={() => setEditing(m.id)} className="inline-flex items-center gap-1.5 rounded-lg border border-ink-700 px-3 py-1.5 text-[13px] text-ink-200 hover:border-brand-500">
                  <Pencil className="size-3.5" /> Edit
                </button>
                <button type="button" onClick={() => retire.mutate(m)} className="rounded-lg border border-ink-700 px-3 py-1.5 text-[13px] text-ink-400 hover:border-ink-500">
                  {m.active ? 'Retire' : 'Restore'}
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
      {editing === 'new' ? (
        <div className="panel p-5">
          <MachineForm onDone={() => setEditing(null)} />
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setEditing('new')}
          className="flex w-full items-center justify-center gap-2 rounded-[22px] border-2 border-dashed border-ink-700 py-5 text-[14px] font-medium text-ink-300 hover:border-brand-500 hover:text-brand-500"
        >
          <Plus className="size-4" /> Add a machine
        </button>
      )}
    </div>
  )
}
