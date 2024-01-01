#  Flowkeeper - Pomodoro timer for power users and teams
#  Copyright (c) 2023 Constantine Kulak
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import sys
import threading

from PySide6 import QtCore, QtWidgets, QtUiTools, QtGui
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import QToolButton

from fk.core import events
from fk.core.abstract_event_source import AbstractEventSource
from fk.core.events import SourceMessagesProcessed, AfterWorkitemComplete
from fk.core.file_event_source import FileEventSource
from fk.core.tenant import Tenant
from fk.core.timer import PomodoroTimer
from fk.core.workitem import Workitem
from fk.desktop.application import Application
from fk.desktop.export_wizard import ExportWizard
from fk.desktop.import_wizard import ImportWizard
from fk.desktop.settings import SettingsDialog
from fk.qt.about_window import AboutWindow
from fk.qt.abstract_tableview import AfterSelectionChanged
from fk.qt.audio_player import AudioPlayer
from fk.qt.backlog_tableview import BacklogTableView
from fk.qt.focus_widget import FocusWidget
from fk.qt.progress_widget import ProgressWidget
from fk.qt.qt_filesystem_watcher import QtFilesystemWatcher
from fk.qt.qt_timer import QtTimer
from fk.qt.resize_event_filter import ResizeEventFilter
from fk.qt.search_completer import SearchBar
from fk.qt.threaded_event_source import ThreadedEventSource
from fk.qt.tray_icon import TrayIcon
from fk.qt.user_tableview import UserTableView
from fk.qt.websocket_event_source import WebsocketEventSource
from fk.qt.workitem_tableview import WorkitemTableView


def get_timer_ui_mode() -> str:
    # Options: keep (don't do anything), focus (collapse main layout), minimize (window to tray)
    return settings.get('Application.timer_ui_mode')


def show_timer_automatically() -> None:
    global continue_workitem
    action_void.setEnabled(True)
    continue_workitem = None
    mode = get_timer_ui_mode()
    if mode == 'focus':
        header_layout.show()
        main_layout.hide()
        left_toolbar.hide()
        window.setMaximumHeight(header_layout.size().height())
        window.setMinimumHeight(header_layout.size().height())
        tool_show_timer_only.hide()
        tool_show_all.show()
    elif mode == 'minimize':
        window.hide()


def hide_timer() -> None:
    main_layout.show()
    header_layout.show()
    left_toolbar.show()
    window.setMaximumHeight(16777215)
    window.setMinimumHeight(0)
    restore_size()


def hide_timer_automatically(workitem) -> None:
    global continue_workitem

    action_void.setDisabled(True)

    # Show "Next" icon if there's pomodoros remaining
    if workitem is not None and workitem.is_startable():
        continue_workitem = workitem
        # TODO Show "Complete" button here, too
        tool_next.show()
        tool_complete.show()
        tray.setIcon(next_icon)
        return

    continue_workitem = None
    tool_next.hide()
    tool_complete.hide()
    reset_tray_icon()

    mode = get_timer_ui_mode()
    if mode == 'focus':
        hide_timer()
    elif mode == 'minimize':
        window.show()


def auto_resize() -> None:
    h: int = QtGui.QFontMetrics(QtGui.QFont()).height() + 8
    users_table.verticalHeader().setDefaultSectionSize(h)
    backlogs_table.verticalHeader().setDefaultSectionSize(h)
    workitems_table.verticalHeader().setDefaultSectionSize(h)
    # Save it to Settings, so that we can use this value when
    # calculating display hints for the Pomodoro Delegate.
    # As of now, this requires app restart to apply.
    settings.set('Application.table_row_height', str(h))


def restore_size() -> None:
    w = int(settings.get('Application.window_width'))
    h = int(settings.get('Application.window_height'))
    splitter_width = int(settings.get('Application.window_splitter_width'))
    splitter.setSizes([splitter_width, w - splitter_width])
    window.resize(QtCore.QSize(w, h))


def save_splitter_size(new_width: int, index: int) -> None:
    old_width = int(settings.get('Application.window_splitter_width'))
    if old_width != new_width:
        settings.set('Application.window_splitter_width', str(new_width))


def toggle_backlogs(visible) -> None:
    backlogs_table.setVisible(visible)
    left_table_layout.setVisible(visible or users_table.isVisible())


def toggle_users(visible) -> None:
    users_table.setVisible(visible)
    left_table_layout.setVisible(backlogs_table.isVisible() or visible)


