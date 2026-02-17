import React, { createContext, useContext, useState, useCallback } from 'react';
import ja from '../../../i18n/ja.json';
import en from '../../../i18n/en.json';

const translations = { ja, en };
const LanguageContext = createContext();

function resolve(obj, path) {
  return path.split('.').reduce((acc, key) => acc?.[key], obj);
}

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => {
    try { return localStorage.getItem('helix_lang') || 'ja'; }
    catch { return 'ja'; }
  });

  const changeLang = useCallback((newLang) => {
    setLang(newLang);
    try { localStorage.setItem('helix_lang', newLang); } catch {}
    // Sync to server (shared with desktop via general_settings.json)
    fetch('/api/settings', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('helix_token')}`,
      },
      body: JSON.stringify({ language: newLang }),
    }).catch(() => {});
  }, []);

  const t = useCallback((key, params = {}) => {
    let text = resolve(translations[lang], key);
    if (text === undefined || typeof text !== 'string') {
      text = resolve(translations['ja'], key);
    }
    if (text === undefined || typeof text !== 'string') return key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v));
    });
    return text;
  }, [lang]);

  return (
    <LanguageContext.Provider value={{ lang, setLang: changeLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error('useI18n must be used within LanguageProvider');
  return ctx;
}
