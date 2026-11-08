import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api, setUnauthorizedHandler } from '../lib/api';
import type { MarketianSignIn, User } from '../lib/types';

type AuthState = {
  user: User | null;
  ready: boolean;
  signupEnabled: boolean;
  marketian: MarketianSignIn;
  login: (username: string, password: string) => Promise<void>;
  register: (body: { username: string; name: string; password: string }) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthCtx = createContext<AuthState>(null!);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [signupEnabled, setSignupEnabled] = useState(false);
  const [marketian, setMarketian] = useState<MarketianSignIn>({ enabled: false, login_url: '', account_url: '' });
  const qc = useQueryClient();

  useEffect(() => {
    setUnauthorizedHandler(() => { setUser(null); qc.clear(); });
    // Also sets the CSRF cookie that every later POST needs.
    api<{ user: User | null; signup_enabled: boolean; marketian: MarketianSignIn }>('/auth/session/')
      .then(r => { setUser(r.user); setSignupEnabled(r.signup_enabled); setMarketian(r.marketian); })
      .catch(() => setUser(null))
      .finally(() => setReady(true));
  }, [qc]);

  const login = useCallback(async (username: string, password: string) => {
    const r = await api<{ user: User }>('/auth/login/', { method: 'POST', body: { username, password } });
    // Django rotates the CSRF token on login; fetch the fresh one.
    await api('/auth/session/');
    qc.clear(); // nothing cached from whoever used this browser before
    setUser(r.user);
  }, [qc]);

  const register = useCallback(async (body: { username: string; name: string; password: string }) => {
    const r = await api<{ user: User }>('/auth/register/', { method: 'POST', body });
    await api('/auth/session/'); // fresh CSRF token after signing in
    qc.clear();
    setUser(r.user);
  }, [qc]);

  const logout = useCallback(async () => {
    const r = await api<{ redirect?: string | null }>('/auth/logout/', { method: 'POST' }).catch(() => null);
    qc.clear();
    // Marketian-account users are also signed out there, then sent back here.
    if (r?.redirect) { window.location.href = r.redirect; return; }
    setUser(null);
  }, [qc]);

  return <AuthCtx.Provider value={{ user, ready, signupEnabled, marketian, login, register, logout }}>{children}</AuthCtx.Provider>;
}
