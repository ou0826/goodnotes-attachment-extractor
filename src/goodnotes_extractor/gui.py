"""
GoodNotes 附件提取器 - 图形用户界面
基于 Tkinter 的桌面应用，提供文件选择、类型筛选、
进度显示、结果预览和批量处理功能。
"""

import os
import sys
import threading
import zipfile
from pathlib import Path
from datetime import datetime
from tkinter import (
    Tk, Frame, Label, Button, Entry, Checkbutton, Listbox,
    Scrollbar, Text, Menu, filedialog, messagebox, ttk,
    StringVar, IntVar, BooleanVar, BOTH, LEFT, RIGHT, TOP,
    X, Y, END, NORMAL, DISABLED,
)

from .classifier import classify_file, FileCategory, classify_file_detailed
from .parser import (
    parse_mp4_audio_metadata,
    parse_jpeg_dimensions,
    parse_png_dimensions,
    parse_pdf_page_count,
    verify_mp4_integrity,
)
from .metadata import parse_goodnotes_index, format_metadata_summary
from .config import get_config
from .logger import setup_logging, get_logger
from . import __version__


# ============================================================
#  样式常量
# ============================================================

FONT_TITLE = ("Microsoft YaHei UI", 14, "bold")
FONT_BODY = ("Microsoft YaHei UI", 10)
FONT_MONO = ("Consolas", 9)
FONT_SMALL = ("Microsoft YaHei UI", 8)

COLOR_BG = "#F5F0E8"          # 背景
COLOR_HEADER = "#4A5B6B"      # 深色标题栏
COLOR_ACCENT = "#C04030"      # 重点操作色
COLOR_BUTTON = "#E8473A"      # 按钮色
COLOR_SUCCESS = "#5B8C5A"     # 成功状态
COLOR_TEXT = "#2C2C2C"        # 正文色
COLOR_BORDER = "#C8C0B0"      # 边界色
COLOR_ROW_ALT = "#EDE8E0"     # 交替行色


