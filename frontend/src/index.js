import { StrictMode } from 'react'
import ReactDOM from 'react-dom'
import { BrowserRouter } from 'react-router-dom'

import App from './App/App'
import SWRProvider from './App/SWRProvider'

ReactDOM.render(
  <StrictMode>
    <SWRProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </SWRProvider>
  </StrictMode>,
  document.querySelector('#root'),
)
