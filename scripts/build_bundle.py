#!/usr/bin/env python3
"""Build helix_source_bundle.txt by concatenating all 25 source files."""
import os

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
output = os.path.join(base, 'helix_source_bundle.txt')

files = [
    'src/utils/constants.py',
    'src/backends/local_agent.py',
    'src/backends/mix_orchestrator.py',
    'src/memory/memory_manager.py',
    'src/rag/rag_builder.py',
    'src/rag/rag_executor.py',
    'src/rag/rag_planner.py',
    'src/rag/rag_verifier.py',
    'src/tabs/information_collection_tab.py',
    'src/tabs/helix_orchestrator_tab.py',
    'src/tabs/settings_cortex_tab.py',
    'src/main_window.py',
    'src/web/server.py',
    'src/web/api_routes.py',
    'src/web/file_transfer.py',
    'src/web/launcher.py',
    'src/widgets/web_lock_overlay.py',
    'frontend/src/App.jsx',
    'frontend/src/components/InputBar.jsx',
    'frontend/src/components/FileManagerView.jsx',
    'frontend/src/components/SettingsView.jsx',
    'frontend/src/hooks/useWebSocket.js',
    'frontend/public/sw.js',
    'config/config.json',
    'config/app_settings.json',
]

separator = '=' * 40

with open(output, 'w', encoding='utf-8') as out:
    for i, rel_path in enumerate(files):
        full_path = os.path.join(base, rel_path)
        display_path = rel_path.replace(os.sep, '/')

        if i > 0:
            out.write('\n')

        out.write(separator + '\n')
        out.write('FILE: ' + display_path + '\n')
        out.write(separator + '\n')

        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            out.write(content)
            if not content.endswith('\n'):
                out.write('\n')
            line_count = content.count('\n') + (0 if content.endswith('\n') else 1)
            print('OK: {} ({} chars, {} lines)'.format(display_path, len(content), line_count))
        else:
            out.write('# FILE NOT FOUND: ' + full_path + '\n')
            print('MISSING: ' + display_path)

total_size = os.path.getsize(output)
print()
print('Bundle written: ' + output)
print('Total size: {:,} bytes ({:.1f} KB)'.format(total_size, total_size / 1024))
