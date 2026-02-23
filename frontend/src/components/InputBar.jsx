import React, { useState, useRef } from 'react';
import FileBrowserModal from './FileBrowserModal';
import { useI18n } from '../i18n';

// v11.0.0: Simplified - removed ContextModeSelector, session buttons, RAG toggle
// Settings are managed from the desktop app

// v9.5.0: Upload + server file browser menu
function AttachMenu({ token, onFileAttached, onOpenBrowser, onClose }) {
  const { t } = useI18n();
  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);

  async function handleLocalUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      alert(t('web.inputBar.fileSizeLimit', { size: (file.size / (1024*1024)).toFixed(1) }));
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const resp = await fetch('/api/files/upload', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();
      onFileAttached({
        name: file.name,
        path: data.path || data.filename || file.name,
        source: 'upload',
      });
    } catch (err) {
      alert(t('web.inputBar.uploadFailed', { error: err.message }));
    }
    setUploading(false);
    onClose();
  }

  return (
    <div className="absolute bottom-full right-0 mb-2 w-48 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50 overflow-hidden">
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
        className="w-full px-4 py-2.5 text-left text-sm text-gray-200 hover:bg-gray-700 disabled:opacity-50">
        {uploading ? t('web.inputBar.uploading') : t('web.inputBar.localUpload')}
      </button>
      <button
        onClick={() => { onOpenBrowser(); onClose(); }}
        className="w-full px-4 py-2.5 text-left text-sm text-gray-200 hover:bg-gray-700 border-t border-gray-700">
        {t('web.inputBar.serverFile')}
      </button>
      <input ref={fileInputRef} type="file" className="hidden" onChange={handleLocalUpload} />
    </div>
  );
}

export default function InputBar({ onSend, disabled, token, placeholder }) {
  const { t } = useI18n();
  const [text, setText] = useState('');
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [showFileBrowser, setShowFileBrowser] = useState(false);
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const textareaRef = useRef(null);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, {
      attachedFiles: attachedFiles.map(f => f.path),
    });
    setText('');
    setAttachedFiles([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e) => {
    setText(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  };

  return (
    <div className="shrink-0 border-t border-gray-800 bg-gray-900 safe-area-inset-bottom">
      {/* Attached files display */}
      {attachedFiles.length > 0 && (
        <div className="flex flex-wrap gap-1 px-4 py-1.5 bg-gray-900/50 border-b border-gray-800/50">
          {attachedFiles.map((f, i) => (
            <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-800 rounded text-xs text-gray-300">
              {f.name}
              {f.source === 'upload' && <span className="text-[10px] text-emerald-500">{t('web.inputBar.sourceUpload')}</span>}
              <button onClick={() => setAttachedFiles(prev => prev.filter((_, j) => j !== i))}
                      className="text-gray-500 hover:text-red-400 ml-0.5">&times;</button>
            </span>
          ))}
        </div>
      )}

      {/* Attach button row */}
      <div className="flex items-center justify-end px-3 py-2 border-b border-gray-800/50">
        <div className="relative">
          <button onClick={() => setShowAttachMenu(!showAttachMenu)}
            disabled={disabled}
            className="px-4 py-1.5 rounded-lg text-xs font-medium bg-gray-700 text-gray-300 hover:bg-gray-600 hover:text-white disabled:opacity-50 transition-colors border border-gray-600">
            {t('web.inputBar.attachButton')}
          </button>
          {showAttachMenu && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowAttachMenu(false)} />
              <AttachMenu
                token={token}
                onFileAttached={(f) => setAttachedFiles(prev => [...prev, f])}
                onOpenBrowser={() => setShowFileBrowser(true)}
                onClose={() => setShowAttachMenu(false)}
              />
            </>
          )}
        </div>
      </div>

      {/* Text input + send button */}
      <div className="flex items-end gap-3 px-4 py-3">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || t('web.inputBar.placeholder')}
          rows={2}
          className="flex-1 resize-none bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 max-h-[200px]"
          disabled={disabled}
        />
        <button
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          className="shrink-0 w-14 h-14 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 flex items-center justify-center transition-colors"
        >
          <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
          </svg>
        </button>
      </div>

      {showFileBrowser && (
        <FileBrowserModal
          token={token}
          onSelect={(files) => setAttachedFiles(prev => [...prev, ...files])}
          onClose={() => setShowFileBrowser(false)}
        />
      )}
    </div>
  );
}
