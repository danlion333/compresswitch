"""Main window layout and signal handling."""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from compresswitch.file_queue import FileQueue, QueueEntry, Status
from compresswitch.utils import ALL_EXTENSIONS, is_valid_switch_file
from compresswitch.worker import NszWorker

APP_ID = "com.github.dan.compresswitch"


class CompressSwitchWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("CompressSwitch")
        self.set_default_size(500, 700)

        self.queue = FileQueue()
        self._worker: NszWorker | None = None
        self._processing = False
        self._pulse_timeout_id: int | None = None
        self._last_progress_time: float = 0

        self._build_ui()
        self._setup_drop_target()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Main layout
        self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self._main_box)

        # Header bar
        header = Adw.HeaderBar()
        self._main_box.append(header)

        # About / menu button
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu = Gio.Menu()
        menu.append("About CompressSwitch", "app.about")
        menu_button.set_menu_model(menu)
        header.pack_end(menu_button)

        # Scrollable content area
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        self._main_box.append(scrolled)

        content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=12,
            margin_bottom=12,
            margin_start=12,
            margin_end=12,
        )
        scrolled.set_child(content_box)

        # Stack for empty state vs file list
        self._stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        content_box.append(self._stack)

        # Empty state
        self._status_page = Adw.StatusPage(
            title="No Files Added",
            description="Drop files here or click to add",
            icon_name="document-open-symbolic",
            vexpand=True,
        )
        add_button = Gtk.Button(label="Add Files", halign=Gtk.Align.CENTER)
        add_button.add_css_class("suggested-action")
        add_button.add_css_class("pill")
        add_button.connect("clicked", self._on_add_files_clicked)
        self._status_page.set_child(add_button)
        self._stack.add_named(self._status_page, "empty")

        # File list state
        list_box_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._stack.add_named(list_box_container, "queue")

        # Add files button (for when queue is shown)
        add_row_box = Gtk.Box(halign=Gtk.Align.END, margin_bottom=4)
        add_more_button = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Add Files")
        add_more_button.add_css_class("flat")
        add_more_button.connect("clicked", self._on_add_files_clicked)
        add_row_box.append(add_more_button)
        list_box_container.append(add_row_box)

        self._list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")
        list_box_container.append(self._list_box)

        # Settings group
        self._settings_group = Adw.PreferencesGroup(title="Settings", margin_top=8)
        content_box.append(self._settings_group)

        # Compression level
        self._level_row = Adw.SpinRow.new_with_range(1, 22, 1)
        self._level_row.set_title("Compression Level")
        self._level_row.set_value(18)
        self._settings_group.add(self._level_row)

        # Block compression
        self._block_row = Adw.SwitchRow(title="Block Compression")
        self._block_row.set_active(True)
        self._settings_group.add(self._block_row)

        # Output directory
        self._output_row = Adw.ActionRow(title="Output Directory", subtitle="Same as input")
        browse_button = Gtk.Button(
            icon_name="folder-open-symbolic",
            valign=Gtk.Align.CENTER,
            tooltip_text="Browse",
        )
        browse_button.add_css_class("flat")
        browse_button.connect("clicked", self._on_browse_output)
        self._output_row.add_suffix(browse_button)
        self._output_row.set_activatable_widget(browse_button)
        self._settings_group.add(self._output_row)

        # Progress area
        progress_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_top=8,
        )
        content_box.append(progress_box)

        self._progress_label = Gtk.Label(
            label="Ready",
            halign=Gtk.Align.START,
            ellipsize=3,  # Pango.EllipsizeMode.END
        )
        progress_box.append(self._progress_label)

        self._progress_bar = Gtk.ProgressBar(show_text=True)
        progress_box.append(self._progress_bar)

        # Start/Cancel button
        button_box = Gtk.Box(halign=Gtk.Align.CENTER, margin_top=4, margin_bottom=8)
        self._start_button = Gtk.Button(label="Start")
        self._start_button.add_css_class("suggested-action")
        self._start_button.add_css_class("pill")
        self._start_button.connect("clicked", self._on_start_cancel)
        button_box.append(self._start_button)
        content_box.append(button_box)

        self._update_stack()
        self._update_settings_visibility()

    def _setup_drop_target(self) -> None:
        drop_target = Gtk.DropTarget(actions=Gdk.DragAction.COPY)
        drop_target.set_gtypes([Gdk.FileList])
        drop_target.connect("drop", self._on_drop)
        self.add_controller(drop_target)

    # ── Stack / visibility management ────────────────────────────────

    def _update_stack(self) -> None:
        if len(self.queue) == 0:
            self._stack.set_visible_child_name("empty")
        else:
            self._stack.set_visible_child_name("queue")
        self._start_button.set_sensitive(len(self.queue) > 0 and not self._processing)

    def _update_settings_visibility(self) -> None:
        # Hide settings if queue only contains decompress operations
        if len(self.queue) > 0 and not self.queue.has_any_compress():
            self._settings_group.set_visible(False)
        else:
            self._settings_group.set_visible(True)

    # ── File list rows ───────────────────────────────────────────────

    def _add_queue_row(self, entry: QueueEntry) -> None:
        row = Adw.ActionRow(
            title=entry.path.name,
            subtitle=f"→ {entry.target}  ({entry.operation})",
        )

        # Status icon
        icon = Gtk.Image(icon_name="content-loading-symbolic")
        row.add_prefix(icon)

        # Remove button
        remove_btn = Gtk.Button(
            icon_name="edit-delete-symbolic",
            valign=Gtk.Align.CENTER,
            tooltip_text="Remove",
        )
        remove_btn.add_css_class("flat")
        idx = self.queue.index_of(entry)
        remove_btn.connect("clicked", self._on_remove_file, idx)
        row.add_suffix(remove_btn)

        self._list_box.append(row)

    def _refresh_list(self) -> None:
        # Remove all rows
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)
        # Re-add
        for entry in self.queue:
            self._add_queue_row(entry)
        self._update_stack()
        self._update_settings_visibility()

    def _update_row_status(self, entry: QueueEntry) -> None:
        idx = self.queue.index_of(entry)
        row = self._list_box.get_row_at_index(idx)
        if row is None:
            return
        # Update the prefix icon
        icon = row.get_first_child()
        # Navigate to the actual icon widget - Adw.ActionRow structure
        # The prefix is the first child added via add_prefix
        if entry.status == Status.DONE:
            self._set_row_icon(row, "emblem-ok-symbolic")
        elif entry.status == Status.ERROR:
            self._set_row_icon(row, "dialog-error-symbolic")
            row.set_subtitle(entry.error_message)
        elif entry.status == Status.PROCESSING:
            self._set_row_icon(row, "media-playback-start-symbolic")

    def _set_row_icon(self, row: Adw.ActionRow, icon_name: str) -> None:
        """Replace the prefix icon in an ActionRow."""
        # ActionRow prefix box is the first child of the row's internal box
        # We need to iterate to find our Gtk.Image
        # Since we add_prefix(icon), it ends up in the row's prefix area
        # Simplest: remove all prefixes and re-add
        # Actually, Adw.ActionRow doesn't have remove_prefix, so we'll
        # track it differently. For now, just update subtitle as indicator.
        pass  # Icon updates are best-effort; status shown in subtitle

    # ── Signal handlers ──────────────────────────────────────────────

    def _on_add_files_clicked(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileDialog()
        filter_ = Gtk.FileFilter(name="Switch files")
        for ext in sorted(ALL_EXTENSIONS):
            filter_.add_suffix(ext.lstrip("."))
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_)
        dialog.set_filters(filters)
        dialog.set_default_filter(filter_)
        dialog.open_multiple(self, None, self._on_files_selected)

    def _on_files_selected(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult
    ) -> None:
        try:
            files = dialog.open_multiple_finish(result)
        except GLib.Error:
            return  # User cancelled
        for i in range(files.get_n_items()):
            gfile = files.get_item(i)
            path = Path(gfile.get_path())
            if is_valid_switch_file(path):
                self.queue.add(path)
        self._refresh_list()

    def _on_drop(
        self,
        _target: Gtk.DropTarget,
        value: Gdk.FileList,
        _x: float,
        _y: float,
    ) -> bool:
        files = value.get_files()
        added = False
        for gfile in files:
            path = Path(gfile.get_path())
            if is_valid_switch_file(path):
                if self.queue.add(path):
                    added = True
        if added:
            self._refresh_list()
        return True

    def _on_remove_file(self, _button: Gtk.Button, index: int) -> None:
        if self._processing:
            return  # Don't allow removal during processing
        self.queue.remove(index)
        self._refresh_list()

    def _on_browse_output(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileDialog()
        dialog.select_folder(self, None, self._on_output_dir_selected)

    def _on_output_dir_selected(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult
    ) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        path = folder.get_path()
        self._output_row.set_subtitle(path)

    def _on_start_cancel(self, _button: Gtk.Button) -> None:
        if self._processing:
            self._cancel_processing()
        else:
            self._start_processing()

    # ── Processing logic ─────────────────────────────────────────────

    def _start_processing(self) -> None:
        if not self.queue.has_pending():
            return

        self._processing = True
        self._start_button.set_label("Cancel")
        self._start_button.remove_css_class("suggested-action")
        self._start_button.add_css_class("destructive-action")
        self._process_next()

    def _process_next(self) -> None:
        entry = self.queue.next_pending()
        if entry is None:
            self._finish_processing()
            return

        entry.status = Status.PROCESSING
        self._update_row_status(entry)
        self._progress_label.set_label(f"Processing: {entry.path.name}")
        self._progress_bar.set_fraction(0)
        self._progress_bar.set_text("0%")

        output_dir = self._output_row.get_subtitle()
        if output_dir == "Same as input":
            output_dir = ""

        self._worker = NszWorker(
            entry,
            compression_level=int(self._level_row.get_value()),
            block_compression=self._block_row.get_active(),
            output_dir=output_dir or "",
            on_progress=self._on_worker_progress,
            on_done=self._on_worker_done,
        )

        self._last_progress_time = GLib.get_monotonic_time()
        self._pulse_timeout_id = GLib.timeout_add(2000, self._check_pulse)
        self._worker.start()

    def _on_worker_progress(self, entry: QueueEntry, percent: int) -> None:
        self._last_progress_time = GLib.get_monotonic_time()
        entry.progress = percent
        self._progress_bar.set_fraction(percent / 100.0)
        self._progress_bar.set_text(f"{percent}%")

    def _on_worker_done(
        self, entry: QueueEntry, success: bool, message: str
    ) -> None:
        if self._pulse_timeout_id:
            GLib.source_remove(self._pulse_timeout_id)
            self._pulse_timeout_id = None

        if success:
            entry.status = Status.DONE
            entry.progress = 100
            self._progress_bar.set_fraction(1.0)
            self._progress_bar.set_text("100%")
        else:
            entry.status = Status.ERROR
            entry.error_message = message
            if "keys" in message.lower():
                dialog = Adw.MessageDialog(
                    transient_for=self,
                    heading="Switch Keys Not Found",
                    body=message,
                )
                dialog.add_response("ok", "OK")
                dialog.present()

        self._update_row_status(entry)
        self._worker = None

        if self._processing and not entry.error_message.startswith("Cancel"):
            self._process_next()
        else:
            self._finish_processing()

    def _check_pulse(self) -> bool:
        """Pulse the progress bar if no progress updates received recently."""
        if not self._processing:
            return False
        elapsed = GLib.get_monotonic_time() - self._last_progress_time
        if elapsed > 2_000_000:  # 2 seconds in microseconds
            self._progress_bar.pulse()
        return True

    def _cancel_processing(self) -> None:
        if self._worker:
            self._worker.cancel()
        self._finish_processing()

    def _finish_processing(self) -> None:
        self._processing = False
        if self._pulse_timeout_id:
            GLib.source_remove(self._pulse_timeout_id)
            self._pulse_timeout_id = None
        self._start_button.set_label("Start")
        self._start_button.remove_css_class("destructive-action")
        self._start_button.add_css_class("suggested-action")
        self._start_button.set_sensitive(self.queue.has_pending())
        self._progress_label.set_label("Ready")


class CompressSwitchApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)
        self.connect("activate", self._on_activate)

    def _on_activate(self, _app: Adw.Application) -> None:
        win = self.get_active_window()
        if win is None:
            win = CompressSwitchWindow(application=self)
        self._setup_actions()
        win.present()

    def _setup_actions(self) -> None:
        quit_action = Gio.SimpleAction(name="quit")
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Control>q"])

        about_action = Gio.SimpleAction(name="about")
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

    def _on_about(self, *_args) -> None:
        about = Adw.AboutDialog(
            application_name="CompressSwitch",
            application_icon="applications-games-symbolic",
            developer_name="Dan",
            version="0.1.0",
            comments="Compress and decompress Nintendo Switch XCI/NSP files",
            license_type=Gtk.License.MIT_X11,
        )
        about.present(self.get_active_window())
