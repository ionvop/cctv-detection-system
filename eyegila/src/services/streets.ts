import { request } from './api';
import type { Street } from '../types';

export const streetsApi = {
  list: () => request<Street[]>('/streets/'),

  get: (id: number) => request<Street>(`/streets/${id}`),

  create: (data: { intersection_id: number; name: string }) =>
    request<Street>('/streets/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: number, data: { name: string }) =>
    request<Street>(`/streets/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  delete: (id: number) =>
    request<{ detail: string }>(`/streets/${id}`, { method: 'DELETE' }),
};
