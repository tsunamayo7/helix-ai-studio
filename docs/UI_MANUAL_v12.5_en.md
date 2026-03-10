# Helix AI Studio v12.8.0 — UI Operations Manual

> Complete guide covering every tab and interactive element
> Last updated: 2026-03-08

---

## Table of Contents

0. [Getting Started](#0-getting-started)
1. [Common Operations](#1-common-operations)
2. [mixAI Tab — 3+1 Phase AI Pipeline](#2-mixai-tab--31-phase-ai-pipeline)
3. [soloAI Tab — Unified AI Chat](#3-soloai-tab--unified-ai-chat)
4. [CloudAI Settings Tab — Cloud Model Management](#4-cloudai-settings-tab--cloud-model-management)
5. [Ollama Settings Tab — Local LLM Management](#5-ollama-settings-tab--local-llm-management)
6. [History Tab — Chat History](#6-history-tab--chat-history)
7. [RAG Tab — Knowledge Base Management](#7-rag-tab--knowledge-base-management)
8. [Virtual Desktop Tab — Sandbox Environment](#8-virtual-desktop-tab--sandbox-environment)
9. [General Settings Tab](#9-general-settings-tab)
10. [Common Workflows](#10-common-workflows)
11. [Troubleshooting](#11-troubleshooting)

---

## 0. Getting Started

### Prerequisites

| Item | Requirement |
|------|-------------|
| OS | Windows 10/11 or macOS 12+ |
| Python | 3.10+ (3.11 recommended) |
| RAM | 16 GB or more |
| GPU | NVIDIA + CUDA (optional, for local LLMs). macOS uses Metal/CPU |

### Launch

```bash
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio
pip install -r requirements.txt
python HelixAIStudio.py          # macOS: python3
```

### First-Time Setup

1. **For local LLMs**: Install [Ollama](https://ollama.com) → go to **Ollama Settings tab** → run connection test
2. **For cloud AI**: Go to **General Settings tab → API Key Management** → enter and save your provider's API key
3. **For combined orchestration (mixAI)**: Complete both steps above, then go to **mixAI tab → Settings** to configure engines and models

---

## 1. Common Operations

### 1.1 Main Tab Bar (Top of Window)

Eight main tabs are displayed at the top of the window. Click to switch between features.

| Tab Name | Description |
|---|---|
| **mixAI** | 3+1 Phase AI pipeline (cloud + local LLM orchestration) |
| **soloAI** | Unified AI chat — Cloud AI (Claude/GPT/Gemini) + Ollama in one tab. Successor to cloudAI + localAI |
| **CloudAI Settings** | Cloud model management, authentication, execution options, MCP |
| **Ollama Settings** | Ollama connection, model management, local LLM settings |
| **History** | Unified chat history (supports legacy cloudAI/localAI logs) |
| **RAG** | Build knowledge bases from documents and ask questions |
| **Virtual Desktop** | Isolated sandbox (Windows Sandbox by default, Docker optional) |
| **General Settings** | API keys, display, Web UI, and global app settings |

### 1.2 Language Switching (Top Right)

- **"Japanese" button**: Active state shown in cyan. Switches to Japanese UI
- **"English" button**: Switches to English UI

Changes are applied in real-time across all tabs.

### 1.3 Status Bar (Bottom of Window)

- **Left**: Current processing state (`Ready`, active phase name, etc.)
- **Right**: Version display (e.g., `v12.5.0`)

### 1.4 Conversation Continue Panel (Shared Component)

Shared across the mixAI / cloudAI / localAI tabs, displayed at the bottom-right of the chat area. Use this panel to quickly respond when the AI asks questions or requests confirmation.

| Element | Action |
|---|---|
| **Continue input field** | Enter additional instructions or messages |
| **"Yes" button** (green) | Instantly send "Yes" |
| **"Continue" button** (teal) | Instantly send "Continue" |
| **"Execute" button** (purple) | Instantly send "Execute" |
| **"Send" / "Continue Send" button** | Send the text from the input field to continue processing |

### 1.5 Helix Pilot Screenshot Button (Bottom Right Corner)

A round button displayed at the bottom-right corner of all tabs. Click to take a screenshot of the current window (for Helix Pilot GUI automation integration).

---

## 2. mixAI Tab — Integrated Orchestration

A pipeline that orchestrates multiple AI models across five phases. Cloud AI (Claude / GPT / Gemini) handles planning and validation, while local LLMs (Ollama) handle execution — delivering high-quality results at a fraction of the cost.

### 2.1 Sub-tabs

- **Chat**: Main execution and display screen
- **Settings**: Detailed pipeline configuration

---

### 2.2 Chat Sub-tab

#### Header Area

| Element | Description |
|---|---|
| **Tab title** | "mixAI - Integrated Orchestration" |
| **Status message** | Current state such as "Ready. Enter a message." |

#### Chat Display Area (Center)

- AI responses are displayed in HTML format
- Phase progress (Phase 1–4) shown in real-time
- Code blocks with syntax highlighting
- User messages aligned right, AI messages aligned left

#### Tool Execution Log (Collapsible)

| Element | Description |
|---|---|
| **"Tool Execution Log (click to expand)"** | Click to expand/collapse. Shows Claude CLI tool usage logs |

#### Message Input Area (Bottom)

| Element | Action |
|---|---|
| **Text input field** | Enter your prompt. `Ctrl+Enter` to send |
| **Attach button** | Attach files (images, text, etc.) |
| **Snippet button** | Show snippet menu with prompt templates (e.g., VD coding templates) |
| **Cancel button** | Cancel the current processing |
| **Execute button** | Start the 3+1 Phase pipeline |

---

### 2.3 Settings Sub-tab

Scroll down to access all settings. After making changes, click "Save All Settings" at the top to save.

#### Save All Settings Button (Top)

| Element | Action |
|---|---|
| **"Save All Settings" button** | Save all sections at once |

#### P1/P3 Model Settings (Phase 1 Planning / Phase 3 Integration)

| Element | Action |
|---|---|
| **Engine selection combo** | Select engine: `claude-cli` / `anthropic-api` / `openai-api` / `google-api` / `ollama` |
| **Timeout (seconds)** | Execution timeout for Phase 1/3 |

> When a Claude engine is selected, additional options for model selection and Extended Thinking appear.

#### Phase 2 Agent Team Settings

| Element | Action |
|---|---|
| **P2 Engine selection combo** | Choose from `Ollama Sequential` / `CrewAI Sequential` / `CrewAI Hierarchical` |
| **Category model selectors** | Assign individual Ollama models to 5 categories: coding / research / thinking / translation / vision |
| **Image analysis model** | Model for image processing (editable combo) |
| **Embedding model** | Model for RAG embeddings (editable combo) |
| **Max retries** | Retry count on Phase 2 failure (0–5) |

#### Phase 3.5 Reasoning Settings

| Element | Action |
|---|---|
| **Phase 3.5 reasoning model** | Select an Ollama model for deep reasoning |

#### Phase 4 Refinement Settings

| Element | Action |
|---|---|
| **Phase 4 refinement model** | Select an Ollama model for final refinement |
| **Phase 4 VD sandbox apply checkbox** | When ON, writes Phase 4 file_changes directly to the Docker virtual desktop |

#### Ollama Connection

| Element | Action |
|---|---|
| **"Ollama Connection Test" button** | Test connection to the Ollama server |
| **"Refresh Model List" button** | Refresh model lists in all combo boxes |

#### Browser Use Settings

| Element | Action |
|---|---|
| **Browser Use enable checkbox** | Enable browser automation tool |

---

## 3. cloudAI Tab — Cloud AI Chat

One-on-one AI chat using Claude CLI, Anthropic API, OpenAI API, Google Gemini API, or Codex CLI.

### 3.1 Sub-tabs

- **Chat**: Main chat screen
- **Settings**: Engine, model, and MCP configuration

---

### 3.2 Chat Sub-tab

#### Model Display Bar (Top of Chat)

| Element | Action |
|---|---|
| **Tab title** | "cloudAI - Cloud AI" |
| **Model display** | Currently selected model name (e.g., `Claude Opus 4.6 [CLI]`) |
| **"..." button** | Show model selection dropdown |
| **Refresh button** | Refresh model list |

#### Chat Display Area

- AI responses streamed in real-time
- Code blocks and Markdown supported
- Tool usage results also displayed

#### Message Input Area

| Element | Action |
|---|---|
| **Text input field** | Enter message. `Ctrl+Enter` to send |
| **Attach button** | Attach files |
| **Snippet button** | Insert prompt templates |
| **"Continue Send" button** | Send follow-up while preserving conversation context |
| **Send button** | Send message (new session) |

---

### 3.3 Settings Sub-tab

#### Model Settings

| Element | Action |
|---|---|
| **Cloud model list** | List of registered models |
| **Add button** | Add a new model |
| **Delete button** | Delete selected model |
| **Edit button** | Edit model settings |
| **Reload button** | Reload model list from file |
| **Timeout (minutes)** | AI response timeout |

#### MCP & Options

| Element | Action |
|---|---|
| **Diff display checkbox** | Enable file change diff display |
| **Context carry-over checkbox** | Carry over conversation context |
| **Permission skip checkbox** | Skip permission confirmations |
| **Browser Use enable checkbox** | Browser automation tool |
| **Save button** | Save option settings |

#### Claude CLI Section

| Element | Action |
|---|---|
| **CLI version display** | Installed Claude CLI version |
| **"Check" button** | Re-check CLI version |

#### MCP Settings

| Element | Action |
|---|---|
| **Filesystem checkbox** | Enable filesystem tools |
| **Git checkbox** | Enable Git tools |
| **Brave Search checkbox** | Enable Brave search tools |
| **Save button** | Save MCP settings |

---

## 4. localAI Tab — Local LLM Chat

Chat with LLMs running locally on your GPU/CPU via Ollama. Works completely offline in a fully private environment.

### 4.1 Sub-tabs

- **Chat**: Main chat screen
- **Settings**: Ollama management, GitHub PAT, MCP settings

---

### 4.2 Chat Sub-tab

#### Model Selection Bar (Top of Chat)

| Element | Action |
|---|---|
| **Tab title** | "localAI - Local LLM Chat" |
| **Model display** | Current model name |
| **Model selection combo** | Choose from Ollama-installed models |
| **Refresh button** | Refresh model list |

#### Chat Display Area

- Local LLM responses displayed in real-time
- Code blocks and Markdown supported

#### Message Input Area

| Element | Action |
|---|---|
| **Text input field** | Enter message. `Ctrl+Enter` to send |
| **Attach button** | Attach files (effective for vision-capable models) |
| **Snippet button** | Insert prompt templates |
| **Send button** | Send message |

---

### 4.3 Settings Sub-tab

#### Ollama Management Section

| Element | Action |
|---|---|
| **Ollama status label** | Shows Ollama installation and connection status |
| **Host URL input** | Ollama server address (default: `http://localhost:11434`) |
| **"Connection Test" button** | Test connectivity to the Ollama server |
| **Model table** | List of installed models. Columns: Name, Size, Updated, Capabilities (Tool/Embed/Vision/Think) |
| **Model name input** | Enter model name to download (e.g., `gemma3:4b`) |
| **"Pull" button** | Download the specified model to Ollama |
| **"Delete" button** | Delete the selected model from the table |

#### GitHub Integration Section

| Element | Action |
|---|---|
| **GitHub PAT input** | GitHub Personal Access Token (password masked) |
| **"Test" button** | Verify PAT validity |
| **"Save" button** | Save PAT to settings file |

#### MCP Settings Section

| Element | Action |
|---|---|
| **Filesystem checkbox** | Enable filesystem tools |
| **Git checkbox** | Enable Git tools |
| **Brave Search checkbox** | Enable Brave search tools |
| **Save button** | Save MCP settings |

#### Browser Use Settings Section

| Element | Action |
|---|---|
| **Browser Use enable checkbox** | Enable browser automation tool |
| **Save button** | Save Browser Use settings |

---

## 5. History Tab — Chat History

Search and browse all past chats across cloudAI / mixAI / localAI / RAG.

### 5.1 Filter Bar (Top)

| Element | Action |
|---|---|
| **Search input** | Text search across chat history (incremental search) |
| **Tab filter combo** | Filter by tab: `All Tabs` / `cloudAI` / `mixAI` / `localAI` / `RAG` |
| **Sort order combo** | `Newest first` / `Oldest first` |
| **Refresh button** | Reload history data |

### 5.2 Message List (Left Panel)

- Message cards grouped by date
- Each card displays:
  - **Tab badge** (cloudAI / localAI etc., color-coded)
  - **Model name**
  - **Time**
  - **Message preview** (first portion)
- Click a card → detailed view on the right

### 5.3 Detail View (Right Panel)

| Element | Action |
|---|---|
| **Detail text display** | Full message text in HTML format |
| **"Copy" button** | Copy message content to clipboard |
| **"Quote to Other Tab" button** | Insert selected message as a quote in another tab's input |

---

## 6. RAG Tab — Knowledge Base Management

Build a RAG (Retrieval-Augmented Generation) knowledge base from your documents so AI can reference them when answering questions.

### 6.1 Sub-tabs

- **Chat**: Ask questions using the RAG knowledge base
- **Build**: Document management and RAG database construction
- **Settings**: Model and parameter configuration

---

### 6.2 Chat Sub-tab

| Element | Action |
|---|---|
| **RAG status display** | Database state ("Ready" / "Not built" etc.) |
| **Chat display area** | Shows AI responses including RAG search results |
| **Question input field** | Enter your question for the RAG |
| **Send button** | Submit the question |

#### Action Buttons (Below Input)

| Element | Action |
|---|---|
| **Add files button** | Add documents for RAG processing |
| **Plan preview button** | Preview the processing plan |
| **Build button** | Start RAG database construction |
| **Stop button** | Interrupt the build process |
| **Delete button** | Delete the RAG database |

---

### 6.3 Build Sub-tab

#### Folder Management Section

| Element | Action |
|---|---|
| **Folder path display** | Currently selected document folder |
| **"Open Folder" button** | Open the folder in file explorer |
| **File tree** | File list (name, size, updated, processing status) |
| **File count summary** | Total file count |
| **"Refresh" button** | Refresh the file list |

#### Plan Management Section

| Element | Action |
|---|---|
| **Plan status** | Plan generation progress |
| **Plan summary text** | Processing plan overview (read-only) |
| **"Copy Plan" button** | Copy plan to clipboard |
| **"Create Plan" button** | Generate a new plan |

#### Execution Control Section

| Element | Action |
|---|---|
| **"Start Build" button** | Begin RAG database construction |
| **"Stop" button** | Interrupt the build |
| **"Retry" button** | Retry a failed build |

#### Data Management Section

| Element | Action |
|---|---|
| **"Scan" button** | Scan for orphaned data (inconsistent entries) |
| **Orphan file tree** | List of orphaned files |
| **"Delete Orphans" button** | Remove detected orphaned data |
| **Document tree** | Individual document management list |
| **"Delete Selected Documents" button** | Remove checked documents from RAG |

---

### 6.4 Settings Sub-tab

#### Model Settings Section

| Element | Action |
|---|---|
| **Claude model selector** | Claude model for RAG processing |
| **Execution LLM selector** | Ollama model for chunk processing |
| **Quality evaluation LLM selector** | Model for quality checks |
| **Embedding model selector** | Model for vector embeddings |
| **Planner model selector** | Model for plan generation |
| **"Refresh Ollama Models" button** | Refresh model lists in combo boxes |

#### Chunk Settings

| Element | Action |
|---|---|
| **Chunk size (tokens)** | Text split size (SpinBox) |
| **Overlap** | Overlap size between chunks |

#### Advanced Features

| Element | Action |
|---|---|
| **Knowledge graph auto-update checkbox** | Automatically build knowledge graph |
| **HYPE enable checkbox** | Enable HYPE ranking |
| **Reranker enable checkbox** | Enable search result reranking |

#### Memory Settings

| Element | Action |
|---|---|
| **Auto-save memory checkbox** | Auto-save RAG conversation memory |
| **Knowledge base enable checkbox** | Enable knowledge base integration |
| **Encyclopedia mode checkbox** | Enable encyclopedic knowledge expansion |

---

## 7. Virtual Desktop Tab — Sandbox Environment

Operate a virtual desktop (Linux + NoVNC) inside a Docker container. Use it as a safe environment where AI writes files, then review diffs before applying changes to your host machine.

**Prerequisite**: Docker Desktop must be installed and running.

### 7.1 Sub-tabs

- **Desktop**: VNC viewer and operation tools
- **Settings**: Docker / Guacamole backend configuration

---

### 7.2 Desktop Sub-tab

#### Toolbar (Top)

| Element | Action |
|---|---|
| **Start button** (blue) | Create and start the sandbox container |
| **Stop button** | Stop the container |
| **Screenshot button** | Capture a screenshot of the virtual desktop |
| **Diff Check button** | Show change diff with host (active only when container is running) |
| **Reset button** (red) | Reset the sandbox to its initial state |

#### Status Display

| Element | Description |
|---|---|
| **"Sandbox: Stopped"** | Current container state: `Running` / `Stopped` / `Creating...` etc. |

#### File Browser (Left Panel)

| Element | Action |
|---|---|
| **File label + Refresh button** | File tree header and refresh |
| **Path display** | Current directory path (default: `/workspace`) |
| **File tree** | File list inside the sandbox. Double-click to navigate folders |
| **"Up" button** | Navigate to parent directory |

#### VNC Viewer (Center Main Area)

| State | Display |
|---|---|
| **Stopped** | Placeholder: "Start the Sandbox to display the virtual desktop here" |
| **Running** | NoVNC web viewer embedded. Mouse and keyboard input supported |

- **"Open in Browser" button**: Open NoVNC in an external browser (if embedded display has issues)

#### Promotion Panel (Shown When Diff Check Is Pressed)

Panel for reviewing and applying sandbox changes to the host machine.

| Element | Action |
|---|---|
| **Changed file tree** | Checklist of changed files (file path, change type) |
| **"Diff Preview" button** | Show diff for selected files |
| **"Apply" button** | Apply checked files to the host |
| **"Cancel" button** | Cancel the promotion |

---

### 7.3 Settings Sub-tab

#### Backend Selection

| Element | Action |
|---|---|
| **Backend combo** | Select `Docker` or `Guacamole` |

#### Docker Settings (When Docker Is Selected)

##### Basic Settings

| Element | Action |
|---|---|
| **Image name combo** | Docker image name (editable, default: `helix-sandbox`) |
| **CPU limit** | Allocated CPU cores (1–16) |
| **Memory limit** | Allocated memory in GB (1–32) |
| **VNC resolution** | `1280x720` / `1920x1080` / `1024x768` |
| **Timeout** | Auto-stop time (5–480 minutes) |

##### Workspace Settings

| Element | Action |
|---|---|
| **Project path input** | Host-side project path |
| **"Browse" button** | Folder selection dialog |
| **Read-only mount** | Mount host folder as read-only |
| **Read-write mount** | Mount host folder with read-write access |
| **Exclude patterns** | Patterns to exclude from mount (e.g., `.git`, `node_modules`) |

##### Network Settings

| Element | Action |
|---|---|
| **Isolated mode** | Network-isolate the container (security-focused) |
| **Bridge mode** | Bridge to host network (when external communication is needed) |

##### Docker Status Section

| Element | Action |
|---|---|
| **Docker daemon status** | Docker Desktop running state |
| **Image status** | helix-sandbox image availability |
| **"Build Image" button** | Build the Docker image (required for first time) |
| **"Delete Image" button** | Delete the image |
| **"Refresh" button** | Re-check status |

#### Guacamole Settings (When Guacamole Is Selected)

| Element | Action |
|---|---|
| **Server URL** | Guacamole server address |
| **Username** | Login username |
| **Password** | Login password (masked) |
| **Connection combo** | Available connection list |
| **Status display** | Guacamole connection state |
| **"Refresh" button** | Re-fetch connection list |

---

## 8. Settings Tab — General Settings

Manage settings that affect the entire application. Scroll to access all sections.

### 8.1 AI Status Check Section

| Element | Action |
|---|---|
| **Status result label** | Shows detection status of Claude CLI and other tools |
| **"AI Status Check" button** | Re-check installed AI tool status |

### 8.2 Optional Tools Section

| Element | Action |
|---|---|
| **Description label** | Explanation of optional dependency packages |
| **browser-use status** | Installation status of browser-use package |
| **sentence-transformers status** | Installation status of sentence-transformers |
| **"Install" button** | Install missing packages |

### 8.3 API Key Management Section

| Element | Action |
|---|---|
| **Security notice** | Warning about API key handling |
| **Brave Search API key input** | Brave Search API key |
| **Anthropic API key input** | Anthropic API key |
| **OpenAI API key input** | OpenAI API key |
| **Google Gemini API key input** | Google API key |

> Each key input field has a masked display and save button.

### 8.4 Display & Theme Section

| Element | Action |
|---|---|
| **Font size** | Adjust UI font size |

### 8.5 Automation Section

| Element | Action |
|---|---|
| **Automation checkboxes** | Enable/disable auto-save, auto-context injection, etc. |

### 8.6 BIBLE Context Injection Section

| Element | Action |
|---|---|
| **Description text** | Explanation of BIBLE file (project specification) auto-injection |
| **BIBLE enable checkbox** | When ON, project specifications from the BIBLE folder are automatically added to all AI prompts |

> Enabling BIBLE allows the AI to understand your project's design principles and rules before responding.

### 8.7 Web UI Settings Section

| Element | Action |
|---|---|
| **Web server status** | FastAPI/Uvicorn server running state |
| **Server URL** | Web UI access URL (click to open in browser) |
| **Auto-start checkbox** | Automatically start web server on app launch |
| **Port number** | Web server listen port (default: `8500`) |

#### Discord Notifications

| Element | Action |
|---|---|
| **Webhook URL input** | Discord Webhook URL |
| **Start notification checkbox** | Notify on AI execution start |
| **Completion notification checkbox** | Notify on execution completion |
| **Error notification checkbox** | Notify on errors |

### 8.8 Helix Pilot (GUI Automation) Settings Section

| Element | Action |
|---|---|
| **Helix Pilot enable checkbox** | Enable/disable GUI automation |
| **Connection status** | Pilot connection state |
| **Vision model input** | Vision LLM model for screen analysis (e.g., `mistral-small3.2`) |
| **Reasoning model input** | Reasoning model for plan generation (e.g., `gemma3:27b`) |
| **Max steps** | Maximum steps for automation |
| **Timeout** | Automation timeout in seconds |
| **Safe mode checkbox** | Enable/disable safety features |
| **Default window name** | Default target window name for operations |

---

## 9. Common Workflows

### 9.1 Chat with a Local LLM

1. Install and start [Ollama](https://ollama.com)
2. **localAI tab → Settings** → confirm Host URL → "Connection Test"
3. If no models exist, type `gemma3:4b` in the model name input → "Pull"
4. **localAI tab → Chat** → select model from combo → type message → Send

### 9.2 Chat with Claude / GPT / Gemini

1. **Settings tab → API Key Management** → enter and save your provider's key
2. **cloudAI tab → Chat** → click "..." button to select model → type message → Send

### 9.3 Run the mixAI Pipeline

1. Ensure a cloud AI API key is configured (for Phase 1/3)
2. Ensure Ollama models are installed (for Phase 2)
3. **mixAI tab → Settings** → configure engines and models for each phase → "Save All Settings"
4. **mixAI tab → Chat** → enter prompt → "Execute"

### 9.4 Build a RAG Knowledge Base and Ask Questions

1. **RAG tab → Build** → "Open Folder" to verify target documents
2. **RAG tab → Settings** → select models
3. **RAG tab → Build** → "Create Plan" → "Start Build"
4. After build completes, **RAG tab → Chat** to ask questions

### 9.5 Use the Docker Virtual Desktop

1. Install and start Docker Desktop
2. **Virtual Desktop tab → Settings** → confirm Docker status shows "Running"
3. If image not built, click "Build Image"
4. **Virtual Desktop tab → Desktop** → "Start" button
5. Work inside the VNC viewer. When done, click "Diff Check" → select files → "Apply" to push changes to host

---

## 10. Troubleshooting

| Symptom | Resolution |
|---|---|
| **Cannot connect to Ollama** | Verify Ollama is running → localAI tab → Settings → Connection Test. Confirm Host URL is `http://localhost:11434` |
| **Cloud AI returns errors** | Check API keys in Settings → API Key Management. Verify you haven't exceeded API rate limits |
| **mixAI Phase 2 fails** | Verify required models are installed in Ollama. Run mixAI → Settings → "Ollama Connection Test" |
| **VNC doesn't display** | Confirm Docker Desktop is running. VD → Settings → check Docker status. Try "Open in Browser" for external viewer |
| **Japanese text is garbled** | Ensure Python encoding is UTF-8. Set `PYTHONUTF8=1` and restart |
| **Send button doesn't respond** | Check that the input field is not empty. Wait for current processing to complete or cancel first |

---

## Appendix: Keyboard Shortcuts

| Shortcut | Action | Applicable Tabs |
|---|---|---|
| `Ctrl+Enter` | Send message / Execute pipeline | All chat tabs |
| `Ctrl+V` | Paste image from clipboard | All chat tabs |
| `Esc` | Cancel current processing | mixAI / cloudAI |

---

*This manual was generated from Helix AI Studio v12.5 source code and actual UI screens.*
