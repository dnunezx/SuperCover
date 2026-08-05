"""Windows desktop interface for SuperCover."""

from __future__ import annotations

import io
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from PIL import Image, ImageTk

from .catalog import load_catalog
from .exporter import ExistingFilePolicy, export_covers
from .libretro import LibretroProvider
from .matching import match_roms
from .network import DownloadCancelled, HttpClient
from .scanner import scan_roms
from .sfcov import LEGACY_SIZE, WIDTH
from .version import __version__
from .workflow import (
    CoverSession,
    artwork_preview_bytes,
    assign_export_results,
    merge_catalogs,
    prepare_session_artwork,
)


POLICY_LABELS = {
    "Preserve existing covers": ExistingFilePolicy.SKIP,
    "Replace existing covers": ExistingFilePolicy.REPLACE,
    "Keep both (comparison only)": ExistingFilePolicy.KEEP_BOTH,
}

EXPORT_SIZE_LABELS = {
    f"{WIDTH} x {WIDTH} (default)": WIDTH,
    f"{LEGACY_SIZE} x {LEGACY_SIZE}": LEGACY_SIZE,
}


def application_dir() -> Path:
    """Return the portable application folder without relying on the CWD."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundled_resource(*parts: str) -> Path:
    """Locate source assets or files unpacked from the one-file executable."""

    root = Path(getattr(sys, "_MEIPASS", application_dir()))
    return root.joinpath(*parts)


class SuperCoverApp:
    """A responsive, review-first Tkinter interface."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"SuperCover {__version__}")
        try:
            self.root.iconbitmap(
                default=str(bundled_resource("assets", "supercover.ico"))
            )
        except tk.TclError:
            pass
        self.root.minsize(980, 700)
        self.root.geometry("1180x780")
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self.session: CoverSession | None = None
        self._busy = False
        self._events: queue.Queue = queue.Queue()
        self._cancel = threading.Event()
        self._preview_photo: ImageTk.PhotoImage | None = None
        self._active_success: Callable | None = None

        self.rom_folder = tk.StringVar()
        self.catalog_file = tk.StringVar()
        self.export_folder = tk.StringVar()
        self.recursive = tk.BooleanVar(value=True)
        self.offline = tk.BooleanVar(value=False)
        self.save_previews = tk.BooleanVar(value=False)
        self.existing_policy = tk.StringVar(value="Preserve existing covers")
        self.export_size = tk.StringVar(value=next(iter(EXPORT_SIZE_LABELS)))
        self.review_title = tk.StringVar()
        self.status_text = tk.StringVar(value="Choose a ROM folder to begin.")
        self.summary_text = tk.StringVar(value="No games scanned yet")

        self._configure_styles()
        self._build_interface()
        self.export_folder.trace_add("write", self._export_folder_changed)
        self.export_size.trace_add("write", self._export_size_changed)
        self._set_action_states()

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        for theme in ("vista", "xpnative", "clam"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10))
        style.configure("Section.TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 8))
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_interface(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 12))
        ttk.Button(header, text="About", command=self._show_about).pack(side="right")
        ttk.Label(header, text="SuperCover", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Find and prepare SuperFW cover art without changing your games.",
            style="Subtitle.TLabel",
        ).pack(anchor="w")

        setup = ttk.LabelFrame(
            outer, text="1. Choose folders", style="Section.TLabelframe", padding=10
        )
        setup.pack(fill="x")
        setup.columnconfigure(1, weight=1)

        self._path_row(
            setup,
            0,
            "GBA game folder",
            self.rom_folder,
            "Choose ROM Folder",
            self._browse_roms,
        )
        self._path_row(
            setup,
            1,
            "Export destination",
            self.export_folder,
            "Choose Export Folder",
            self._browse_export,
        )
        ttk.Label(
            setup,
            text=(
                "Nothing is exported until you choose this folder. For direct SD-card "
                "installation, choose its .superfw\\covers folder."
            ),
            foreground="#555555",
        ).grid(row=2, column=1, columnspan=2, sticky="w", pady=(0, 5))
        self._path_row(
            setup,
            3,
            "Trusted catalog (optional)",
            self.catalog_file,
            "Choose JSON Catalog",
            self._browse_catalog,
        )
        ttk.Label(
            setup,
            text="Without a JSON catalog, SuperCover uses the curated online cover list.",
            foreground="#555555",
        ).grid(row=4, column=1, columnspan=2, sticky="w", pady=(0, 4))

        options = ttk.Frame(setup)
        options.grid(row=5, column=1, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Checkbutton(
            options, text="Include subfolders", variable=self.recursive
        ).pack(side="left")
        ttk.Checkbutton(
            options, text="Work offline from cache", variable=self.offline
        ).pack(side="left", padx=(18, 0))
        ttk.Checkbutton(
            options,
            text="Save PNG previews in an export subfolder",
            variable=self.save_previews,
        ).pack(side="left", padx=(18, 0))

        export_options = ttk.Frame(setup)
        export_options.grid(row=6, column=1, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(export_options, text="Existing covers:").pack(side="left", padx=(0, 5))
        ttk.Combobox(
            export_options,
            textvariable=self.existing_policy,
            values=tuple(POLICY_LABELS),
            state="readonly",
            width=27,
        ).pack(side="left")
        ttk.Label(export_options, text="Export size:").pack(side="left", padx=(18, 5))
        ttk.Combobox(
            export_options,
            textvariable=self.export_size,
            values=tuple(EXPORT_SIZE_LABELS),
            state="readonly",
            width=17,
        ).pack(side="left")

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=10)
        self.scan_button = ttk.Button(
            actions,
            text="Scan and Match Games",
            style="Primary.TButton",
            command=self._start_scan,
        )
        self.scan_button.pack(side="left")
        self.prepare_button = ttk.Button(
            actions,
            text="Prepare Selected Artwork",
            command=self._start_prepare,
        )
        self.prepare_button.pack(side="left", padx=(8, 0))
        self.export_button = ttk.Button(
            actions,
            text="Export Covers",
            style="Primary.TButton",
            command=self._start_export,
        )
        self.export_button.pack(side="left", padx=(8, 0))
        self.cancel_button = ttk.Button(
            actions, text="Cancel", command=self._cancel_work
        )
        self.cancel_button.pack(side="left", padx=(8, 0))

        self.progress = ttk.Progressbar(actions, mode="determinate", maximum=100)
        self.progress.pack(side="right", fill="x", expand=True, padx=(24, 0))

        content = ttk.Panedwindow(outer, orient="horizontal")
        content.pack(fill="both", expand=True)

        games_frame = ttk.LabelFrame(
            content, text="2. Review every game", style="Section.TLabelframe", padding=8
        )
        review_frame = ttk.LabelFrame(
            content, text="3. Confirm the selected game", style="Section.TLabelframe", padding=12
        )
        content.add(games_frame, weight=4)
        content.add(review_frame, weight=2)

        ttk.Label(games_frame, textvariable=self.summary_text).pack(anchor="w", pady=(0, 6))
        table_frame = ttk.Frame(games_frame)
        table_frame.pack(fill="both", expand=True)
        columns = ("include", "status", "rom", "match", "artwork")
        self.games_table = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="browse"
        )
        headings = {
            "include": "Use",
            "status": "Match",
            "rom": "ROM filename",
            "match": "Artwork title",
            "artwork": "Artwork",
        }
        widths = {"include": 55, "status": 85, "rom": 250, "match": 270, "artwork": 120}
        for name in columns:
            self.games_table.heading(name, text=headings[name])
            self.games_table.column(
                name,
                width=widths[name],
                minwidth=45,
                stretch=name in ("rom", "match"),
            )
        scrollbar = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.games_table.yview
        )
        self.games_table.configure(yscrollcommand=scrollbar.set)
        self.games_table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.games_table.bind("<<TreeviewSelect>>", self._show_selected_game)
        self.games_table.bind("<Double-1>", self._toggle_selected)
        self.games_table.tag_configure("attention", background="#fff4d6")
        self.games_table.tag_configure("error", background="#ffe2e2")
        self.games_table.tag_configure("ready", background="#e7f6e7")

        self.selected_rom_label = ttk.Label(
            review_frame,
            text="Select a game from the list.",
            font=("Segoe UI", 11, "bold"),
            wraplength=330,
        )
        self.selected_rom_label.pack(fill="x", anchor="w")
        self.selected_message = ttk.Label(
            review_frame, text="", wraplength=330, foreground="#555555"
        )
        self.selected_message.pack(fill="x", anchor="w", pady=(4, 12))

        ttk.Label(review_frame, text="Artwork title:").pack(anchor="w")
        self.title_box = ttk.Combobox(
            review_frame, textvariable=self.review_title, state="normal"
        )
        self.title_box.pack(fill="x", pady=(3, 7))
        self.approve_button = ttk.Button(
            review_frame,
            text="Use This Artwork Title",
            command=self._approve_selected,
        )
        self.approve_button.pack(fill="x")
        self.include_button = ttk.Button(
            review_frame,
            text="Include / Skip This Game",
            command=self._toggle_selected,
        )
        self.include_button.pack(fill="x", pady=(6, 12))

        self.preview_label = ttk.Label(
            review_frame,
            text=f"The final {WIDTH} x {WIDTH} GBA-color preview will appear here.",
            anchor="center",
            justify="center",
            relief="solid",
            padding=8,
        )
        self.preview_label.pack(fill="both", expand=True)

        status = ttk.Frame(outer)
        status.pack(fill="x", pady=(10, 0))
        ttk.Label(status, textvariable=self.status_text).pack(side="left", fill="x", expand=True)

    def _path_row(
        self,
        parent: ttk.Widget,
        row: int,
        label: str,
        variable: tk.StringVar,
        button_text: str,
        command: Callable,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Button(parent, text=button_text, command=command).grid(
            row=row, column=2, sticky="ew", padx=(8, 0), pady=3
        )

    def _browse_roms(self) -> None:
        selected = filedialog.askdirectory(title="Choose your GBA game folder", mustexist=True)
        if selected:
            self.rom_folder.set(selected)

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About SuperCover",
            f"SuperCover {__version__}\n\n"
            "Portable GBA cover-art manager for SuperFW.\n\n"
            "Licensed under GPL-3.0-or-later. Online artwork metadata comes "
            "from the curated Libretro GBA thumbnail project.\n\n"
            "See LICENSE and THIRD_PARTY_NOTICES in the release folder for details.\n\n"
            "github.com/dnunezx/SuperCover",
        )

    def _browse_export(self) -> None:
        selected = filedialog.askdirectory(
            title="Choose exactly where .sfcov files will be exported",
            mustexist=False,
        )
        if selected:
            self.export_folder.set(selected)

    def _export_folder_changed(self, *_args) -> None:
        self._set_action_states()

    def _selected_export_size(self) -> int:
        return EXPORT_SIZE_LABELS[self.export_size.get()]

    def _export_size_changed(self, *_args) -> None:
        if self.session is None or not self.games_table.selection():
            size = self._selected_export_size()
            self.preview_label.configure(
                image="",
                text=f"The final {size} x {size} GBA-color preview will appear here.",
            )
            return
        self._show_selected_game()

    def _browse_catalog(self) -> None:
        selected = filedialog.askopenfilename(
            title="Choose an optional SuperCover JSON catalog",
            filetypes=(("JSON catalog", "*.json"), ("All files", "*.*")),
        )
        if selected:
            self.catalog_file.set(selected)

    def _provider(self, offline: bool) -> LibretroProvider:
        return LibretroProvider(
            application_dir() / ".supercover-cache",
            offline=offline,
            http=HttpClient(cancelled=self._cancel.is_set),
        )

    def _start_scan(self) -> None:
        rom_text = self.rom_folder.get().strip()
        if not rom_text:
            messagebox.showwarning("Choose a ROM folder", "Choose the folder containing your GBA games.")
            return
        rom_folder = Path(rom_text)
        catalog_text = self.catalog_file.get().strip()
        catalog_path = Path(catalog_text) if catalog_text else None
        recursive = self.recursive.get()
        offline = self.offline.get()

        def work(progress):
            progress(0, 3, "Loading the curated cover list")
            provider = self._provider(offline)
            filenames = provider.load_index()
            trusted = load_catalog(catalog_path) if catalog_path else []
            catalog = merge_catalogs(filenames, trusted)
            progress(1, 3, "Reading GBA filenames and checksums")
            roms = scan_roms(rom_folder, recursive=recursive)
            progress(2, 3, "Matching games to artwork titles")
            matches = match_roms(roms, catalog)
            progress(3, 3, "Scan complete")
            return CoverSession(matches, catalog)

        self._run_background(work, self._scan_complete)

    def _scan_complete(self, session: CoverSession) -> None:
        self.session = session
        self.title_box.configure(values=session.titles)
        self._refresh_table()
        if session.games:
            self.games_table.selection_set("0")
            self.games_table.focus("0")
            self.games_table.see("0")
            self._show_selected_game()
        self.status_text.set(
            f"Scan complete: {len(session.games)} game(s), {session.included_count} automatically selected."
        )
        self._set_action_states()

    def _start_prepare(self) -> None:
        if self.session is None or self.session.included_count == 0:
            messagebox.showwarning("Nothing selected", "Include at least one approved game first.")
            return
        session = self.session
        offline = self.offline.get()
        export_size = self._selected_export_size()

        def work(progress):
            return prepare_session_artwork(
                session,
                self._provider(offline),
                progress=progress,
                cancelled=self._cancel.is_set,
                size=export_size,
            )

        self._run_background(work, self._prepare_complete)

    def _prepare_complete(self, summary) -> None:
        self._refresh_table()
        self._show_selected_game()
        self.status_text.set(
            f"Artwork ready for {summary.prepared} game(s); {summary.failed} failed; "
            f"{summary.skipped} skipped."
        )
        self._set_action_states()

    def _start_export(self) -> None:
        if self.session is None or self.session.prepared_count == 0:
            messagebox.showwarning("No artwork ready", "Prepare selected artwork before exporting.")
            return
        destination_text = self.export_folder.get().strip()
        if not destination_text:
            messagebox.showwarning(
                "Choose an export folder",
                "Choose exactly where SuperCover should place the .sfcov files.",
            )
            return
        session = self.session
        destination = Path(destination_text)
        preview_dir = destination / "SuperCover Previews" if self.save_previews.get() else None
        policy = POLICY_LABELS[self.existing_policy.get()]
        export_size = self._selected_export_size()

        def work(progress):
            requests = session.export_requests()
            progress(0, 1, f"Converting {len(requests)} selected cover(s)")
            results = export_covers(
                requests,
                destination,
                preview_dir=preview_dir,
                existing=policy,
                size=export_size,
            )
            assign_export_results(session, results)
            progress(1, 1, "Export complete")
            return results

        self._run_background(work, self._export_complete)

    def _export_complete(self, results) -> None:
        self._refresh_table()
        exported = sum(result.status.value == "exported" for result in results)
        preserved = len(results) - exported
        destination = Path(self.export_folder.get().strip())
        self.status_text.set(
            f"Done: {exported} cover(s) exported to {destination}; {preserved} existing cover(s) preserved."
        )
        messagebox.showinfo(
            "Export complete",
            f"SuperCover finished successfully.\n\nExported: {exported}\n"
            f"Preserved: {preserved}\n\nFolder:\n{destination}",
        )
        self._set_action_states()

    def _selected_index(self) -> int | None:
        selection = self.games_table.selection()
        return int(selection[0]) if selection else None

    def _approve_selected(self) -> None:
        if self.session is None or self._busy:
            return
        index = self._selected_index()
        if index is None:
            return
        try:
            self.session.approve_title(index, self.review_title.get())
        except ValueError as exc:
            messagebox.showwarning("Choose an artwork title", str(exc))
            return
        self._refresh_table(keep=index)
        self._show_selected_game()
        self.status_text.set("Manual artwork choice approved. Prepare artwork to preview it.")
        self._set_action_states()

    def _toggle_selected(self, _event=None) -> None:
        if self.session is None or self._busy:
            return
        index = self._selected_index()
        if index is None:
            return
        try:
            self.session.toggle_included(index)
        except ValueError as exc:
            messagebox.showwarning("Approval required", str(exc))
            return
        self._refresh_table(keep=index)
        self._show_selected_game()
        self._set_action_states()

    def _refresh_table(self, keep: int | None = None) -> None:
        for item in self.games_table.get_children():
            self.games_table.delete(item)
        if self.session is None:
            return
        for index, game in enumerate(self.session.games):
            art_status = game.artwork_message
            if game.export_result is not None:
                art_status = game.export_result.status.value.title()
            tag = ""
            if art_status.startswith("Error"):
                tag = "error"
            elif game.artwork is not None:
                tag = "ready"
            elif not game.approved:
                tag = "attention"
            self.games_table.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    "Yes" if game.included else "No",
                    game.status_label,
                    game.original.rom.filename,
                    game.selected_entry.name if game.selected_entry else "Choose a title",
                    art_status,
                ),
                tags=(tag,) if tag else (),
            )
        automatic = sum(game.original.status.value == "automatic" for game in self.session.games)
        needs_review = sum(not game.approved for game in self.session.games)
        self.summary_text.set(
            f"{len(self.session.games)} game(s)  |  {automatic} automatic  |  "
            f"{needs_review} need review  |  {self.session.included_count} selected"
        )
        if keep is not None and str(keep) in self.games_table.get_children():
            self.games_table.selection_set(str(keep))
            self.games_table.focus(str(keep))

    def _show_selected_game(self, _event=None) -> None:
        if self.session is None:
            return
        index = self._selected_index()
        if index is None:
            return
        game = self.session.games[index]
        export_size = self._selected_export_size()
        self.selected_rom_label.configure(text=game.original.rom.filename)
        self.selected_message.configure(
            text=f"{game.original.message}\nArtwork: {game.artwork_message}"
        )
        self.review_title.set(game.selected_entry.name if game.selected_entry else "")
        self.include_button.configure(
            text="Skip This Game" if game.included else "Include This Game"
        )
        if game.artwork is not None and game.preview_size != export_size:
            try:
                game.preview_png = artwork_preview_bytes(game.artwork, export_size)
                game.preview_size = export_size
            except (OSError, ValueError):
                game.preview_png = None
                game.preview_size = None
        if game.preview_png:
            with Image.open(io.BytesIO(game.preview_png)) as image:
                preview = image.convert("RGB").resize((216, 216), Image.Resampling.NEAREST)
            self._preview_photo = ImageTk.PhotoImage(preview)
            self.preview_label.configure(image=self._preview_photo, text="")
        else:
            self._preview_photo = None
            self.preview_label.configure(
                image="",
                text=(
                    "Prepare this game's artwork to see its final "
                    f"{export_size} x {export_size} GBA-color preview."
                ),
            )

    def _run_background(self, work: Callable, success: Callable) -> None:
        if self._busy:
            return
        self._busy = True
        self._cancel.clear()
        self._active_success = success
        self.progress.configure(value=0)
        self.status_text.set("Working...")
        self._set_action_states()

        def report(done: int, total: int, message: str) -> None:
            self._events.put(("progress", done, total, message))

        def runner() -> None:
            try:
                result = work(report)
                self._events.put(("success", result))
            except Exception as exc:  # GUI boundary: surface all worker failures.
                self._events.put(("error", exc))

        threading.Thread(target=runner, daemon=True, name="SuperCover worker").start()
        self.root.after(50, self._poll_events)

    def _poll_events(self) -> None:
        finished = False
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            if event[0] == "progress":
                _, done, total, message = event
                percent = 100 if total == 0 else int(done * 100 / total)
                self.progress.configure(value=percent)
                self.status_text.set(message)
            elif event[0] == "success":
                finished = True
                self._finish_work()
                assert self._active_success is not None
                self._active_success(event[1])
            elif event[0] == "error":
                finished = True
                self._finish_work()
                error = event[1]
                if isinstance(error, DownloadCancelled):
                    self.status_text.set("Operation cancelled. No partial cover was exported.")
                else:
                    self.status_text.set(f"Could not finish: {error}")
                    messagebox.showerror("SuperCover could not finish", str(error))
        if self._busy and not finished:
            self.root.after(50, self._poll_events)

    def _finish_work(self) -> None:
        self._busy = False
        self.progress.configure(value=0)
        self._set_action_states()

    def _cancel_work(self) -> None:
        if self._busy:
            self._cancel.set()
            self.status_text.set("Cancelling safely...")

    def _set_action_states(self) -> None:
        busy_state = "disabled" if self._busy else "normal"
        self.scan_button.configure(state=busy_state)
        self.cancel_button.configure(state="normal" if self._busy else "disabled")
        can_prepare = (
            not self._busy and self.session is not None and self.session.included_count > 0
        )
        can_export = (
            not self._busy
            and self.session is not None
            and self.session.prepared_count > 0
            and bool(self.export_folder.get().strip())
        )
        self.prepare_button.configure(state="normal" if can_prepare else "disabled")
        self.export_button.configure(state="normal" if can_export else "disabled")
        state = "disabled" if self._busy or self.session is None else "normal"
        self.approve_button.configure(state=state)
        self.include_button.configure(state=state)

    def _close(self) -> None:
        self._cancel.set()
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    SuperCoverApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
