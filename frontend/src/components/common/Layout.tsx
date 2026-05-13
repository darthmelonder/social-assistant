import { Link, Outlet, useNavigate } from 'react-router-dom';
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

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
        <Link to="/" className="font-semibold text-gray-900 hover:text-blue-600">
          Social Assistant
        </Link>
        <div className="flex items-center gap-4 text-sm text-gray-600">
          <span>{user.email}</span>
          <button onClick={handleLogout} className="hover:text-gray-900">
            Sign out
          </button>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
