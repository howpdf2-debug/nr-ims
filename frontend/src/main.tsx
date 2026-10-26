import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { isChunkLoadError, reloadOnce } from './lib/chunkReload'

// A tab opened before a deploy still asks for the old hashed chunk names: reload once to pick up the new build.
window.addEventListener('vite:preloadError', (event) => {
  if (reloadOnce()) event.preventDefault()
})
window.addEventListener('unhandledrejection', (event) => {
  if (isChunkLoadError(event.reason)) reloadOnce()
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
