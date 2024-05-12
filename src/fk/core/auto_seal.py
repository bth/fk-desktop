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
from typing import Iterable, Callable, Type

from fk.core.abstract_strategy import AbstractStrategy
from fk.core.pomodoro_strategies import StartRestStrategy, FinishPomodoroInternalStrategy
from fk.core.workitem import Workitem


def auto_seal(workitems: Iterable[Workitem],
              delta: float,
              executor: Callable[[Type[AbstractStrategy], list[str], bool, datetime.datetime], None]) -> None:
    # If there are pomodoros which should have been completed X seconds ago, but are not,
    # then void them automatically.
    for workitem in workitems:
        for pomodoro in workitem.values():
            if pomodoro.is_running():
                remaining_time = pomodoro.total_remaining_time()
                if remaining_time + delta < 0:
                    # This pomodoro has finished, i.e. work + rest happened in the past
                    # This used to produce a warning, but since version 0.3.1 this is a normal
                    # thing, as all pomodoros are completed implic
                    executor(FinishPomodoroInternalStrategy,
                             [workitem.get_uid()],
                             False,
                             pomodoro.planned_end_of_rest())
                    print(f'Info - automatically finished a pomodoro on '
                          f'{workitem.get_name()} '
                          f'(transition happened when the client was offline)')
                elif pomodoro.is_working():
                    remaining_time = pomodoro.remaining_time_in_current_state()
                    if remaining_time + delta < 0:
                        # This pomodoro should've transitioned to "rest" in the past, but it hasn't
                        # quite expired yet
                        executor(StartRestStrategy,
                                 [workitem.get_uid(), str(pomodoro.get_rest_duration())],
                                 False,
                                 pomodoro.planned_end_of_work())
                        # TODO: This leaves the timer in "Rest: 00:00" state and nothing gets scheduled
                        print(f'Warning - automatically started rest on '
                              f'{workitem.get_name()} '
                              f'(transition happened when the client was offline)')
