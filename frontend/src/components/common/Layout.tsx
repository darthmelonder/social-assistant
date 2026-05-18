import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { clearAccessToken } from '../../api/client';
import { logout } from '../../api/auth';
import type { AuthUser } from '../../types';

interface Props {
  user: AuthUser;
  onLogout: () => void;
}

export default function Layout({ user, onLogout }: Props) {
  const navigate = useNavigate();

  async function handleLogout() {
    await logout().catch(() => {});
    clearAccessToken();
    onLogout();
    navigate('/');
  }

  const initials = (user.display_name ?? user.email).slice(0, 2).toUpperCase();

  return (
    <div className="flex min-h-screen bg-[#080c1a]">

      {/* ── Sidebar ── */}
      <aside className="w-56 shrink-0 flex flex-col bg-white/[0.02] border-r border-white/[0.06]">

        {/* Logo */}
        <div className="px-5 pt-7 pb-5">
          <div className="flex items-center gap-3">
            <div
              className="w-8 h-8 rounded-xl flex items-center justify-center text-white font-bold text-sm shrink-0"
              style={{ background: 'linear-gradient(135deg, #7c3aed, #06b6d4)', boxShadow: '0 0 16px rgba(124,58,237,0.35)' }}
            >
              S
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-100 leading-tight">Social</p>
              <p className="text-xs text-slate-500 leading-tight">Assistant</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 space-y-0.5">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `nav-item ${isActive ? 'nav-item-active' : ''}`}
          >
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 13.5h3.86a2.25 2.25 0 012.012 1.244l.256.512a2.25 2.25 0 002.013 1.244h3.218a2.25 2.25 0 002.013-1.244l.256-.512a2.25 2.25 0 012.013-1.244h3.859m-19.5.338V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18v-4.162c0-.224-.034-.447-.1-.661L19.24 5.338a2.25 2.25 0 00-2.15-1.588H6.911a2.25 2.25 0 00-2.15 1.588L2.35 13.177a2.25 2.25 0 00-.1.661z" />
            </svg>
            Inbox
          </NavLink>
        </nav>

        {/* User footer */}
        <div className="px-3 pb-4 pt-3 border-t border-white/[0.06]">
          <div className="flex items-center gap-2.5 px-2 py-2 rounded-xl">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold text-white shrink-0"
              style={{ background: 'linear-gradient(135deg, rgba(124,58,237,0.6), rgba(6,182,212,0.5))', border: '1px solid rgba(255,255,255,0.1)' }}
            >
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-slate-300 truncate leading-tight">
                {user.display_name ?? user.email}
              </p>
              {user.display_name && (
                <p className="text-[10px] text-slate-600 truncate leading-tight">{user.email}</p>
              )}
            </div>
            <button
              onClick={handleLogout}
              title="Sign out"
              className="text-slate-600 hover:text-slate-300 transition-colors duration-150 cursor-pointer"
              aria-label="Sign out"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75" />
              </svg>
            </button>
          </div>
        </div>

      </aside>

      {/* ── Main ── */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>

    </div>
  );
}
