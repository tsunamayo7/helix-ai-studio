import React, { useState, useEffect } from 'react';
import { useI18n } from '../i18n';

export default function FileBrowserModal({ token, onSelect, onClose }) {
  const { t } = useI18n();
  const [currentDir, setCurrentDir] = useState('');
  const [items, setItems] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [loading, setLoading] = useState(false);

  const headers = { 'Authorization': `Bearer ${token}` };

  useEffect(() => {
    fetchDir(currentDir);
  }, [currentDir]);

  async function fetchDir(dir) {
    setLoading(true);
    try {
      const res = await fetch(`/api/files/browse?dir_path=${encodeURIComponent(dir)}`, { headers });
      if (res.ok) setItems(await res.json());
      else setItems([]);
    } catch (e) { console.error(e); }
    setLoading(false);
  }

  function handleItemClick(item) {
    if (item.is_dir) {
      setCurrentDir(item.path);
    } else {
      setSelectedFiles(prev => {
        const exists = prev.find(f => f.path === item.path);
        if (exists) return prev.filter(f => f.path !== item.path);
        return [...prev, item];
      });
    }
  }

  function handleConfirm() {
    onSelect(selectedFiles);
    onClose();
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center">
      <div className="bg-gray-900 w-full sm:w-96 sm:rounded-xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <h3 className="text-gray-100 font-medium">{t('web.fileBrowser.title')}</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300">&times;</button>
        </div>

        <div className="px-4 py-2 flex items-center gap-1 text-xs text-gray-400 overflow-x-auto">
          <button onClick={() => setCurrentDir('')} className="hover:text-emerald-400">/</button>
          {currentDir.split('/').filter(Boolean).map((seg, i, arr) => (
            <React.Fragment key={i}>
              <span>/</span>
              <button
                onClick={() => setCurrentDir(arr.slice(0, i + 1).join('/'))}
                className="hover:text-emerald-400"
              >{seg}</button>
            </React.Fragment>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto min-h-0">
          {currentDir && (
            <button
              onClick={() => setCurrentDir(currentDir.split('/').slice(0, -1).join('/'))}
              className="w-full text-left px-4 py-2.5 text-gray-400 hover:bg-gray-800 text-sm"
            >
              &uarr; {t('web.fileBrowser.parentDir')}
            </button>
          )}
          {items.map((item) => {
            const isSelected = selectedFiles.some(f => f.path === item.path);
            return (
              <button
                key={item.path}
                onClick={() => handleItemClick(item)}
                className={`w-full text-left px-4 py-2.5 flex items-center gap-2 text-sm hover:bg-gray-800
                  ${isSelected ? 'bg-emerald-900/30 text-emerald-300' : 'text-gray-300'}`}
              >
                <span className="text-base">{item.is_dir ? '\uD83D\uDCC1' : '\uD83D\uDCC4'}</span>
                <span className="flex-1 truncate">{item.name}</span>
                {!item.is_dir && (
                  <span className="text-xs text-gray-500">{(item.size / 1024).toFixed(1)}KB</span>
                )}
                {isSelected && <span className="text-emerald-400">&check;</span>}
              </button>
            );
          })}
        </div>

        <div className="p-4 border-t border-gray-800 flex items-center justify-between">
          <span className="text-xs text-gray-500">{t('web.fileBrowser.selectedCount', { count: selectedFiles.length })}</span>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-4 py-2 bg-gray-800 text-gray-300 rounded-lg text-sm">
              {t('common.cancel')}
            </button>
            <button
              onClick={handleConfirm}
              disabled={selectedFiles.length === 0}
              className="px-4 py-2 bg-emerald-600 disabled:bg-gray-600 text-white rounded-lg text-sm"
            >
              {t('web.fileBrowser.attachButton')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
