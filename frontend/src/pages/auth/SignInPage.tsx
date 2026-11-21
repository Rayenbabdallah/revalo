import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Eye, EyeOff, QrCode, Recycle, ScanLine } from 'lucide-react'
import { motion } from 'motion/react'
import { useId, useState, type ReactNode } from 'react'

import { Wordmark } from '../../components/brand/Logo'
import { setupWorkshop, signIn, type Me } from '../../lib/api'

const PROOF = [
  { icon: ScanLine, text: 'Remnants and scrap found in your CNC files, weighed and priced.' },
  { icon: QrCode, text: 'Every offcut labelled, approved and traceable on the rack.' },
  { icon: Recycle, text: 'Reuse, sell or recycle: the best outcome in TND and CO₂.' },
]

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: (id: string) => ReactNode
}) {
  const id = useId()
  return (
    <div>
      <label htmlFor={id} className="text-[13px] font-medium text-ink-200">
        {label}
      </label>
      <div className="mt-1.5">{children(id)}</div>
      {hint && <p className="mt-1 text-[12px] text-ink-500">{hint}</p>}
    </div>
  )
}

const INPUT =
  'w-full rounded-xl border border-ink-700 bg-ink-950 px-3.5 py-2.5 text-[15px] text-ink-50 placeholder:text-ink-500 focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-500/15'

function PasswordInput({
  id,
  value,
  onChange,
  autoComplete,
}: {
  id: string
  value: string
  onChange: (v: string) => void
  autoComplete: string
}) {
  const [shown, setShown] = useState(false)
  return (
    <div className="relative">
      <input
        id={id}
        type={shown ? 'text' : 'password'}
        required
        minLength={autoComplete === 'new-password' ? 8 : undefined}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        className={`${INPUT} pr-11`}
      />
      <button
        type="button"
        onClick={() => setShown((s) => !s)}
        aria-label={shown ? 'Hide password' : 'Show password'}
        className="absolute inset-y-0 right-0 grid w-11 place-items-center text-ink-400 hover:text-ink-100"
      >
        {shown ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  )
}

/** Sign in, or on a fresh install, create the workshop and its owner. */
export function SignInPage({ me }: { me: Me }) {
  const setup = me.setup_required
  const queryClient = useQueryClient()
  const [workshop, setWorkshop] = useState(me.workshop.name === 'Pilot workshop' ? '' : me.workshop.name)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const submit = useMutation({
    mutationFn: () =>
      setup
        ? setupWorkshop({ workshop_name: workshop || undefined, name, email, password })
        : signIn(email, password),
    onSuccess: (result) => {
      // Data loaded for someone else (or for nobody) must not show to this person.
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== 'me' })
      queryClient.setQueryData(['me'], result)
    },
  })

  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      <aside className="stage relative hidden overflow-hidden !rounded-none p-12 lg:flex lg:flex-col">
        {/* A faint sheet grid, like a nest on the cutting table. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 opacity-[0.13]"
          style={{
            backgroundImage:
              'linear-gradient(rgb(255 255 255 / 0.6) 1px, transparent 1px), linear-gradient(90deg, rgb(255 255 255 / 0.6) 1px, transparent 1px)',
            backgroundSize: '44px 44px',
            maskImage: 'radial-gradient(90% 80% at 30% 40%, black, transparent)',
          }}
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-24 -right-16 h-80 w-96 rotate-[-8deg] rounded-[28px] border-2 border-reclaim-400/70 bg-reclaim-400/15 shadow-[0_0_80px_rgb(102_202_83_/_0.35)]"
        />
        <Wordmark tone="white" className="relative h-9 self-start" />
        <div className="relative mt-auto max-w-lg">
          <h1 className="font-display text-[44px] font-semibold leading-[1.05] tracking-tight text-ink-950">
            Every offcut,
            <br />
            <span className="text-reclaim-400">on the record.</span>
          </h1>
          <ul className="mt-8 space-y-4">
            {PROOF.map(({ icon: Icon, text }, i) => (
              <motion.li
                key={text}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.15 + i * 0.1 }}
                className="flex items-start gap-3 text-[15px] leading-snug text-ink-950/85"
              >
                <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-ink-950/12 ring-1 ring-ink-950/20">
                  <Icon className="size-4 text-reclaim-400" />
                </span>
                {text}
              </motion.li>
            ))}
          </ul>
        </div>
      </aside>

      <main className="flex items-center justify-center px-5 py-12">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="w-full max-w-[400px]"
        >
          <Wordmark className="mb-10 h-8 lg:hidden" />
          <p className="eyebrow">{setup ? 'First start' : me.workshop.name}</p>
          <h2 className="mt-2 font-display text-[30px] font-semibold tracking-tight text-ink-50">
            {setup ? 'Set up your workshop' : 'Sign in'}
          </h2>
          <p className="mt-2 text-[14.5px] text-ink-400">
            {setup
              ? 'You will be the owner. Add your managers and operators after.'
              : 'Use the email and password your workshop owner gave you.'}
          </p>

          <form
            className="mt-8 space-y-4"
            onSubmit={(e) => {
              e.preventDefault()
              submit.mutate()
            }}
          >
            {setup && (
              <>
                <Field label="Workshop name">
                  {(id) => (
                    <input
                      id={id}
                      value={workshop}
                      onChange={(e) => setWorkshop(e.target.value)}
                      placeholder="Atelier Ben Arous"
                      autoComplete="organization"
                      className={INPUT}
                    />
                  )}
                </Field>
                <Field label="Your name">
                  {(id) => (
                    <input
                      id={id}
                      required
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      autoComplete="name"
                      className={INPUT}
                    />
                  )}
                </Field>
              </>
            )}
            <Field label="Email">
              {(id) => (
                <input
                  id={id}
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="username"
                  className={INPUT}
                />
              )}
            </Field>
            <Field label="Password" hint={setup ? 'At least 8 characters.' : undefined}>
              {(id) => (
                <PasswordInput
                  id={id}
                  value={password}
                  onChange={setPassword}
                  autoComplete={setup ? 'new-password' : 'current-password'}
                />
              )}
            </Field>

            {submit.isError && (
              <p role="alert" className="rounded-xl bg-alarm-400/10 px-3.5 py-2.5 text-[13.5px] text-alarm-400">
                {submit.error.message}
              </p>
            )}

            <button
              type="submit"
              disabled={submit.isPending}
              className="group mt-2 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand-500 px-5 py-3 text-[15px] font-semibold text-ink-950 shadow-[0_12px_30px_-12px_rgb(25_74_203_/_0.9)] transition hover:bg-brand-400 disabled:opacity-60"
            >
              {submit.isPending ? 'One moment…' : setup ? 'Create workshop' : 'Sign in'}
              <ArrowRight className="size-4 transition group-hover:translate-x-0.5" />
            </button>
          </form>
          {!setup && (
            <p className="mt-6 text-[12.5px] text-ink-500">Forgot your password? Ask your workshop owner to reset it.</p>
          )}
        </motion.div>
      </main>
    </div>
  )
}
