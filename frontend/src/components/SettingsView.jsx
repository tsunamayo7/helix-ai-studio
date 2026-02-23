import React from 'react';
import { useI18n } from '../i18n';

// v11.0.0: Settings view removed — all settings managed from desktop app
// GPU monitor, model config, project, RAG, PIN, language settings all moved to desktop
export default function SettingsView({ token }) {
  const { t } = useI18n();

  return (
    <div className="flex-1 flex items-center justify-center text-gray-500">
      <div className="text-center">
        <p className="text-4xl mb-4">⚙️</p>
        <p className="text-lg font-medium">{t('web.settings.managedByDesktop') || 'Settings managed by desktop app'}</p>
        <p className="text-sm mt-2 text-gray-600">
          {t('web.settings.managedByDesktopDesc') || 'Please use the Helix AI Studio desktop application to configure settings.'}
        </p>
      </div>
    </div>
  );
}
