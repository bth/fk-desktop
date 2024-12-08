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
import os
import sys

from PySide6.QtWidgets import QWizardPage, QLabel, QVBoxLayout, QWizard, QWidget, QRadioButton, QMainWindow

from fk.desktop.application import Application
#from fk.desktop.desktop import MainWindow
from fk.qt.actions import Actions
from fk.qt.focus_widget import FocusWidget
from fk.qt.qt_settings import QtSettings


class PageConfigFocus(QWizardPage):
    def __init__(self, application: Application, actions: Actions):
        super().__init__()
        layout_v = QVBoxLayout()

        label = QLabel("This wizard will help you configure Flowkeeper after installation. First choose "
                       "how would you like to see the Focus bar:")
        label.setWordWrap(True)
        layout_v.addWidget(label)

        option_minimal = QRadioButton("Minimalistic", self)
        option_minimal.setChecked(True)
        layout_v.addWidget(option_minimal)

        focus_minimal = FocusWidget(self,
                                    application,
                                    None,
                                    application.get_source_holder(),
                                    application.get_settings(),
                                    actions,
                                    'minimal')
        layout_v.addWidget(focus_minimal)

        option_classic = QRadioButton("Classic", self)
        option_classic.setChecked(False)
        layout_v.addWidget(option_classic)

        focus_classic = FocusWidget(self,
                                    application,
                                    None,
                                    application.get_source_holder(),
                                    application.get_settings(),
                                    actions,
                                    'classic')
        layout_v.addWidget(focus_classic)

        label = QLabel("You can change this in Settings > Appearance")
        label.setWordWrap(True)
        layout_v.addWidget(label)

        self.setLayout(layout_v)


class PageConfigIcons(QWizardPage):
    def __init__(self):
        super().__init__()
        layout_v = QVBoxLayout()
        label = QLabel("Now choose how you prefer your icons:")
        label.setWordWrap(True)
        layout_v.addWidget(label)

        option_monochrome = QRadioButton("Monochrome", self)
        option_monochrome.setChecked(True)
        layout_v.addWidget(option_monochrome)

        option_classic = QRadioButton("Classic", self)
        option_classic.setChecked(False)
        layout_v.addWidget(option_classic)

        self.setLayout(layout_v)


class ConfigWizard(QWizard):
    page_focus: PageConfigFocus
    page_icons: PageConfigIcons

    def __init__(self, application: Application, actions: Actions, parent: QWidget | None):
        super().__init__(parent)
        self._settings = application.get_settings()
        self.setWindowTitle("First-time configuration")
        self.page_focus = PageConfigFocus(application, actions)
        self.page_icons = PageConfigIcons()
        self.addPage(self.page_focus)
        self.addPage(self.page_icons)

        # Account for a Qt bug which shrinks dialogs opened on non-primary displays
        self.setMinimumSize(500, 350)
        if os.name == 'nt':
            # AeroStyle is default on Windows 11, but it looks all white (another Qt bug?) The Classic style looks fine.
            self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)


if __name__ == '__main__':
    app = Application([])
    window = QMainWindow()
    actions = Actions(window, app.get_settings())
    FocusWidget.define_actions(actions)
    MainWindow.define_actions(actions)
    settings = QtSettings()
    wizard = ConfigWizard(app, actions, None)
    wizard.show()
    sys.exit(app.exec())
