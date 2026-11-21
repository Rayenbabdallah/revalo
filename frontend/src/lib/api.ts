/** Typed client for the Revalo API. All calls go through the /api dev proxy. */

const BASE = import.meta.env.VITE_API_URL ?? '/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, init)
  } catch {
    throw new ApiError(0, 'The Revalo server cannot be reached.')
  }
  if (!response.ok) {
    let message = response.statusText
    try {
      const body = await response.json()
      message = typeof body.detail === 'string' ? body.detail : message
    } catch {
      /* keep status text */
    }
    throw new ApiError(response.status, message)
  }
  return response.json() as Promise<T>
}

export interface Health {
  status: string
  version: string
}

export const getHealth = () => request<Health>('/health')
