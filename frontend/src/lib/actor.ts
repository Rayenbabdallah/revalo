import { useState } from 'react'

/**
 * Who is using this device, recorded on every correction and approval.
 * Kept per device until accounts exist; storage can fail (private mode), so
 * every access is guarded and the app works without it.
 */
const KEY = 'revalo.actor'

function read(): string {
  try {
    return localStorage.getItem(KEY) || 'Manager'
  } catch {
    return 'Manager'
  }
}

export function useActor(): [string, (name: string) => void] {
  const [actor, setActor] = useState(read)
  const update = (name: string) => {
    const value = name.trim().slice(0, 120) || 'Manager'
    setActor(value)
    try {
      localStorage.setItem(KEY, value)
    } catch {
      /* not persisted; still used for this session */
    }
  }
  return [actor, update]
}
