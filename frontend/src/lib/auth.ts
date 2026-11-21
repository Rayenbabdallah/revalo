import { createContext, useContext } from 'react'

import type { Role, User } from './api'

const RANK: Record<Role, number> = { operator: 1, manager: 2, owner: 3 }

export const ROLE_LABEL: Record<Role, string> = {
  operator: 'Operator',
  manager: 'Manager',
  owner: 'Owner',
}

export const ROLE_HINT: Record<Role, string> = {
  operator: 'Uploads jobs, measures and moves pieces, takes remnants for new jobs.',
  manager: 'Also approves records, sells, books pickups, sets prices and machines.',
  owner: 'Everything, plus who has an account.',
}

/** The signed-in person. Set by AuthGate, so every page inside the app has one. */
export const UserContext = createContext<User | null>(null)

export function useUser(): User {
  const user = useContext(UserContext)
  if (!user) throw new Error('useUser is only available inside AuthGate')
  return user
}

export function atLeast(role: Role, min: Role): boolean {
  return RANK[role] >= RANK[min]
}

/** Whether the signed-in person may do what `min` and above may do. */
export function useCan(min: Role): boolean {
  const user = useContext(UserContext)
  return user !== null && atLeast(user.role, min)
}
