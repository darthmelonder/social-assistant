import { useState } from 'react';
import { getAuthorizeUrl } from '../../api/auth';

const FEATURES = [
  {
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
      </svg>
    ),
    label: 'Priority triage',
    desc: 'Urgent → Important → Maybe, classified by AI instantly',
  },
  {
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
      </svg>
    ),
    label: 'Draft replies',
    desc: 'Written in your voice — copy and send in one click',
  },
  {
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
      </svg>
    ),
    label: 'Read-only access',
    desc: 'Zero write access — nothing ever sent without you',
  },
];

export default function ConnectGmail() {
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

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
    <div className="relative flex flex-col items-center justify-center min-h-screen bg-[#080c1a] px-4 overflow-hidden">

      {/* Ambient glow blobs */}
      <div className="pointer-events-none absolute inset-0" aria-hidden="true">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[500px] h-[500px] rounded-full bg-violet-600/10 blur-[100px]" />
        <div className="absolute bottom-1/3 left-1/3 w-[350px] h-[350px] rounded-full bg-cyan-600/8 blur-[90px]" />
      </div>

      <div className="relative glass rounded-2xl p-10 max-w-md w-full text-center space-y-8 animate-fade-in">

        {/* Logo */}
        <div className="flex flex-col items-center gap-5">
          <div
            className="w-14 h-14 rounded-2xl flex items-center justify-center text-white font-bold text-2xl"
            style={{ background: 'linear-gradient(135deg, #7c3aed, #06b6d4)', boxShadow: '0 0 32px rgba(124,58,237,0.4)' }}
          >
            S
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-100 tracking-tight">Social Assistant</h1>
            <p className="text-slate-500 text-sm mt-1">Your AI-powered inbox, decluttered</p>
          </div>
        </div>

        {/* Feature list */}
        <ul className="space-y-4 text-left" role="list">
          {FEATURES.map(f => (
            <li key={f.label} className="flex items-start gap-3">
              <span className="mt-0.5 p-1.5 rounded-lg bg-white/[0.06] border border-white/[0.08] text-violet-400 shrink-0">
                {f.icon}
              </span>
              <div>
                <p className="text-sm font-semibold text-slate-200">{f.label}</p>
                <p className="text-xs text-slate-500 mt-0.5">{f.desc}</p>
              </div>
            </li>
          ))}
        </ul>

        {error && (
          <p role="alert" className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-2.5">
            {error}
          </p>
        )}

        <button
          onClick={handleConnect}
          disabled={loading}
          className="btn-primary w-full py-3 text-base"
        >
          {loading ? (
            <>
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" aria-hidden="true" />
              Redirecting…
            </>
          ) : 'Connect Gmail'}
        </button>

        <p className="text-[11px] text-slate-600">
          Read-only Gmail access · No emails sent on your behalf
        </p>
      </div>
    </div>
  );
}
