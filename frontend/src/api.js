/**
 * ATOA API & WebSocket Client
 * Connects the live React Dashboard directly to the FastAPI Marketplace Backend.
 * Automatically fails over silently to the in-browser simulation when deployed standalone (e.g. GitHub Pages).
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/v1/events/ws';

export async function fetchAnalytics() {
  try {
    const res = await fetch(`${API_BASE}/v1/analytics/overview`, { signal: AbortSignal.timeout(2000) });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    return null;
  }
}

export async function fetchTasks() {
  try {
    const res = await fetch(`${API_BASE}/v1/tasks`, { signal: AbortSignal.timeout(2000) });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    return null;
  }
}

export async function fetchWallets() {
  try {
    const res = await fetch(`${API_BASE}/v1/wallets`, { signal: AbortSignal.timeout(2000) });
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    return null;
  }
}

export function subscribeToLiveEvents(onEvent, onStatusChange) {
  let ws = null;
  let reconnectTimer = null;
  let isClosed = false;

  function connect() {
    if (isClosed) return;
    try {
      ws = new WebSocket(WS_BASE);

      ws.onopen = () => {
        if (onStatusChange) onStatusChange(true);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          onEvent(payload);
        } catch (e) {
          // ignore parsing error
        }
      };

      ws.onclose = () => {
        if (onStatusChange) onStatusChange(false);
        if (!isClosed) {
          reconnectTimer = setTimeout(connect, 5000);
        }
      };

      ws.onerror = () => {
        if (ws) ws.close();
      };
    } catch (err) {
      if (onStatusChange) onStatusChange(false);
      if (!isClosed) {
        reconnectTimer = setTimeout(connect, 5000);
      }
    }
  }

  connect();

  return () => {
    isClosed = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (ws) ws.close();
  };
}
