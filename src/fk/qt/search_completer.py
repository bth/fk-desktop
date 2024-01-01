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

from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import QModelIndex, QItemSelectionModel
from PySide6.QtGui import QStandardItemModel, QStandardItem, QAction

from fk.core.abstract_event_source import AbstractEventSource
from fk.core.backlog import Backlog
from fk.core.user import User
from fk.core.workitem import Workitem
from fk.qt.abstract_tableview import AbstractTableView, AfterSelectionChanged
from fk.qt.invoker import invoke_in_main_thread


class SearchBar(QtWidgets.QLineEdit):
    _source: AbstractEventSource
    _backlogs_table: AbstractTableView[User, Backlog]
    _workitems_table: AbstractTableView[Backlog, Workitem]
    _show_completed: bool
    _actions: dict[str, QAction]

    def __init__(self,
                 parent: QtWidgets.QWidget,
                 source: AbstractEventSource,
                 actions: dict[str, QAction],
                 backlogs_table: AbstractTableView[User, Backlog],
                 workitems_table: AbstractTableView[Backlog, Workitem]):
        super().__init__(parent)
        self.setObjectName("search")
        self._source = source
        self._backlogs_table = backlogs_table
        self._workitems_table = workitems_table
        self._show_completed = True
        self.hide()
        self.setPlaceholderText('Search')
        self.installEventFilter(self)
        self._actions = actions
        actions['showCompleted'].toggled.connect(self.show_completed)

    def _select(self, index: QModelIndex):
        workitem: Workitem = index.data(500)
        backlog: Backlog = workitem.get_parent()
        self._backlogs_table.select(backlog)
        # Queue the second selection step, as AfterSelectionChanged
        # will go through Qt postEvent
        invoke_in_main_thread(lambda w: self._workitems_table.select(w),
                              None,
                              w=workitem)
        self.hide()

    def show(self) -> None:
        completer = QtWidgets.QCompleter()
        completer.activated[QModelIndex].connect(lambda index: self._select(index))
        completer.setFilterMode(QtGui.Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(QtGui.Qt.CaseSensitivity.CaseInsensitive)

        model = QStandardItemModel()
        for wi in self._source.workitems():
            if not self._show_completed and wi.is_sealed():
                continue
            item = QStandardItem()
            item.setText(wi.get_name())
            item.setData(wi, 500)
            model.appendRow(item)
        completer.setModel(model)

        self.setCompleter(completer)
        self.setFocus()
        if not self.isVisible():
            self.setText("")
        super().show()

    def eventFilter(self, widget: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if widget == self and event.type() == QtCore.QEvent.Type.KeyPress and isinstance(event, QtGui.QKeyEvent):
            if event.matches(QtGui.QKeySequence.StandardKey.Cancel):
                self.hide()
        return False

    def show_completed(self, show: bool) -> None:
        self._show_completed = show
