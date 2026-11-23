import clsx from 'clsx'
import { FileUp } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { t } from '../../lib/i18n'

const ACCEPT = '.dxf,.nc,.gcode,.ngc,.tap,.cnc,.gc,.csv,.tsv,.txt'
const STAGES = [t('Reading contours'), t('Finding the sheet'), t('Measuring remnants'), t('Weighing scrap')]

function Ruler({ vertical = false }: { vertical?: boolean }) {
  // Millimetre ticks with a longer tick every 10, like a machine bed ruler.
  const ticks = Array.from({ length: 61 }, (_, i) => i)
  return (
    <div
      aria-hidden
      className={clsx(
        'pointer-events-none absolute flex justify-between text-ink-600',
        vertical ? 'start-0 top-6 bottom-6 w-3 flex-col' : 'start-6 end-6 top-0 h-3',
      )}
    >
      {ticks.map((i) => (
        <span
          key={i}
          className={clsx('bg-current', vertical ? 'h-px' : 'w-px', i % 10 === 0 ? (vertical ? 'w-3' : 'h-3') : vertical ? 'w-1.5' : 'h-1.5')}
        />
      ))}
    </div>
  )
}

/** Cycles through what the engine is doing; mounted only while busy. */
function BusyStages() {
  const [stage, setStage] = useState(0)
  useEffect(() => {
    const timer = setInterval(() => setStage((s) => (s + 1) % STAGES.length), 650)
    return () => clearInterval(timer)
  }, [])
  return (
    <p className="readout mt-2 text-sm text-brand-300">
      {STAGES[stage]}
      <span className="animate-pulse">_</span>
    </p>
  )
}

interface DropZoneProps {
  busy: boolean
  onFile: (file: File) => void
}

export function DropZone({ busy, onFile }: DropZoneProps) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setOver(false)
        const file = e.dataTransfer.files[0]
        if (file && !busy) onFile(file)
      }}
      className={clsx(
        'panel group relative isolate flex min-h-[360px] flex-col items-center justify-center overflow-hidden p-10 text-center transition-[border-color,background-color] duration-300 md:min-h-[440px]',
        over && 'border-brand-500/80 bg-brand-500/[0.06]',
      )}
    >
      <Ruler />
      <Ruler vertical />

      {/* The sheet on the bed */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-10 -z-10 rounded-lg border border-ink-700/70"
        style={{
          backgroundImage:
            'linear-gradient(115deg, rgb(255 255 255 / 0.035), transparent 40%, rgb(255 255 255 / 0.02) 70%, transparent)',
        }}
      />

      {/* Laser head sweeping the sheet */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-x-10 -z-10 h-px"
        style={{
          background: 'linear-gradient(90deg, transparent, #66ca53 20%, #e4f6df 50%, #66ca53 80%, transparent)',
          boxShadow: '0 0 18px 2px rgb(102 202 83 / 0.6)',
        }}
        animate={{ top: ['14%', '86%', '14%'] }}
        transition={{ duration: busy ? 1.4 : 6, repeat: Infinity, ease: 'easeInOut' }}
      />

      <div className="relative flex size-16 items-center justify-center rounded-2xl bg-brand-500 shadow-[0_0_40px_-8px_rgb(25_74_203_/_0.45)]">
        <FileUp className="size-7 text-ink-950" strokeWidth={1.5} />
      </div>

      <AnimatePresence mode="wait">
        {busy ? (
          <motion.div
            key="busy"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-6"
          >
            <p className="font-display text-2xl font-semibold text-ink-50">{t('Analyzing the job')}</p>
            <BusyStages />
          </motion.div>
        ) : (
          <motion.div key="idle" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-6">
            <p className="font-display text-2xl font-semibold text-ink-50 md:text-[28px]">
              {t('Drop the file your machine already makes')}
            </p>
            <p className="mx-auto mt-2 max-w-md text-[15px] text-ink-300">
              {t('Revalo reads the cut, finds every reusable remnant, and weighs the scrap. No measuring tape, no typing.')}
            </p>
            <button
              type="button"
              onClick={() => input.current?.click()}
              className="mt-7 inline-flex items-center gap-2 rounded-xl bg-brand-500 px-5 py-3 text-[15px] font-semibold text-ink-950 shadow-[0_10px_30px_-10px_rgb(25_74_203_/_0.9)] transition hover:bg-brand-400 active:translate-y-px"
            >
              {t('Choose a file')}
            </button>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
              {[t('DXF nest'), 'G-code', t('CSV cut list')].map((label) => (
                <span key={label} className="rounded-full border border-ink-700 px-3 py-1 font-mono text-[11px] text-ink-300">
                  {label}
                </span>
              ))}
              <span className="font-mono text-[11px] text-ink-500">{t('up to 25 MB')}</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <input
        ref={input}
        type="file"
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) onFile(file)
          e.target.value = ''
        }}
      />
    </div>
  )
}
