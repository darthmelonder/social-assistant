import { apiFetch } from './client';
import type { Connection } from '../types';

export async function listConnections(): Promise<Connection[]> {
  return apiFetch('/api/v1/connections');
}

export async function getConnection(id: string): Promise<Connection> {
  return apiFetch(`/api/v1/connections/${id}`);
}

export async function disconnectConnection(id: string): Promise<null> {
  return apiFetch(`/api/v1/connections/${id}`, { method: 'DELETE' });
}

export async function triggerSync(id: string): Promise<{ job_id: string }> {
  return apiFetch(`/api/v1/connections/${id}/sync`, { method: 'POST' });
}
