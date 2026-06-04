import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App/App'
import SWRProvider from './App/SWRProvider'

const rootElement = document.querySelector('#root')
const root = createRoot(rootElement)

root.render(
  <StrictMode>
    <SWRProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </SWRProvider>
  </StrictMode>,
)