class GoodNotesExtractorGUI:
    """GoodNotes 附件提取器主窗口。

    提供图形化操作界面，支持：
      - 单个或批量 .goodnotes 文件选择
      - 按文件类型筛选提取
      - 实时进度显示
      - 提取结果预览
    """

    def __init__(self):
        self.root = Tk()
        self._apply_window_icon()
        self.root.title(f"GoodNotes 附件提取器 v{__version__}")
        self.root.geometry("1024x720")
        self.root.configure(bg=COLOR_BG)
        self.root.minsize(800, 600)

        # 状态变量
        self.input_files: list = []
        self.output_dir: str = ""
        self.is_processing = False
        self.extraction_results: list = []
        self.current_log_lines: list = []

        # 配置
        self.config = get_config()

        # UI 变量
        self.var_audio = BooleanVar(value=True)
        self.var_image = BooleanVar(value=True)
        self.var_pdf = BooleanVar(value=True)
        self.var_organize = BooleanVar(value=True)
        self.var_open_output = BooleanVar(value=True)
        self.status_text = StringVar(value="就绪")

        # 构建界面
        self._build_ui()
        self._setup_logger()

        # 居中窗口
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"+{x}+{y}")

    def _apply_window_icon(self):
        """设置窗口图标，源码运行和打包后都适用。"""
        candidates = []
        base = getattr(sys, "_MEIPASS", None)
        if base:
            candidates.append(Path(base) / "assets" / "icon.ico")
        candidates.append(
            Path(__file__).resolve().parent.parent.parent / "assets" / "icon.ico"
        )
        for icon in candidates:
            if icon.exists():
                try:
                    self.root.iconbitmap(str(icon))
                    return
                except Exception:
                    pass

    def _build_ui(self):
        """构建完整的用户界面布局。"""
        self._build_menu_bar()
        self._build_header()
        self._build_main_area()
        self._build_status_bar()

    def _build_menu_bar(self):
        """构建顶部菜单栏。"""
        menubar = Menu(self.root, bg=COLOR_BG, fg=COLOR_TEXT)

        file_menu = Menu(menubar, tearoff=0)
        file_menu.add_command(label="选择文件", command=self._select_files)
        file_menu.add_command(label="选择目录（批量）", command=self._select_directory)
        file_menu.add_separator()
        file_menu.add_command(label="设置输出目录", command=self._set_output_dir)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        menubar.add_cascade(label="文件", menu=file_menu)

        tools_menu = Menu(menubar, tearoff=0)
        tools_menu.add_command(label="开始提取", command=self._start_extraction)
        tools_menu.add_command(label="停止", command=self._stop_extraction)
        tools_menu.add_separator()
        tools_menu.add_command(label="清除结果", command=self._clear_results)
        menubar.add_cascade(label="操作", menu=tools_menu)

        help_menu = Menu(menubar, tearoff=0)
        help_menu.add_command(label="使用说明", command=self._show_help)
        help_menu.add_command(label="关于版本", command=self._show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_header(self):
        """构建顶部标题和文件选择区域。"""
        header = Frame(self.root, bg=COLOR_HEADER, height=100)
        header.pack(fill=X)
        header.pack_propagate(False)

        # 标题
        title_frame = Frame(header, bg=COLOR_HEADER)
        title_frame.pack(fill=X, padx=20, pady=(15, 0))

        Label(
            title_frame,
            text="GoodNotes 附件提取器",
            font=("Microsoft YaHei UI", 18, "bold"),
            fg="#FFFFFF",
            bg=COLOR_HEADER,
        ).pack(side=LEFT)

        Label(
            title_frame,
            text=f"v{__version__}",
            font=FONT_SMALL,
            fg="#C0C8D0",
            bg=COLOR_HEADER,
        ).pack(side=LEFT, padx=(8, 0))

        # 文件选择行
        select_frame = Frame(header, bg=COLOR_HEADER)
        select_frame.pack(fill=X, padx=20, pady=(10, 8))

        self.btn_select = Button(
            select_frame,
            text="选择 .goodnotes 文件",
            command=self._select_files,
            bg=COLOR_ACCENT,
            fg="#FFFFFF",
            font=FONT_BODY,
            relief="flat",
            cursor="hand2",
            padx=16,
            pady=4,
        )
        self.btn_select.pack(side=LEFT)

        self.lbl_file = Label(
            select_frame,
            text="未选择文件",
            font=FONT_BODY,
            fg="#D0D4D8",
            bg=COLOR_HEADER,
            anchor="w",
        )
        self.lbl_file.pack(side=LEFT, padx=(12, 0), fill=X, expand=True)

    def _build_main_area(self):
        """构建主内容区（选项面板 + 结果列表 + 日志）。"""
        main = Frame(self.root, bg=COLOR_BG)
        main.pack(fill=BOTH, expand=True, padx=12, pady=8)

        # ---------- 左侧面板 ----------
        left_panel = Frame(main, bg=COLOR_BG, width=280)
        left_panel.pack(side=LEFT, fill=Y, padx=(0, 6))
        left_panel.pack_propagate(False)

        # 提取选项组
        opt_frame = Frame(left_panel, bg="#FFFFFF", highlightbackground=COLOR_BORDER,
                          highlightthickness=1)
        opt_frame.pack(fill=X, pady=(0, 8))

        Label(
            opt_frame, text="提取选项", font=FONT_TITLE,
            bg="#FFFFFF", fg=COLOR_TEXT,
        ).pack(anchor="w", padx=12, pady=(10, 6))

        Checkbutton(
            opt_frame, text="音频文件 (.m4a)", variable=self.var_audio,
            bg="#FFFFFF", font=FONT_BODY, activebackground="#FFFFFF",
        ).pack(anchor="w", padx=16, pady=2)

        Checkbutton(
            opt_frame, text="图片文件 (.jpg / .png)", variable=self.var_image,
            bg="#FFFFFF", font=FONT_BODY, activebackground="#FFFFFF",
        ).pack(anchor="w", padx=16, pady=2)

        Checkbutton(
            opt_frame, text="PDF文档 (.pdf)", variable=self.var_pdf,
            bg="#FFFFFF", font=FONT_BODY, activebackground="#FFFFFF",
        ).pack(anchor="w", padx=16, pady=2)

        Checkbutton(
            opt_frame, text="按类型分文件夹", variable=self.var_organize,
            bg="#FFFFFF", font=FONT_BODY, activebackground="#FFFFFF",
        ).pack(anchor="w", padx=16, pady=(6, 2))

        Checkbutton(
            opt_frame, text="完成后打开输出目录", variable=self.var_open_output,
            bg="#FFFFFF", font=FONT_BODY, activebackground="#FFFFFF",
        ).pack(anchor="w", padx=16, pady=2)

        Button(
            opt_frame, text="开始提取", command=self._start_extraction,
            bg=COLOR_BUTTON, fg="#FFFFFF", font=FONT_BODY,
            relief="flat", cursor="hand2", padx=14, pady=6,
        ).pack(padx=16, pady=(6, 12), fill=X)

        # 批量列表
        batch_frame = Frame(left_panel, bg="#FFFFFF", highlightbackground=COLOR_BORDER,
                            highlightthickness=1)
        batch_frame.pack(fill=BOTH, expand=True)

        Label(
            batch_frame, text="待处理文件", font=FONT_TITLE,
            bg="#FFFFFF", fg=COLOR_TEXT,
        ).pack(anchor="w", padx=12, pady=(10, 4))

        list_frame = Frame(batch_frame, bg="#FFFFFF")
        list_frame.pack(fill=BOTH, expand=True, padx=8, pady=(0, 8))

        scrollbar = Scrollbar(list_frame)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.file_listbox = Listbox(
            list_frame, yscrollcommand=scrollbar.set,
            font=FONT_MONO, bg="#FAF8F5", fg=COLOR_TEXT,
            selectbackground=COLOR_HEADER, selectforeground="#FFFFFF",
            relief="flat", highlightthickness=0,
        )
        self.file_listbox.pack(fill=BOTH, expand=True)
        scrollbar.config(command=self.file_listbox.yview)

        # ---------- 右侧面板 ----------
        right_panel = Frame(main, bg=COLOR_BG)
        right_panel.pack(side=LEFT, fill=BOTH, expand=True)

        # 结果列表
        result_frame = Frame(right_panel, bg="#FFFFFF", highlightbackground=COLOR_BORDER,
                             highlightthickness=1)
        result_frame.pack(fill=BOTH, expand=True, pady=(0, 6))

        Label(
            result_frame, text="提取结果", font=FONT_TITLE,
            bg="#FFFFFF", fg=COLOR_TEXT,
        ).pack(anchor="w", padx=12, pady=(10, 4))

        # Treeview 结果表
        tree_frame = Frame(result_frame, bg="#FFFFFF")
        tree_frame.pack(fill=BOTH, expand=True, padx=8, pady=(0, 6))

        columns = ("type", "name", "size", "info")
        self.result_tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", height=10,
        )
        self.result_tree.heading("type", text="类型")
        self.result_tree.heading("name", text="文件名")
        self.result_tree.heading("size", text="大小")
        self.result_tree.heading("info", text="详情")

        self.result_tree.column("type", width=60, anchor="center")
        self.result_tree.column("name", width=180)
        self.result_tree.column("size", width=70, anchor="e")
        self.result_tree.column("info", width=200)

        # 样式
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview",
            background="#FAF8F5",
            foreground=COLOR_TEXT,
            rowheight=22,
            fieldbackground="#FAF8F5",
        )

        self.result_tree.pack(fill=BOTH, expand=True)

        # 日志输出
        log_frame = Frame(right_panel, bg="#FFFFFF", highlightbackground=COLOR_BORDER,
                          highlightthickness=1)
        log_frame.pack(fill=X)

        Label(
            log_frame, text="处理日志", font=FONT_TITLE,
            bg="#FFFFFF", fg=COLOR_TEXT,
        ).pack(anchor="w", padx=12, pady=(8, 4))

        self.log_text = Text(
            log_frame, height=6, font=FONT_MONO,
            bg="#2C2C2C", fg="#E0E0E0", relief="flat",
            padx=8, pady=4, state=DISABLED,
        )
        self.log_text.pack(fill=X, padx=8, pady=(0, 8))

    def _build_status_bar(self):
        """构建底部状态栏。"""
        status = Frame(self.root, bg=COLOR_HEADER, height=28)
        status.pack(fill=X, side="bottom")
        status.pack_propagate(False)

        Label(
            status, textvariable=self.status_text,
            font=FONT_SMALL, fg="#D0D4D8", bg=COLOR_HEADER,
            anchor="w",
        ).pack(side=LEFT, padx=12)

        # 进度条
        self.progress = ttk.Progressbar(
            status, mode="determinate", length=200,
        )
        self.progress.pack(side=RIGHT, padx=12)

    def _setup_logger(self):
        """初始化日志系统。"""
        setup_logging(level=self.config.get("logging.level", "INFO"))
        self.logger = get_logger("gui")

    def _log(self, message: str, level: str = "INFO"):
        """向日志区域追加一条消息。"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"

        self.log_text.config(state=NORMAL)
        self.log_text.insert(END, line + "\n")
        self.log_text.see(END)
        self.log_text.config(state=DISABLED)

        self.current_log_lines.append(line)
        # 限制日志行数
        if len(self.current_log_lines) > 500:
            self.current_log_lines = self.current_log_lines[-300:]

    # ============================================================
    #  事件处理
    # ============================================================

    def _select_files(self):
        """打开文件选择对话框。"""
        files = filedialog.askopenfilenames(
            title="选择 GoodNotes 文件",
            filetypes=[
                ("GoodNotes 文件", "*.goodnotes"),
                ("所有文件", "*.*"),
            ],
        )
        if files:
            self.input_files = list(files)
            self._refresh_file_list()
            if not self.output_dir:
                self.output_dir = str(Path(files[0]).parent / "提取输出")
            self._log(f"选择了 {len(files)} 个文件")

    def _select_directory(self):
        """选择包含 .goodnotes 文件的目录进行批量扫描。"""
        dir_path = filedialog.askdirectory(title="选择包含 .goodnotes 文件的目录")
        if dir_path:
            from .batch import find_goodnotes_files
            found = find_goodnotes_files(dir_path, recursive=True)
            if found:
                self.input_files = [str(f) for f in found]
                self._refresh_file_list()
                self._log(f"在目录中找到 {len(found)} 个 .goodnotes 文件")
            else:
                messagebox.showinfo("提示", "所选目录中未找到 .goodnotes 文件")

    def _set_output_dir(self):
        """设置输出目录。"""
        dir_path = filedialog.askdirectory(title="选择输出目录")
        if dir_path:
            self.output_dir = dir_path
            self._log(f"输出目录: {dir_path}")

    def _refresh_file_list(self):
        """刷新待处理文件列表。"""
        self.file_listbox.delete(0, END)
        for f in self.input_files:
            p = Path(f)
            size_mb = p.stat().st_size / 1024 / 1024
            self.file_listbox.insert(END, f"{p.name}  ({size_mb:.1f} MB)")

    def _clear_results(self):
        """清除结果列表和日志。"""
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)
        self.extraction_results.clear()
        self.log_text.config(state=NORMAL)
        self.log_text.delete("1.0", END)
        self.log_text.config(state=DISABLED)
        self.current_log_lines.clear()

    def _start_extraction(self):
        """启动提取任务（在后台线程中执行）。"""
        if not self.input_files:
            messagebox.showwarning("提示", "请先选择 .goodnotes 文件")
            return

        if self.is_processing:
            return

        self.is_processing = True
        self.status_text.set("正在提取...")
        self.progress["value"] = 0
        self.progress["maximum"] = len(self.input_files)

        # 清除旧结果
        for item in self.result_tree.get_children():
            self.result_tree.delete(item)

        thread = threading.Thread(target=self._extraction_thread, daemon=True)
        thread.start()

    def _extraction_thread(self):
        """后台提取线程。"""
        total_extracted = 0
        total_errors = 0

        for idx, filepath in enumerate(self.input_files):
            if not self.is_processing:
                break

            try:
                extracted = self._extract_single(filepath)
                total_extracted += len(extracted)
            except Exception as e:
                total_errors += 1
                self._log(f"处理失败: {Path(filepath).name} - {e}", "ERROR")

            self.progress["value"] = idx + 1
            self.status_text.set(
                f"进度: {idx + 1}/{len(self.input_files)}  |  "
                f"已提取: {total_extracted} 个文件"
            )

        # 完成
        self._log(f"提取完成: {total_extracted} 个文件, {total_errors} 个失败")
        self.status_text.set(f"完成 - 共提取 {total_extracted} 个文件")
        self.is_processing = False

        if self.var_open_output.get() and self.output_dir and total_extracted > 0:
            os.startfile(self.output_dir)

    def _extract_single(self, filepath: str) -> list:
        """处理单个 .goodnotes 文件。"""
        extracted = []
        gn_path = Path(filepath)
        gn_name = gn_path.stem

        if not self.output_dir:
            base_out = gn_path.parent / f"{gn_name}_提取"
        else:
            base_out = Path(self.output_dir) / gn_name

        base_out.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(filepath, "r") as zf:
                # 收集附件
                members = [
                    m for m in zf.namelist()
                    if m.startswith("attachments/") and not m.endswith("/")
                ]

                # 也加入根目录的非 protobuf 文件
                members += [
                    m for m in zf.namelist()
                    if not m.startswith("attachments/") and not m.endswith("/")
                    and not m.endswith(".pb") and m != "schema.pb"
                ]

                for member in members:
                    if not self.is_processing:
                        break

                    try:
                        with zf.open(member) as f:
                            header = f.read(12)
                            full_data = header + f.read()
                    except Exception:
                        continue

                    ftype = classify_file(full_data)

                    # 类型过滤
                    if ftype == FileCategory.AUDIO and not self.var_audio.get():
                        continue
                    if ftype == FileCategory.IMAGE and not self.var_image.get():
                        continue
                    if ftype == FileCategory.PDF and not self.var_pdf.get():
                        continue
                    if ftype in (FileCategory.VIDEO, FileCategory.UNKNOWN,
                                 FileCategory.PROTOBUF):
                        continue

                    # 确定输出
                    if ftype == FileCategory.AUDIO:
                        sub = "音频" if self.var_organize.get() else ""
                        meta = parse_mp4_audio_metadata(full_data)
                        dur = meta.get("duration", 0)
                        if dur > 0:
                            mins, secs = int(dur // 60), int(dur % 60)
                            name = f"录音_{mins}m{secs:02d}s.m4a"
                        else:
                            name = f"录音_{Path(member).stem[:8]}.m4a"
                    elif ftype == FileCategory.IMAGE:
                        sub = "图片" if self.var_organize.get() else ""
                        if full_data[:8] == b"\x89PNG\r\n\x1a\n":
                            w, h = parse_png_dimensions(full_data)
                            ext = ".png"
                        else:
                            w, h = parse_jpeg_dimensions(full_data)
                            ext = ".jpg"
                        if w > 0:
                            name = f"图片_{w}x{h}{ext}"
                        else:
                            name = f"图片_{Path(member).stem[:8]}{ext}"
                    elif ftype == FileCategory.PDF:
                        sub = "文档" if self.var_organize.get() else ""
                        name = f"文档_{Path(member).stem[:8]}.pdf"
                    else:
                        continue

                    # 写文件
                    out_dir = base_out / sub if sub else base_out
                    out_dir.mkdir(parents=True, exist_ok=True)
                    out_path = out_dir / name
                    counter = 1
                    while out_path.exists():
                        out_path = out_dir / f"{Path(name).stem}_{counter}{Path(name).suffix}"
                        counter += 1

                    out_path.write_bytes(full_data)
                    extracted.append(str(out_path))

                    # 更新UI
                    size_kb = len(full_data) / 1024
                    self.root.after(0, self._add_result_row,
                                    FileCategory.label(ftype),
                                    out_path.name,
                                    f"{size_kb:.0f} KB",
                                    f"{w}x{h}" if ftype == FileCategory.IMAGE and w > 0 else "",
                                    )

                    self._log(
                        f"  [{FileCategory.label(ftype)}] {out_path.name}  "
                        f"({size_kb:.0f} KB)"
                    )

        except zipfile.BadZipFile:
            self._log(f"文件损坏或格式不正确: {gn_name}", "ERROR")

        return extracted

    def _add_result_row(self, ftype: str, name: str, size: str, info: str):
        """向结果表格添加一行。"""
        self.result_tree.insert("", END, values=(ftype, name, size, info))

    def _stop_extraction(self):
        """停止正在进行的提取。"""
        self.is_processing = False
        self.status_text.set("已停止")
        self._log("用户停止了提取操作")

    def _show_help(self):
        """显示使用帮助对话框。"""
        help_text = (
            f"GoodNotes 附件提取器 v{__version__} 使用说明\n\n"
            "1. 点击「选择 .goodnotes 文件」加载笔记文件\n"
            "2. 在左侧面板勾选需要提取的文件类型\n"
            "3. 点击「开始提取」执行导出\n"
            "4. 提取结果会显示在右侧表格中\n\n"
            "支持格式:\n"
            "  - 音频: M4A/AAC (自动解析时长和采样率)\n"
            "  - 图片: JPEG/PNG (自动解析尺寸)\n"
            "  - 文档: PDF\n\n"
            "批量处理:\n"
            "  - 菜单「文件 → 选择目录」可扫描整个文件夹\n"
            "  - 所有子目录中的 .goodnotes 都会被处理\n"
        )
        messagebox.showinfo("使用说明", help_text)

    def _show_about(self):
        """显示关于对话框。"""
        about_text = (
            f"GoodNotes 附件提取器 v{__version__}\n\n"
            "第三方、非官方工具，与 GoodNotes 开发者无任何关联。\n"
            "GoodNotes 是 Time Base Technology Limited 的注册商标。\n\n"
            "支持提取 .goodnotes 容器中的音频、图片和 PDF 附件。\n\n"
            "技术基础:\n"
            "  - ISO BMFF (MP4/M4A) 原子树解析\n"
            "  - JPEG/PNG 二进制元数据解码\n"
            "  - Protocol Buffer 索引数据读取\n"
            "  - ZIP 容器直接访问\n\n"
            "许可证: MIT\n"
        )
        messagebox.showinfo("关于", about_text)

    def run(self):
        """启动 GUI 主循环。"""
        self.root.mainloop()


# ============================================================
#  入口
# ============================================================

def main():
    """GUI 模式入口。"""
    app = GoodNotesExtractorGUI()
    app.run()


if __name__ == "__main__":
    main()
