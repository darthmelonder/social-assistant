import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { clearAccessToken, setAccessToken } from './api/client';
import ConnectGmail from './components/auth/ConnectGmail';
import LoadingSpinner from './components/common/LoadingSpinner';
import Layout from './components/common/Layout';
import AuthCallbackPage from './pages/AuthCallbackPage';
import InboxPage from './pages/InboxPage';
import ThreadPage from './pages/ThreadPage';
import type { AuthUser } from './types';

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [initializing, setInitializing] = useState(true);

  useEffect(() => {
    // Attempt silent session restore via the httpOnly refresh cookie
    fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'include' })
      .then(r => (r.ok ? r.json() : null))
      .then(async data => {
        if (!data?.access_token) return;
        setAccessToken(data.access_token);
        const me = await fetch('/api/v1/auth/me', {
          headers: { Authorization: `Bearer ${data.access_token}` },
        });
        if (me.ok) setUser(await me.json());
      })
      .catch(() => {})
      .finally(() => setInitializing(false));
  }, []);

  if (initializing) return <LoadingSpinner />;

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/auth/callback" element={<AuthCallbackPage onAuth={setUser} />} />
          {user ? (
            <Route
              path="/"
              element={
                <Layout
                  user={user}
                  onLogout={() => {
                    clearAccessToken();
                    setUser(null);
                  }}
                />
              }
            >
              <Route index element={<InboxPage />} />
              <Route path="threads/:id" element={<ThreadPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          ) : (
            <Route path="*" element={<ConnectGmail />} />
          )}
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
