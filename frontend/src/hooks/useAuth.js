import { useState, useEffect, useCallback } from 'react';

const TOKEN_KEY = 'helix_jwt_token';
const API_BASE = '';  // 同一オリジン (vite proxy or production)

export function useAuth() {
  const [token, setToken] = useState(() => {
    // メモリ内で保持（localStorage不使用、sessionStorageも不使用）
    return null;
  });

  // ページリロード時のトークン復元用（一時的にwindowオブジェクトに保存）
  useEffect(() => {
    if (window.__helix_token) {
      setToken(window.__helix_token);
    }
  }, []);

  const login = useCallback(async (pin) => {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Login failed');
    }

    const data = await res.json();
    setToken(data.token);
    window.__helix_token = data.token;  // リロード時の一時保存
    return data;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    window.__helix_token = null;
  }, []);

  return {
    token,
    isAuthenticated: !!token,
    login,
    logout,
  };
}
