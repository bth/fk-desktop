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

from typing import Callable, Self, TypeVar, Generic

from fk.core.abstract_event_source import AbstractEventSource
from fk.core.abstract_settings import AbstractSettings

TRoot = TypeVar('TRoot')


class EventSourceFactory(Generic[TRoot]):
    _source_producers: dict[str, Callable[[AbstractSettings, object], AbstractEventSource[TRoot]]]
    _instance: Self = None

    def __init__(self):
        self._source_producers = dict()

    def is_valid(self, name: str) -> bool:
        return name in self._source_producers

    def get_producer(self, name: str) -> Callable[[AbstractSettings, object], AbstractEventSource[TRoot]]:
        return self._source_producers.get(name)

    def register_producer(self,
                          name: str,
                          producer: Callable[[AbstractSettings, object], AbstractEventSource[TRoot]]) -> None:
        self._source_producers[name] = producer


def get_event_source_factory() -> EventSourceFactory[TRoot]:
    if EventSourceFactory._instance is None:
        EventSourceFactory._instance = EventSourceFactory[TRoot]()
    return EventSourceFactory._instance
