"""Native desktop UI for the Honkai: Star Rail Gacha Analyzer.

Run with ``python app.py``. The application uses Tkinter and never starts a
web server or opens a browser.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("TkAgg")

import pandas as pd
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from tkinter import filedialog, messagebox, ttk

from config.gacha_rules import POOL_LABELS
from src.analyzer import analyze_account
from src.api_client import GachaAPIClient, GachaAPIError
from src.exporter import to_csv_bytes, to_excel_bytes, to_json_bytes
from src.parser import GachaDataError, load_csv_bytes, load_json_bytes, records_to_dataframe
from src.pity import apply_pity_and_guarantee
from src.storage import AccountStorage, SAMPLE_ACCOUNT_KEY


ROOT = Path(__file__).resolve().parent
SAMPLE_PATH = ROOT / "data" / "sample_gacha.json"

COLORS = {
    "background": "#07111E",
    "sidebar": "#091727",
    "panel": "#101F36",
    "panel_alt": "#162A48",
    "line": "#294465",
    "text": "#EAF1FF",
    "muted": "#94A9C8",
    "purple": "#9B8CFF",
    "teal": "#56D6C9",
    "gold": "#FFD36B",
    "red": "#FF6278",
    "green": "#59D98E",
    "blue": "#78A6FF",
}
FONT = "Microsoft YaHei UI"
URL_PLACEHOLDER = (
    "https://public-operation-hkrpg.../getGachaLog?"
    "...&authkey=...&gacha_type=11"
)
SAMPLE_ACCOUNT_LABEL = "初始数据（隐藏信息）"


class PlaceholderEntry(tk.Entry):
    """Password entry that shows a readable gray URL shape while empty."""

    def __init__(self, parent: tk.Misc, placeholder: str, **kwargs: Any) -> None:
        self.placeholder = placeholder
        self.normal_color = str(kwargs.pop("normal_color", COLORS["text"]))
        self.placeholder_color = str(kwargs.pop("placeholder_color", "#718198"))
        super().__init__(parent, **kwargs)
        self._placeholder_visible = False
        self.bind("<FocusIn>", self._focus_in)
        self.bind("<FocusOut>", self._focus_out)
        self.reset()

    def _focus_in(self, _: tk.Event) -> None:
        if self._placeholder_visible:
            super().delete(0, tk.END)
            self.configure(foreground=self.normal_color, show="•")
            self._placeholder_visible = False

    def _focus_out(self, _: tk.Event) -> None:
        if not super().get():
            self.reset()

    def get(self) -> str:
        return "" if self._placeholder_visible else super().get()

    def reset(self) -> None:
        super().delete(0, tk.END)
        super().insert(0, self.placeholder)
        self.configure(foreground=self.placeholder_color, show="")
        self._placeholder_visible = True


class RoundedScrollbar(tk.Canvas):
    """Borderless canvas scrollbar with a soft, rounded thumb."""

    def __init__(
        self,
        parent: tk.Misc,
        command: Callable[..., Any],
        orient: str = "vertical",
    ) -> None:
        self.orient = orient
        self.command = command
        self._first = 0.0
        self._last = 1.0
        self._drag_offset = 0.0
        self._hovered = False
        size = 12
        super().__init__(
            parent,
            width=size if orient == "vertical" else 1,
            height=size if orient == "horizontal" else 1,
            background=COLORS["background"],
            highlightthickness=0,
            borderwidth=0,
            cursor="hand2",
        )
        self.bind("<Configure>", lambda _: self._draw())
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)

    def set(self, first: str | float, last: str | float) -> None:
        self._first = float(first)
        self._last = float(last)
        self._draw()

    def _geometry(self) -> tuple[float, float, float]:
        length = float(self.winfo_height() if self.orient == "vertical" else self.winfo_width())
        minimum = min(34.0, length)
        thumb_length = max(minimum, length * (self._last - self._first))
        travel = max(length - thumb_length, 0.0)
        start = travel * self._first / max(1.0 - (self._last - self._first), 0.0001)
        return length, thumb_length, min(max(start, 0.0), travel)

    def _draw(self) -> None:
        self.delete("all")
        if self._last - self._first >= 0.999:
            return
        _, thumb_length, start = self._geometry()
        color = COLORS["line"] if self._hovered else COLORS["panel_alt"]
        inset = 3
        if self.orient == "vertical":
            x1, x2 = inset, max(self.winfo_width() - inset, inset + 2)
            radius = max((x2 - x1) / 2, 1)
            self.create_rectangle(x1, start + radius, x2, start + thumb_length - radius, fill=color, outline="")
            self.create_oval(x1, start, x2, start + radius * 2, fill=color, outline="")
            self.create_oval(x1, start + thumb_length - radius * 2, x2, start + thumb_length, fill=color, outline="")
        else:
            y1, y2 = inset, max(self.winfo_height() - inset, inset + 2)
            radius = max((y2 - y1) / 2, 1)
            self.create_rectangle(start + radius, y1, start + thumb_length - radius, y2, fill=color, outline="")
            self.create_oval(start, y1, start + radius * 2, y2, fill=color, outline="")
            self.create_oval(start + thumb_length - radius * 2, y1, start + thumb_length, y2, fill=color, outline="")

    def _pointer(self, event: tk.Event) -> float:
        return float(event.y if self.orient == "vertical" else event.x)

    def _press(self, event: tk.Event) -> None:
        _, thumb_length, start = self._geometry()
        pointer = self._pointer(event)
        if start <= pointer <= start + thumb_length:
            self._drag_offset = pointer - start
        else:
            self._drag_offset = thumb_length / 2
            self._move(pointer)

    def _drag(self, event: tk.Event) -> None:
        self._move(self._pointer(event))

    def _move(self, pointer: float) -> None:
        length, thumb_length, _ = self._geometry()
        visible_fraction = self._last - self._first
        maximum = max(1.0 - visible_fraction, 0.0)
        fraction = min(max((pointer - self._drag_offset) / max(length, 1.0), 0.0), maximum)
        self.command("moveto", fraction)

    def _enter(self, _: tk.Event) -> None:
        self._hovered = True
        self._draw()

    def _leave(self, _: tk.Event) -> None:
        self._hovered = False
        self._draw()


class ScrollFrame(tk.Frame):
    """A vertically scrollable frame used inside notebook tabs."""

    def __init__(self, parent: tk.Misc, background: str = COLORS["background"]):
        super().__init__(parent, background=background)
        self.canvas = tk.Canvas(
            self,
            background=background,
            highlightthickness=0,
            borderwidth=0,
        )
        self.scrollbar = RoundedScrollbar(self, orient="vertical", command=self.canvas.yview)
        self.content = tk.Frame(self.canvas, background=background)
        self.window_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.content.bind("<Configure>", self._update_scrollregion)
        self.canvas.bind("<Configure>", self._resize_content)
        self.canvas.bind("<Enter>", lambda _: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda _: self.canvas.unbind_all("<MouseWheel>"))

    def _update_scrollregion(self, _: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_content(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _wheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-event.delta / 120), "units")


class HSRGachaDesktopApp:
    """Native, fully local desktop application."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("崩坏：星穹铁道抽卡概率分析器")
        self.root.geometry("1460x920")
        self.root.minsize(1180, 760)
        self.root.configure(background=COLORS["background"])

        self.frame = pd.DataFrame()
        self.summary: dict[str, Any] = {}
        self.account_storage = AccountStorage()
        self.active_uid: str | None = None
        self.account_choice = tk.StringVar(value=SAMPLE_ACCOUNT_LABEL)
        self._account_by_label: dict[str, str | None] = {SAMPLE_ACCOUNT_LABEL: None}
        self.data_source = tk.StringVar(value=SAMPLE_ACCOUNT_LABEL)
        self.status_text = tk.StringVar(value="准备就绪")
        self.uid_text = tk.StringVar(value="—")
        self.total_text = tk.StringVar(value="0")
        self.five_text = tk.StringVar(value="0")
        self.average_text = tk.StringVar(value="—")
        self._chart_canvas: FigureCanvasTkAgg | None = None

        self._configure_styles()
        self._build_layout()
        self._load_startup_account()

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=COLORS["background"])
        style.configure(
            "TLabel",
            background=COLORS["background"],
            foreground=COLORS["text"],
            font=(FONT, 10),
        )
        style.configure(
            "TNotebook",
            background=COLORS["background"],
            borderwidth=0,
            relief="flat",
            bordercolor=COLORS["background"],
            lightcolor=COLORS["background"],
            darkcolor=COLORS["background"],
            tabmargins=(0, 8, 0, 0),
        )
        style.layout("TNotebook", [("Notebook.client", {"sticky": "nswe"})])
        style.configure(
            "TNotebook.Tab",
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            padding=(18, 10),
            font=(FONT, 10),
            borderwidth=0,
            relief="flat",
            bordercolor=COLORS["panel"],
            lightcolor=COLORS["panel"],
            darkcolor=COLORS["panel"],
            focuscolor=COLORS["panel"],
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLORS["panel_alt"])],
            foreground=[("selected", COLORS["text"])],
            bordercolor=[("selected", COLORS["panel_alt"])],
            lightcolor=[("selected", COLORS["panel_alt"])],
            darkcolor=[("selected", COLORS["panel_alt"])],
        )
        style.configure(
            "Treeview",
            background=COLORS["panel"],
            fieldbackground=COLORS["panel"],
            foreground=COLORS["text"],
            rowheight=31,
            bordercolor=COLORS["line"],
            font=(FONT, 9),
        )
        style.configure(
            "Treeview.Heading",
            background=COLORS["panel_alt"],
            foreground=COLORS["text"],
            relief="flat",
            font=(FONT, 9, "bold"),
        )
        style.map("Treeview", background=[("selected", "#304E78")])
        style.configure(
            "Account.TCombobox",
            background=COLORS["panel_alt"],
            fieldbackground=COLORS["panel"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["muted"],
            bordercolor=COLORS["line"],
            lightcolor=COLORS["line"],
            darkcolor=COLORS["line"],
            padding=(8, 6),
            font=(FONT, 9),
        )
        style.map(
            "Account.TCombobox",
            fieldbackground=[("readonly", COLORS["panel"])],
            foreground=[("readonly", COLORS["text"])],
            selectbackground=[("readonly", COLORS["panel"])],
            selectforeground=[("readonly", COLORS["text"])],
        )
        matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
        matplotlib.rcParams["axes.unicode_minus"] = False

    def _build_layout(self) -> None:
        shell = tk.Frame(self.root, background=COLORS["background"])
        shell.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(shell, width=292, background=COLORS["sidebar"])
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        main = tk.Frame(shell, background=COLORS["background"])
        main.pack(side="left", fill="both", expand=True, padx=(22, 22), pady=(18, 14))

        header = tk.Frame(main, background=COLORS["background"])
        header.pack(fill="x", pady=(0, 14))
        tk.Label(
            header,
            text="崩坏：星穹铁道抽卡概率分析器",
            font=(FONT, 22, "bold"),
            foreground=COLORS["text"],
            background=COLORS["background"],
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Honkai: Star Rail Gacha Analyzer · 本地桌面版",
            font=(FONT, 10),
            foreground=COLORS["muted"],
            background=COLORS["background"],
        ).pack(anchor="w", pady=(4, 0))

        self.state_area = tk.Frame(main, background=COLORS["background"])
        self.state_area.pack(fill="x", pady=(0, 14))
        self.state_area.grid_columnconfigure(0, weight=1)
        self.state_area.grid_columnconfigure(1, weight=1)

        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill="both", expand=True)
        self.overview_tab = ScrollFrame(self.notebook)
        self.character_tab = ScrollFrame(self.notebook)
        self.lightcone_tab = ScrollFrame(self.notebook)
        self.standard_tab = ScrollFrame(self.notebook)
        self.beginner_tab = ScrollFrame(self.notebook)
        self.detail_tab = tk.Frame(self.notebook, background=COLORS["background"])
        self.notebook.add(self.overview_tab, text="总览")
        self.notebook.add(self.character_tab, text="角色活动跃迁")
        self.notebook.add(self.lightcone_tab, text="光锥活动跃迁")
        self.notebook.add(self.standard_tab, text="常驻跃迁")
        self.notebook.add(self.beginner_tab, text="新手跃迁")
        self.notebook.add(self.detail_tab, text="详细记录")

        status_bar = tk.Frame(self.root, background="#050C15", height=27)
        status_bar.pack(fill="x", side="bottom")
        tk.Label(
            status_bar,
            textvariable=self.status_text,
            background="#050C15",
            foreground=COLORS["muted"],
            font=(FONT, 9),
            anchor="w",
            padx=12,
        ).pack(fill="x")

    def _build_sidebar(self) -> None:
        tk.Label(
            self.sidebar,
            text="✦  本地数据中心",
            font=(FONT, 15, "bold"),
            foreground=COLORS["text"],
            background=COLORS["sidebar"],
        ).pack(anchor="w", padx=20, pady=(24, 18))
        input_header = tk.Frame(self.sidebar, background=COLORS["sidebar"])
        input_header.pack(fill="x", padx=20)
        tk.Label(
            input_header,
            text="粘贴抽卡记录链接",
            font=(FONT, 10, "bold"),
            foreground=COLORS["text"],
            background=COLORS["sidebar"],
        ).pack(side="left")
        tk.Button(
            input_header,
            text="获取教程",
            command=self._show_url_tutorial,
            background=COLORS["sidebar"],
            activebackground=COLORS["sidebar"],
            foreground=COLORS["blue"],
            activeforeground=COLORS["teal"],
            relief="flat",
            cursor="hand2",
            font=(FONT, 8, "underline"),
            padx=0,
        ).pack(side="right")
        self.url_entry = PlaceholderEntry(
            self.sidebar,
            placeholder=URL_PLACEHOLDER,
            background="#0E2037",
            insertbackground=COLORS["text"],
            relief="flat",
            font=(FONT, 8),
        )
        self.url_entry.pack(fill="x", padx=20, pady=(8, 4), ipady=8)
        tk.Label(
            self.sidebar,
            text="链接只用于本次获取，完成后会自动清空",
            background=COLORS["sidebar"],
            foreground=COLORS["muted"],
            font=(FONT, 7),
        ).pack(anchor="w", padx=20, pady=(0, 9))
        self.fetch_button = self._button(
            self.sidebar,
            "从 API 获取 / 更新",
            self.fetch_from_api,
            COLORS["purple"],
            "#120F25",
        )
        self.fetch_button.pack(fill="x", padx=20, pady=(0, 8))
        self._button(self.sidebar, "导入 JSON / CSV", self.import_file).pack(fill="x", padx=20, pady=4)
        self._button(self.sidebar, "显示初始数据（隐藏信息）", self.load_sample).pack(fill="x", padx=20, pady=4)

        self._separator(self.sidebar).pack(fill="x", padx=20, pady=18)
        tk.Label(
            self.sidebar,
            text="账号概览",
            font=(FONT, 10, "bold"),
            foreground=COLORS["text"],
            background=COLORS["sidebar"],
        ).pack(anchor="w", padx=20, pady=(0, 8))
        tk.Label(
            self.sidebar,
            text="选择账号",
            background=COLORS["sidebar"],
            foreground=COLORS["muted"],
            font=(FONT, 8),
        ).pack(anchor="w", padx=20, pady=(0, 4))
        self.account_selector = ttk.Combobox(
            self.sidebar,
            textvariable=self.account_choice,
            state="readonly",
            style="Account.TCombobox",
        )
        self.account_selector.pack(fill="x", padx=20, pady=(0, 8))
        self.account_selector.bind("<<ComboboxSelected>>", self._on_account_selected)
        self._sidebar_metric("UID", self.uid_text)
        self._sidebar_metric("总抽数", self.total_text)
        self._sidebar_metric("五星数量", self.five_text)
        self._sidebar_metric("平均出金", self.average_text)

        self._separator(self.sidebar).pack(fill="x", padx=20, pady=18)
        tk.Label(
            self.sidebar,
            text="导出本地文件",
            font=(FONT, 10, "bold"),
            foreground=COLORS["text"],
            background=COLORS["sidebar"],
        ).pack(anchor="w", padx=20, pady=(0, 8))
        self._button(self.sidebar, "Export CSV", lambda: self.export_file("csv")).pack(fill="x", padx=20, pady=4)
        self._button(self.sidebar, "Export Excel", lambda: self.export_file("xlsx")).pack(fill="x", padx=20, pady=4)
        self._button(self.sidebar, "Export JSON", lambda: self.export_file("json")).pack(fill="x", padx=20, pady=4)

        source_box = tk.Frame(self.sidebar, background=COLORS["panel"])
        source_box.pack(side="bottom", fill="x", padx=20, pady=20)
        tk.Label(
            source_box,
            text="当前数据源",
            background=COLORS["panel"],
            foreground=COLORS["muted"],
            font=(FONT, 8),
        ).pack(anchor="w", padx=12, pady=(10, 2))
        tk.Label(
            source_box,
            textvariable=self.data_source,
            background=COLORS["panel"],
            foreground=COLORS["text"],
            font=(FONT, 9, "bold"),
            wraplength=220,
            justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 10))

    def _show_url_tutorial(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("如何获取抽卡记录链接")
        dialog.geometry("680x560")
        dialog.minsize(620, 500)
        dialog.configure(background=COLORS["background"])
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(
            dialog,
            text="获取抽卡记录链接",
            background=COLORS["background"],
            foreground=COLORS["text"],
            font=(FONT, 18, "bold"),
        ).pack(anchor="w", padx=28, pady=(24, 4))
        tk.Label(
            dialog,
            text="只需要链接，不需要账号密码。请勿把链接分享给其他人。",
            background=COLORS["background"],
            foreground=COLORS["muted"],
            font=(FONT, 9),
        ).pack(anchor="w", padx=28, pady=(0, 18))

        steps = [
            ("1", "打开跃迁记录", "进入游戏的「跃迁」页面，打开「查看详情」→「历史记录」，等待记录加载完成。"),
            ("2", "复制 getGachaLog 链接", "使用你信任的抽卡链接提取方式，在刚加载的记录请求中找到路径以 getGachaLog 结尾的完整 URL。"),
            ("3", "确认链接结构", "链接中应包含 authkey、game_biz、region 等参数；不需要修改其中任何内容。"),
            ("4", "粘贴并获取", "回到本程序，将完整链接粘贴到左侧输入框，然后点击「从 API 获取 / 更新」。"),
        ]
        for number, title, detail in steps:
            row = tk.Frame(dialog, background=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1)
            row.pack(fill="x", padx=28, pady=5)
            tk.Label(
                row,
                text=number,
                width=3,
                background=COLORS["purple"],
                foreground="#120F25",
                font=(FONT, 11, "bold"),
                pady=10,
            ).pack(side="left", padx=(12, 14), pady=12)
            text_area = tk.Frame(row, background=COLORS["panel"])
            text_area.pack(side="left", fill="both", expand=True, pady=10)
            tk.Label(text_area, text=title, background=COLORS["panel"], foreground=COLORS["text"], font=(FONT, 10, "bold")).pack(anchor="w")
            tk.Label(text_area, text=detail, background=COLORS["panel"], foreground=COLORS["muted"], font=(FONT, 8), wraplength=520, justify="left").pack(anchor="w", pady=(3, 0))

        example = tk.Frame(dialog, background="#0E2037")
        example.pack(fill="x", padx=28, pady=(16, 8))
        tk.Label(example, text="链接示例", background="#0E2037", foreground=COLORS["muted"], font=(FONT, 8, "bold")).pack(anchor="w", padx=12, pady=(9, 2))
        tk.Label(example, text=URL_PLACEHOLDER, background="#0E2037", foreground="#718198", font=("Consolas", 8), wraplength=590, justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        footer = tk.Frame(dialog, background=COLORS["background"])
        footer.pack(fill="x", padx=28, pady=(8, 20))
        tk.Label(
            footer,
            text="安全提示：authkey 是临时凭据。本程序不会保存它，但你仍不应截图或公开分享完整 URL。",
            background=COLORS["background"],
            foreground=COLORS["gold"],
            font=(FONT, 8),
            wraplength=500,
            justify="left",
        ).pack(side="left")
        self._button(footer, "知道了", dialog.destroy, COLORS["panel_alt"]).pack(side="right", ipadx=12)

    def _button(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
        background: str = COLORS["panel_alt"],
        foreground: str = COLORS["text"],
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            background=background,
            activebackground=COLORS["blue"],
            foreground=foreground,
            activeforeground="#07111E",
            relief="flat",
            cursor="hand2",
            font=(FONT, 9, "bold"),
            pady=9,
        )

    @staticmethod
    def _separator(parent: tk.Misc) -> tk.Frame:
        return tk.Frame(parent, height=1, background=COLORS["line"])

    def _sidebar_metric(self, label: str, variable: tk.StringVar) -> None:
        row = tk.Frame(self.sidebar, background=COLORS["sidebar"])
        row.pack(fill="x", padx=20, pady=4)
        tk.Label(
            row,
            text=label,
            background=COLORS["sidebar"],
            foreground=COLORS["muted"],
            font=(FONT, 9),
        ).pack(side="left")
        tk.Label(
            row,
            textvariable=variable,
            background=COLORS["sidebar"],
            foreground=COLORS["text"],
            font=(FONT, 10, "bold"),
        ).pack(side="right")

    def prepare_records(self, records: list[dict[str, Any]]) -> pd.DataFrame:
        frame = records_to_dataframe(records)
        if frame.empty:
            raise GachaDataError("没有找到可用的抽卡记录。")
        return apply_pity_and_guarantee(frame)

    def _refresh_account_selector(self, selected_uid: str | None) -> None:
        self._account_by_label = {SAMPLE_ACCOUNT_LABEL: None}
        for uid in self.account_storage.list_account_uids():
            self._account_by_label[f"UID {uid}"] = uid
        self.account_selector.configure(values=list(self._account_by_label))
        selected_label = SAMPLE_ACCOUNT_LABEL if selected_uid is None else f"UID {selected_uid}"
        self.account_choice.set(selected_label)

    def _activate_account(
        self,
        frame: pd.DataFrame,
        uid: str | None,
        source: str,
        remember: bool = True,
    ) -> None:
        self.frame = frame
        self.active_uid = uid
        self.data_source.set(source)
        self.refresh_all()
        self._refresh_account_selector(uid)
        if remember:
            try:
                self.account_storage.set_last_account(uid)
            except OSError:
                self.status_text.set("数据已载入，但无法保存上次查看的账号设置")

    def _load_startup_account(self) -> None:
        last_account = self.account_storage.get_last_account()
        if last_account and last_account != SAMPLE_ACCOUNT_KEY and self.account_storage.has_account(last_account):
            if self._load_stored_account(last_account, show_error=False):
                return
        self.load_sample(show_message=False)

    def _load_stored_account(self, uid: str, show_error: bool = True) -> bool:
        try:
            frame = self.account_storage.load_account(uid)
            self._activate_account(frame, uid, f"本地历史 · UID {uid}")
            self.status_text.set(f"已载入 UID {uid} 的 {len(frame)} 条本地历史记录")
            return True
        except (OSError, GachaDataError) as exc:
            if show_error:
                messagebox.showerror("账号载入失败", str(exc), parent=self.root)
            return False

    def _on_account_selected(self, _: tk.Event) -> None:
        uid = self._account_by_label.get(self.account_choice.get())
        if uid is None:
            self.load_sample(show_message=False)
            return
        if not self._load_stored_account(uid):
            self._refresh_account_selector(self.active_uid)

    def load_sample(self, show_message: bool = True) -> None:
        try:
            records = load_json_bytes(SAMPLE_PATH.read_bytes())
            frame = self.prepare_records(records)
            self._activate_account(frame, None, SAMPLE_ACCOUNT_LABEL)
            self.status_text.set(f"已载入 {len(self.frame)} 条示例记录")
            if show_message:
                messagebox.showinfo("初始数据", "已切换到匿名初始数据。", parent=self.root)
        except Exception as exc:
            messagebox.showerror("载入失败", str(exc), parent=self.root)

    def fetch_from_api(self) -> None:
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("缺少链接", "请先粘贴抽卡记录链接。", parent=self.root)
            return
        self.fetch_button.configure(state="disabled", text="正在分页获取…")
        self.status_text.set("正在从官方 API 分页获取记录，请稍候…")

        def worker() -> None:
            try:
                records = GachaAPIClient().fetch_all(url)
                updated_accounts = self.account_storage.merge_records(records)
                uid, frame = next(iter(updated_accounts.items()))
            except (GachaAPIError, GachaDataError, OSError) as exc:
                message = str(exc)
                self.root.after(0, lambda: self._fetch_failed(message))
                return
            except Exception:
                self.root.after(0, lambda: self._fetch_failed("获取失败，请检查网络和链接后重试。"))
                return
            self.root.after(0, lambda: self._fetch_succeeded(frame, uid))

        threading.Thread(target=worker, daemon=True).start()

    def _fetch_succeeded(self, frame: pd.DataFrame, uid: str) -> None:
        self.url_entry.reset()
        self.fetch_button.configure(state="normal", text="从 API 获取 / 更新")
        self._activate_account(frame, uid, f"API 更新 · UID {uid}")
        self.status_text.set(f"UID {uid} 已合并为 {len(frame)} 条本地记录；链接凭据未保存")
        messagebox.showinfo("获取完成", f"UID {uid} 的历史已更新，共 {len(frame)} 条记录。", parent=self.root)

    def _fetch_failed(self, message: str) -> None:
        self.fetch_button.configure(state="normal", text="从 API 获取 / 更新")
        self.status_text.set("API 获取失败")
        messagebox.showerror("获取失败", message, parent=self.root)

    def import_file(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="导入抽卡历史",
            filetypes=[("抽卡历史", "*.json *.csv"), ("JSON", "*.json"), ("CSV", "*.csv")],
        )
        if not filename:
            return
        try:
            path = Path(filename)
            content = path.read_bytes()
            records = load_json_bytes(content) if path.suffix.lower() == ".json" else load_csv_bytes(content)
            updated_accounts = self.account_storage.merge_records(records)
            uid, frame = next(iter(updated_accounts.items()))
            self._activate_account(frame, uid, f"文件导入 · UID {uid}")
            account_count = len(updated_accounts)
            detail = f"，并更新了 {account_count} 个账号" if account_count > 1 else ""
            self.status_text.set(f"已导入并合并 UID {uid} 的 {len(frame)} 条记录{detail}")
        except (OSError, GachaDataError) as exc:
            messagebox.showerror("导入失败", str(exc), parent=self.root)

    def export_file(self, export_type: str) -> None:
        if self.frame.empty:
            messagebox.showwarning("没有数据", "请先载入抽卡记录。", parent=self.root)
            return
        config = {
            "csv": ("CSV", ".csv", "hsr_gacha_history.csv"),
            "xlsx": ("Excel", ".xlsx", "hsr_gacha_analysis.xlsx"),
            "json": ("JSON", ".json", "hsr_gacha_history.json"),
        }[export_type]
        filename = filedialog.asksaveasfilename(
            parent=self.root,
            title=f"导出 {config[0]}",
            defaultextension=config[1],
            initialfile=config[2],
            filetypes=[(config[0], f"*{config[1]}")],
        )
        if not filename:
            return
        try:
            if export_type == "csv":
                content = to_csv_bytes(self.frame)
            elif export_type == "xlsx":
                content = to_excel_bytes(self.frame, self.summary)
            else:
                content = to_json_bytes(self.frame)
            Path(filename).write_bytes(content)
            self.status_text.set(f"已导出：{filename}")
            messagebox.showinfo("导出完成", f"文件已保存到：\n{filename}", parent=self.root)
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc), parent=self.root)

    def refresh_all(self) -> None:
        self.summary = analyze_account(self.frame)
        self.uid_text.set(self.active_uid or "模拟账号")
        self.total_text.set(str(self.summary["total_pulls"]))
        self.five_text.set(str(self.summary["five_stars"]))
        self.average_text.set(self._fmt_number(self.summary["average_pity"]))
        self._render_state_area()
        self._render_overview()
        self._render_pool_tab(self.character_tab, "character_event")
        self._render_pool_tab(self.lightcone_tab, "lightcone_event")
        self._render_pool_tab(self.standard_tab, "standard")
        self._render_pool_tab(self.beginner_tab, "beginner")
        self._render_detail_tab()

    @staticmethod
    def _clear(parent: tk.Misc) -> None:
        for child in parent.winfo_children():
            child.destroy()

    @staticmethod
    def _fmt_number(value: float | int | None, decimals: int = 1) -> str:
        if value is None or pd.isna(value):
            return "—"
        numeric = float(value)
        return str(int(numeric)) if numeric.is_integer() else f"{numeric:.{decimals}f}"

    @staticmethod
    def _fmt_rate(value: float | None) -> str:
        return "—" if value is None or pd.isna(value) else f"{value:.1%}"

    @staticmethod
    def _pity_color(pity_count: int | float) -> str:
        return COLORS["red"] if int(pity_count) >= 70 else COLORS["green"]

    def _render_state_area(self) -> None:
        self._clear(self.state_area)
        self._state_card(self.state_area, 0, "角色活动跃迁", self.summary["pools"]["character_event"])
        self._state_card(self.state_area, 1, "光锥活动跃迁", self.summary["pools"]["lightcone_event"])

    def _state_card(self, parent: tk.Misc, column: int, title: str, stats: dict[str, Any]) -> None:
        card = tk.Frame(
            parent,
            background=COLORS["panel"],
            highlightbackground=COLORS["line"],
            highlightthickness=1,
        )
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 7) if column == 0 else (7, 0))
        card.grid_columnconfigure(0, weight=1)
        tk.Label(card, text=title, background=COLORS["panel"], foreground=COLORS["muted"], font=(FONT, 10, "bold")).grid(row=0, column=0, sticky="w", padx=18, pady=(15, 2))
        current_pity = int(stats["current_pity"])
        pity_color = self._pity_color(current_pity)
        tk.Label(card, text=f"{current_pity} 抽", background=COLORS["panel"], foreground=pity_color, font=(FONT, 24, "bold")).grid(row=1, column=0, sticky="w", padx=18, pady=(1, 16))
        guaranteed = stats["guaranteed_next"]
        status = "大保底" if guaranteed else "小保底"
        status_color = COLORS["gold"] if guaranteed else COLORS["teal"]
        next_state = tk.Frame(card, background=COLORS["panel"])
        next_state.grid(row=0, column=1, rowspan=2, sticky="e", padx=18)
        tk.Label(next_state, text="下一金：", background=COLORS["panel"], foreground=COLORS["muted"], font=(FONT, 10)).pack(side="left", anchor="s", pady=(7, 0))
        tk.Label(next_state, text=status, background=COLORS["panel"], foreground=status_color, font=(FONT, 16, "bold")).pack(side="left")

    def _section_title(self, parent: tk.Misc, text: str, pady: tuple[int, int] = (14, 8)) -> None:
        tk.Label(parent, text=text, background=COLORS["background"], foreground=COLORS["text"], font=(FONT, 13, "bold")).pack(anchor="w", padx=4, pady=pady)

    def _metric_row(self, parent: tk.Misc, metrics: list[tuple[str, str]]) -> None:
        row = tk.Frame(parent, background=COLORS["background"])
        row.pack(fill="x")
        for column, (label, value) in enumerate(metrics):
            row.grid_columnconfigure(column, weight=1)
            card = tk.Frame(row, background=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1)
            card.grid(row=0, column=column, sticky="nsew", padx=4, pady=3)
            tk.Label(card, text=label, background=COLORS["panel"], foreground=COLORS["muted"], font=(FONT, 8)).pack(anchor="w", padx=12, pady=(10, 2))
            tk.Label(card, text=value, background=COLORS["panel"], foreground=COLORS["text"], font=(FONT, 16, "bold")).pack(anchor="w", padx=12, pady=(0, 10))

    def _render_overview(self) -> None:
        parent = self.overview_tab.content
        self._clear(parent)
        five_history = self.frame[self.frame["is_five_star"]].sort_values("time")
        recent_pity = (
            self._fmt_number(five_history.iloc[-1]["pity_count"])
            if not five_history.empty
            else "—"
        )
        metrics = [
            ("总抽卡数", str(self.summary["total_pulls"])),
            ("已出金", str(self.summary["five_stars"])),
            ("最近出金", f"{recent_pity} 抽" if recent_pity != "—" else "—"),
            ("歪了几次", str(self.summary["off_banner_count"])),
        ]
        self._section_title(parent, "账号概览", (12, 5))
        self._metric_row(parent, metrics)
        self._section_title(parent, "最近五星")
        self._five_star_cards(parent, self.frame, limit=8)
        self._section_title(parent, "抽卡概况")
        self._render_charts(parent)
        tk.Label(
            parent,
            text="当前 pity 与保证状态由已导入的可见历史推断；若更早记录缺失，首次五星的 pity 与导入起点状态可能不完整。",
            background=COLORS["background"],
            foreground=COLORS["muted"],
            font=(FONT, 8),
        ).pack(anchor="w", padx=4, pady=(4, 16))

    def _five_star_cards(self, parent: tk.Misc, frame: pd.DataFrame, limit: int | None = None) -> None:
        five = frame[frame["is_five_star"]].sort_values("time", ascending=False)
        if limit:
            five = five.head(limit)
        if five.empty:
            tk.Label(parent, text="当前范围内还没有五星记录。", background=COLORS["background"], foreground=COLORS["muted"], font=(FONT, 10)).pack(anchor="w", padx=4)
            return
        grid = tk.Frame(parent, background=COLORS["background"])
        grid.pack(fill="x")
        for column in range(4):
            grid.grid_columnconfigure(column, weight=1)
        for position, (_, row) in enumerate(five.iterrows()):
            card = tk.Frame(grid, background=COLORS["panel"], highlightbackground=COLORS["line"], highlightthickness=1)
            card.grid(row=position // 4, column=position % 4, sticky="nsew", padx=4, pady=4)
            title_row = tk.Frame(card, background=COLORS["panel"])
            title_row.pack(fill="x", padx=12, pady=(10, 0))
            tk.Label(title_row, text=self._five_star_display_name(row), background=COLORS["panel"], foreground=COLORS["text"], font=(FONT, 10, "bold")).pack(side="left")
            if row["pool_type"] in {"character_event", "lightcone_event"}:
                if bool(row["is_off_banner"]):
                    self._badge(title_row, "歪", COLORS["red"])
                elif bool(row["is_guaranteed"]):
                    self._badge(title_row, "保底", COLORS["gold"], "#2B1D00")
            pity_count = int(row["pity_count"])
            pity_color = self._pity_color(pity_count)
            tk.Label(card, text=f"{pity_count} 抽", background=COLORS["panel"], foreground=pity_color, font=(FONT, 17, "bold")).pack(anchor="w", padx=12, pady=(7, 2))
            meta = f"{POOL_LABELS.get(row['pool_type'], row['pool_type'])}\n{row['time']:%Y-%m-%d %H:%M}"
            tk.Label(card, text=meta, background=COLORS["panel"], foreground=COLORS["muted"], font=(FONT, 8), justify="left").pack(anchor="w", padx=12, pady=(0, 10))

    @staticmethod
    def _badge(parent: tk.Misc, text: str, background: str, foreground: str = "#FFFFFF") -> None:
        tk.Label(parent, text=text, background=background, foreground=foreground, font=(FONT, 8, "bold"), padx=6, pady=1).pack(side="left", padx=7)

    @staticmethod
    def _five_star_display_name(row: pd.Series) -> str:
        """Keep imported item names intact; only bundled sample rows are anonymous."""
        return str(row["name"])

    def _render_charts(self, parent: tk.Misc) -> None:
        figure = Figure(figsize=(11.5, 3.8), dpi=100, facecolor=COLORS["background"])
        axes = figure.subplots(1, 2)
        palette = [COLORS["gold"], COLORS["purple"], COLORS["blue"]]
        for axis in axes:
            axis.set_facecolor(COLORS["panel"])
            axis.tick_params(colors=COLORS["muted"], labelsize=8)
            for spine in axis.spines.values():
                spine.set_color(COLORS["line"])
            axis.title.set_color(COLORS["text"])
            axis.xaxis.label.set_color(COLORS["muted"])
            axis.yaxis.label.set_color(COLORS["muted"])

        rank_counts = self.frame["rank_type"].value_counts()
        rank_values = [int(rank_counts.get(rank, 0)) for rank in (5, 4, 3)]
        total = max(sum(rank_values), 1)
        rank_labels = [
            f"{rank} 星  {value / total:.1%}"
            for rank, value in zip((5, 4, 3), rank_values)
        ]
        axes[0].pie(
            rank_values,
            labels=rank_labels,
            colors=palette,
            startangle=90,
            counterclock=False,
            textprops={"color": COLORS["text"], "fontsize": 9},
            wedgeprops={"width": .42, "edgecolor": COLORS["panel"]},
        )
        axes[0].text(0, 0.04, str(len(self.frame)), ha="center", va="center", color=COLORS["text"], fontsize=16, fontweight="bold")
        axes[0].text(0, -0.14, "总抽数", ha="center", va="center", color=COLORS["muted"], fontsize=8)
        axes[0].set_title("物品星级分布", fontsize=11)

        pool_order = ["character_event", "lightcone_event", "standard", "beginner"]
        pool_values = [int(self.frame["pool_type"].eq(pool).sum()) for pool in pool_order]
        pool_labels = [POOL_LABELS[pool] for pool in pool_order]
        bar_colors = [COLORS["purple"], COLORS["teal"], COLORS["blue"], COLORS["gold"]]
        bars = axes[1].barh(pool_labels[::-1], pool_values[::-1], color=bar_colors[::-1], height=.55)
        axes[1].set_title("各卡池抽数", fontsize=11)
        axes[1].set_xlabel("抽数")
        axes[1].grid(axis="x", color=COLORS["line"], alpha=.35, linewidth=.7)
        axes[1].set_axisbelow(True)
        for bar, value in zip(bars, pool_values[::-1]):
            axes[1].text(value + max(pool_values) * .015, bar.get_y() + bar.get_height() / 2, str(value), va="center", color=COLORS["text"], fontsize=9)

        figure.tight_layout(pad=2.0)
        self._chart_canvas = FigureCanvasTkAgg(figure, master=parent)
        self._chart_canvas.draw()
        self._chart_canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=(0, 6))

    def _render_pool_tab(self, scroll_frame: ScrollFrame, pool_type: str) -> None:
        parent = scroll_frame.content
        self._clear(parent)
        stats = self.summary["pools"][pool_type]
        pool = self.frame[self.frame["pool_type"].eq(pool_type)]
        metrics = [
            ("抽卡数", str(stats["total_pulls"])),
            ("五星", str(stats["five_stars"])),
            ("平均出金", self._fmt_number(stats["average_pity"])),
            ("当前垫池", str(stats["current_pity"])),
            (
                "非保底 UP 率" if pool_type in {"character_event", "lightcone_event"} else "最晚出金",
                self._fmt_rate(stats["small_pity_win_rate"]) if pool_type in {"character_event", "lightcone_event"} else self._fmt_number(stats["latest_pity"]),
            ),
        ]
        self._section_title(parent, POOL_LABELS[pool_type], (12, 5))
        self._metric_row(parent, metrics)
        self._section_title(parent, "五星历史")
        self._five_star_cards(parent, pool)
        self._section_title(parent, "该池记录")
        rows = []
        for _, row in pool.sort_values("time", ascending=False).iterrows():
            result = self._result_label(row)
            tag = "off_banner" if result == "歪" else "guaranteed" if result == "保底" else "normal"
            values = (row["time"].strftime("%Y-%m-%d %H:%M:%S"), row["name"], row["item_type"], row["rank_type"], row["pity_count"], result)
            rows.append((values, tag))
        self._tree(parent, ["time", "name", "type", "rank", "pity", "result"], ["时间", "名称", "类型", "星级", "Pity", "结果"], [165, 180, 90, 60, 65, 80], rows, height=12)
        tk.Frame(parent, height=15, background=COLORS["background"]).pack()

    @staticmethod
    def _result_label(row: pd.Series) -> str:
        if row["pool_type"] not in {"character_event", "lightcone_event"} or not bool(row["is_five_star"]):
            return ""
        if bool(row["is_off_banner"]):
            return "歪"
        if bool(row["is_guaranteed"]):
            return "保底"
        return "UP"

    def _render_detail_tab(self) -> None:
        self._clear(self.detail_tab)
        tk.Label(
            self.detail_tab,
            text="全部抽卡记录",
            background=COLORS["background"],
            foreground=COLORS["text"],
            font=(FONT, 13, "bold"),
        ).pack(anchor="w", padx=4, pady=(14, 8))
        rows = []
        for _, row in self.frame.sort_values("time", ascending=False).iterrows():
            result = self._result_label(row)
            tag = "off_banner" if result == "歪" else "guaranteed" if result == "保底" else "normal"
            values = (
                row["time"].strftime("%Y-%m-%d %H:%M:%S"),
                POOL_LABELS.get(row["pool_type"], row["pool_type"]),
                row["name"],
                row["item_type"],
                row["rank_type"],
                row["pity_count"],
                result,
            )
            rows.append((values, tag))
        self._tree(
            self.detail_tab,
            ["time", "pool", "name", "type", "rank", "pity", "result"],
            ["时间", "卡池", "名称", "类型", "星级", "Pity", "结果"],
            [165, 140, 190, 90, 60, 65, 80],
            rows,
            height=22,
            expand=True,
        )

    def _tree(
        self,
        parent: tk.Misc,
        columns: list[str],
        headings: list[str],
        widths: list[int],
        rows: list[tuple[tuple[Any, ...], str]],
        height: int,
        expand: bool = False,
    ) -> ttk.Treeview:
        container = tk.Frame(parent, background=COLORS["background"])
        container.pack(fill="both" if expand else "x", expand=expand, padx=4, pady=(0, 4))
        tree = ttk.Treeview(container, columns=columns, show="headings", height=height)
        y_scroll = RoundedScrollbar(container, orient="vertical", command=tree.yview)
        x_scroll = RoundedScrollbar(container, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        for name, heading, width in zip(columns, headings, widths):
            tree.heading(name, text=heading)
            tree.column(name, width=width, minwidth=55, anchor="center" if name in {"rank", "pity", "result"} else "w")
        tree.tag_configure("off_banner", foreground=COLORS["red"])
        tree.tag_configure("guaranteed", foreground=COLORS["gold"])
        tree.tag_configure("normal", foreground=COLORS["text"])
        for values, tag in rows:
            tree.insert("", "end", values=values, tags=(tag,))
        tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        return tree


def main() -> None:
    root = tk.Tk()
    HSRGachaDesktopApp(root)
    if "--smoke-test" in sys.argv:
        root.update_idletasks()
        print("desktop-ui-smoke-test: ok")
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
