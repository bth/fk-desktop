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

from PySide6.QtCore import QEvent, QPoint
from PySide6.QtGui import Qt, QMouseEvent, QAction
from PySide6.QtWidgets import QWidget, QToolBar, QMenu, QStyleFactory, QApplication

from fk.core.events import AfterSettingsChanged
from fk.qt.actions import Actions
from fk.qt.info_overlay import show_info_overlay


class ConfigurableToolBar(QToolBar):
    _actions: Actions

    def __init__(self, parent: QWidget, actions: Actions):
        super().__init__(parent)
        self._actions = actions
        settings = actions.get_settings()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setStyle(QStyleFactory.create("windows"))
        self.setVisible(settings.get('Application.show_toolbar') == 'True')
        settings.on(AfterSettingsChanged, self._on_setting_changed)

    def _on_setting_changed(self, event: str, old_values: dict[str, str], new_values: dict[str, str]):
        if 'Application.show_toolbar' in new_values:
            self.setVisible(new_values['Application.show_toolbar'] == 'True')

    def _hide(self, pos: QPoint):
        self._actions.get_settings().set({
            'Application.show_toolbar': 'False'
        })
        show_info_overlay("You can re-enable toolbar in Settings > Appearance",
                          self.mapToGlobal(pos),
                          ":/icons/info.png",
                          5)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.RightButton:
            act = QAction(self)
            act.setText("Hide toolbar")
            act.triggered.connect(lambda: self._hide(event.pos()))
            context_menu = QMenu(self)
            context_menu.setStyle(QApplication.style())
            context_menu.addAction(act)
            context_menu.exec(
                self.parentWidget().mapToGlobal(event.pos()))
