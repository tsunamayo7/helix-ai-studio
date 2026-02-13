# -*- coding: utf-8 -*-
"""
Hello World GUI Application
簡易的なUIを表示するアプリケーション
"""

import tkinter as tk
from tkinter import messagebox


def on_button_click():
    """ボタンクリック時の処理"""
    name = entry.get().strip()
    if name:
        messagebox.showinfo("挨拶", f"こんにちは、{name}さん！")
    else:
        messagebox.showinfo("挨拶", "Hello, World!")


def main():
    """メイン関数"""
    global entry

    # メインウィンドウの作成
    root = tk.Tk()
    root.title("Hello World App")
    root.geometry("400x200")
    root.resizable(False, False)

    # ラベル
    label = tk.Label(root, text="Hello, World!", font=("Arial", 24, "bold"))
    label.pack(pady=20)

    # 入力フレーム
    frame = tk.Frame(root)
    frame.pack(pady=10)

    # 名前入力
    name_label = tk.Label(frame, text="名前を入力:")
    name_label.pack(side=tk.LEFT, padx=5)

    entry = tk.Entry(frame, width=20)
    entry.pack(side=tk.LEFT, padx=5)

    # ボタン
    button = tk.Button(root, text="挨拶する", command=on_button_click,
                       width=15, height=2)
    button.pack(pady=20)

    # メインループ
    root.mainloop()


if __name__ == "__main__":
    main()
