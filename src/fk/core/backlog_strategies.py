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
from typing import Callable

from fk.core import events
from fk.core.abstract_settings import AbstractSettings
from fk.core.abstract_strategy import AbstractStrategy
from fk.core.backlog import Backlog
from fk.core.strategy_factory import strategy
from fk.core.tenant import Tenant
from fk.core.workitem_strategies import DeleteWorkitemStrategy


# CreateBacklog("123-456-789", "The first backlog")
@strategy
class CreateBacklogStrategy(AbstractStrategy[Tenant]):
    _backlog_uid: str
    _backlog_name: str

    def get_backlog_uid(self) -> str:
        return self._backlog_uid

    def __init__(self,
                 seq: int,
                 when: datetime.datetime,
                 user_identity: str,
                 params: list[str],
                 settings: AbstractSettings,
                 carry: any = None):
        super().__init__(seq, when, user_identity, params, settings, carry)
        self._backlog_uid = params[0]
        self._backlog_name = params[1]

    def execute(self,
                emit: Callable[[str, dict[str, any], any], None],
                data: Tenant) -> (str, any):
        user = data[self._user_identity]
        if self._backlog_uid in user:
            raise Exception(f'Backlog "{self._backlog_uid}" already exists')

        emit(events.BeforeBacklogCreate, {
            'backlog_name': self._backlog_name,
            'backlog_owner': user,
            'backlog_uid': self._backlog_uid,
        }, None)
        backlog = Backlog(self._backlog_name, user, self._backlog_uid, self._when)
        user[self._backlog_uid] = backlog
        backlog.item_updated(self._when)    # This will also update the User
        emit(events.AfterBacklogCreate, {
            'backlog': backlog
        }, None)
        return None, None


# DeleteBacklog("123-456-789", "")
@strategy
class DeleteBacklogStrategy(AbstractStrategy[Tenant]):
    _backlog_uid: str

    def get_backlog_uid(self) -> str:
        return self._backlog_uid

    def __init__(self,
                 seq: int,
                 when: datetime.datetime,
                 user_identity: str,
                 params: list[str],
                 settings: AbstractSettings,
                 carry: any = None):
        super().__init__(seq, when, user_identity, params, settings, carry)
        self._backlog_uid = params[0]

    def execute(self,
                emit: Callable[[str, dict[str, any], any], None],
                data: Tenant) -> (str, any):
        user = data[self._user_identity]
        if self._backlog_uid not in user:
            raise Exception(f'Backlog "{self._backlog_uid}" not found')
        backlog = user[self._backlog_uid]

        params = {
            'backlog': backlog
        }
        emit(events.BeforeBacklogDelete, params, None)

        # First delete all workitems recursively
        for workitem in list(backlog.values()):
            self.execute_another(emit,
                                 data,
                                 DeleteWorkitemStrategy,
                                 [workitem.get_uid()])
        backlog.item_updated(self._when)    # This will also update the User

        # Now we can delete the backlog itself
        del user[self._backlog_uid]

        emit(events.AfterBacklogDelete, params, None)
        return None, None


# RenameBacklog("123-456-789", "New name")
@strategy
class RenameBacklogStrategy(AbstractStrategy['Tenant']):
    _backlog_uid: str
    _backlog_new_name: str

    def get_backlog_uid(self) -> str:
        return self._backlog_uid

    def __init__(self,
                 seq: int,
                 when: datetime.datetime,
                 user_identity: str,
                 params: list[str],
                 settings: AbstractSettings,
                 carry: any = None):
        super().__init__(seq, when, user_identity, params, settings, carry)
        self._backlog_uid = params[0]
        self._backlog_new_name = params[1]

    def execute(self,
                emit: Callable[[str, dict[str, any], any], None],
                data: Tenant) -> (str, any):
        user = data[self._user_identity]
        if self._backlog_uid not in user:
            raise Exception(f'Backlog "{self._backlog_uid}" not found')
        backlog = user[self._backlog_uid]

        params = {
            'backlog': backlog,
            'old_name': backlog.get_name(),
            'new_name': self._backlog_new_name,
        }
        emit(events.BeforeBacklogRename, params, None)
        backlog.set_name(self._backlog_new_name)
        backlog.item_updated(self._when)
        emit(events.AfterBacklogRename, params, None)
        return None, None
