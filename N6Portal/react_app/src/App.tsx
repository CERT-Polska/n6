import { FC, Suspense } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClientProvider, QueryClient } from 'react-query';
import { ErrorBoundary } from 'react-error-boundary';
import Keycloak from 'keycloak-js';
import { ReactQueryDevtools } from 'react-query/devtools';
import { MatchMediaContextProvider } from 'context/MatchMediaContext';
import ErrorBoundaryFallback from 'components/errors/ErrorBoundaryFallback';
import { KeycloakStub } from 'api/auth';
import { LanguageProvider } from 'context/LanguageProvider';
import { AuthContextProvider } from 'context/AuthContext';
import { LoginContextProvider } from 'context/LoginContext';
import RoutesProvider from 'routes/RoutesProvider';
import Loader from 'components/loading/Loader';
import Header from 'components/layout/Header';
import Footer from 'components/layout/Footer';
import { ForgotPasswordContextProvider } from 'context/ForgotPasswordContext';
import { UserSettingsMfaContextProvider } from 'context/UserSettingsMfaContext';
import { KeycloakContextProvider } from 'context/KeycloakContext';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      refetchOnMount: false,
      retry: 1
    }
  }
});

const isOidcEnabled =
  typeof process.env.REACT_APP_OIDC_AUTH_ENABLED === 'string'
    ? JSON.parse(process.env.REACT_APP_OIDC_AUTH_ENABLED)
    : false;
export const keycloak = isOidcEnabled ? new Keycloak() : new KeycloakStub();

const App: FC = () => (
  <BrowserRouter>
    <ErrorBoundary FallbackComponent={ErrorBoundaryFallback} onReset={() => window.location.reload()}>
      <LanguageProvider>
        <QueryClientProvider client={queryClient}>
          <MatchMediaContextProvider>
            <KeycloakContextProvider keycloak={keycloak}>
              <AuthContextProvider>
                <LoginContextProvider>
                  <ForgotPasswordContextProvider>
                    <UserSettingsMfaContextProvider>
                      <Header />
                      <main className="page-container">
                        <Suspense fallback={<Loader />}>
                          <RoutesProvider />
                        </Suspense>
                      </main>
                      <Footer />
                    </UserSettingsMfaContextProvider>
                  </ForgotPasswordContextProvider>
                </LoginContextProvider>
              </AuthContextProvider>
            </KeycloakContextProvider>
          </MatchMediaContextProvider>
          <ReactQueryDevtools />
        </QueryClientProvider>
      </LanguageProvider>
    </ErrorBoundary>
  </BrowserRouter>
);

export default App;
