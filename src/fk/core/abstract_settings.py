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

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Callable

from fk.core import events
from fk.core.abstract_event_emitter import AbstractEventEmitter


def _always_show(_) -> bool:
    return True


def _never_show(_) -> bool:
    return False


def _show_for_gradient_eyecandy(values: dict[str, str]) -> bool:
    return values['Application.eyecandy_type'] == 'gradient'


def _show_for_image_eyecandy(values: dict[str, str]) -> bool:
    return values['Application.eyecandy_type'] == 'image'


def _show_for_file_source(values: dict[str, str]) -> bool:
    return values['Source.type'] == 'local'


def _show_for_websocket_source(values: dict[str, str]) -> bool:
    return values['Source.type'] in ('websocket', 'flowkeeper.org', 'flowkeeper.pro')


def _show_for_custom_websocket_source(values: dict[str, str]) -> bool:
    return values['Source.type'] == 'websocket'


def _show_for_basic_auth(values: dict[str, str]) -> bool:
    return _show_for_websocket_source(values) and values['WebsocketEventSource.auth_type'] == 'basic'


def _show_for_google_auth(values: dict[str, str]) -> bool:
    return _show_for_websocket_source(values) and values['WebsocketEventSource.auth_type'] == 'google'


def _show_if_play_alarm_enabled(values: dict[str, str]) -> bool:
    return values['Application.play_alarm_sound'] == 'True'


def _show_if_play_rest_enabled(values: dict[str, str]) -> bool:
    return values['Application.play_rest_sound'] == 'True'


def _show_if_play_tick_enabled(values: dict[str, str]) -> bool:
    return values['Application.play_tick_sound'] == 'True'


