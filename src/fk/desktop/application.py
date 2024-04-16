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

import datetime
import random
import sys
import traceback
import urllib
import webbrowser

from PySide6.QtCore import QFile
from PySide6.QtGui import QFont, QFontMetrics, QGradient
from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog, QCheckBox
from semantic_version import Version

from fk.core import events
from fk.core.abstract_event_emitter import AbstractEventEmitter
from fk.core.abstract_event_source import AbstractEventSource
from fk.core.abstract_settings import AbstractSettings
from fk.core.ephemeral_event_source import EphemeralEventSource
from fk.core.event_source_factory import EventSourceFactory
from fk.core.event_source_holder import EventSourceHolder, AfterSourceChanged
from fk.core.events import AfterSettingsChanged
from fk.core.file_event_source import FileEventSource
from fk.desktop.export_wizard import ExportWizard
from fk.desktop.import_wizard import ImportWizard
from fk.desktop.settings import SettingsDialog
from fk.qt.about_window import AboutWindow
from fk.qt.actions import Actions
from fk.qt.app_version import get_latest_version, get_current_version
from fk.qt.heartbeat import Heartbeat
from fk.qt.oauth import authenticate, AuthenticationRecord
from fk.qt.qt_filesystem_watcher import QtFilesystemWatcher
from fk.qt.qt_invoker import invoke_in_main_thread
from fk.qt.qt_settings import QtSettings
from fk.qt.qt_timer import QtTimer
from fk.qt.threaded_event_source import ThreadedEventSource
from fk.qt.tutorial_window import TutorialWindow
from fk.qt.websocket_event_source import WebsocketEventSource

AfterFontsChanged = "AfterFontsChanged"
NewReleaseAvailable = "NewReleaseAvailable"


