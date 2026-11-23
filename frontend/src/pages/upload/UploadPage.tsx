import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { CheckCircle2, Cpu, FileUp, Loader2, RotateCcw } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useRef, useState } from 'react'
import { Link } from 'wouter'

import { createJob, getMachines, type JobDetail, type Machine } from '../../lib/api'
import { fmtKg, fmtTnd, materialLabel, processLabel } from '../../lib/format'

const ACCEPT = '.dxf,.nc,.gcode,.ngc,.tap,.cnc,.gc,.csv,.tsv,.txt'

function MachineTile({ machine, selected, onSelect }: { machine: Machine; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={clsx(
        'flex w-full items-center gap-4 rounded-[20px] border-2 p-4 text-start transition',
        selected ? 'border-brand-500 bg-brand-500 text-ink-950 shadow-lg' : 'border-ink-700 bg-ink-900 hover:border-brand-500/50',
      )}
    >
      <span className={clsx('grid size-12 shrink-0 place-items-center rounded-2xl', selected ? 'bg-white/15' : 'bg-ink-800')}>
        <Cpu className={clsx('size-6', selected ? 'text-reclaim-400' : 'text-brand-500')} />
      </span>
      <span className="min-w-0">
        <span className="block font-display text-[17px] font-semibold">{machine.name}</span>
        <span className={clsx('block truncate text-[13px]', selected ? 'text-ink-950/80' : 'text-ink-400')}>
          {processLabel(machine.process)}
          {machine.material_code && ` · ${materialLabel(machine.material_code)}`}
          {machine.thickness_mm && ` ${machine.thickness_mm} mm`}
        </span>
      </span>
    </button>
  )
}

/** For the operator at the machine: two taps and the job is with the manager. */
export function UploadPage() {
  const queryClient = useQueryClient()
  const machines = useQuery({ queryKey: ['machines'], queryFn: () => getMachines() })
  const [machineId, setMachineId] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)
  const upload = useMutation({
    mutationFn: ({ file, machine }: { file: File; machine: string | null }) =>
      createJob(file, {}, machine ?? undefined),
    onSuccess: (job) => {
      queryClient.setQueryData(['job', job.id], job)
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })
  const list = machines.data?.machines ?? []
  const chosen = machineId ?? (list.length === 1 ? list[0].id : null)
  const done: JobDetail | undefined = upload.data

  return (
    <div className="mx-auto max-w-xl px-4 py-8 md:py-12">
      <p className="eyebrow">At the machine</p>
      <h1 className="mt-3 font-display text-[34px] font-semibold leading-tight tracking-tight">Send a finished job</h1>
      <p className="mt-2 text-[15px] text-ink-400">Pick your machine, then the file it just cut. The manager checks the rest.</p>

      <AnimatePresence mode="wait">
        {done ? (
          <motion.section
            key="done"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="panel-brand mt-8 p-7 text-center"
          >
            <CheckCircle2 className="mx-auto size-12 text-reclaim-400" />
            <p className="mt-3 font-display text-2xl font-semibold">Sent for review</p>
            <p className="mt-1 text-[14.5px] text-ink-950/85">{done.file_name}</p>
            <div className="mt-5 grid grid-cols-2 gap-3 text-start">
              <div className="rounded-xl bg-white/10 px-4 py-3">
                <p className="eyebrow !text-[10px] !text-ink-950/75">Remnants</p>
                <p className="readout mt-1 text-2xl text-reclaim-400">
                  {done.remnant_count}
                  <span className="ms-1 text-sm text-ink-950/75">· {fmtKg(done.remnant_weight_kg)} kg</span>
                </p>
              </div>
              <div className="rounded-xl bg-white/10 px-4 py-3">
                <p className="eyebrow !text-[10px] !text-ink-950/75">Worth about</p>
                <p className="readout mt-1 text-2xl text-reclaim-400">
                  {done.recovered.priced_pieces ? fmtTnd(done.recovered.value_tnd) : '—'}
                </p>
              </div>
            </div>
            <div className="mt-6 flex justify-center gap-2">
              <button
                type="button"
                onClick={() => upload.reset()}
                className="inline-flex items-center gap-2 rounded-xl bg-ink-950 px-5 py-3 text-[15px] font-semibold text-brand-500"
              >
                <RotateCcw className="size-4" /> Next job
              </button>
              <Link href={`/jobs/${done.id}`} className="rounded-xl border border-white/30 px-5 py-3 text-[15px] font-medium">
                Open review
              </Link>
            </div>
          </motion.section>
        ) : (
          <motion.div key="form" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <section className="mt-8">
              <p className="mb-3 text-[13px] font-semibold uppercase tracking-[0.12em] text-ink-400">1 · Machine</p>
              {machines.isPending ? (
                <p className="font-mono text-sm text-ink-500">Loading…</p>
              ) : list.length === 0 ? (
                <div className="panel p-5 text-[14px] text-ink-300">
                  No machine is set up yet.{' '}
                  <Link href="/settings" className="font-medium text-brand-500 hover:underline">
                    Add your machines
                  </Link>{' '}
                  so uploads need no typing. You can still send a file: Revalo reads what it can from it.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {list.map((m) => (
                    <MachineTile key={m.id} machine={m} selected={chosen === m.id} onSelect={() => setMachineId(m.id)} />
                  ))}
                </div>
              )}
            </section>

            <section className="mt-8">
              <p className="mb-3 text-[13px] font-semibold uppercase tracking-[0.12em] text-ink-400">2 · Job file</p>
              <button
                type="button"
                disabled={upload.isPending || (list.length > 0 && !chosen)}
                onClick={() => input.current?.click()}
                className="flex w-full flex-col items-center gap-3 rounded-[22px] border-2 border-dashed border-brand-500/50 bg-ink-900 px-6 py-10 text-brand-500 transition hover:bg-brand-500/5 disabled:opacity-50"
              >
                {upload.isPending ? <Loader2 className="size-9 animate-spin" /> : <FileUp className="size-9" />}
                <span className="font-display text-lg font-semibold">
                  {upload.isPending ? 'Reading the cut…' : 'Choose the file'}
                </span>
                <span className="text-[13px] text-ink-400">DXF nest, G-code program or CSV cut list</span>
              </button>
              <input
                ref={input}
                type="file"
                accept={ACCEPT}
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) upload.mutate({ file, machine: chosen })
                  e.target.value = ''
                }}
              />
              {upload.isError && <p className="mt-3 text-[14px] text-alarm-400">{upload.error.message}</p>}
            </section>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
