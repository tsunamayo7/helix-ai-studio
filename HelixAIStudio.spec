# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['HelixAIStudio.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src', 'src'),
        ('config', 'config'),
    ],
    hiddenimports=[
        # PyQt6 Core modules (required for EXE)
        'PyQt6',
        'PyQt6.sip',  # Critical: Required for PyInstaller EXE
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        # Application modules
        'src',
        'src.main_window',
        'src.backends',
        'src.backends.base',
        'src.backends.claude_backend',
        'src.backends.gemini_backend',
        'src.backends.local_backend',
        'src.backends.local_connector',  # Phase 3.0
        'src.backends.registry',  # Phase 2.0
        'src.claude',
        'src.claude.diff_viewer',
        'src.claude.prompt_preprocessor',
        'src.data',
        'src.data.history_manager',
        'src.data.project_manager',
        'src.data.session_manager',
        'src.data.workflow_logger',
        'src.data.workflow_state',
        'src.data.workflow_templates',
        'src.data.chat_history_manager',  # v3.1.0: Chat history management
        'src.gemini',
        'src.memory',  # v8.1.0: 4層メモリシステム
        'src.memory.memory_manager',  # v8.1.0: HelixMemoryManager
        # v8.3.0: src.helix_core 完全削除済 — memory_manager.pyが4層メモリ+TKG+RAPTORを内包
        'src.mcp',
        'src.mcp.mcp_executor',
        'src.mcp_client',
        'src.mcp_client.helix_mcp_client',  # Phase 3.x
        'src.mcp_client.server_manager',  # Phase 3.x
        'src.metrics',
        'src.metrics.usage_metrics',
        'src.metrics.budget_breaker',  # Phase 2.8
        'src.prompts',  # Phase 2.9
        'src.prompts.prompt_packs',  # Phase 2.9
        'src.routing',
        'src.routing.task_types',
        'src.routing.classifier',
        'src.routing.router',
        'src.routing.fallback',
        'src.routing.execution',
        'src.routing.decision_logger',  # Phase 2.5
        'src.routing.policy_checker',  # Phase 2.6
        'src.routing.model_presets',  # Phase 2.7
        'src.routing.routing_executor',  # Phase 2.x
        'src.routing.hybrid_router',  # Phase 4.0 (v2.0.0)
        'src.backends.model_repository',  # Phase 4.0 (v2.0.0)
        # v8.3.0: helix_core残余 (feedback_collector, vector_store, rag_pipeline, mother_ai) 削除済
        'src.backends.local_llm_manager',  # Phase 3.0 (corrected path)
        'src.backends.thermal_monitor',  # Phase 3.0 (corrected: was thermal_controller)
        'src.backends.thermal_policy',  # Phase 3.0
        'src.backends.cloud_adapter',  # Phase 4.0
        # v4.0: 削除済み - 'src.tabs.knowledge_dashboard_tab'
        # v4.0: 削除済み - 'src.tabs.encyclopedia_tab'
        # v4.0: 削除済み - 'src.tabs.trinity_dashboard_tab'
        # v4.0: 削除済み - 'src.tabs.screenshot_capturer'
        'src.security',
        'src.security.risk_gate',
        'src.security.approvals_store',
        'src.security.mcp_policy',
        'src.security.project_approval_profiles',
        'src.tabs',
        'src.tabs.claude_tab',
        # v4.0: 削除済み - 'src.tabs.gemini_designer_tab'
        'src.tabs.settings_cortex_tab',
        # v4.0: 削除済み - 'src.tabs.trinity_ai_tab'
        'src.tabs.helix_orchestrator_tab',  # v4.0: Claude中心型ToolOrchestrator
        'src.tabs.information_collection_tab',  # v8.5.0: 情報収集タブ
        # v6.0.0: 削除済み - 'src.tabs.chat_creation_tab'
        # v4.0: 削除済み - 'src.tabs.cortex_audit_tab'
        # v4.0: 削除済み - 'src.tabs.routing_log_widget'
        'src.backends.tool_orchestrator',  # v4.0: NEW
        # v7.0.0: 3Phase実行パイプライン
        'src.backends.mix_orchestrator',  # v7.0.0: 3Phase Orchestrator
        'src.backends.sequential_executor',  # v7.0.0: Phase 2 順次実行エンジン
        # v7.0.0: 削除済み - parallel_pool, quality_verifier, phase1_parser, phase1_prompt, phase4_prompt
        'src.widgets',  # v5.0: UI enhancement widgets
        'src.widgets.chat_input',  # v5.0: Enhanced chat input
        'src.widgets.neural_visualizer',  # v6.2.0: Neural Flow Visualizer
        'src.widgets.vram_simulator',  # v6.2.0: VRAM Budget Simulator
        'src.widgets.bible_panel',  # v8.0.0: BIBLE Manager UI Panel
        'src.widgets.bible_notification',  # v8.0.0: BIBLE Notification Widget
        'src.widgets.chat_widgets',  # v8.0.0: Chat enhancement widgets
        'src.widgets.rag_progress_widget',  # v8.5.0: RAG Progress Widget
        'src.widgets.rag_lock_overlay',  # v8.5.0: RAG Lock Overlay
        # v6.1.0: ondemand_settings 削除 (5Phase統合で不要)
        'src.knowledge',  # v5.0: Knowledge management
        'src.knowledge.knowledge_manager',  # v5.0: Knowledge manager
        'src.knowledge.knowledge_worker',  # v5.0: Knowledge worker
        'src.ui',
        'src.ui.components',
        'src.ui.components.workflow_bar',  # Phase 2.x
        'src.ui.components.history_citation_widget',  # v3.1.0: History citation dialog
        'src.ui_designer',
        'src.ui_designer.ui_refiner',  # Phase 3.x
        'src.ui_designer.qss_generator',  # Phase 3.x
        'src.ui_designer.layout_analyzer',  # Phase 3.x
        'src.utils',
        'src.utils.constants',
        'src.utils.diagnostics',
        'src.utils.diff_risk',
        'src.utils.markdown_renderer',  # v8.0.0: Markdown→HTML renderer
        'src.utils.styles',  # v8.0.0: Cyberpunk Minimal theme styles
        # v8.0.0: BIBLE Manager modules
        'src.bible',
        'src.bible.bible_schema',
        'src.bible.bible_parser',
        'src.bible.bible_discovery',
        'src.bible.bible_injector',
        'src.bible.bible_lifecycle',
        # v8.5.0: RAG構築モジュール
        'src.rag',
        'src.rag.rag_builder',
        'src.rag.rag_planner',
        'src.rag.rag_executor',
        'src.rag.rag_verifier',
        'src.rag.document_chunker',
        'src.rag.document_cleanup',
        'src.rag.diff_detector',
        'src.rag.time_estimator',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='HelixAIStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # v2.2.4: Production build (no console)
    disable_windowed_traceback=True,  # v3.9.6: PyInstaller一時ディレクトリ削除警告を非表示
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',  # v3.3.0: Application icon
)
