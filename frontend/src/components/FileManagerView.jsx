import React, { useState, useEffect, useRef } from 'react';
import { useI18n } from '../i18n';

const TEXT_EXTENSIONS = ['.txt', '.md', '.py', '.js', '.jsx', '.ts', '.tsx',
  '.json', '.yaml', '.yml', '.html', '.css', '.sql', '.sh', '.csv', '.xml',
  '.env', '.cfg', '.ini', '.toml', '.log', '.bat', '.gitignore'];
const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'];

// v9.5.0: File transfer section
function TransferSection({ token }) {
  const { t } = useI18n();
  const [uploads, setUploads] = useState([]);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => { fetchUploads(); }, []);

  async function fetchUploads() {
    try {
      const res = await fetch('/api/files/uploads', {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUploads(data.files || []);
      }
    } catch (e) { console.error(e); }
  }

  async function handleUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch('/api/files/upload', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      if (res.ok) fetchUploads();
      else {
        let detail = t('web.fileManager.uploadFailed', { status: res.status });
        try { const err = await res.json(); detail = err.detail || detail; } catch (_) {}
        alert(detail);
      }
    } catch (e) { alert(t('web.fileManager.uploadError', { message: e.message || '' })); }
    setUploading(false);
  }

  async function handleCopyToProject(filename) {
    const dest = prompt(t('web.fileManager.copyDest'), '');
    if (dest === null) return;
    try {
      const res = await fetch(
        `/api/files/copy-to-project?filename=${encodeURIComponent(filename)}&dest_dir=${encodeURIComponent(dest)}`,
        { method: 'POST', headers: { 'Authorization': `Bearer ${token}` } }
      );
      if (res.ok) {
        const data = await res.json();
        alert(t('web.fileManager.copyDone', { path: data.path }));
      }
    } catch (e) { alert(t('web.fileManager.copyFailed')); }
  }

  async function handleDeleteUpload(filename) {
    if (!confirm(t('web.fileManager.deleteConfirm', { name: filename }))) return;
    try {
      await fetch(`/api/files/uploads/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      fetchUploads();
    } catch (e) { console.error(e); }
  }

  function formatSize(bytes) {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  }

  return (
    <div className="mt-4 px-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-emerald-400">{t('web.fileManager.fileTransfer')}</h3>
        <button onClick={() => fileInputRef.current?.click()} disabled={uploading}
          className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white
                     text-xs rounded-lg transition-colors disabled:opacity-50">
          {uploading ? t('common.uploading') : t('web.fileManager.uploadFromDevice')}
        </button>
        <input ref={fileInputRef} type="file" className="hidden" onChange={handleUpload}
               accept=".txt,.md,.py,.js,.json,.csv,.html,.pdf,.docx,.png,.jpg,.jpeg" />
      </div>

      {uploads.length > 0 && (
        <div className="bg-gray-900 rounded-lg border border-gray-800 divide-y divide-gray-800">
          {uploads.map(f => (
            <div key={f.name} className="flex items-center justify-between px-3 py-2">
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-300 truncate">{f.name}</p>
                <p className="text-[10px] text-gray-600">{formatSize(f.size)}</p>
              </div>
              <div className="flex items-center gap-1">
                <button onClick={() => handleCopyToProject(f.name)}
                  className="text-[10px] px-2 py-1 bg-blue-900/50 text-blue-300 rounded hover:bg-blue-800/50">
                  {t('web.fileManager.copyToProject')}
                </button>
                <button onClick={() => handleDeleteUpload(f.name)}
                  className="text-[10px] px-2 py-1 text-red-400 hover:bg-red-900/30 rounded">
                  {t('common.delete')}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {uploads.length === 0 && (
        <p className="text-gray-600 text-xs text-center py-4">
          {t('web.fileManager.noUploads')}
        </p>
      )}

      <p className="text-[10px] text-gray-700 mt-2">
        {t('web.fileManager.supportedFormats')}
      </p>
    </div>
  );
}

export default function FileManagerView({ token }) {
  const { t } = useI18n();
  const [currentDir, setCurrentDir] = useState('');
  const [items, setItems] = useState([]);
  const [openFile, setOpenFile] = useState(null);
  const [editContent, setEditContent] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' };

  useEffect(() => { fetchDir(currentDir); }, [currentDir]);

  async function fetchDir(dir) {
    try {
      const res = await fetch(`/api/files/browse?dir_path=${encodeURIComponent(dir)}`,
        { headers: { 'Authorization': `Bearer ${token}` } });
      if (res.ok) setItems(await res.json());
      else setItems([]);
    } catch (e) { console.error(e); }
  }

  async function openFileHandler(item) {
    if (item.is_dir) {
      setCurrentDir(item.path);
      setOpenFile(null);
      return;
    }
    const ext = item.extension.toLowerCase();
    if (!TEXT_EXTENSIONS.includes(ext) && !IMAGE_EXTENSIONS.includes(ext)) {
      setMessage(t('web.fileManager.unsupportedFormat', { ext }));
      setTimeout(() => setMessage(''), 3000);
      return;
    }
    try {
      const res = await fetch(`/api/files/content?file_path=${encodeURIComponent(item.path)}`,
        { headers: { 'Authorization': `Bearer ${token}` } });
      if (res.ok) {
        const data = await res.json();
        setOpenFile({ ...data, name: item.name });
        setEditContent(data.type === 'text' ? data.content : '');
        setIsEditing(false);
      }
    } catch (e) { console.error(e); }
  }

  async function saveFile() {
    if (!openFile) return;
    setSaving(true);
    try {
      const res = await fetch(`/api/files/content?file_path=${encodeURIComponent(openFile.path)}`, {
        method: 'PUT', headers,
        body: JSON.stringify({ content: editContent }),
      });
      if (res.ok) {
        setMessage(t('web.fileManager.fileSaved'));
        setOpenFile({ ...openFile, content: editContent });
        setIsEditing(false);
      } else {
        setMessage(t('common.saveFailed'));
      }
    } catch (e) { setMessage(t('common.error') + ': ' + e.message); }
    setSaving(false);
    setTimeout(() => setMessage(''), 3000);
  }

  async function handleDownload(path) {
    try {
      const res = await fetch(`/api/files/download?path=${encodeURIComponent(path)}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = path.split('/').pop();
        a.click();
        URL.revokeObjectURL(url);
      } else {
        const err = await res.json();
        alert(err.detail);
      }
    } catch (e) { alert(t('web.fileManager.downloadError')); }
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {openFile ? (
        <div className="flex-1 flex flex-col min-h-0">
          <div className="shrink-0 flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-800">
            <div className="flex items-center gap-2">
              <button onClick={() => setOpenFile(null)} className="text-gray-400 hover:text-white">&larr;</button>
              <span className="text-gray-200 text-sm font-medium truncate">{openFile.name}</span>
              <span className="text-gray-500 text-xs">{(openFile.size / 1024).toFixed(1)}KB</span>
            </div>
            <div className="flex items-center gap-2">
              {openFile.type === 'text' && !isEditing && (
                <button onClick={() => { setIsEditing(true); setEditContent(openFile.content); }}
                  className="px-3 py-1 bg-emerald-700 text-emerald-200 rounded text-xs">
                  {t('common.edit')}
                </button>
              )}
              {isEditing && (
                <>
                  <button onClick={() => setIsEditing(false)}
                    className="px-3 py-1 bg-gray-700 text-gray-300 rounded text-xs">
                    {t('common.cancel')}
                  </button>
                  <button onClick={saveFile} disabled={saving}
                    className="px-3 py-1 bg-emerald-600 text-white rounded text-xs">
                    {saving ? t('common.saving') : t('common.save')}
                  </button>
                </>
              )}
              {message && <span className="text-xs text-emerald-400">{message}</span>}
            </div>
          </div>

          <div className="flex-1 overflow-auto min-h-0">
            {openFile.type === 'text' ? (
              isEditing ? (
                <textarea
                  value={editContent}
                  onChange={e => setEditContent(e.target.value)}
                  className="w-full h-full bg-gray-950 text-gray-200 text-sm font-mono p-4 resize-none outline-none"
                  spellCheck={false}
                />
              ) : (
                <pre className="text-gray-200 text-sm font-mono p-4 whitespace-pre-wrap break-words">
                  {openFile.content}
                </pre>
              )
            ) : openFile.type === 'image' ? (
              <div className="flex items-center justify-center p-4">
                <img
                  src={`data:${openFile.mime};base64,${openFile.content}`}
                  alt={openFile.name}
                  className="max-w-full max-h-[70vh] object-contain rounded-lg"
                />
              </div>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col min-h-0">
          <div className="shrink-0 px-4 py-2 flex items-center gap-1 text-xs text-gray-400 bg-gray-900 border-b border-gray-800">
            <button onClick={() => setCurrentDir('')} className="hover:text-emerald-400">{t('web.fileManager.project')}</button>
            {currentDir.split('/').filter(Boolean).map((seg, i, arr) => (
              <React.Fragment key={i}>
                <span className="mx-0.5">/</span>
                <button onClick={() => setCurrentDir(arr.slice(0, i + 1).join('/'))}
                  className="hover:text-emerald-400">{seg}</button>
              </React.Fragment>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto min-h-0">
            {currentDir && (
              <button onClick={() => setCurrentDir(currentDir.split('/').slice(0, -1).join('/'))}
                className="w-full text-left px-4 py-3 text-gray-400 hover:bg-gray-800/50 text-sm border-b border-gray-800/50">
                &uarr; {t('web.fileManager.parentDir')}
              </button>
            )}
            {items.map(item => {
              const ext = item.extension?.toLowerCase() || '';
              const isViewable = TEXT_EXTENSIONS.includes(ext) || IMAGE_EXTENSIONS.includes(ext);
              const icon = item.is_dir ? '\uD83D\uDCC1' : IMAGE_EXTENSIONS.includes(ext) ? '\uD83D\uDDBC\uFE0F' : '\uD83D\uDCC4';

              return (
                <div
                  key={item.path}
                  className={`w-full px-4 py-3 flex items-center gap-3 text-sm border-b border-gray-800/30
                    ${item.is_dir || isViewable ? 'hover:bg-gray-800/50 text-gray-300' : 'text-gray-600'}`}
                >
                  <button
                    onClick={() => openFileHandler(item)}
                    className="flex-1 flex items-center gap-3 text-left min-w-0"
                    disabled={!item.is_dir && !isViewable}
                  >
                    <span className="text-lg">{icon}</span>
                    <span className="flex-1 truncate">{item.name}</span>
                  </button>
                  {!item.is_dir && (
                    <span className="text-xs text-gray-600 shrink-0">{(item.size / 1024).toFixed(1)}KB</span>
                  )}
                  {!item.is_dir && (
                    <button onClick={() => handleDownload(item.path)}
                      className="text-[10px] px-2 py-1 text-gray-400 hover:text-emerald-300
                                 hover:bg-emerald-900/30 rounded shrink-0"
                      title={t('web.fileManager.downloadTitle')}>
                      {t('common.download')}
                    </button>
                  )}
                </div>
              );
            })}
            {items.length === 0 && (
              <p className="text-gray-600 text-sm text-center py-8">{t('web.fileManager.emptyDir')}</p>
            )}

            <TransferSection token={token} />
          </div>
        </div>
      )}
    </div>
  );
}
