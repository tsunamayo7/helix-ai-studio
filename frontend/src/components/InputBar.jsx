import React, { useState, useRef } from 'react';
import FileBrowserModal from './FileBrowserModal';
import ContextModeSelector from './ContextModeSelector';
import { useI18n } from '../i18n';

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

    const allowedExts = ['.txt','.md','.py','.js','.jsx','.ts','.json','.csv',
      '.html','.css','.yaml','.sql','.pdf','.docx','.png','.jpg','.jpeg','.gif'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!allowedExts.includes(ext)) {
      alert(t('web.inputBar.unsupportedExt', { ext }));
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch('/api/files/upload', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        onFileAttached({
          name: file.name,
          path: data.path || data.filename,
          size: data.size,
          source: 'upload',
        });
        onClose();
      } else {
        let detail = t('web.inputBar.uploadFailed', { status: res.status });
        try {
          const err = await res.json();
          detail = err.detail || detail;
        } catch (_) {}
        alert(detail);
      }
    } catch (e) {
      alert(t('web.inputBar.uploadError', { message: e.message || '' }));
    }
    setUploading(false);
  }

  return (
    <div className="absolute bottom-full right-0 mb-2 bg-gray-800 rounded-lg
                    border border-gray-700 shadow-xl p-2 min-w-[200px] z-50">
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
        className="w-full text-left px-3 py-2 text-sm text-gray-300
                   hover:bg-gray-700 rounded flex items-center gap-2"
      >
        <span>{t('web.inputBar.uploadFromDevice')}</span>
        {uploading && <span className="text-[10px] text-emerald-400">{t('common.uploading')}</span>}
      </button>
      <input ref={fileInputRef} type="file" className="hidden"
             onChange={handleLocalUpload}
             accept=".txt,.md,.py,.js,.jsx,.ts,.json,.csv,.html,.css,.yaml,.sql,.pdf,.docx,.png,.jpg,.jpeg,.gif" />

      <button
        onClick={() => { onOpenBrowser(); onClose(); }}
        className="w-full text-left px-3 py-2 text-sm text-gray-300
                   hover:bg-gray-700 rounded flex items-center gap-2"
      >
        <span>{t('web.inputBar.browseServerFiles')}</span>
      </button>

      <div className="px-3 py-1 text-[10px] text-gray-600 border-t border-gray-700 mt-1">
        {t('web.inputBar.attachLimit')}
      </div>
    </div>
  );
}

export default function InputBar({ onSend, disabled, placeholder, token,
                                    contextMode, onModeChange, tokenEstimate }) {
  const { t } = useI18n();
  const [text, setText] = useState('');
  const [ragEnabled, setRagEnabled] = useState(true);
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [showFileBrowser, setShowFileBrowser] = useState(false);
  const [showAttachMenu, setShowAttachMenu] = useState(false);
  const textareaRef = useRef(null);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, {
      enableRag: ragEnabled,
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

      {/* Context mode + RAG toggle row */}
      <div className="flex items-center justify-between px-3 py-1 border-b border-gray-800/50">
        <ContextModeSelector mode={contextMode} onChange={onModeChange}
                              tokenEstimate={tokenEstimate} />
        <div className="flex items-center gap-2">
          <button onClick={() => setRagEnabled(!ragEnabled)}
            className={`px-2 py-0.5 rounded text-[10px] transition-colors ${
              ragEnabled ? 'bg-emerald-800 text-emerald-300' : 'bg-gray-800 text-gray-500'
            }`}>
            {ragEnabled ? t('web.inputBar.ragOn') : t('web.inputBar.ragOff')}
          </button>
          <div className="relative">
            <button onClick={() => setShowAttachMenu(!showAttachMenu)}
              disabled={disabled}
              className="px-2 py-0.5 rounded text-[10px] bg-gray-800 text-gray-400 hover:text-gray-200 disabled:opacity-50">
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
      </div>

      {/* Text input + send button */}
      <div className="flex items-end gap-2 px-4 py-3">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || t('web.inputBar.placeholder')}
          rows={1}
          className="flex-1 resize-none bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 max-h-[200px]"
          disabled={disabled}
        />
        <button
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          className="shrink-0 w-12 h-12 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 flex items-center justify-center transition-colors"
        >
          <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
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