def on_messages(event: str = None) -> None:
    global replay_completed

    if replay_completed:
        return
    replay_completed = True

    print('Replay completed')

    users_table.upstream_selected(root)
    backlogs_table.upstream_selected(root.get_current_user())

    # It's important to do it after window.show() above
    if pomodoro_timer.is_working() or pomodoro_timer.is_resting():
        show_timer_automatically()


def restart_warning() -> None:
    QtWidgets.QMessageBox().warning(window,
                                    "Restart required",
                                    f"Please restart Flowkeeper to apply new settings",
                                    QtWidgets.QMessageBox.StandardButton.Ok)


def on_setting_changed(event: str, name: str, old_value: str, new_value: str):
    # print(f'Setting {name} changed from {old_value} to {new_value}')
    status.showMessage('Settings changed')
    if name == 'Source.type':
        restart_warning()
    elif name == 'Application.timer_ui_mode' and (pomodoro_timer.is_working() or pomodoro_timer.is_resting()):
        # TODO: This really doesn't work well
        hide_timer_automatically(None)
        show_timer_automatically()
    elif name == 'Application.quit_on_close':
        app.setQuitOnLastWindowClosed(new_value == 'True')
    elif 'Application.font_' in name:
        initialize_fonts(settings)
    elif name == 'Application.show_main_menu':
        main_menu.setVisible(new_value == 'True')
    elif name == 'Application.show_status_bar':
        status.setVisible(new_value == 'True')
    elif name == 'Application.show_toolbar':
        toolbar.setVisible(new_value == 'True')
    elif name == 'Application.show_left_toolbar':
        left_toolbar.setVisible(new_value == 'True')
    elif name == 'Application.show_tray_icon':
        tray.setVisible(new_value == 'True')
    elif name == 'Application.theme':
        restart_warning()
        # app.set_theme(new_value)
    elif name.startswith('WebsocketEventSource.'):
        source.start()
    # TODO: Subscribe to sound settings
    # TODO: Subscribe the sources to the settings they use
    # TODO: Reload the app when the source changes


def repair_file_event_source(_):
    if QtWidgets.QMessageBox().warning(window,
                                        "Confirmation",
                                        f"Are you sure you want to repair the data source? "
                                        f"This action will\n"
                                        f"1. Remove duplicates,\n"
                                        f"2. Create missing data entities like users and backlogs, on first reference,\n"
                                        f"3. Renumber / reindex data,\n"
                                        f"4. Remove any events, which fail after 1 -- 3,\n"
                                        f"5. Create a backup file and overwrite the original data source one,\n"
                                        f"6. Display a detailed log of what it did.\n"
                                        f"\n"
                                        f"If there are no errors, then this action won't create or overwrite any files.",
                                        QtWidgets.QMessageBox.StandardButton.Ok,
                                        QtWidgets.QMessageBox.StandardButton.Cancel) \
            == QtWidgets.QMessageBox.StandardButton.Ok:
        cast: FileEventSource = source
        log = cast.repair()
        QtWidgets.QInputDialog.getMultiLineText(window,
                                                "Repair completed",
                                                "Please save this log for future reference. "
                                                "You can find all new items by searching (CTRL+F) for [Repaired] string.\n"
                                                "Flowkeeper restart is required to reload the changes.",
                                                "\n".join(log))


# The order is important here. Some Sources use Qt APIs, so we need an Application instance created first.
# Then we initialize a Source. This needs to happen before we configure UI, because the Source will replay
# Strategies in __init__, and we don't want anyone to be subscribed to their events yet. It will build the
# data model. Once the Source is constructed, we can initialize the rest of the UI, including Qt data models.
# From that moment we can respond to user actions and events from the backend, which the Source + Strategies
# will pass through to Qt data models via Qt-like connect / emit mechanism.
app = Application(sys.argv)

print('UI thread:', threading.get_ident())

settings = app.get_settings()
settings.on(events.AfterSettingChanged, on_setting_changed)

replay_completed = False

#print(QtWidgets.QStyleFactory.keys())
#app.setStyle(QtWidgets.QStyleFactory.create("Windows"))

source: AbstractEventSource
source_type = settings.get('Source.type')
root = Tenant(settings)
if source_type == 'local':
    inner_source = FileEventSource(settings, root, QtFilesystemWatcher())
    source = ThreadedEventSource(inner_source)
