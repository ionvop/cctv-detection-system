import { request } from './api';
import type { User } from '../types';

// Users endpoints require SUPER_KEY as Bearer token, not a regular session token.
// Pass adminKey explicitly for each call.

export const usersApi = {
  list: (adminKey: string) =>
    request<User[]>('/users/', { authToken: adminKey }),

  get: (id: number, adminKey: string) =>
    request<User>(`/users/${id}`, { authToken: adminKey }),

  create: (data: { username: string; password: string }, adminKey: string) =>
    request<User>('/users/', {
      method: 'POST',
      body: JSON.stringify(data),
      authToken: adminKey,
    }),

  update: (id: number, data: { password: string }, adminKey: string) =>
    request<User>(`/users/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
      authToken: adminKey,
    }),

  delete: (id: number, adminKey: string) =>
    request<{ detail: string }>(`/users/${id}`, {
      method: 'DELETE',
      authToken: adminKey,
    }),
};
