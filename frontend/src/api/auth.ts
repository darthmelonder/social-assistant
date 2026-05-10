import { apiFetch, setAccessToken } from './client';
import type { AuthResponse, AuthUser, Profile } from '../types';

export async function getAuthorizeUrl(): Promise<{ authorize_url: string; state: string }> {
  return apiFetch('/api/v1/auth/google/authorize');
}

export async function refreshToken(): Promise<{ access_token: string }> {
  return apiFetch('/api/v1/auth/refresh', { method: 'POST' });
}

export async function logout(): Promise<null> {
  return apiFetch('/api/v1/auth/logout', { method: 'POST' });
}

export async function getMe(): Promise<AuthUser> {
  return apiFetch('/api/v1/auth/me');
}

export async function getProfile(): Promise<Profile> {
  return apiFetch('/api/v1/profile');
}

export async function triggerProfileRebuild(): Promise<{ job_id: string }> {
  return apiFetch('/api/v1/profile/rebuild', { method: 'POST' });
}

export async function getJob(id: string): Promise<import('../types').Job> {
  return apiFetch(`/api/v1/jobs/${id}`);
}
