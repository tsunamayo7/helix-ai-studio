# Helix AI Studio — Sandbox Environment
# Docker image for isolated virtual desktop (Xvfb + NoVNC)
# GPU不要: AI推論はホスト側で実行、sandbox はファイル操作+UI確認のみ

FROM ubuntu:24.04

LABEL maintainer="tsunamayo7"
LABEL description="Helix AI Studio Sandbox — Virtual Desktop with NoVNC"

# 非対話モード
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99
ENV VNC_PASSWORD=""
ENV RESOLUTION=1280x720x24

# --- 1. 必須パッケージインストール ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 仮想ディスプレイ + VNC
    xvfb \
    x11vnc \
    # 軽量ウィンドウマネージャ
    openbox \
    # NoVNC (ブラウザVNC)
    novnc \
    websockify \
    # Python
    python3 \
    python3-pip \
    python3-venv \
    # 基本ツール
    git \
    curl \
    procps \
    xdotool \
    imagemagick \
    # 日本語フォント (i18n対応)
    fonts-noto-cjk \
    # Qt/GUI依存 (Ubuntu 24.04 では旧名パッケージ廃止)
    libgl1 \
    libglx-mesa0 \
    libegl1 \
    libegl-mesa0 \
    libxkbcommon0 \
    libxkbcommon-x11-0 \
    # X11基本
    xterm \
    # クリーンアップ用
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# --- 2. 非rootユーザー作成 ---
RUN useradd -m -s /bin/bash -o -u 1000 sandbox \
    && mkdir -p /workspace /workspace-overlay \
    && chown -R sandbox:sandbox /workspace /workspace-overlay

# --- 3. openbox 設定 ---
RUN mkdir -p /home/sandbox/.config/openbox \
    && echo '<?xml version="1.0" encoding="UTF-8"?>\n\
<openbox_config xmlns="http://openbox.org/3.4/rc">\n\
  <theme><name>Clearlooks</name></theme>\n\
  <desktops><number>1</number></desktops>\n\
</openbox_config>' > /home/sandbox/.config/openbox/rc.xml \
    && chown -R sandbox:sandbox /home/sandbox/.config

# --- 4. entrypoint ---
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# --- 5. ポート公開 ---
EXPOSE 5900 6080

# --- 6. ワークスペース ---
VOLUME ["/workspace"]
WORKDIR /workspace

USER sandbox

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
