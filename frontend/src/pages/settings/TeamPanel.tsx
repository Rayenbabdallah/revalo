import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { KeyRound, Plus, RefreshCw, UserMinus, UserPlus } from 'lucide-react'
import { useState } from 'react'

import { addUser, listUsers, updateUser, type Role, type User } from '../../lib/api'
import { ROLE_HINT, ROLE_LABEL, useUser } from '../../lib/auth'
import { fmtDateTime } from '../../lib/format'
import { t } from '../../lib/i18n'

const ROLES: Role[] = ['operator', 'manager', 'owner']

const INPUT =
  'w-full rounded-xl border border-ink-700 bg-ink-950 px-3 py-2 text-[14px] text-ink-50 focus:border-brand-500 focus:outline-none'

/** A temporary password that is easy to read out loud: no 0/O or 1/l. */
function temporaryPassword() {
  const alphabet = 'abcdefghijkmnpqrstuvwxyz23456789'
  const bytes = crypto.getRandomValues(new Uint8Array(12))
  const chars = Array.from(bytes, (b) => alphabet[b % alphabet.length])
  return `${chars.slice(0, 4).join('')}-${chars.slice(4, 8).join('')}-${chars.slice(8).join('')}`
}

function AddPerson({ onDone }: { onDone: () => void }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Role>('operator')
  const [password, setPassword] = useState(temporaryPassword)
  const add = useMutation({
    mutationFn: () => addUser({ name, email, role, password }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      onDone()
    },
  })

  return (
    <form
      className="panel grid gap-4 p-5 md:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault()
        add.mutate()
      }}
    >
      <label className="text-[13px] font-medium text-ink-200">
        {t('Name')}
        <input required value={name} onChange={(e) => setName(e.target.value)} className={clsx(INPUT, 'mt-1.5')} />
      </label>
      <label className="text-[13px] font-medium text-ink-200">
        {t('Email')}
        <input
          required
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={clsx(INPUT, 'mt-1.5')}
        />
      </label>
      <label className="text-[13px] font-medium text-ink-200">
        {t('Role')}
        <select value={role} onChange={(e) => setRole(e.target.value as Role)} className={clsx(INPUT, 'mt-1.5')}>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABEL[r]}
            </option>
          ))}
        </select>
        <span className="mt-1 block text-[12px] font-normal text-ink-500">{ROLE_HINT[role]}</span>
      </label>
      <label className="text-[13px] font-medium text-ink-200">
        {t('Temporary password')}
        <span className="mt-1.5 flex gap-2">
          <input
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={clsx(INPUT, 'readout')}
          />
          <button
            type="button"
            onClick={() => setPassword(temporaryPassword())}
            aria-label={t('New temporary password')}
            className="grid w-10 shrink-0 place-items-center rounded-xl border border-ink-700 text-ink-300 hover:border-brand-500"
          >
            <RefreshCw className="size-4" />
          </button>
        </span>
        <span className="mt-1 block text-[12px] font-normal text-ink-500">
          {t('Give it to them in person. They can change it under Account.')}
        </span>
      </label>
      {add.isError && <p className="text-[13px] text-alarm-400 md:col-span-2">{add.error.message}</p>}
      <div className="flex gap-2 md:col-span-2">
        <button
          type="submit"
          disabled={add.isPending}
          className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-[14px] font-semibold text-ink-950 hover:bg-brand-400 disabled:opacity-60"
        >
          <UserPlus className="size-4" /> {t('Add to the team')}
        </button>
        <button type="button" onClick={onDone} className="rounded-xl px-4 py-2.5 text-[14px] text-ink-400 hover:text-ink-100">
          {t('Cancel')}
        </button>
      </div>
    </form>
  )
}

