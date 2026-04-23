import { request } from './api';

export async function getVapidPublicKey(): Promise<string> {
  const res = await request<{ public_key: string }>('/push/vapid-public-key', {
    skipAuth: true,
  });
  return res.public_key;
}

export async function subscribePush(subscription: PushSubscriptionJSON): Promise<void> {
  if (!subscription.endpoint || !subscription.keys) return;
  await request('/push/subscribe', {
    method: 'POST',
    body: JSON.stringify({
      endpoint: subscription.endpoint,
      keys: subscription.keys,
    }),
  });
}

export async function unsubscribePush(endpoint: string): Promise<void> {
  await request('/push/subscribe', {
    method: 'DELETE',
    body: JSON.stringify({ endpoint }),
  });
}

// urlBase64ToUint8Array converts the VAPID public key for use with
// pushManager.subscribe()
export function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 -(base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

export async function registerServiceWorkerAndSubscribe(): Promise<void> {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;

  try {
    const registration = await navigator.serviceWorker.register('/sw.js');
    await navigator.serviceWorker.ready;

    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return;

    const vapidKey = await getVapidPublicKey().catch(() => null);
    if (!vapidKey) return;

    const existing = await registration.pushManager.getSubscription();
    if (existing) {
      await subscribePush(existing.toJSON());
      return;
    }

    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidKey).buffer as ArrayBuffer,
    });

    await subscribePush(subscription.toJSON());
  } catch (err) {
    console.warn('[push] Registration failed:', err);
  }
}