class Application(QApplication, AbstractEventEmitter):
    _settings: AbstractSettings
    _font_main: QFont
    _font_header: QFont
    _row_height: int
    _source_holder: EventSourceHolder | None
    _heartbeat: Heartbeat
    _version_timer: QtTimer
    _tutorial_timer: QtTimer

    def __init__(self, args: [str]):
        super().__init__(args,
                         allowed_events=[AfterFontsChanged, NewReleaseAvailable],
                         callback_invoker=invoke_in_main_thread)
        def local_source_producer(settings, root):
            inner_source = FileEventSource(settings, root, QtFilesystemWatcher())
            return ThreadedEventSource(inner_source)
        EventSourceFactory.get_instance().register_producer('local', local_source_producer)

        def ephemeral_source_producer(settings, root):
            inner_source = EphemeralEventSource(settings, root)
            return ThreadedEventSource(inner_source)
        EventSourceFactory.get_instance().register_producer('ephemeral', ephemeral_source_producer)

        def websocket_source_producer(settings, root):
            return WebsocketEventSource(settings, self, root)
        EventSourceFactory.get_instance().register_producer('websocket', websocket_source_producer)
        EventSourceFactory.get_instance().register_producer('flowkeeper.org', websocket_source_producer)
        EventSourceFactory.get_instance().register_producer('flowkeeper.pro', websocket_source_producer)

        self._heartbeat = None
        sys.excepthook = self.on_exception

        # It's important to initialize settings after the QApplication
        # has been constructed, as it uses default QFont and other
        # OS-specific values
        if self.is_e2e_mode():
            self._settings = QtSettings('desktop-client-e2e')
            self._settings.reset_to_defaults()
            from fk.e2e.backlog_e2e import BacklogE2eTest
            test = BacklogE2eTest(self)
            test.start()
        else:
            self._settings = QtSettings()
        self._settings.on(AfterSettingsChanged, self._on_setting_changed)

        # Quit app on close
        quit_on_close = (self._settings.get('Application.quit_on_close') == 'True')
        self.setQuitOnLastWindowClosed(quit_on_close)

        self.set_theme(self._settings.get('Application.theme'))

        # Fonts, styles, etc.
        self._initialize_fonts()
        self._row_height = self._auto_resize()

        # Version checks
        self._version_timer = QtTimer('Version checker')
        self.on(NewReleaseAvailable, self.on_new_version)
        if self._settings.get('Application.check_updates') == 'True':
            self._version_timer.schedule(5000, self.check_version, None, True)

        # Tutorial
        self._tutorial_timer = QtTimer('Tutorial')
        if self._settings.get('Application.show_tutorial') == 'True':
            self._tutorial_timer.schedule(1000, self.show_tutorial, None, True)

        self._source_holder = EventSourceHolder(self._settings)
        self._source_holder.on(AfterSourceChanged, self._on_source_changed)
        self._source_holder.recreate_source()

    def _on_source_changed(self, event: str, source: AbstractEventSource):
        if self._heartbeat is not None:
            self._heartbeat.stop()
        if source.can_connect():
            self._heartbeat = Heartbeat(self._source_holder, 3000, 500)
            self._heartbeat.on(events.WentOffline, self._on_went_offline)
            self._heartbeat.on(events.WentOnline, self._on_went_online)

    def is_e2e_mode(self):
        print('E2e mode:', 'e2e' in self.arguments())
        return 'e2e' in self.arguments()

    def _on_went_offline(self, event, after: int, last_received: datetime.datetime) -> None:
        # TODO -- lock the UI
        print(f'WARNING - We detected that the client went offline after {after}ms')
        print(f'          Last time we heard from the server was {last_received}')

    def _on_went_online(self, event, ping: int) -> None:
        # TODO -- unlock the UI
        print(f'We are (back) online with the roundtrip delay of {ping}ms')

    def get_settings(self):
        return self._settings

    def get_source_holder(self):
        return self._source_holder

    # noinspection PyUnresolvedReferences
    def set_theme(self, theme: str):
        # Apply CSS
        import fk.desktop.theme_common
        if theme == 'light':
            import fk.desktop.theme_light
        elif theme == 'dark':
            import fk.desktop.theme_dark
        elif theme == 'mixed':
            import fk.desktop.theme_mixed

        # TODO: Can't change this on the fly
        f = QFile(":/style.qss")
        f.open(QFile.OpenModeFlag.ReadOnly)
        self.setStyleSheet(f.readAll().toStdString())
        f.close()

        print('Stylesheet loaded')

    def _initialize_fonts(self) -> (QFont, QFont):
        self._font_header = QFont(self._settings.get('Application.font_header_family'),
                                  int(self._settings.get('Application.font_header_size')))
        if self._font_header is None:
            self._font_header = QFont()
            self._font_header.setPointSize(int(self._font_header.pointSize() * 24.0 / 9))
    
        self._font_main = QFont(self._settings.get('Application.font_main_family'),
                                int(self._settings.get('Application.font_main_size')))
        if self._font_main is None:
            self._font_main = QFont()

        self.setFont(self._font_main)
        self._emit(AfterFontsChanged, {
            'main_font': self._font_main,
            'header_font': self._font_header,
            'application': self
        })

    def _auto_resize(self) -> int:
        h: int = QFontMetrics(self._font_main).height() + 8
        # users_table.verticalHeader().setDefaultSectionSize(h)
        # backlogs_table.verticalHeader().setDefaultSectionSize(h)
        # workitems_table.verticalHeader().setDefaultSectionSize(h)
        # Save it to Settings, so that we can use this value when
        # calculating display hints for the Pomodoro Delegate.
        # As of now, this requires app restart to apply.
        self._settings.set({'Application.table_row_height': str(h)})
        return h

    def restart_warning(self) -> None:
        if QMessageBox().warning(self.activeWindow(),
                                 "Restart required",
                                 f"To apply new settings Flowkeeper needs a restart. "
                                 f"Please run it again after pressing OK. We apologize for this inconvenience.",
                                 QMessageBox.StandardButton.Ok) == QMessageBox.StandardButton.Ok:
            self.exit(0)

    def on_exception(self, exc_type, exc_value, exc_trace):
        to_log = "".join(traceback.format_exception(exc_type, exc_value, exc_trace))
        print("Exception", to_log)
        if (QMessageBox().critical(self.activeWindow(),
                                   "Unexpected error",
                                   f"{exc_type.__name__}: {exc_value}\nWe will appreciate it if you click Open to report it on GitHub.",
                                   QMessageBox.StandardButton.Ok,
                                   QMessageBox.StandardButton.Open)
                == QMessageBox.StandardButton.Open):
            params = urllib.parse.urlencode({
                'labels': 'exception',
                'title': f'Unhandled {exc_type.__name__}',
                'body': f'PLEASE PROVIDE SOME DETAILS HERE.\nREVIEW THE BELOW PART FOR SENSITIVE DATA.\n\n```\n{to_log}```'
            })
            webbrowser.open(f"https://github.com/flowkeeper-org/fk-desktop/issues/new?{params}")

    def get_main_font(self):
        return self._font_main

    def get_header_font(self):
        return self._font_header

    def get_row_height(self):
        return self._row_height

    def _on_setting_changed(self, event: str, old_values: dict[str, str], new_values: dict[str, str]):
        # print(f'Setting {name} changed from {old_value} to {new_value}')
        show_restart_warning = False
        for name in new_values.keys():
            if name == 'Source.type' or name.startswith('WebsocketEventSource.') or name.startswith('FileEventSource.'):
                self._source_holder.recreate_source()
            elif name == 'Application.quit_on_close':
                self.setQuitOnLastWindowClosed(new_values[name] == 'True')
            elif 'Application.font_' in name:
                self._initialize_fonts()
            elif name == 'Application.theme':
                show_restart_warning = True
                # app.set_theme(new_value)
            elif name == 'Application.check_updates':
                if new_values[name] == 'True':
                    self._version_timer.schedule(1000, self.check_version, None, True)

        if show_restart_warning:
            self.restart_warning()

        # TODO: Subscribe to sound settings
        # TODO: Subscribe the sources to the settings they use
        # TODO: Reload the app when the source changes
        # TODO: Recreate the source

    def show_settings_dialog(self):
        SettingsDialog(self._settings, {
            'FileEventSource.repair': self.repair_file_event_source,
            'Application.eyecandy_gradient_generate': self.generate_gradient,
            'WebsocketEventSource.authenticate': self.sign_in,
        }).show()

    def repair_file_event_source(self, _):
        if QMessageBox().warning(self.activeWindow(),
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
                                 QMessageBox.StandardButton.Ok,
                                 QMessageBox.StandardButton.Cancel) \
                == QMessageBox.StandardButton.Ok:
            cast: FileEventSource = self._source_holder.get_source()
            log = cast.repair()
            QInputDialog.getMultiLineText(None,
                                          "Repair completed",
                                          "Please save this log for future reference. "
                                          "You can find all new items by searching (CTRL+F) for [Repaired] string.\n"
                                          "Flowkeeper restart is required to reload the changes.",
                                          "\n".join(log))

    def generate_gradient(self, _):
        preset_names = [preset.name for preset in QGradient.Preset]
        if 'NumPresets' in preset_names:
            preset_names.remove('NumPresets')
        chosen = random.choice(preset_names)
        self._settings.set({'Application.eyecandy_gradient': chosen})

    def sign_in(self, _):
        def check_server(auth: AuthenticationRecord):
            pass

        def save(auth: AuthenticationRecord):
            self._settings.set({
                'WebsocketEventSource.auth_type': 'google',
                'WebsocketEventSource.username': auth.email,
                'WebsocketEventSource.refresh_token': auth.refresh_token,
            })

        if QMessageBox().warning(self.activeWindow(),
                                 "Known bug",
                                 f"After you login the app may crash. It will remember your credentials, so you just "
                                 f"need to restart it. This is due to a bug in Qt6 OAuth module, for which we are "
                                 f"implementing a workaround. In the meantime we apologize for the inconvenience.",
                                 QMessageBox.StandardButton.Ok,
                                 QMessageBox.StandardButton.Cancel
                                 ) == QMessageBox.StandardButton.Ok:
            authenticate(self, save)

    @staticmethod
    def define_actions(actions: Actions):
        actions.add('application.settings', "Settings", 'F10', None, Application.show_settings_dialog)
        actions.add('application.quit', "Quit", 'Ctrl+Q', None, Application.quit_local)
        actions.add('application.import', "Import...", 'Ctrl+I', None, Application.show_import_wizard)
        actions.add('application.export', "Export...", 'Ctrl+E', None, Application.show_export_wizard)
        actions.add('application.tutorial', "Tutorial", '', None, Application.show_tutorial)
        actions.add('application.about', "About", '', None, Application.show_about)

    def quit_local(self):
        Application.quit()

    def show_import_wizard(self):
        ImportWizard(self._source_holder.get_source(),
                     self.activeWindow()).show()

    def show_export_wizard(self):
        ExportWizard(self._source_holder.get_source(),
                     self.activeWindow()).show()

    def show_about(self):
        AboutWindow(self.activeWindow()).show()

    def get_heartbeat(self) -> Heartbeat:
        return self._heartbeat

    def check_version(self, event: str) -> None:
        def on_version(latest: Version, changelog: str):
            if latest is not None:
                current: Version = get_current_version()
                if latest > current:
                    self._emit(NewReleaseAvailable, {
                        'current': current,
                        'latest': latest,
                        'changelog': changelog,
                    })
                else:
                    print(f'We are on the latest Flowkeeper version already (current is {current}, latest is {latest})')
            else:
                print("Warning: Couldn't get the latest release info from GitHub")
        print('Will check GitHub releases for the latest version')
        get_latest_version(self, on_version)

    def show_tutorial(self, event: str = None) -> None:
        TutorialWindow(self.activeWindow(), self._settings).show()

    def on_new_version(self, event: str, current: Version, latest: Version, changelog: str) -> None:
        ignored = self._settings.get('Application.ignored_updates').split(',')
        latest_str = str(latest)
        if latest_str in ignored:
            print(f'An updated version {latest_str} is available, but the user chose to ignore it')
            return
        msg = QMessageBox(QMessageBox.Icon.Information,
                          "An update is available",
                          f"You currently use Flowkeeper {current}. A newer version {latest_str} is now available at "
                          f"flowkeeper.org. Would you like to download it? The changes include:\n\n"
                          f"{changelog}",
                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                          self.activeWindow())
        check = QCheckBox("Ignore this update", msg)
        msg.setCheckBox(check)
        res = msg.exec()
        if check.isChecked():
            ignored.append(latest_str)
            self._settings.set({'Application.ignored_updates': ','.join(ignored)})
        if res == QMessageBox.StandardButton.Yes:
            webbrowser.open(f"https://flowkeeper.org/#download")
