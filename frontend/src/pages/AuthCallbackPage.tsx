import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { setAccessToken } from '../api/client';
import LoadingSpinner from '../components/common/LoadingSpinner';
import ErrorMessage from '../components/common/ErrorMessage';
import type { AuthUser } from '../types';

interface Props {
  onAuth: (user: AuthUser) => void;
}

export default function AuthCallbackPage({ onAuth }: Props) {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const state = params.get('state') ?? '';

    if (!code) {
      setError('No authorization code received. Please try signing in again.');
      return;
    }

    // Exchange the code via the backend callback endpoint
    fetch(`/api/v1/auth/google/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`)
      .then(r => (r.ok ? r.json() : Promise.reject(new Error('Authentication failed'))))
      .then((data: { access_token: string; user: AuthUser }) => {
        setAccessToken(data.access_token);
        onAuth(data.user);
        navigate('/', { replace: true });
      })
      .catch(() => setError('Authentication failed. Please try again.'));
  }, [navigate, onAuth]);

  if (error) return <ErrorMessage message={error} />;
  return <LoadingSpinner />;
}
