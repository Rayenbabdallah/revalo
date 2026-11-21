import { useMutation } from '@tanstack/react-query'
import clsx from 'clsx'
import { Box, FileText, RotateCcw, Scan, SlidersHorizontal, X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { lazy, Suspense, useState } from 'react'

import { analyzeFile, fetchSampleFile, type Analysis, type AnalysisOptions, type Sample } from '../../lib/api'
import { formatLabel, processLabel, sourceLabel } from '../../lib/format'
import type { ViewMode } from '../../components/viewer/SheetViewer'
import { visualThickness } from '../../components/viewer/thickness'
import { DropZone } from './DropZone'
import { ResultsPanel } from './ResultsPanel'
import { SampleGallery } from './SampleGallery'
import { SettingsPanel } from './SettingsPanel'

const SheetViewer = lazy(() => import('../../components/viewer/SheetViewer'))

const ease = [0.16, 1, 0.3, 1] as const

function Chip({ label, value, source }: { label: string; value: string; source?: string }) {
  return (
    <div className="rounded-lg border border-graphite-800 bg-graphite-900/70 px-3 py-2">
      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-graphite-500">{label}</p>
      <p className="mt-0.5 text-[14px] font-medium text-graphite-100">
        {value}
        {source && <span className="ml-1.5 text-[11px] font-normal text-graphite-500">{source}</span>}
      </p>
    </div>
  )
}

function Results({
  analysis,
  file,
  onReset,
  onRerun,
  options,
  setOptions,
  busy,
}: {
  analysis: Analysis
  file: File
  onReset: () => void
  onRerun: () => void
  options: AnalysisOptions
  setOptions: (o: AnalysisOptions) => void
  busy: boolean
}) {
  const [sheetIndex, setSheetIndex] = useState(0)
  const [highlighted, setHighlighted] = useState<string | null>(null)
  const [mode, setMode] = useState<ViewMode>('3d')
  const [showSettings, setShowSettings] = useState(false)
  const sheet = analysis.sheets[Math.min(sheetIndex, analysis.sheets.length - 1)]
  const { exaggeration } = visualThickness(sheet, analysis.thickness_mm)

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }}>
      {/* Job header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="eyebrow flex items-center gap-2">
            <FileText className="size-3.5" /> {formatLabel(analysis.source.format)}
            {analysis.source.layout_estimated && <span className="text-ember-400">· layout estimated</span>}
          </p>
          <h1 className="mt-2 truncate font-display text-3xl font-semibold tracking-tight md:text-4xl">{file.name}</h1>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setShowSettings((s) => !s)}
            className={clsx(
              'inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition',
              showSettings
                ? 'border-ember-500/60 bg-ember-500/10 text-ember-300'
                : 'border-graphite-700 text-graphite-200 hover:border-graphite-500',
            )}
          >
            <SlidersHorizontal className="size-4" /> Adjust
          </button>
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-2 rounded-xl border border-graphite-700 px-4 py-2.5 text-sm font-medium text-graphite-200 transition hover:border-graphite-500"
          >
            <RotateCcw className="size-4" /> New job
          </button>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        <Chip
          label="Material"
          value={analysis.material?.name.en ?? 'Unknown'}
          source={analysis.material ? sourceLabel(analysis.material.source) : undefined}
        />
        <Chip
          label="Thickness"
          value={analysis.thickness_mm ? `${analysis.thickness_mm} mm` : 'Unknown'}
          source={analysis.thickness_mm ? sourceLabel(analysis.thickness_source) : undefined}
        />
        <Chip label="Process" value={processLabel(analysis.process)} source={analysis.process ? sourceLabel(analysis.process_source) : undefined} />
        <Chip label="Cut width" value={`${analysis.kerf_mm} mm`} />
        <Chip label="Sheet" value={`${Math.round(sheet.width)} × ${Math.round(sheet.height)} mm`} source={sheet.sheet_detected ? 'from file' : 'assumed'} />
      </div>

      <AnimatePresence>
        {showSettings && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.35, ease }}
            className="overflow-hidden"
          >
            <SettingsPanel
              className="mt-5"
              value={options}
              onChange={setOptions}
              footer={
                <button
                  type="button"
                  disabled={busy}
                  onClick={onRerun}
                  className="w-full rounded-xl bg-ember-500 py-3 text-sm font-semibold text-graphite-950 transition hover:bg-ember-400 disabled:opacity-60"
                >
                  {busy ? 'Analyzing…' : 'Run again with these settings'}
                </button>
              }
            />
          </motion.div>
        )}
      </AnimatePresence>

      <div className="mt-6 grid gap-5 lg:grid-cols-12">
        <section className="panel relative h-[440px] overflow-hidden md:h-[620px] lg:col-span-8">
          <Suspense
            fallback={<div className="grid h-full place-items-center font-mono text-sm text-graphite-500">Loading 3D view…</div>}
          >
            <SheetViewer
              key={`${analysis.source.name}-${sheet.index}`}
              sheet={sheet}
              family={analysis.material?.family ?? null}
              thicknessMm={analysis.thickness_mm}
              highlighted={highlighted}
              onHighlight={setHighlighted}
              mode={mode}
            />
          </Suspense>

          {/* Overlay controls */}
          <div className="pointer-events-none absolute inset-x-4 top-4 flex items-start justify-between gap-3">
            <div className="pointer-events-auto flex rounded-xl border border-graphite-700 bg-graphite-950/80 p-1 backdrop-blur-md">
              {([
                ['3d', '3D', Box],
                ['top', 'Top', Scan],
              ] as const).map(([value, label, Icon]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setMode(value)}
                  className={clsx(
                    'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium transition',
                    mode === value ? 'bg-graphite-700 text-graphite-50' : 'text-graphite-400 hover:text-graphite-100',
                  )}
                >
                  <Icon className="size-3.5" /> {label}
                </button>
              ))}
            </div>
            {analysis.sheets.length > 1 && (
              <div className="pointer-events-auto flex flex-wrap justify-end gap-1 rounded-xl border border-graphite-700 bg-graphite-950/80 p-1 backdrop-blur-md">
                {analysis.sheets.map((s) => (
                  <button
                    key={s.index}
                    type="button"
                    onClick={() => setSheetIndex(s.index)}
                    className={clsx(
                      'rounded-lg px-3 py-1.5 font-mono text-[12px] transition',
                      s.index === sheet.index ? 'bg-graphite-700 text-graphite-50' : 'text-graphite-400 hover:text-graphite-100',
                    )}
                  >
                    Sheet {s.index + 1}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="pointer-events-none absolute inset-x-4 bottom-4 flex flex-wrap items-end justify-between gap-3">
            <div className="flex flex-wrap gap-3 rounded-xl border border-graphite-800 bg-graphite-950/70 px-3.5 py-2 font-mono text-[11px] text-graphite-300 backdrop-blur-md">
              <span className="flex items-center gap-1.5">
                <span className="size-2.5 rounded-sm bg-reclaim-400" /> Remnant
              </span>
              <span className="flex items-center gap-1.5">
                <span className="size-2.5 rounded-sm bg-graphite-500" /> Part
              </span>
              <span className="flex items-center gap-1.5">
                <span className="size-2.5 rounded-sm bg-graphite-300" /> Scrap skeleton
              </span>
            </div>
            {exaggeration > 1.5 && (
              <span className="rounded-lg bg-graphite-950/70 px-2.5 py-1.5 font-mono text-[10.5px] text-graphite-500 backdrop-blur-md">
                thickness shown ×{Math.round(exaggeration)}
              </span>
            )}
          </div>
        </section>

        <div className="lg:col-span-4">
          <ResultsPanel analysis={analysis} sheet={sheet} highlighted={highlighted} onHighlight={setHighlighted} />
        </div>
      </div>
    </motion.div>
  )
}

export function AnalyzePage() {
  const [file, setFile] = useState<File | null>(null)
  const [options, setOptions] = useState<AnalysisOptions>({})
  const run = useMutation({ mutationFn: ({ f, o }: { f: File; o: AnalysisOptions }) => analyzeFile(f, o) })
  const sample = useMutation({ mutationFn: fetchSampleFile })

  const start = (f: File) => {
    setFile(f)
    run.mutate({ f, o: options })
  }
  const pickSample = (s: Sample) => sample.mutate(s, { onSuccess: start })
  const reset = () => {
    run.reset()
    setFile(null)
  }

  const busy = run.isPending || sample.isPending
  const error = run.error ?? sample.error

  return (
    <div className="mx-auto max-w-[1480px] px-4 py-8 md:px-10 md:py-12">
      {run.data && file ? (
        <Results
          analysis={run.data}
          file={file}
          onReset={reset}
          onRerun={() => run.mutate({ f: file, o: options })}
          options={options}
          setOptions={setOptions}
          busy={busy}
        />
      ) : (
        <>
          <motion.header initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease }}>
            <p className="eyebrow">Leftover engine</p>
            <h1 className="mt-4 max-w-3xl font-display text-[40px] font-semibold leading-[1.02] tracking-[-0.03em] text-graphite-50 md:text-[64px]">
              Every sheet leaves{' '}
              <span className="relative whitespace-nowrap text-reclaim-400">
                money
                <svg aria-hidden viewBox="0 0 200 12" className="absolute -bottom-2 left-0 w-full" preserveAspectRatio="none">
                  <path d="M2 9 Q 60 2 120 6 T 198 4" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                </svg>
              </span>{' '}
              behind.
            </h1>
            <p className="mt-6 max-w-xl text-[17px] leading-relaxed text-graphite-300">
              Upload a nest, a G-code program or a cut list. Revalo shows you every reusable remnant
              with its size and weight, and what is only fit for the scrap bin.
            </p>
          </motion.header>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease, delay: 0.12 }}
            className="mt-10 grid gap-5 lg:grid-cols-12"
          >
            <div className="lg:col-span-7">
              <DropZone busy={busy} onFile={start} />
            </div>
            <SettingsPanel className="lg:col-span-5" value={options} onChange={setOptions} />
          </motion.div>

          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="mt-5 flex items-start justify-between gap-4 rounded-xl border border-alarm-400/40 bg-alarm-400/10 px-5 py-4 text-[14px] text-graphite-100"
              >
                <span>
                  <strong className="font-semibold text-alarm-400">Could not analyze {file?.name ?? 'the file'}.</strong>{' '}
                  {error.message}
                </span>
                <button type="button" onClick={() => { run.reset(); sample.reset() }} aria-label="Dismiss">
                  <X className="size-4 text-graphite-400" />
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          <SampleGallery disabled={busy} onPick={pickSample} />
        </>
      )}
    </div>
  )
}
