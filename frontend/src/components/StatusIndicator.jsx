import React from 'react';
import { useI18n } from '../i18n';

export default function StatusIndicator({ status }) {
  const { t } = useI18n();

  const STATUS_STYLES = {
    connected: { dot: 'bg-emerald-400', text: t('web.status.connected'), color: 'text-emerald-400' },
    executing: { dot: 'bg-amber-400 animate-pulse', text: t('web.status.executing'), color: 'text-amber-400' },
    completed: { dot: 'bg-emerald-400', text: t('web.status.completed'), color: 'text-emerald-400' },
    disconnected: { dot: 'bg-gray-500', text: t('web.status.disconnected'), color: 'text-gray-500' },
    error: { dot: 'bg-red-400', text: t('web.status.error'), color: 'text-red-400' },
  };

  const style = STATUS_STYLES[status] || STATUS_STYLES.disconnected;

  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${style.dot}`} />
      <span className={`text-xs font-medium ${style.color}`}>{style.text}</span>
    </div>
  );
}
