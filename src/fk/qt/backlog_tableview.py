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

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtWidgets import QWidget, QHeaderView, QMenu, QMessageBox, QInputDialog

from fk.core import events
from fk.core.abstract_data_item import generate_unique_name, generate_uid
from fk.core.backlog import Backlog
from fk.core.backlog_strategies import CreateBacklogStrategy, DeleteBacklogStrategy
from fk.core.event_source_holder import EventSourceHolder, AfterSourceChanged
from fk.core.events import AfterBacklogCreate, SourceMessagesProcessed
from fk.core.user import User
from fk.desktop.application import Application
from fk.qt.abstract_tableview import AbstractTableView, AfterSelectionChanged
from fk.qt.actions import Actions
from fk.qt.backlog_model import BacklogModel


class BacklogTableView(AbstractTableView[User, Backlog]):
    _application: Application

    def __init__(self,
                 parent: QWidget,
                 application: Application,
                 source_holder: EventSourceHolder,
                 actions: Actions):
        super().__init__(parent,
                         source_holder,
                         BacklogModel(parent, source_holder),
                         'backlogs_table',
                         actions,
                         'Loading, please wait...',
                         'No data or connection error.',
                         "You haven't got any backlogs yet.\nCreate the first one by pressing Ctrl+N.",
                         0)
        self._init_menu(actions)
        source_holder.on(AfterSourceChanged, self._on_source_changed)
        self._on_source_changed("", source_holder.get_source())
        self.on(AfterSelectionChanged, lambda event, before, after: self._source_holder.set_config_parameters({
            'Application.last_selected_backlog': after.get_uid() if after is not None else ''
        }))
        self._application = application

        heartbeat = application.get_heartbeat()
        if heartbeat is not None:
            heartbeat.on(events.WentOffline, self._lock_ui)
            heartbeat.on(events.WentOnline, self._unlock_ui)

    def _lock_ui(self, event, after: int, last_received: datetime.datetime) -> None:
        self.update_actions(self.get_current())

    def _unlock_ui(self, event, ping: int) -> None:
        self.update_actions(self.get_current())

    def _on_source_changed(self, event, source):
        super()._on_source_changed(event, source)
        self.selectionModel().clear()
        self.upstream_selected(None)
        source.on(AfterBacklogCreate, self._on_new_backlog)
        source.on(SourceMessagesProcessed, self._on_messages)

    def _init_menu(self, actions: Actions):
        menu: QMenu = QMenu()
        menu.addActions([
            actions['backlogs_table.newBacklog'],
            actions['backlogs_table.renameBacklog'],
            actions['backlogs_table.deleteBacklog'],
            # Uncomment to troubleshoot
            # actions['backlogs_table.dumpBacklog'],
        ])
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda p: menu.exec(self.mapToGlobal(p)))

    @staticmethod
    def define_actions(actions: Actions):
        actions.add('backlogs_table.newBacklog', "New Backlog", 'Ctrl+N', None, BacklogTableView.create_backlog)
        actions.add('backlogs_table.renameBacklog', "Rename Backlog", 'Ctrl+R', None, BacklogTableView.rename_selected_backlog)
        actions.add('backlogs_table.deleteBacklog', "Delete Backlog", 'F8', None, BacklogTableView.delete_selected_backlog)
        actions.add('backlogs_table.dumpBacklog', "Dump (DEBUG)", 'Ctrl+D', None, BacklogTableView.dump_selected_backlog)

    def upstream_selected(self, user: User) -> None:
        super().upstream_selected(user)
        self._actions['backlogs_table.newBacklog'].setEnabled(user is not None)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

    def update_actions(self, selected: Backlog) -> None:
        print(f'Backlog table - update_actions({selected})')
        # It can be None for example if we don't have any backlogs left, or if
        # we haven't loaded any yet. BacklogModel supports None.
        is_backlog_selected = selected is not None

        heartbeat = self._application.get_heartbeat()
        is_online = heartbeat is None or heartbeat.is_online()
        print(f' - Online: {is_online}')
        print(f' - Backlog selected: {is_backlog_selected}')
        print(f' - Heartbeat: {heartbeat}')
        self._actions['backlogs_table.newBacklog'].setEnabled(is_online)
        self._actions['backlogs_table.renameBacklog'].setEnabled(is_backlog_selected and is_online)
        self._actions['backlogs_table.deleteBacklog'].setEnabled(is_backlog_selected and is_online)
        self._actions['backlogs_table.dumpBacklog'].setEnabled(is_backlog_selected)
        # TODO: Double-clicking the backlog name doesn't use those

    # Actions

    def create_backlog(self) -> None:
        prefix: str = datetime.datetime.today().strftime('%Y-%m-%d, %A')   # Locale-formatted
        new_name = generate_unique_name(prefix, self._source_holder.get_data().get_current_user().names())
        self._source_holder.execute(CreateBacklogStrategy, [generate_uid(), new_name], carry='edit')

        # A simpler, more efficient, but a bit uglier single-step alternative
        # new_name = generate_unique_name(prefix, self._source.get_data().get_current_user().names())
        # (new_name, ok) = QInputDialog.getText(self,
        #                                       "New backlog",
        #                                       "Provide a name for the new backlog",
        #                                       text=new_name)
        # if ok:
        #     self._source.execute(CreateBacklogStrategy, [generate_uid(), new_name])

    def _on_new_backlog(self, backlog: Backlog, carry: any = None, **kwargs):
        if carry == 'edit':
            index: QModelIndex = self.select(backlog)
            self.edit(index)

    def rename_selected_backlog(self) -> None:
        index: QModelIndex = self.currentIndex()
        if index is None:
            raise Exception("Trying to rename a backlog, while there's none selected")
        self.edit(index)

    def delete_selected_backlog(self) -> None:
        selected: Backlog = self.get_current()
        if selected is None:
            raise Exception("Trying to delete a backlog, while there's none selected")
        if QMessageBox().warning(self,
                                 "Confirmation",
                                 f"Are you sure you want to delete backlog '{selected.get_name()}'?",
                                 QMessageBox.StandardButton.Ok,
                                 QMessageBox.StandardButton.Cancel
                                 ) == QMessageBox.StandardButton.Ok:
            self._source_holder.execute(DeleteBacklogStrategy, [selected.get_uid()])

    def dump_selected_backlog(self) -> None:
        selected: Backlog = self.get_current()
        if selected is None:
            raise Exception("Trying to dump a backlog, while there's none selected")
        QInputDialog.getMultiLineText(None,
                                      "Backlog dump",
                                      "Technical information for debug / development purposes",
                                      selected.dump())

    def _on_messages(self, event):
        user = self._source_holder.get_data().get_current_user()
        self.upstream_selected(user)
        last_selected_oid = self._source_holder.get_settings().get('Application.last_selected_backlog')
        if user is not None and last_selected_oid != '' and last_selected_oid in user:
            self.select(user[last_selected_oid])
