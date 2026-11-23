import { Lock } from 'lucide-react'
import type { ReactNode } from 'react'

import type { Role } from '../../lib/api'
import { ROLE_LABEL, useCan } from '../../lib/auth'
import { t } from '../../lib/i18n'

/** A page only some roles use. Others see who to ask instead of an error. */
export function RequireRole({ min, children }: { min: Role; children: ReactNode }) {
  if (useCan(min)) return children
  return (
    <div className="mx-auto grid max-w-md place-items-center px-6 py-24 text-center">
      <span className="grid size-12 place-items-center rounded-2xl bg-ink-850 text-ink-300">
        <Lock className="size-5" />
      </span>
      <p className="mt-5 font-display text-xl font-semibold text-ink-50">{t('For a {role}', { role: ROLE_LABEL[min].toLowerCase() })}</p>
      <p className="mt-2 text-[14.5px] text-ink-400">
        {t('Your account cannot open this page. Ask your workshop owner if you need it.')}
      </p>
    </div>
  )
}
