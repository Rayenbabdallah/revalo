import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { getMe } from '../../lib/api'
import { UserContext } from '../../lib/auth'
import { SignInPage } from '../../pages/auth/SignInPage'
import { LogoMark } from '../brand/Logo'

/** Shows the sign-in screen until someone is signed in, then the app as them. */
export function AuthGate({ children }: { children: ReactNode }) {
  const me = useQuery({ queryKey: ['me'], queryFn: getMe, staleTime: 5 * 60_000 })

  if (me.isPending) {
    return (
      <div className="grid min-h-screen place-items-center">
        <LogoMark className="size-12 animate-pulse" />
      </div>
    )
  }
  if (me.isError) {
    return (
      <div className="grid min-h-screen place-items-center px-6 text-center">
        <div>
          <LogoMark className="mx-auto size-12" />
          <p className="mt-5 text-[15px] text-ink-200">{me.error.message}</p>
          <button
            type="button"
            onClick={() => me.refetch()}
            className="mt-4 rounded-xl border border-ink-700 px-4 py-2 text-[14px] font-medium text-ink-100 hover:border-brand-500"
          >
            Try again
          </button>
        </div>
      </div>
    )
  }
  if (!me.data.user) return <SignInPage me={me.data} />
  return <UserContext.Provider value={me.data.user}>{children}</UserContext.Provider>
}
