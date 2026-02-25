#!/usr/bin/env python3
"""Build helix_source_bundle.txt by concatenating all source files."""
import os

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
output = os.path.join(base, 'helix_source_bundle.txt')

files = [
    # --- Root ---
    'HelixAIStudio.py',
    'launcher.py',

    # --- src/ core ---
    'src/__init__.py',
    'src/main_window.py',

    # --- src/utils ---
    'src/utils/__init__.py',
    'src/utils/constants.py',
    'src/utils/styles.py',
    'src/utils/i18n.py',
    'src/utils/log_setup.py',
    'src/utils/model_capabilities.py',
    'src/utils/chat_logger.py',
    'src/utils/model_catalog.py',
    'src/utils/style_helpers.py',
    'src/utils/error_utils.py',
    'src/utils/discord_notifier.py',
    'src/utils/prompt_cache.py',
    'src/utils/diagnostics.py',
    'src/utils/diff_risk.py',
    'src/utils/markdown_renderer.py',
    'src/utils/subprocess_utils.py',

    # --- src/backends ---
    'src/backends/__init__.py',
    'src/backends/base.py',
    'src/backends/registry.py',
    'src/backends/cloud_adapter.py',
    'src/backends/anthropic_api_backend.py',
    'src/backends/openai_api_backend.py',
    'src/backends/google_api_backend.py',
    'src/backends/api_priority_resolver.py',
    'src/backends/sequential_executor.py',
    'src/backends/claude_backend.py',
    'src/backends/claude_cli_backend.py',
    'src/backends/codex_cli_backend.py',
    'src/backends/gemini_backend.py',
    'src/backends/local_agent.py',
    'src/backends/local_backend.py',
    'src/backends/local_connector.py',
    'src/backends/local_llm_manager.py',
    'src/backends/mix_orchestrator.py',
    'src/backends/model_repository.py',
    'src/backends/thermal_monitor.py',
    'src/backends/thermal_policy.py',
    'src/backends/tool_orchestrator.py',

    # --- src/bible ---
    'src/bible/__init__.py',
    'src/bible/bible_discovery.py',
    'src/bible/bible_injector.py',
    'src/bible/bible_lifecycle.py',
    'src/bible/bible_parser.py',
    'src/bible/bible_schema.py',

    # --- src/claude ---
    'src/claude/__init__.py',
    'src/claude/diff_viewer.py',
    'src/claude/prompt_preprocessor.py',
    'src/claude/snippet_manager.py',

    # --- src/data ---
    'src/data/__init__.py',
    'src/data/chat_history_manager.py',
    'src/data/history_manager.py',
    'src/data/project_manager.py',
    'src/data/session_manager.py',
    'src/data/workflow_logger.py',
    'src/data/workflow_state.py',
    'src/data/workflow_templates.py',

    # --- src/knowledge ---
    'src/knowledge/__init__.py',
    'src/knowledge/knowledge_manager.py',
    'src/knowledge/knowledge_worker.py',

    # --- src/mcp ---
    'src/mcp/__init__.py',
    'src/mcp/mcp_executor.py',
    'src/mcp/ollama_tools.py',

    # --- src/mcp_client ---
    'src/mcp_client/__init__.py',
    'src/mcp_client/helix_mcp_client.py',
    'src/mcp_client/server_manager.py',

    # --- src/memory ---
    'src/memory/__init__.py',
    'src/memory/memory_manager.py',
    'src/memory/model_config.py',

    # --- src/metrics ---
    'src/metrics/__init__.py',
    'src/metrics/budget_breaker.py',
    'src/metrics/usage_metrics.py',

    # --- src/mixins ---
    'src/mixins/__init__.py',
    'src/mixins/bible_context_mixin.py',

    # --- src/prompts ---
    'src/prompts/__init__.py',
    'src/prompts/prompt_packs.py',

    # --- src/rag ---
    'src/rag/__init__.py',
    'src/rag/diff_detector.py',
    'src/rag/document_chunker.py',
    'src/rag/document_cleanup.py',
    'src/rag/rag_builder.py',
    'src/rag/rag_executor.py',
    'src/rag/rag_planner.py',
    'src/rag/rag_verifier.py',
    'src/rag/time_estimator.py',

    # --- src/routing ---
    'src/routing/__init__.py',
    'src/routing/classifier.py',
    'src/routing/decision_logger.py',
    'src/routing/execution.py',
    'src/routing/fallback.py',
    'src/routing/hybrid_router.py',
    'src/routing/model_presets.py',
    'src/routing/policy_checker.py',
    'src/routing/router.py',
    'src/routing/routing_executor.py',
    'src/routing/task_types.py',

    # --- src/security ---
    'src/security/__init__.py',
    'src/security/approvals_store.py',
    'src/security/mcp_policy.py',
    'src/security/project_approval_profiles.py',
    'src/security/risk_gate.py',

    # --- src/tabs ---
    'src/tabs/__init__.py',
    'src/tabs/helix_orchestrator_tab.py',
    'src/tabs/claude_tab.py',
    'src/tabs/local_ai_tab.py',
    'src/tabs/history_tab.py',
    'src/tabs/information_collection_tab.py',
    'src/tabs/settings_cortex_tab.py',

    # --- src/ui ---
    'src/ui/__init__.py',
    'src/ui/components/__init__.py',
    'src/ui/components/history_citation_widget.py',
    'src/ui/components/workflow_bar.py',

    # --- src/ui_designer ---
    'src/ui_designer/__init__.py',
    'src/ui_designer/layout_analyzer.py',
    'src/ui_designer/qss_generator.py',
    'src/ui_designer/ui_refiner.py',

    # --- src/web ---
    'src/web/__init__.py',
    'src/web/server.py',
    'src/web/api_routes.py',
    'src/web/auth.py',
    'src/web/chat_store.py',
    'src/web/file_transfer.py',
    'src/web/launcher.py',
    'src/web/rag_bridge.py',
    'src/web/signal_bridge.py',
    'src/web/ws_manager.py',

    # --- src/widgets ---
    'src/widgets/__init__.py',
    'src/widgets/bible_notification.py',
    'src/widgets/bible_panel.py',
    'src/widgets/chat_history_panel.py',
    'src/widgets/chat_input.py',
    'src/widgets/chat_widgets.py',
    'src/widgets/execution_monitor_widget.py',
    'src/widgets/neural_visualizer.py',
    'src/widgets/no_scroll_widgets.py',
    'src/widgets/rag_lock_overlay.py',
    'src/widgets/rag_progress_widget.py',
    'src/widgets/section_save_button.py',
    'src/widgets/web_lock_overlay.py',

    # --- frontend ---
    'frontend/src/main.jsx',
    'frontend/src/App.jsx',
    'frontend/src/i18n/index.jsx',
    'frontend/src/components/ChatListPanel.jsx',
    'frontend/src/components/ChatView.jsx',
    'frontend/src/components/ContextModeSelector.jsx',
    'frontend/src/components/FileBrowserModal.jsx',
    'frontend/src/components/FileManagerView.jsx',
    'frontend/src/components/InputBar.jsx',
    'frontend/src/components/LLMStatusPanel.jsx',
    'frontend/src/components/LocalAIView.jsx',
    'frontend/src/components/LoginScreen.jsx',
    'frontend/src/components/MarkdownRenderer.jsx',
    'frontend/src/components/MixAIView.jsx',
    'frontend/src/components/PhaseIndicator.jsx',
    'frontend/src/components/SettingsView.jsx',
    'frontend/src/components/StatusIndicator.jsx',
    'frontend/src/components/TabBar.jsx',
    'frontend/src/hooks/useAuth.js',
    'frontend/src/hooks/useWebSocket.js',
    'frontend/public/sw.js',

    # --- i18n ---
    # config/ is intentionally excluded - may contain API keys / webhook URLs
    'i18n/ja.json',
    'i18n/en.json',
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
print('Total files: {}'.format(len(files)))
