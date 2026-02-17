import React, { useState } from 'react';
import { useI18n } from '../i18n';

export default function LoginScreen({ onLogin }) {
  const { t } = useI18n();
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!pin) return;
    setLoading(true);
    setError('');

    try {
      await onLogin(pin);
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-950">
      <div className="w-full max-w-sm p-8 bg-gray-900 rounded-2xl border border-gray-800">
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-emerald-600 flex items-center justify-center text-white font-bold text-2xl mb-4">
            H
          </div>
          <h1 className="text-xl font-semibold text-gray-100">Helix AI Studio</h1>
          <p className="text-sm text-gray-400 mt-1">Web Interface</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">{t('web.login.pin')}</label>
          <input
            type="password"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={10}
            value={pin}
            onChange={(e) => setPin(e.target.value)}
            className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-xl text-center text-2xl tracking-widest text-gray-100 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            placeholder={t('web.login.placeholder')}
            autoFocus
          />
          {error && <p className="mt-2 text-sm text-red-400">{error}</p>}
          <button
            onClick={handleSubmit}
            disabled={loading || !pin}
            className="w-full mt-4 py-3 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium rounded-xl transition-colors"
          >
            {loading ? t('web.login.authenticating') : t('web.login.loginButton')}
          </button>
        </div>
      </div>
    </div>
  );
}
