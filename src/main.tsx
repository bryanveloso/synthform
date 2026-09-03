import gsap from 'gsap'
import Flip from 'gsap/Flip'
import { useGSAP } from '@gsap/react'
import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import { RouterProvider, createRouter } from '@tanstack/react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { routeTree } from './routeTree.gen'
import { preloadSounds } from './lib/audio-preloader'
import { connectRealtime } from './store/wiring'
import { connectMicStatus } from './lib/mic-status-adapter'

import './index.css'

const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

const queryClient = new QueryClient()

gsap.registerPlugin(Flip)
gsap.registerPlugin(useGSAP)

preloadSounds()

// Open the realtime transport and wire it into the store. Previously this ran
// as a side effect of importing the store; doing it explicitly here keeps the
// store import pure (and testable).
connectRealtime()
connectMicStatus()

const rootElement = document.getElementById('root')!
if (!rootElement.innerHTML) {
  const root = ReactDOM.createRoot(rootElement)
  root.render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </StrictMode>
  )
}
