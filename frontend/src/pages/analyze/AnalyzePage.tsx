import { useMutation, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Box, FileText, RotateCcw, Save, Scan, SlidersHorizontal, X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { lazy, Suspense, useState } from 'react'
import { useLocation } from 'wouter'

import { RepeatRunPrompt } from '../../components/jobs/RepeatRunPrompt'
import { analyzeFile, createJob, fetchSampleFile, repeatRunQuestion, type Analysis, type AnalysisOptions, type Sample } from '../../lib/api'
import { formatLabel, processLabel, sourceLabel, materialLabel } from '../../lib/format'
import type { ViewMode } from '../../components/viewer/SheetViewer'
import { visualThickness } from '../../components/viewer/thickness'
import { DropZone } from './DropZone'
import { ResultsPanel } from './ResultsPanel'
import { SampleGallery } from './SampleGallery'
import { SettingsPanel } from './SettingsPanel'
import { t } from '../../lib/i18n'

const SheetViewer = lazy(() => import('../../components/viewer/SheetViewer'))

const ease = [0.16, 1, 0.3, 1] as const

function Chip({ label, value, source }: { label: string; value: string; source?: string }) {
  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900/70 px-3 py-2">
      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">{label}</p>
      <p className="mt-0.5 text-[14px] font-medium text-ink-100">
        {value}
        {source && <span className="ms-1.5 text-[11px] font-normal text-ink-500">{source}</span>}
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
  const [, navigate] = useLocation()
  const queryClient = useQueryClient()
  const save = useMutation({
    mutationFn: (repeat?: 'new') => createJob(file, options, undefined, { repeat }),
    onSuccess: (job) => {
      queryClient.setQueryData(['job', job.id], job)
      queryClient.invalidateQueries({ queryKey: ['jobs'] })
      navigate(`/jobs/${job.id}`)
    },
  })
  const sheet = analysis.sheets[Math.min(sheetIndex, analysis.sheets.length - 1)]
  const { exaggeration } = visualThickness(sheet, analysis.thickness_mm)

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }}>
      {/* Job header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="eyebrow flex items-center gap-2">
            <FileText className="size-3.5" /> {formatLabel(analysis.source.format)}
            {analysis.source.layout_estimated && <span className="text-brand-400">{t('· layout estimated')}</span>}
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
                ? 'border-brand-500/60 bg-brand-500/10 text-brand-300'
                : 'border-ink-700 text-ink-200 hover:border-ink-500',
            )}
          >
            <SlidersHorizontal className="size-4" /> {t('Adjust')}
          </button>
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-2 rounded-xl border border-ink-700 px-4 py-2.5 text-sm font-medium text-ink-200 transition hover:border-ink-500"
          >
            <RotateCcw className="size-4" /> {t('New job')}
          </button>
          <button
            type="button"
            onClick={() => save.mutate(undefined)}
            disabled={save.isPending}
            className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-semibold text-ink-950 shadow-[0_10px_30px_-10px_rgb(25_74_203_/_0.9)] transition hover:bg-brand-400 disabled:opacity-60"
          >
            <Save className="size-4" /> {save.isPending ? t('Saving…') : t('Save & review')}
          </button>
        </div>
      </div>
      {repeatRunQuestion(save.error) ? (
        <RepeatRunPrompt
          question={repeatRunQuestion(save.error)!}
          busy={save.isPending}
          onRepeat={() => save.mutate('new')}
          onOpen={(jobId) => navigate(`/jobs/${jobId}`)}
        />
      ) : (
        save.isError && <p className="mt-3 text-[13px] text-alarm-400">{t('Could not save the job: {error}', { error: save.error.message })}</p>
      )}

      <div className="mt-5 flex flex-wrap gap-2">
        <Chip
          label={t('Material')}
          value={analysis.material ? materialLabel(analysis.material.code) : t('Unknown')}
          source={analysis.material ? sourceLabel(analysis.material.source) : undefined}
        />
        <Chip
          label={t('Thickness')}
          value={analysis.thickness_mm ? `${analysis.thickness_mm} mm` : t('Unknown')}
          source={analysis.thickness_mm ? sourceLabel(analysis.thickness_source) : undefined}
        />
        <Chip label={t('Process')} value={processLabel(analysis.process)} source={analysis.process ? sourceLabel(analysis.process_source) : undefined} />
        <Chip label={t('Cut width')} value={`${analysis.kerf_mm} mm`} />
        <Chip label={t('Sheet')} value={`${Math.round(sheet.width)} × ${Math.round(sheet.height)} mm`} source={sheet.sheet_detected ? 'from file' : 'assumed'} />
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
                  className="w-full rounded-xl bg-brand-500 py-3 text-sm font-semibold text-ink-950 transition hover:bg-brand-400 disabled:opacity-60"
                >
                  {busy ? t('Analyzing…') : t('Run again with these settings')}
                </button>
              }
            />
          </motion.div>
        )}
      </AnimatePresence>

      <div className="mt-6 grid gap-5 lg:grid-cols-12">
        <section className="stage relative h-[440px] overflow-hidden md:h-[620px] lg:col-span-8">
          <Suspense
            fallback={<div className="grid h-full place-items-center font-mono text-sm text-ink-500">{t('Loading 3D view…')}</div>}
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
            <div className="pointer-events-auto flex rounded-xl border border-ink-700 bg-ink-950/80 p-1 backdrop-blur-md">
              {([
                ['3d', '3D', Box],
                ['top', t('Top'), Scan],
              ] as const).map(([value, label, Icon]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setMode(value)}
                  className={clsx(
                    'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-medium transition',
                    mode === value ? 'bg-ink-700 text-ink-50' : 'text-ink-400 hover:text-ink-100',
                  )}
                >
                  <Icon className="size-3.5" /> {label}
                </button>
              ))}
            </div>
            {analysis.sheets.length > 1 && (
              <div className="pointer-events-auto flex flex-wrap justify-end gap-1 rounded-xl border border-ink-700 bg-ink-950/80 p-1 backdrop-blur-md">
                {analysis.sheets.map((s) => (
                  <button
                    key={s.index}
                    type="button"
                    onClick={() => setSheetIndex(s.index)}
                    className={clsx(
                      'rounded-lg px-3 py-1.5 font-mono text-[12px] transition',
                      s.index === sheet.index ? 'bg-ink-700 text-ink-50' : 'text-ink-400 hover:text-ink-100',
                    )}
                  >
                    Sheet {s.index + 1}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="pointer-events-none absolute inset-x-4 bottom-4 flex flex-wrap items-end justify-between gap-3">
            <div className="flex flex-wrap gap-3 rounded-xl border border-ink-800 bg-ink-950/70 px-3.5 py-2 font-mono text-[11px] text-ink-300 backdrop-blur-md">
              <span className="flex items-center gap-1.5">
                <span className="size-2.5 rounded-sm bg-reclaim-400" /> {t('Remnant')}
              </span>
              <span className="flex items-center gap-1.5">
                <span className="size-2.5 rounded-sm bg-ink-500" /> {t('Part')}
              </span>
              <span className="flex items-center gap-1.5">
                <span className="size-2.5 rounded-sm bg-ink-300" /> {t('Scrap skeleton')}
              </span>
            </div>
            {exaggeration > 1.5 && (
              <span className="rounded-lg bg-ink-950/70 px-2.5 py-1.5 font-mono text-[10.5px] text-ink-500 backdrop-blur-md">
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
            <p className="eyebrow">{t('Leftover engine')}</p>
            <h1 className="mt-4 max-w-3xl font-display text-[40px] font-semibold leading-[1.02] tracking-[-0.03em] text-ink-50 md:text-[64px]">
              {t('Every sheet leaves')}{' '}
              <span className="relative whitespace-nowrap text-reclaim-600">
                {t('money')}
                <svg aria-hidden viewBox="0 0 200 12" className="absolute -bottom-2 start-0 w-full text-reclaim-400" preserveAspectRatio="none">
                  <path d="M2 9 Q 60 2 120 6 T 198 4" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                </svg>
              </span>{' '}
              {t('behind.')}
            </h1>
            <p className="mt-6 max-w-xl text-[17px] leading-relaxed text-ink-300">
              {t('Upload a nest, a G-code program or a cut list. Revalo shows you every reusable remnant with its size and weight, and what is only fit for the scrap bin.')}
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
                className="mt-5 flex items-start justify-between gap-4 rounded-xl border border-alarm-400/40 bg-alarm-400/10 px-5 py-4 text-[14px] text-ink-100"
              >
                <span>
                  <strong className="font-semibold text-alarm-400">{t('Could not analyze {file}.', { file: file?.name ?? t('the file') })}</strong>{' '}
                  {error.message}
                </span>
                <button type="button" onClick={() => { run.reset(); sample.reset() }} aria-label={t('Dismiss')}>
                  <X className="size-4 text-ink-400" />
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