elif source_type in ('websocket', 'flowkeeper.org', 'flowkeeper.pro'):
    source = WebsocketEventSource(settings, root)
else:
    raise Exception(f"Source type {source_type} not supported")
source.on(SourceMessagesProcessed, on_messages)

pomodoro_timer = PomodoroTimer(source, QtTimer("Pomodoro Tick"), QtTimer("Pomodoro Transition"))
pomodoro_timer.on("TimerRestComplete", lambda timer, workitem, pomodoro, event: hide_timer_automatically(workitem))
pomodoro_timer.on("TimerWorkStart", lambda timer, event: show_timer_automatically())

loader = QtUiTools.QUiLoader()

# Load main window
file = QtCore.QFile(":/core.ui")
file.open(QtCore.QFile.OpenModeFlag.ReadOnly)
# noinspection PyTypeChecker
window: QtWidgets.QMainWindow = loader.load(file, None)
file.close()

audio = AudioPlayer(window, source, settings, pomodoro_timer)

# Context menus
# noinspection PyTypeChecker
menu_file: QtWidgets.QMenu = window.findChild(QtWidgets.QMenu, "menuFile")
# noinspection PyTypeChecker
menu_workitem: QtWidgets.QMenu = window.findChild(QtWidgets.QMenu, "menuEdit")

# noinspection PyTypeChecker
left_layout: QtWidgets.QVBoxLayout = window.findChild(QtWidgets.QVBoxLayout, "leftTableLayoutInternal")

actions: dict[str, QAction] = {
    'showAll': QAction("Show All", window),
    'showTimerOnly': QAction("Show Timer Only", window),
    'showMainWindow': QAction("Show Main Window", window),
    'settings': QAction("Settings", window),
    'quit': QAction("Quit", window),
}
actions['showAll'].triggered.connect(hide_timer)
actions['showAll'].setIcon(QIcon(":/icons/tool-show-all.svg"))
actions['showTimerOnly'].triggered.connect(show_timer_automatically)
actions['showTimerOnly'].setIcon(QIcon(":/icons/tool-show-timer-only.svg"))
actions['showMainWindow'].triggered.connect(window.show)
actions['quit'].triggered.connect(app.quit)
actions['quit'].setShortcut('Ctrl+Q')
actions['settings'].triggered.connect(lambda: SettingsDialog(settings, {
    'FileEventSource.repair': repair_file_event_source
}).show())

# Backlogs table
backlogs_table: BacklogTableView = BacklogTableView(window, source, actions)
backlogs_table.on(AfterSelectionChanged, lambda event, before, after: workitems_table.upstream_selected(after))
backlogs_table.on(AfterSelectionChanged, lambda event, before, after: progress_widget.update_progress(after) if after is not None else None)
left_layout.addWidget(backlogs_table)

# Users table
users_table: UserTableView = UserTableView(window, source, actions)
users_table.setVisible(False)
left_layout.addWidget(users_table)

# noinspection PyTypeChecker
right_Layout: QtWidgets.QVBoxLayout = window.findChild(QtWidgets.QVBoxLayout, "rightTableLayoutInternal")

# Workitems table
workitems_table: WorkitemTableView = WorkitemTableView(window, source, actions)
source.on(AfterWorkitemComplete, hide_timer)
right_Layout.addWidget(workitems_table)

progress_widget = ProgressWidget(window, source)
right_Layout.addWidget(progress_widget)

# noinspection PyTypeChecker
search_bar: QtWidgets.QHBoxLayout = window.findChild(QtWidgets.QHBoxLayout, "searchBar")
search = SearchBar(window, source, actions, backlogs_table, workitems_table)
search_bar.addWidget(search)

# noinspection PyTypeChecker
root_layout: QtWidgets.QVBoxLayout = window.findChild(QtWidgets.QVBoxLayout, "rootLayoutInternal")
focus = FocusWidget(window, pomodoro_timer, source, settings, actions, QFont())
root_layout.insertWidget(0, focus)

# Layouts
# noinspection PyTypeChecker
main_layout: QtWidgets.QWidget = window.findChild(QtWidgets.QWidget, "mainLayout")
# noinspection PyTypeChecker
header_layout: QtWidgets.QWidget = window.findChild(QtWidgets.QWidget, "headerLayout")
# noinspection PyTypeChecker
left_table_layout: QtWidgets.QWidget = window.findChild(QtWidgets.QWidget, "leftTableLayout")

