import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowLeft, Printer } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'wouter'

import { QrCode } from '../../components/ui/QrCode'
import { getJob, type Piece } from '../../lib/api'
import { fmtDate, fmtKg, fmtMm, materialLabel } from '../../lib/format'

type LabelFormat = 'thermal' | 'a4'

const PRINT_CSS: Record<LabelFormat, string> = {
  // One 50 x 30 mm label per page: common thermal label printers (Xprinter, Zebra, Brother).
  thermal: '@page { size: 50mm 30mm; margin: 0 } .label-sheet { display: block } .label { break-after: page }',
  // 3 x 7 labels of 63.5 x 38.1 mm on A4 sticker sheets.
  a4: '@page { size: A4; margin: 15mm 7mm } .label-sheet { display: grid; grid-template-columns: repeat(3, 63.5mm); gap: 0 2.5mm }',
}

function Label({ piece, format }: { piece: Piece; format: LabelFormat }) {
  const remnant = piece.kind === 'remnant'
  return (
    <div
      className={clsx(
        'label flex items-center gap-[2.5mm] overflow-hidden bg-white p-[2mm] text-black',
        format === 'thermal' ? 'h-[30mm] w-[50mm]' : 'h-[38.1mm] w-[63.5mm]',
      )}
    >
      <QrCode value={piece.label_url} className={format === 'thermal' ? 'size-[24mm] shrink-0' : 'size-[30mm] shrink-0'} />
      <div className="min-w-0 leading-tight">
        <p className="font-mono text-[9pt] font-medium tracking-tight">{piece.code}</p>
        <p className="mt-[1mm] font-mono text-[8pt] font-medium">
          {remnant ? `${fmtMm(piece.width_mm ?? 0)}×${fmtMm(piece.height_mm ?? 0)}` : 'SCRAP LOT'}
        </p>
        <p className="mt-[0.5mm] truncate text-[6.5pt]">
          {materialLabel(piece.material_code)}
          {piece.thickness_mm ? ` ${piece.thickness_mm}mm` : ''}
        </p>
        {piece.weight_kg !== null && <p className="text-[6.5pt]">{fmtKg(piece.weight_kg)} kg</p>}
        <p className="mt-[0.5mm] text-[5.5pt] text-neutral-600">revalo · {fmtDate(piece.updated_at)}</p>
      </div>
    </div>
  )
}

export function LabelsPage({ id }: { id: string }) {
  const job = useQuery({ queryKey: ['job', id], queryFn: () => getJob(id) })
  const [format, setFormat] = useState<LabelFormat>('thermal')
  const pieces = (job.data?.pieces ?? []).filter((p) => p.status !== 'rejected' && p.status !== 'draft')

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8 md:px-10">
      <style>{`@media print { ${PRINT_CSS[format]} }`}</style>
      <div className="no-print">
        <Link href={`/jobs/${id}`} className="inline-flex items-center gap-1.5 text-[13px] text-ink-400 hover:text-ink-100">
          <ArrowLeft className="size-4" /> Back to job
        </Link>
        <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="eyebrow">QR labels</p>
            <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight">{job.data?.file_name ?? 'Labels'}</h1>
            <p className="mt-1.5 text-[14px] text-ink-400">
              {pieces.length} label{pieces.length === 1 ? '' : 's'}. Each QR opens the piece's record, so anyone at the
              rack can see its size, weight and history.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex rounded-xl border border-ink-700 p-1">
              {([
                ['thermal', 'Thermal 50×30'],
                ['a4', 'A4 sheet'],
              ] as const).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setFormat(value)}
                  className={clsx(
                    'rounded-lg px-3 py-1.5 text-[13px] font-medium transition',
                    format === value ? 'bg-ink-700 text-ink-50' : 'text-ink-400 hover:text-ink-100',
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => window.print()}
              disabled={!pieces.length}
              className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-semibold text-ink-950 transition hover:bg-brand-400 disabled:opacity-50"
            >
              <Printer className="size-4" /> Print
            </button>
          </div>
        </div>
        {job.data && job.data.status !== 'approved' && (
          <p className="mt-6 rounded-xl border border-brand-500/30 bg-brand-500/5 px-4 py-3 text-[14px] text-brand-300">
            Labels are printed after the batch is approved.
          </p>
        )}
      </div>

      <div className="print-area mt-8">
        <div className="label-sheet flex flex-wrap gap-4">
          {pieces.map((p) => (
            <div key={p.id} className="rounded-sm shadow-[0_8px_30px_-10px_rgb(0_0_0_/_0.8)] print:shadow-none">
              <Label piece={p} format={format} />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
