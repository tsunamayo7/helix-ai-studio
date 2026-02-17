import React from 'react';
import { useI18n } from '../i18n';

export default function TabBar({ activeTab, onTabChange }) {
  const { t } = useI18n();

  const TABS = [
    { id: 'soloAI', label: t('tabs.soloAI'), desc: t('tabs.soloAIDesc') },
    { id: 'mixAI', label: t('tabs.mixAI'), desc: t('tabs.mixAIDesc') },
    { id: 'files', label: t('tabs.files'), desc: t('tabs.filesDesc') },
    { id: 'settings', label: t('tabs.settings'), desc: t('tabs.settingsDesc') },
  ];

  return (
    <div className="shrink-0 flex border-b border-gray-800 bg-gray-900">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={`flex-1 py-2.5 text-center transition-colors relative ${
            activeTab === tab.id
              ? 'text-emerald-400'
              : 'text-gray-500 hover:text-gray-300'
          }`}
        >
          <span className="text-sm font-medium">{tab.label}</span>
          <span className="block text-[10px] mt-0.5 opacity-60">{tab.desc}</span>
          {activeTab === tab.id && (
            <div className="absolute bottom-0 left-4 right-4 h-0.5 bg-emerald-400 rounded-full" />
          )}
        </button>
      ))}
    </div>
  );
}
