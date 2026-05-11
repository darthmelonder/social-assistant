import { useState } from 'react';
import { getAuthorizeUrl } from '../../api/auth';

export default function ConnectGmail() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConnect() {
    setLoading(true);
    setError(null);
    try {
      const { authorize_url } = await getAuthorizeUrl();
      window.location.href = authorize_url;
    } catch {
      setError('Could not start the sign-in flow. Please try again.');
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 px-4">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-10 max-w-md w-full text-center space-y-6">
        <h1 className="text-2xl font-semibold text-gray-900">Social Assistant</h1>
        <p className="text-gray-500 text-sm leading-relaxed">
          Connect your Gmail to get a smart summary of your inbox, AI-powered draft replies,
          and priority triage — all read-only, nothing sent without your approval.
        </p>
        {error && (
          <p role="alert" className="text-sm text-red-600">{error}</p>
        )}
        <button
          onClick={handleConnect}
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 px-4 rounded-lg transition-colors disabled:opacity-50"
        >
          {loading ? 'Redirecting…' : 'Connect Gmail'}
        </button>
      </div>
    </div>
  );
}
