#!/usr/bin/env python3
"""Run 7: Add i18n keys for routing_log, diff_viewer, workflow_bar, history_citation"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for lang_file in ['i18n/ja.json', 'i18n/en.json']:
    fp = os.path.join(BASE, lang_file)
    with open(fp, 'r', encoding='utf-8') as f:
        data = json.load(f)

    is_en = 'en' in lang_file

    for ns in ['routingLog', 'diffViewer', 'workflowBar', 'historyCitation']:
        if ns not in data['desktop']:
            data['desktop'][ns] = {}

    # ========= routingLog =========
    rl = data['desktop']['routingLog']
    if is_en:
        rl.update({
            'detailDialogTitle': 'Routing Decision Detail',
            'detailHeader': '=== Routing Decision Detail ===',
            'fieldTimestamp': 'Timestamp',
            'fieldSessionId': 'Session ID',
            'fieldPhase': 'Phase',
            'fieldTaskType': 'Task Type',
            'fieldSelectedBackend': 'Selected Backend',
            'fieldUserForced': 'User Specified',
            'fieldFinalStatus': 'Final Status',
            'fieldFallbackAttempted': 'Fallback Attempted',
            'fieldPreset': 'Preset',
            'fieldPromptPack': 'Prompt Pack',
            'fieldLocalAvailable': 'Local Available',
            'fieldDurationMs': 'Duration (ms)',
            'fieldTokensEst': 'Tokens (est)',
            'fieldCostEst': 'Cost (USD)',
            'fieldErrorType': 'Error Type',
            'fieldErrorMessage': 'Error Message',
            'fieldPolicyBlocked': 'Policy Blocked',
            'fieldBlockReason': 'Block Reason',
            'reasonCodesLabel': 'Reason Codes:',
            'fallbackChainLabel': 'Fallback Chain:',
            'approvalSnapshotLabel': 'Approval Snapshot:',
            'title': 'Routing Decision Log',
            'titleTooltip': 'View backend selection history.\nTrack why each backend was selected, fallback status, etc.',
            'refreshBtn': '\U0001f504 Refresh',
            'refreshTooltip': 'Reload logs',
            'filterGroup': 'Filter',
            'statusLabel': 'Status:',
            'statusAll': 'All',
            'statusFilterTooltip': 'Filter by success/error/blocked',
            'backendLabel': 'Backend:',
            'backendAll': 'All',
            'backendFilterTooltip': 'Filter by backend',
            'sessionLabel': 'Session:',
            'sessionPlaceholder': 'Filter by session ID...',
            'sessionFilterTooltip': 'Show only logs for a specific session',
            'tableHeaders': ['Timestamp', 'Backend', 'Status', 'Task Type', 'Fallback', 'Reason'],
            'loadingStatus': 'Loading logs...',
            'detailBtn': 'Show Details',
            'detailTooltip': 'Show details of the selected log',
            'logCount': 'Logs: {count}',
            'errorStatus': 'Error: {error}',
            'loadErrorTitle': 'Log Load Error',
            'loadErrorMsg': 'Failed to load routing logs:\n{error}',
            'filteredLogCount': 'Logs: {count} (filtered)',
            'statsFormat': 'Success rate: {rate}% | Success: {success} | Error: {error} | Blocked: {blocked} | Fallback: {fallback}',
            'noStats': 'No statistics',
        })
    else:
        rl.update({
            'detailDialogTitle': '\u30eb\u30fc\u30c6\u30a3\u30f3\u30b0\u6c7a\u5b9a\u8a73\u7d30',
            'detailHeader': '=== \u30eb\u30fc\u30c6\u30a3\u30f3\u30b0\u6c7a\u5b9a\u8a73\u7d30 ===',
            'fieldTimestamp': '\u30bf\u30a4\u30e0\u30b9\u30bf\u30f3\u30d7',
            'fieldSessionId': '\u30bb\u30c3\u30b7\u30e7\u30f3ID',
            'fieldPhase': '\u30d5\u30a7\u30fc\u30ba',
            'fieldTaskType': '\u30bf\u30b9\u30af\u7a2e\u5225',
            'fieldSelectedBackend': '\u9078\u629eBackend',
            'fieldUserForced': '\u30e6\u30fc\u30b6\u30fc\u6307\u5b9a',
            'fieldFinalStatus': '\u6700\u7d42\u30b9\u30c6\u30fc\u30bf\u30b9',
            'fieldFallbackAttempted': '\u30d5\u30a9\u30fc\u30eb\u30d0\u30c3\u30af\u8a66\u884c',
            'fieldPreset': 'Preset',
            'fieldPromptPack': 'Prompt Pack',
            'fieldLocalAvailable': 'Local\u5229\u7528\u53ef\u80fd',
            'fieldDurationMs': '\u51e6\u7406\u6642\u9593 (ms)',
            'fieldTokensEst': '\u30c8\u30fc\u30af\u30f3\u6570 (\u63a8\u5b9a)',
            'fieldCostEst': '\u30b3\u30b9\u30c8 (USD)',
            'fieldErrorType': '\u30a8\u30e9\u30fc\u7a2e\u5225',
            'fieldErrorMessage': '\u30a8\u30e9\u30fc\u30e1\u30c3\u30bb\u30fc\u30b8',
            'fieldPolicyBlocked': '\u30dd\u30ea\u30b7\u30fc\u30d6\u30ed\u30c3\u30af',
            'fieldBlockReason': '\u30d6\u30ed\u30c3\u30af\u7406\u7531',
            'reasonCodesLabel': '\u7406\u7531\u30b3\u30fc\u30c9:',
            'fallbackChainLabel': '\u30d5\u30a9\u30fc\u30eb\u30d0\u30c3\u30af\u30c1\u30a7\u30fc\u30f3:',
            'approvalSnapshotLabel': '\u627f\u8a8d\u30b9\u30ca\u30c3\u30d7\u30b7\u30e7\u30c3\u30c8:',
            'title': '\u30eb\u30fc\u30c6\u30a3\u30f3\u30b0\u6c7a\u5b9a\u30ed\u30b0',
            'titleTooltip': 'Backend\u9078\u629e\u306e\u5c65\u6b74\u3092\u78ba\u8a8d\u3067\u304d\u307e\u3059\u3002\n\u306a\u305c\u305d\u306eBackend\u304c\u9078\u3070\u308c\u305f\u304b\u3001\u30d5\u30a9\u30fc\u30eb\u30d0\u30c3\u30af\u306e\u6709\u7121\u306a\u3069\u3092\u8ffd\u8de1\u3067\u304d\u307e\u3059\u3002',
            'refreshBtn': '\U0001f504 \u66f4\u65b0',
            'refreshTooltip': '\u30ed\u30b0\u3092\u518d\u8aad\u307f\u8fbc\u307f\u3057\u307e\u3059',
            'filterGroup': '\u30d5\u30a3\u30eb\u30bf',
            'statusLabel': '\u30b9\u30c6\u30fc\u30bf\u30b9:',
            'statusAll': '\u5168\u3066',
            'statusFilterTooltip': '\u6210\u529f/\u30a8\u30e9\u30fc/\u30d6\u30ed\u30c3\u30af\u3067\u30d5\u30a3\u30eb\u30bf\u3057\u307e\u3059',
            'backendLabel': 'Backend:',
            'backendAll': '\u5168\u3066',
            'backendFilterTooltip': 'Backend\u3067\u30d5\u30a3\u30eb\u30bf\u3057\u307e\u3059',
            'sessionLabel': '\u30bb\u30c3\u30b7\u30e7\u30f3:',
            'sessionPlaceholder': '\u30bb\u30c3\u30b7\u30e7\u30f3ID\u3067\u30d5\u30a3\u30eb\u30bf...',
            'sessionFilterTooltip': '\u7279\u5b9a\u306e\u30bb\u30c3\u30b7\u30e7\u30f3\u306e\u30ed\u30b0\u306e\u307f\u8868\u793a\u3057\u307e\u3059',
            'tableHeaders': ['\u30bf\u30a4\u30e0\u30b9\u30bf\u30f3\u30d7', 'Backend', '\u30b9\u30c6\u30fc\u30bf\u30b9', '\u30bf\u30b9\u30af\u7a2e\u5225', '\u30d5\u30a9\u30fc\u30eb\u30d0\u30c3\u30af', '\u7406\u7531'],
            'loadingStatus': '\u30ed\u30b0\u8aad\u307f\u8fbc\u307f\u4e2d...',
            'detailBtn': '\u8a73\u7d30\u3092\u8868\u793a',
            'detailTooltip': '\u9078\u629e\u3057\u305f\u30ed\u30b0\u306e\u8a73\u7d30\u3092\u8868\u793a\u3057\u307e\u3059',
            'logCount': '\u30ed\u30b0: {count}\u4ef6',
            'errorStatus': '\u30a8\u30e9\u30fc: {error}',
            'loadErrorTitle': '\u30ed\u30b0\u8aad\u307f\u8fbc\u307f\u30a8\u30e9\u30fc',
            'loadErrorMsg': '\u30eb\u30fc\u30c6\u30a3\u30f3\u30b0\u30ed\u30b0\u306e\u8aad\u307f\u8fbc\u307f\u306b\u5931\u6557\u3057\u307e\u3057\u305f:\n{error}',
            'filteredLogCount': '\u30ed\u30b0: {count}\u4ef6 (\u30d5\u30a3\u30eb\u30bf\u5f8c)',
            'statsFormat': '\u6210\u529f\u7387: {rate}% | \u6210\u529f: {success} | \u30a8\u30e9\u30fc: {error} | \u30d6\u30ed\u30c3\u30af: {blocked} | \u30d5\u30a9\u30fc\u30eb\u30d0\u30c3\u30af: {fallback}',
            'noStats': '\u7d71\u8a08\u306a\u3057',
        })

    # ========= diffViewer =========
    dv = data['desktop']['diffViewer']
    if is_en:
        dv.update({
            'windowTitle': 'Diff Preview - Risk Assessment',
            'riskSummaryGroup': 'Risk Summary',
            'riskLevelHigh': '\u26a0\ufe0f Risk Level: HIGH (Score: {score}/100)',
            'riskLevelMedium': '\u26a0\ufe0f Risk Level: MEDIUM (Score: {score}/100)',
            'riskLevelLow': '\u2713 Risk Level: LOW (Score: {score}/100)',
            'statsFormat': 'Files changed: {files} | Added: +{added} lines | Deleted: -{deleted} lines',
            'filesDeletedSuffix': ' | Files deleted: {count}',
            'riskFactorsLabel': '\u3010Risk Factors\u3011',
            'sensitiveWarning': '\u26a0\ufe0f Contains changes to sensitive files',
            'sensitiveFilesMore': ' and {count} more',
            'sensitiveTarget': 'Affected: {files}',
            'diffPreviewGroup': 'Diff Preview',
            'cancelBtn': 'Cancel',
            'applyBtn': 'Apply',
            'applyBtnHighRisk': '\u26a0\ufe0f Apply (HIGH RISK)',
            'approvalRequiredTitle': 'Approval Required',
            'approvalRequiredMsg': 'This operation requires approval.\n\n{message}\n\nPlease complete approval in S3 Risk Gate and try again.',
            'highRiskConfirmTitle': 'High Risk Operation Confirmation',
            'highRiskConfirmMsg': 'This operation has been assessed as high risk.\n\nRisk Score: {score}/100\n\nMain factors:\n{reasons}\n\nProceed with applying?',
        })
    else:
        dv.update({
            'windowTitle': 'Diff \u30d7\u30ec\u30d3\u30e5\u30fc - \u5371\u967a\u5ea6\u8a55\u4fa1',
            'riskSummaryGroup': '\u5371\u967a\u5ea6\u30b5\u30de\u30ea',
            'riskLevelHigh': '\u26a0\ufe0f \u30ea\u30b9\u30af\u30ec\u30d9\u30eb: HIGH (\u30b9\u30b3\u30a2: {score}/100)',
            'riskLevelMedium': '\u26a0\ufe0f \u30ea\u30b9\u30af\u30ec\u30d9\u30eb: MEDIUM (\u30b9\u30b3\u30a2: {score}/100)',
            'riskLevelLow': '\u2713 \u30ea\u30b9\u30af\u30ec\u30d9\u30eb: LOW (\u30b9\u30b3\u30a2: {score}/100)',
            'statsFormat': '\u5909\u66f4\u30d5\u30a1\u30a4\u30eb\u6570: {files} | \u8ffd\u52a0: +{added}\u884c | \u524a\u9664: -{deleted}\u884c',
            'filesDeletedSuffix': ' | \u30d5\u30a1\u30a4\u30eb\u524a\u9664: {count}\u4ef6',
            'riskFactorsLabel': '\u3010\u30ea\u30b9\u30af\u8981\u56e0\u3011',
            'sensitiveWarning': '\u26a0\ufe0f \u30bb\u30f3\u30b7\u30c6\u30a3\u30d6\u306a\u30d5\u30a1\u30a4\u30eb\u3078\u306e\u5909\u66f4\u304c\u542b\u307e\u308c\u3066\u3044\u307e\u3059',
            'sensitiveFilesMore': ' \u4ed6{count}\u4ef6',
            'sensitiveTarget': '\u5bfe\u8c61: {files}',
            'diffPreviewGroup': '\u5dee\u5206\u30d7\u30ec\u30d3\u30e5\u30fc',
            'cancelBtn': '\u30ad\u30e3\u30f3\u30bb\u30eb',
            'applyBtn': '\u9069\u7528\u3059\u308b',
            'applyBtnHighRisk': '\u26a0\ufe0f \u9069\u7528\u3059\u308b\uff08HIGH RISK\uff09',
            'approvalRequiredTitle': '\u627f\u8a8d\u4e0d\u8db3',
            'approvalRequiredMsg': '\u3053\u306e\u64cd\u4f5c\u306b\u306f\u627f\u8a8d\u304c\u5fc5\u8981\u3067\u3059\u3002\n\n{message}\n\nS3 Risk Gate\u3067\u5fc5\u8981\u306a\u627f\u8a8d\u3092\u884c\u3063\u3066\u304b\u3089\u518d\u5ea6\u304a\u8a66\u3057\u304f\u3060\u3055\u3044\u3002',
            'highRiskConfirmTitle': '\u9ad8\u30ea\u30b9\u30af\u64cd\u4f5c\u306e\u78ba\u8a8d',
            'highRiskConfirmMsg': '\u3053\u306e\u64cd\u4f5c\u306f\u9ad8\u30ea\u30b9\u30af\u3068\u5224\u5b9a\u3055\u308c\u307e\u3057\u305f\u3002\n\n\u30ea\u30b9\u30af\u30b9\u30b3\u30a2: {score}/100\n\n\u4e3b\u306a\u8981\u56e0:\n{reasons}\n\n\u672c\u5f53\u306b\u9069\u7528\u3057\u307e\u3059\u304b\uff1f',
        })

    # ========= workflowBar =========
    wb = data['desktop']['workflowBar']
    if is_en:
        wb.update({
            'defaultPhase': 'S0: Intake',
            'defaultDesc': 'Receive the request from the user and organize requirements.',
            'flagsTooltip': 'Artifact flag status',
            'prevTooltip': 'Go back one phase (one step only)',
            'nextTooltip': 'Proceed to next phase (only if conditions are met)',
            'riskApprovalLabel': '\U0001f510 Approve Dangerous Operations (Risk Gate)',
            'riskApprovalTooltip': 'Approve dangerous operations (write, delete, etc.) in this phase.\nCannot proceed without approval.',
            'resetBtn': '\U0001f504 Phase Reset',
            'resetTooltip': 'Reset to S0 (Intake).',
            'nextDisabledTooltip': 'Cannot proceed: {msg}',
        })
    else:
        wb.update({
            'defaultPhase': 'S0: \u4f9d\u983c\u53d7\u9818 (Intake)',
            'defaultDesc': '\u30e6\u30fc\u30b6\u30fc\u304b\u3089\u306e\u4f9d\u983c\u3092\u53d7\u9818\u3057\u3001\u8981\u4ef6\u3092\u6574\u7406\u3057\u307e\u3059\u3002',
            'flagsTooltip': '\u6210\u679c\u7269\u30d5\u30e9\u30b0\u306e\u72b6\u614b',
            'prevTooltip': '\u524d\u306e\u5de5\u7a0b\u306b\u623b\u308a\u307e\u3059\uff081\u6bb5\u968e\u306e\u307f\uff09',
            'nextTooltip': '\u6b21\u306e\u5de5\u7a0b\u306b\u9032\u307f\u307e\u3059\uff08\u6761\u4ef6\u3092\u6e80\u305f\u3057\u3066\u3044\u308b\u5834\u5408\u306e\u307f\uff09',
            'riskApprovalLabel': '\U0001f510 \u5371\u967a\u64cd\u4f5c\u3092\u627f\u8a8d\u3059\u308b (Risk Gate)',
            'riskApprovalTooltip': '\u3053\u306e\u5de5\u7a0b\u3067\u5b9f\u65bd\u3059\u308b\u5371\u967a\u306a\u64cd\u4f5c\uff08\u66f8\u304d\u8fbc\u307f\u3001\u524a\u9664\u7b49\uff09\u3092\u627f\u8a8d\u3057\u307e\u3059\u3002\n\u627f\u8a8d\u3057\u306a\u3044\u3068\u6b21\u306e\u5de5\u7a0b\u306b\u9032\u3081\u307e\u305b\u3093\u3002',
            'resetBtn': '\U0001f504 \u5de5\u7a0b\u30ea\u30bb\u30c3\u30c8',
            'resetTooltip': '\u5de5\u7a0b\u3092S0\uff08\u4f9d\u983c\u53d7\u9818\uff09\u306b\u30ea\u30bb\u30c3\u30c8\u3057\u307e\u3059\u3002',
            'nextDisabledTooltip': '\u6b21\u306e\u5de5\u7a0b\u306b\u9032\u3081\u307e\u305b\u3093: {msg}',
        })

    # ========= historyCitation =========
    hc = data['desktop']['historyCitation']
    if is_en:
        hc.update({
            'aiLabel': 'AI:',
            'aiAll': 'All',
            'periodLabel': 'Period:',
            'periodAll': 'All',
            'periodToday': 'Today',
            'periodWeek': '1 Week',
            'periodMonth': '1 Month',
            'searchPlaceholder': 'Search keywords...',
            'searchBtn': '\U0001f50d Search',
            'previewGroup': 'Preview',
            'previewPlaceholder': 'Select a history item to preview it here',
            'insertBtn': '\U0001f4cb Insert Citation',
            'searchResultCount': 'Results: {count}',
            'searchError': 'Search error: {error}',
            'dialogTitle': 'Cite from Chat History',
            'dialogDesc': 'Search past chat history and insert selected content as a citation.\nSearch, select an item, and press "Insert Citation".',
            'promptLabel': '\U0001f4dd Prompt:',
            'responseLabel': '\U0001f916 Response ({source}):',
        })
    else:
        hc.update({
            'aiLabel': 'AI:',
            'aiAll': '\u3059\u3079\u3066',
            'periodLabel': '\u671f\u9593:',
            'periodAll': '\u3059\u3079\u3066',
            'periodToday': '\u4eca\u65e5',
            'periodWeek': '1\u9031\u9593',
            'periodMonth': '1\u30f6\u6708',
            'searchPlaceholder': '\u691c\u7d22\u30ad\u30fc\u30ef\u30fc\u30c9...',
            'searchBtn': '\U0001f50d \u691c\u7d22',
            'previewGroup': '\u30d7\u30ec\u30d3\u30e5\u30fc',
            'previewPlaceholder': '\u5c65\u6b74\u3092\u9078\u629e\u3059\u308b\u3068\u3053\u3053\u306b\u30d7\u30ec\u30d3\u30e5\u30fc\u304c\u8868\u793a\u3055\u308c\u307e\u3059',
            'insertBtn': '\U0001f4cb \u5f15\u7528\u3092\u633f\u5165',
            'searchResultCount': '\u691c\u7d22\u7d50\u679c: {count} \u4ef6',
            'searchError': '\u691c\u7d22\u30a8\u30e9\u30fc: {error}',
            'dialogTitle': '\u30c1\u30e3\u30c3\u30c8\u5c65\u6b74\u304b\u3089\u5f15\u7528',
            'dialogDesc': '\u904e\u53bb\u306e\u30c1\u30e3\u30c3\u30c8\u5c65\u6b74\u3092\u691c\u7d22\u3057\u3001\u9078\u629e\u3057\u305f\u5185\u5bb9\u3092\u30d7\u30ed\u30f3\u30d7\u30c8\u306b\u5f15\u7528\u3067\u304d\u307e\u3059\u3002\n\u691c\u7d22\u3057\u3066\u30a2\u30a4\u30c6\u30e0\u3092\u9078\u629e\u3057\u3001\u300c\u5f15\u7528\u3092\u633f\u5165\u300d\u3092\u62bc\u3057\u3066\u304f\u3060\u3055\u3044\u3002',
            'promptLabel': '\U0001f4dd \u30d7\u30ed\u30f3\u30d7\u30c8:',
            'responseLabel': '\U0001f916 \u5fdc\u7b54 ({source}):',
        })

    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

print('Done - keys added to both JSON files')

# Verify
for lang_file in ['i18n/ja.json', 'i18n/en.json']:
    fp = os.path.join(BASE, lang_file)
    with open(fp, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for ns in ['routingLog', 'diffViewer', 'workflowBar', 'historyCitation']:
        count = len(data['desktop'][ns])
        print(f'{lang_file}: {ns} = {count} keys')