function PersonRow({ person, isMe }: { person: User; isMe: boolean }) {
  const queryClient = useQueryClient()
  const [newPassword, setNewPassword] = useState<string | null>(null)
  const change = useMutation({
    mutationFn: (body: Parameters<typeof updateUser>[1]) => updateUser(person.id, body),
    onSuccess: (_user, body) => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      if (isMe) queryClient.invalidateQueries({ queryKey: ['me'] })
      if (body.password) setNewPassword(body.password)
    },
  })

  return (
    <li className={clsx('grid gap-3 px-5 py-4 md:grid-cols-[1.4fr_11rem_1fr_9.5rem] md:items-center', !person.active && 'opacity-55')}>
      <div className="min-w-0">
        <p className="truncate text-[14.5px] font-semibold text-ink-50">
          {person.name}
          {isMe && <span className="ms-2 text-[12px] font-normal text-ink-400">{t('(you)')}</span>}
        </p>
        <p className="truncate text-[12.5px] text-ink-400">{person.email}</p>
      </div>
      <select
        value={person.role}
        disabled={!person.active || change.isPending}
        onChange={(e) => change.mutate({ role: e.target.value as Role })}
        aria-label={`Role of ${person.name}`}
        className={INPUT}
      >
        {ROLES.map((r) => (
          <option key={r} value={r}>
            {ROLE_LABEL[r]}
          </option>
        ))}
      </select>
      <p className="text-[12.5px] text-ink-400">
        {person.active
          ? person.last_login_at
            ? t('Last sign-in {date}', { date: fmtDateTime(person.last_login_at) })
            : t('Has not signed in yet')
          : t('No access')}
      </p>
      <div className="flex gap-1.5 md:justify-end">
        {person.active && (
          <button
            type="button"
            onClick={() => change.mutate({ password: temporaryPassword() })}
            title={t('Reset password')}
            aria-label={`Reset the password of ${person.name}`}
            className="grid size-9 place-items-center rounded-xl border border-ink-700 text-ink-300 hover:border-brand-500"
          >
            <KeyRound className="size-4" />
          </button>
        )}
        {!isMe && (
          <button
            type="button"
            onClick={() => change.mutate({ active: !person.active })}
            className={clsx(
              'inline-flex h-9 items-center gap-1.5 rounded-xl border px-3 text-[13px]',
              person.active
                ? 'border-ink-700 text-ink-300 hover:border-alarm-400 hover:text-alarm-400'
                : 'border-ink-700 text-ink-200 hover:border-brand-500',
            )}
          >
            {person.active ? (
              <>
                <UserMinus className="size-4" /> {t('Remove')}
              </>
            ) : (
              t('Restore')
            )}
          </button>
        )}
      </div>
      {newPassword && (
        <p className="rounded-xl bg-reclaim-400/12 px-3 py-2 text-[13px] text-ink-100 md:col-span-4">
          {t('New password for {name}:', { name: person.name })} <span className="readout font-semibold">{newPassword}</span>.{' '}
          {t('They are signed out everywhere until they use it.')}
        </p>
      )}
      {change.isError && <p className="text-[13px] text-alarm-400 md:col-span-4">{change.error.message}</p>}
    </li>
  )
}

/** The owner decides who has an account and what they may do. */
export function TeamPanel() {
  const me = useUser()
  const users = useQuery({ queryKey: ['users'], queryFn: listUsers })
  const [adding, setAdding] = useState(false)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <p className="max-w-2xl text-[14.5px] text-ink-400">
          {t('Operators record jobs and pieces; managers approve, sell and price; owners also manage the team. Every record keeps the name of who made it.')}
        </p>
        {!adding && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-[14px] font-semibold text-ink-950 hover:bg-brand-400"
          >
            <Plus className="size-4" /> {t('Add a person')}
          </button>
        )}
      </div>
      {adding && <AddPerson onDone={() => setAdding(false)} />}
      {users.isPending ? (
        <p className="font-mono text-sm text-ink-500">{t('Loading the team…')}</p>
      ) : users.isError ? (
        <p className="text-sm text-alarm-400">{users.error.message}</p>
      ) : (
        <ul className="panel divide-y divide-ink-800 overflow-hidden p-0">
          {users.data.users.map((u) => (
            <PersonRow key={u.id} person={u} isMe={u.id === me.id} />
          ))}
        </ul>
      )}
    </div>
  )
}