# Settings
# noinspection PyTypeChecker
settings_action: QtGui.QAction = window.findChild(QtGui.QAction, "actionSettings")
settings_action.triggered.connect(lambda: SettingsDialog(settings, {
    'FileEventSource.repair': repair_file_event_source
}).show())

# Connect menu actions to the toolbar

# noinspection PyTypeChecker
import_action: QtGui.QAction = window.findChild(QtGui.QAction, "actionImport")
import_action.triggered.connect(lambda: ImportWizard(source, window).show())

# noinspection PyTypeChecker
export_action: QtGui.QAction = window.findChild(QtGui.QAction, "actionExport")
export_action.triggered.connect(lambda: ExportWizard(source, window).show())

# noinspection PyTypeChecker
action_backlogs: QtGui.QAction = window.findChild(QtGui.QAction, "actionBacklogs")
action_backlogs.toggled.connect(toggle_backlogs)

# noinspection PyTypeChecker
action_teams: QtGui.QAction = window.findChild(QtGui.QAction, "actionTeams")
action_teams.toggled.connect(toggle_users)

# noinspection PyTypeChecker
action_search: QtGui.QAction = window.findChild(QtGui.QAction, "actionSearch")
action_search.triggered.connect(lambda: search.show())

# noinspection PyTypeChecker
action_about: QtGui.QAction = window.findChild(QtGui.QAction, "actionAbout")
action_about.triggered.connect(lambda: AboutWindow(window).show())

# Main menu
# noinspection PyTypeChecker
main_menu: QtWidgets.QMenuBar = window.findChild(QtWidgets.QMenuBar, "menuBar")
if main_menu is not None:
    show_main_menu = (settings.get('Application.show_main_menu') == 'True')
    main_menu.setVisible(show_main_menu)

# Status bar
# noinspection PyTypeChecker
status: QtWidgets.QStatusBar = window.findChild(QtWidgets.QStatusBar, "statusBar")
if status is not None:
    show_status_bar = (settings.get('Application.show_status_bar') == 'True')
    status.showMessage('Ready')
    status.setVisible(show_status_bar)

# Toolbar
# noinspection PyTypeChecker
toolbar: QtWidgets.QToolBar = window.findChild(QtWidgets.QToolBar, "toolBar")
if toolbar is not None:
    show_toolbar = (settings.get('Application.show_toolbar') == 'True')
    toolbar.setVisible(show_toolbar)

# Tray icon
show_tray_icon = (settings.get('Application.show_tray_icon') == 'True')
tray = TrayIcon(window, pomodoro_timer, source, actions)
tray.setVisible(show_tray_icon)

# Some global variables to support "Next pomodoro" mode
# TODO Empty it if it gets deleted or completed
continue_workitem: Workitem | None = None

# Left toolbar
# noinspection PyTypeChecker
left_toolbar: QtWidgets.QWidget = window.findChild(QtWidgets.QWidget, "left_toolbar")
show_left_toolbar = (settings.get('Application.show_left_toolbar') == 'True')
left_toolbar.setVisible(show_left_toolbar)

# noinspection PyTypeChecker
tool_backlogs: QtWidgets.QToolButton = window.findChild(QtWidgets.QToolButton, "toolBacklogs")
tool_backlogs.setDefaultAction(action_backlogs)

# noinspection PyTypeChecker
tool_teams: QtWidgets.QToolButton = window.findChild(QtWidgets.QToolButton, "toolTeams")
tool_teams.setDefaultAction(action_teams)
action_teams.setEnabled(settings.is_team_supported())
tool_teams.setVisible(settings.is_team_supported())

# noinspection PyTypeChecker
tool_settings: QtWidgets.QToolButton = window.findChild(QtWidgets.QToolButton, "toolSettings")
tool_settings.clicked.connect(lambda: menu_file.exec(
    tool_settings.parentWidget().mapToGlobal(tool_settings.geometry().center())
))

# Splitter
# noinspection PyTypeChecker
splitter: QtWidgets.QSplitter = window.findChild(QtWidgets.QSplitter, "splitter")
splitter.splitterMoved.connect(save_splitter_size)

restore_size()
event_filter = ResizeEventFilter(window, main_layout, settings)
window.installEventFilter(event_filter)
window.move(app.primaryScreen().geometry().center() - window.frameGeometry().center())

window.show()

try:
    source.start()
except Exception as ex:
    app.on_exception(type(ex), ex, ex.__traceback__)

sys.exit(app.exec())
