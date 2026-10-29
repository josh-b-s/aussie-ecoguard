
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { AuthProvider } from 'react-oidc-context'
import App from './App.jsx'
import './index.css'

const cognitoConfig = {
  authority: 'https://cognito-idp.ap-southeast-2.amazonaws.com/ap-southeast-2_WI1ngaH1k',
  client_id: '5tv0jne3t88vcrc5408vrtnl6s',
  redirect_uri: window.location.origin,
  response_type: 'code',
  scope: 'openid email',
  onSigninCallback: () => {
    window.history.replaceState({}, document.title, window.location.pathname)
  },
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AuthProvider {...cognitoConfig}>
      <App />
    </AuthProvider>
  </StrictMode>,
)
