// Auth0 sign-in (Universal Login: passwords are typed on Auth0's page, never in our app).
// Guests never need this; signed-in users can save fields, keep history and get alerts.
import { Auth0Provider, useAuth0 } from '@auth0/auth0-react'
import { createContext, useContext, useMemo, type ReactNode } from 'react'

const DOMAIN = import.meta.env.VITE_AUTH0_DOMAIN as string | undefined
const CLIENT_ID = import.meta.env.VITE_AUTH0_CLIENT_ID as string | undefined
const AUDIENCE = import.meta.env.VITE_AUTH0_AUDIENCE as string | undefined

export type Session = {
  configured: boolean
  loading: boolean
  signedIn: boolean
  email?: string
  name?: string
  /** returnTo: app state restored after Auth0 sends the user back (e.g. a pending save). */
  login: (options?: { signup?: boolean; returnTo?: string }) => void
  logout: () => void
  token: () => Promise<string | null>
}

const Off: Session = {
  configured: false,
  loading: false,
  signedIn: false,
  login: () => window.alert('Sign-in is not set up on this copy of SowSmart. You can keep using it as a guest.'),
  logout: () => undefined,
  token: async () => null,
}

const SessionContext = createContext<Session>(Off)

export function useSession() {
  return useContext(SessionContext)
}

export function SessionProvider({ children, onReturn }: { children: ReactNode; onReturn: (returnTo?: string) => void }) {
  if (!DOMAIN || !CLIENT_ID || !AUDIENCE) {
    return <SessionContext.Provider value={Off}>{children}</SessionContext.Provider>
  }
  return (
    <Auth0Provider
      domain={DOMAIN}
      clientId={CLIENT_ID}
      authorizationParams={{ redirect_uri: window.location.origin, audience: AUDIENCE, scope: 'openid profile email' }}
      cacheLocation="localstorage"
      onRedirectCallback={(appState) => {
        window.history.replaceState(null, '', window.location.pathname)
        onReturn(appState?.returnTo as string | undefined)
      }}
    >
      <Bridge>{children}</Bridge>
    </Auth0Provider>
  )
}

function Bridge({ children }: { children: ReactNode }) {
  const { isLoading, isAuthenticated, user, loginWithRedirect, logout, getAccessTokenSilently } = useAuth0()
  const value = useMemo<Session>(
    () => ({
      configured: true,
      loading: isLoading,
      signedIn: isAuthenticated,
      email: user?.email,
      name: user?.name,
      login: ({ signup, returnTo } = {}) =>
        void loginWithRedirect({
          authorizationParams: signup ? { screen_hint: 'signup' } : {},
          appState: { returnTo },
        }),
      logout: () => void logout({ logoutParams: { returnTo: window.location.origin } }),
      token: async () => {
        if (!isAuthenticated) return null
        try {
          return (await getAccessTokenSilently()) ?? null
        } catch {
          return null
        }
      },
    }),
    [isLoading, isAuthenticated, user, loginWithRedirect, logout, getAccessTokenSilently],
  )
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
