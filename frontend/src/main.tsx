import '@fontsource/montserrat/600.css'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/ibm-plex-sans-arabic/400.css'
import '@fontsource/ibm-plex-sans-arabic/500.css'
import '@fontsource/ibm-plex-sans-arabic/600.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import './index.css'

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App.tsx'
import { ApiError } from './lib/api'
import { applyDocumentLocale } from './lib/i18n'

// A 401 means the sign-in ended (expired, or removed by the owner): ask again.
const onError = (error: Error) => {
  if (error instanceof ApiError && error.status === 401) queryClient.invalidateQueries({ queryKey: ['me'] })
}

// Retry once when the server is unreachable or failing, never when it said no.
const retry = (count: number, error: Error) =>
  count < 1 && !(error instanceof ApiError && error.status >= 400 && error.status < 500)

const queryClient: QueryClient = new QueryClient({
  defaultOptions: { queries: { retry, refetchOnWindowFocus: false } },
  queryCache: new QueryCache({ onError }),
  mutationCache: new MutationCache({
    onError,
    // Any change (approve, sell, pickup...) can open or close an alert.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  }),
})

applyDocumentLocale()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
