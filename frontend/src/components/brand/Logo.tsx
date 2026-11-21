import clsx from 'clsx'
import { useId } from 'react'

/** A sheet with a clean remnant set aside in its corner. */
export function LogoMark({ className }: { className?: string }) {
  // Unique per instance: a gradient inside a hidden SVG cannot be referenced elsewhere.
  const gradient = `rv-steel-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
  return (
    <svg viewBox="0 0 32 32" className={clsx('shrink-0', className)} aria-hidden="true">
      <defs>
        <linearGradient id={gradient} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#c5c9d1" />
          <stop offset="1" stopColor="#6f7684" />
        </linearGradient>
      </defs>
      <path d="M5 5h22v13h-9v9H5z" fill={`url(#${gradient})`} />
      <rect x="20" y="20" width="7" height="7" rx="1.2" fill="#c8f169" />
    </svg>
  )
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={clsx('inline-flex items-center gap-2.5', className)}>
      <LogoMark className="size-7" />
      <span className="font-display text-[19px] font-semibold tracking-[-0.02em] text-graphite-50">
        revalo
      </span>
    </span>
  )
}
