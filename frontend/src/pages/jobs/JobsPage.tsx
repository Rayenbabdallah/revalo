import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Inbox } from 'lucide-react'
import { motion } from 'motion/react'
import { Link } from 'wouter'

import { StatusBadge } from '../../components/ui/StatusBadge'
import { listJobs } from '../../lib/api'
import { fmtDateTime, fmtKg, fmtTnd, formatLabel, materialLabel } from '../../lib/format'

export function JobsPage() {
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: listJobs })
  const rows = jobs.data?.jobs ?? []
  const toReview = rows.filter((j) => j.status === 'draft').length

  return (
    <div className="mx-auto max-w-[1480px] px-4 py-8 md:px-10 md:py-12">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Jobs</p>
          <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight">Cutting jobs</h1>
          <p className="mt-2 text-[15px] text-ink-400">
            {rows.length ? `${rows.length} jobs · ${toReview} waiting for review` : 'Every saved upload appears here.'}
          </p>
        </div>
        <Link
          href="/analyze"
          className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-semibold text-ink-950 transition hover:bg-brand-400"
        >
          Upload a job
        </Link>
      </div>

      <section className="panel mt-8 overflow-hidden">
        {jobs.isPending ? (
          <p className="px-6 py-10 font-mono text-sm text-ink-500">Loading jobs…</p>
        ) : jobs.isError ? (
          <p className="px-6 py-10 text-sm text-alarm-400">{jobs.error.message}</p>
        ) : rows.length === 0 ? (
          <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
            <Inbox className="size-8 text-ink-500" strokeWidth={1.5} />
            <p className="font-display text-lg font-semibold">No jobs yet</p>
            <p className="max-w-sm text-[14px] text-ink-400">
              Analyze a file and save it as a job to start building your leftover stock.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left">
              <thead>
                <tr className="border-b border-ink-800 font-mono text-[10.5px] uppercase tracking-[0.14em] text-ink-500">
                  <th className="px-6 py-3 font-normal">File</th>
                  <th className="px-3 py-3 font-normal">Material</th>
                  <th className="px-3 py-3 text-right font-normal">Remnants</th>
                  <th className="px-3 py-3 text-right font-normal">Reusable</th>
                  <th className="px-3 py-3 text-right font-normal">Scrap</th>
                  <th className="px-3 py-3 text-right font-normal">Value</th>
                  <th className="px-3 py-3 font-normal">Status</th>
                  <th className="px-3 py-3 font-normal">Saved</th>
                  <th className="w-10" />
                </tr>
              </thead>
              <tbody>
                {rows.map((job, i) => (
                  <motion.tr
                    key={job.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.03 }}
                    className="group border-b border-ink-800/70 last:border-0 hover:bg-ink-850"
                  >
                    <td className="px-6 py-4">
                      <Link href={`/jobs/${job.id}`} className="block max-w-[320px] truncate font-medium text-ink-50 group-hover:text-brand-300">
                        {job.file_name}
                      </Link>
                      <span className="font-mono text-[11px] text-ink-500">
                        {formatLabel(job.file_format)} · {job.part_count} parts · {job.sheet_count} sheet{job.sheet_count > 1 ? 's' : ''}
                      </span>
                    </td>
                    <td className="px-3 py-4 text-[14px] text-ink-200">
                      {materialLabel(job.material_code)}
                      {job.thickness_mm && <span className="text-ink-500"> · {job.thickness_mm} mm</span>}
                    </td>
                    <td className="readout px-3 py-4 text-right text-ink-200">{job.remnant_count}</td>
                    <td className="readout px-3 py-4 text-right text-reclaim-300">
                      {job.remnant_weight_kg !== null ? `${fmtKg(job.remnant_weight_kg)} kg` : '—'}
                    </td>
                    <td className="readout px-3 py-4 text-right text-rust-400">
                      {job.scrap_weight_kg !== null ? `${fmtKg(job.scrap_weight_kg)} kg` : '—'}
                    </td>
                    <td className="readout px-3 py-4 text-right text-ink-100">
                      {job.recovered.priced_pieces > 0 ? fmtTnd(job.recovered.value_tnd) : '—'}
                    </td>
                    <td className="px-3 py-4">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="px-3 py-4 font-mono text-[12px] text-ink-400">{fmtDateTime(job.created_at)}</td>
                    <td className="pr-5">
                      <Link href={`/jobs/${job.id}`} aria-label={`Open ${job.file_name}`}>
                        <ArrowRight className="size-4 text-ink-600 transition group-hover:translate-x-0.5 group-hover:text-brand-400" />
                      </Link>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
