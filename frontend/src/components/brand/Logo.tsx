import clsx from 'clsx'

/** The brand icon on its blue tile, as on the brand charter. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={clsx('grid shrink-0 place-items-center rounded-[28%] bg-brand-500 p-[16%]', className)}
    >
      <img src="/brand/revalo-icon.png" alt="" className="size-full object-contain" draggable={false} />
    </span>
  )
}

/** The main logo: blue mark, green wordmark. `tone` picks the white or black variant. */
export function Wordmark({ className, tone = 'color' }: { className?: string; tone?: 'color' | 'white' | 'black' }) {
  const src = {
    color: '/brand/revalo-logo.png',
    white: '/brand/revalo-logo-white.png',
    black: '/brand/revalo-logo-black.png',
  }[tone]
  return <img src={src} alt="Revalo" className={clsx('h-7 w-auto', className)} draggable={false} />
}