class AbstractSettings(AbstractEventEmitter, ABC):
    # Category -> [(id, type, display, default, options)]
    _definitions: dict[str, list[tuple[str, str, str, str, list[any], Callable[[dict[str, str]], bool]]]]
    _defaults: dict[str, str]
    _callback_invoker: Callable

    def __init__(self,
                 default_font_family: str,
                 default_font_size: int,
                 callback_invoker: Callable,
                 buttons_mapping: dict[str, Callable[[dict[str, str]], None]] | None = None):
        AbstractEventEmitter.__init__(self, [
            events.BeforeSettingChanged,
            events.AfterSettingChanged,
        ], callback_invoker)

        self._callback_invoker = callback_invoker

        self._definitions = {
            'General': [
                ('Pomodoro.default_work_duration', 'int', 'Default work duration (s)', str(25 * 60), [1, 120 * 60], _always_show),
                ('Pomodoro.default_rest_duration', 'int', 'Default rest duration (s)', str(5 * 60), [1, 60 * 60], _always_show),
                ('Pomodoro.auto_seal_after', 'int', 'Auto-seal items after (s)', str(5), [1, 120], _always_show),
                ('', 'separator', '', '', [], _always_show),
                ('Application.shortcuts', 'shortcuts', 'Shortcuts', '{}', [], _always_show),
            ],
            'Connection': [
                ('Source.fullname', 'str', 'User full name', 'Local User', [], _never_show),
                ('Source.type', 'choice', 'Data source', 'local', [
                    "local:Local file (offline)",
                    "flowkeeper.org:Flowkeeper.org",
                    "flowkeeper.pro:Flowkeeper.pro",
                    "websocket:Self-hosted server",
                ], _always_show),
                ('', 'separator', '', '', [], _always_show),
                ('FileEventSource.filename', 'file', 'Data file', str(Path.home() / 'flowkeeper-data.txt'), ['*.txt'], _show_for_file_source),
                ('FileEventSource.watch_changes', 'bool', 'Watch changes', 'True', ['*.wav;*.mp3'], _show_for_file_source),
                ('FileEventSource.repair', 'button', 'Repair', '', [], _show_for_file_source),
                ('WebsocketEventSource.auth_type', 'choice', 'Authentication', 'basic', [
                    "basic:Simple username and password",
                    "google:Google account",
                ], _show_for_websocket_source),
                ('WebsocketEventSource.url', 'str', 'Server URL', 'wss://localhost:8443', [], _show_for_custom_websocket_source),
                ('WebsocketEventSource.username', 'email', 'User email', 'user@local.host', [], _show_for_basic_auth),
                ('WebsocketEventSource.password', 'secret', 'Password', '', [], _show_for_basic_auth),
                ('WebsocketEventSource.token', 'secret', 'OAuth Token', '', [], _never_show),
                ('WebsocketEventSource.authenticate', 'button', 'Sign in', '', [], _show_for_google_auth),
                ('WebsocketEventSource.ignore_errors', 'bool', 'Ignore errors', 'False', [], _show_for_websocket_source),
                ('WebsocketEventSource.ignore_invalid_sequence', 'bool', 'Ignore invalid sequences', 'False', [], _show_for_websocket_source),
            ],
            'Appearance': [
                ('Application.timer_ui_mode', 'choice', 'When timer starts', 'focus', [
                    "keep:Keep application window as-is",
                    "focus:Switch to focus mode",
                    "minimize:Hide application window",
                ], _always_show),
                ('Application.theme', 'choice', 'Theme', 'mixed', [
                    "light:Light",
                    "dark:Dark",
                    "mixed:Mixed",
                ], _always_show),
                ('Application.quit_on_close', 'bool', 'Quit on close', 'False', [], _always_show),
                ('Application.show_main_menu', 'bool', 'Show main menu', 'False', [], _always_show),
                ('Application.show_status_bar', 'bool', 'Show status bar', 'False', [], _always_show),
                ('Application.show_toolbar', 'bool', 'Show top toolbar', 'False', [], _always_show),
                ('Application.show_left_toolbar', 'bool', 'Show left toolbar', 'True', [], _always_show),
                ('Application.show_tray_icon', 'bool', 'Show tray icon', 'True', [], _always_show),
                ('Application.eyecandy_type', 'choice', 'Header background', 'default', [
                    "default:Default",
                    "image:Image",
                    "gradient:Gradient",
                ], _always_show),
                ('Application.eyecandy_image', 'file', 'Background image', '', ['*.png;*.jpg'], _show_for_image_eyecandy),
                ('Application.eyecandy_gradient_generate', 'button', 'Surprise me!', '', [], _show_for_gradient_eyecandy),
                ('Application.eyecandy_gradient', 'str', 'Background gradient', 'SugarLollipop', [], _never_show),
                ('Application.window_width', 'int', 'Main window width', '700', [5, 5000], _never_show),
                ('Application.window_height', 'int', 'Main window height', '500', [5, 5000], _never_show),
                ('Application.window_splitter_width', 'int', 'Splitter width', '200', [0, 5000], _never_show),
                ('Application.backlogs_visible', 'bool', 'Show backlogs', 'True', [], _never_show),
                ('Application.users_visible', 'bool', 'Show users', 'False', [], _never_show),
                ('Application.last_selected_backlog', 'str', 'Last selected backlog', '', [], _never_show),
                ('Application.table_row_height', 'int', 'Table row height', '30', [0, 5000], _never_show),
            ],
            'Fonts': [
                ('Application.font_main_family', 'font', 'Main font family', default_font_family, [], _always_show),
                ('Application.font_main_size', 'int', 'Main font size', str(default_font_size), [3, 48], _always_show),
                ('Application.font_header_family', 'font', 'Title font family', default_font_family, [], _always_show),
                ('Application.font_header_size', 'int', 'Title font size', str(int(24.0 / 9 * default_font_size)), [3, 72], _always_show),
            ],
            'Audio': [
                ('Application.play_alarm_sound', 'bool', 'Play alarm sound', 'True', [], _always_show),
                ('Application.alarm_sound_file', 'file', 'Alarm sound file', 'qrc:/sound/bell.wav', ['*.wav;*.mp3'], _show_if_play_alarm_enabled),
                ('Application.alarm_sound_volume', 'int', 'Alarm volume %', '100', [0, 100], _show_if_play_alarm_enabled),
                ('separator', 'separator', '', '', [], _always_show),
                ('Application.play_rest_sound', 'bool', 'Play "rest" sound', 'False', [], _always_show),
                ('Application.rest_sound_file', 'file', '"Rest" sound file', '', ['*.wav;*.mp3'], _show_if_play_rest_enabled),
                ('Application.rest_sound_volume', 'int', 'Rest volume %', '66', [0, 100], _show_if_play_rest_enabled),
                ('separator', 'separator', '', '', [], _always_show),
                ('Application.play_tick_sound', 'bool', 'Play ticking sound', 'True', [], _always_show),
                ('Application.tick_sound_file', 'file', 'Ticking sound file', 'qrc:/sound/tick.wav', ['*.wav;*.mp3'], _show_if_play_tick_enabled),
                ('Application.tick_sound_volume', 'int', 'Ticking volume %', '50', [0, 100], _show_if_play_tick_enabled),
            ],
        }

        self._defaults = dict()
        for lst in self._definitions.values():
            for s in lst:
                self._defaults[s[0]] = s[3]
        # print('Filled defaults', self._defaults)

    def invoke_callback(self, fn: Callable, **kwargs) -> None:
        self._callback_invoker(fn, **kwargs)

    @abstractmethod
    def set(self, name: str, value: str) -> str:
        pass

    @abstractmethod
    def get(self, name: str) -> str:
        # Note that there's no default value -- we can get it from self._defaults
        pass

    @abstractmethod
    def location(self) -> str:
        pass

    def get_username(self) -> str:
        if self.get('Source.type') == 'local':
            return 'user@local.host'
        else:
            return self.get('WebsocketEventSource.username')

    def is_team_supported(self) -> bool:
        return self.get('Source.type') != 'local'

    def get_fullname(self) -> str:
        return self.get('Source.fullname')

    def get_work_duration(self) -> int:
        return int(self.get('Pomodoro.default_work_duration'))

    def get_rest_duration(self) -> int:
        return int(self.get('Pomodoro.default_rest_duration'))

    def get_categories(self) -> Iterable[str]:
        return self._definitions.keys()

    def get_settings(self, category) -> Iterable[tuple[str, str, str, str, list[any], Callable[[dict[str, str]], bool]]]:
        return [
            (
                option_id,
                option_type,
                option_display,
                self.get(option_id) if option_type != 'separator' else '',
                option_options,
                option_visible
            )
            for option_id, option_type, option_display, option_default, option_options, option_visible
            in self._definitions[category]
        ]

    def reset_to_defaults(self) -> None:
        for lst in self._definitions.values():
            for option_id, option_type, option_display, option_default, option_options, option_visible in lst:
                self.set(option_id, option_default)
