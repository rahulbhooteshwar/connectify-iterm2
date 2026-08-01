import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'
import { StoreProvider } from './store'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <StoreProvider>
      <App />
    </StoreProvider>
  </React.StrictMode>,
)

// PWA: lets the app install as a desktop window and start instantly.
// The worker only caches hashed assets - the API always hits the server.
if ('serviceWorker' in navigator && !import.meta.env.DEV) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}
