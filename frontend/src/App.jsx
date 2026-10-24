
import { useAuth } from 'react-oidc-context'

const cognitoDomain = 'https://ap-southeast-2wi1ngah1k.auth.ap-southeast-2.amazoncognito.com'
const clientId = '5tv0jne3t88vcrc5408vrtnl6s'

function App() {
  const auth = useAuth()

  async function handleLogout() {
    await auth.removeUser()

    const logoutUrl = new URL(`${cognitoDomain}/logout`)
    logoutUrl.searchParams.set('client_id', clientId)
    logoutUrl.searchParams.set('logout_uri', 'http://localhost:5173')

    window.location.assign(logoutUrl.toString())
  }

  if (auth.isLoading) {
    return <p>Checking authentication...</p>
  }

  if (auth.error) {
    return <p>Authentication error: {auth.error.message}</p>
  }

  return (
    <main>
      <h1>Aussie EcoGuard</h1>
      <p>Invasive Pest & Pet Monitoring Platform</p>

      {auth.isAuthenticated ? (
        <div>
          <h2>Welcome!</h2>
          <p>Signed in as: {auth.user?.profile.email}</p>
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
