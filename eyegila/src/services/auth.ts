import { request } from './api';

export async function login(username: string, password: string): Promise<{ token: string }> {
  return request('/login/', {
    method: 'POST',
    skipAuth: true,
    body: JSON.stringify({ username, password }),
  });
}

export async function logout(): Promise<void> {
  await request('/login/', { method: 'DELETE' });
}
