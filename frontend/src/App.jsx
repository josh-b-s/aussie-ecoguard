
import { useAuth } from 'react-oidc-context'
import Dashboard from './Dashboard.jsx'

const cognitoDomain = 'https://ap-southeast-2wi1ngah1k.auth.ap-southeast-2.amazoncognito.com'
const clientId = '5tv0jne3t88vcrc5408vrtnl6s'

function App() {
  const auth = useAuth()

  async function handleLogout() {
    await auth.removeUser()

    const logoutUrl = new URL(`${cognitoDomain}/logout`)
    logoutUrl.searchParams.set('client_id', clientId)
    logoutUrl.searchParams.set('logout_uri', window.location.origin)

    window.location.assign(logoutUrl.toString())
  }

  if (auth.isLoading) {
    return <p>Checking authentication...</p>
  }

  if (auth.error) {
    return <p>Authentication error: {auth.error.message}</p>
  }

  return (
    <main className={auth.isAuthenticated ? 'dashboard-layout' : 'login-layout'}>
      <h1>Aussie EcoGuard</h1>
      <p>Invasive Pest & Pet Monitoring Platform</p>

      
{auth.isAuthenticated ? (
  <div>
    <Dashboard
  email={auth.user?.profile.email}
  idToken={auth.user?.id_token}
/>
    <button onClick={handleLogout}>
      Log out
    </button>
  </div>
) : (
  <div>
    <p>Please sign in to continue.</p>
    <button onClick={() => auth.signinRedirect()}>
      Login with Cognito
    </button>
  </div>
)}

    </main>
  )
}

export default App
