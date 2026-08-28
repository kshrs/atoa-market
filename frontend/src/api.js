/**
 * ATOA API & WebSocket Client
 * Connects the live React Dashboard directly to the FastAPI Marketplace Backend.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/v1/events/ws';

export async function fetchAnalytics() {
  try {
    const res = await fetch(`${API_BASE}/v1/analytics/overview`);
    if (!res.ok) throw new Error('Failed to fetch analytics');
    return await res.json();
  } catch (err) {
    console.warn('[ATOA API] Analytics fetch failed, fallback to local', err);
    return null;
  }
}

export async function fetchTasks() {
  try {
    const res = await fetch(`${API_BASE}/v1/tasks`);
    if (!res.ok) throw new Error('Failed to fetch tasks');
    return await res.json();
  } catch (err) {
    console.warn('[ATOA API] Tasks fetch failed, fallback to local', err);
    return [];
  }
}

export async function fetchWallets() {
  try {
    const res = await fetch(`${API_BASE}/v1/wallets`);
    if (!res.ok) throw new Error('Failed to fetch wallets');
    return await res.json();
  } catch (err) {
    console.warn('[ATOA API] Wallets fetch failed, fallback to local', err);
    return [];
  }
}

export function subscribeToLiveEvents(onEvent, onStatusChange) {
  let ws = null;
  let reconnectTimer = null;

  function connect() {
    try {
      ws = new WebSocket(WS_BASE);

      ws.onopen = () => {
        console.log('[ATOA WebSocket] Connected to live backend event feed');
        if (onStatusChange) onStatusChange(true);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          onEvent(payload);
        } catch (e) {
          console.error('[ATOA WebSocket] Error parsing message', e);
        }
      };

      ws.onclose = () => {
        console.log('[ATOA WebSocket] Disconnected. Reconnecting in 3s...');
        if (onStatusChange) onStatusChange(false);
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onerror = (err) => {
        console.warn('[ATOA WebSocket] Connection error:', err);
        ws.close();
      };
    } catch (err) {
      console.warn('[ATOA WebSocket] Setup failed:', err);
      reconnectTimer = setTimeout(connect, 3000);
    }
  }

  connect();

  return () => {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (ws) ws.close();
  };
}
