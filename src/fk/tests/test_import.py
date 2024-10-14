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
from unittest import TestCase

from fk.core.abstract_cryptograph import AbstractCryptograph
from fk.core.abstract_settings import AbstractSettings
from fk.core.ephemeral_event_source import EphemeralEventSource
from fk.core.event_source_factory import get_event_source_factory
from fk.core.fernet_cryptograph import FernetCryptograph
from fk.core.file_event_source import FileEventSource
from fk.core.import_export import import_
from fk.core.mock_settings import MockSettings
from fk.core.tenant import Tenant
from fk.core.user import User
from fk.qt.threaded_event_source import ThreadedEventSource

TEMP_FILENAME = 'src/fk/tests/fixtures/flowkeeper-data-TEMP.txt'
RAND_FILENAME = 'src/fk/tests/fixtures/random.txt'
RAND_DUMP_FILENAME = 'src/fk/tests/fixtures/random-dump.txt'


def _skip_first(dump: str, skip_rows: int) -> str:
    return '\n'.join(dump.split('\n')[skip_rows:])


class TestImport(TestCase):
    settings_temp: AbstractSettings
    cryptograph_temp: AbstractCryptograph
    source_temp: FileEventSource
    data_temp: dict[str, User]

    settings_rand: AbstractSettings
    cryptograph_rand: AbstractCryptograph
    source_rand: FileEventSource
    data_rand: dict[str, User]

    def setUp(self) -> None:
        self.settings_temp = MockSettings(filename=TEMP_FILENAME)
        self.cryptograph_temp = FernetCryptograph(self.settings_temp)
        self.source_temp = FileEventSource[Tenant](self.settings_temp, self.cryptograph_temp, Tenant(self.settings_temp))
        self.source_temp.start()
        self.data_temp = self.source_temp.get_data()

        self.settings_rand = MockSettings(filename=RAND_FILENAME)
        self.cryptograph_rand = FernetCryptograph(self.settings_rand)
        self.source_rand = FileEventSource[Tenant](self.settings_rand, self.cryptograph_rand, Tenant(self.settings_rand))
        self.source_rand.start()
        self.data_rand = self.source_rand.get_data()

        # Needed by smart import
        self._register_source_producers()

    def tearDown(self) -> None:
        os.unlink(TEMP_FILENAME)

    def _register_source_producers(self):
        def ephemeral_source_producer(settings: AbstractSettings, cryptograph: AbstractCryptograph, root: Tenant):
            inner_source = EphemeralEventSource[Tenant](settings, cryptograph, root)
            return ThreadedEventSource(inner_source, self)

        get_event_source_factory().register_producer('ephemeral', ephemeral_source_producer)

    def test_initialize(self):
        self.assertIn('user@local.host', self.data_temp)
        user_temp = self.data_temp['user@local.host']
        self.assertEqual(len(user_temp), 0)

        self.assertIn('user@local.host', self.data_rand)
        user_rand = self.data_rand['user@local.host']
        self.assertEqual(len(user_rand), 22)

        dump = user_rand.dump()
        with open(RAND_DUMP_FILENAME, encoding='UTF-8') as f:
            self.assertEqual(f.read(), dump)

    def _execute_import(self, ignore_errors: bool, merge: bool) -> (int, int):
        total_start = 0

        def set_total_start(total):
            nonlocal total_start
            total_start = total

        total_end = 0

        def set_total_end(total):
            nonlocal total_end
            total_end = total

        def nothing(*args):
            pass

        import_(self.source_temp,
                RAND_FILENAME,
                ignore_errors,
                merge,
                set_total_start,
                nothing,
                set_total_end)

        return total_start, total_end

    def test_import_classic_ok(self):
        total_start, total_end = self._execute_import(False, False)
        self.assertEqual(total_start, total_end)
        self.assertEqual(total_end, 708)    # That's how many strategies are in random.txt

        # We skip the first 7 lines, as the existing user is kept
        dump_imported = _skip_first(self.data_temp['user@local.host'].dump(), 7)
        dump_original = _skip_first(self.data_rand['user@local.host'].dump(), 7)
        self.assertEqual(dump_imported, dump_original)

    def test_import_classic_twice_error(self):
        self._execute_import(False, False)
        self.assertRaises(Exception, self._execute_import, [False, False])

    def test_import_classic_twice_ignore_errors(self):
        self._execute_import(False, False)
        self._execute_import(True, False)

        # We expect to have all the same backlogs and workitems, but random number of pomodoros in them
        user_temp = self.data_temp['user@local.host']
        user_rand = self.data_rand['user@local.host']
        self.assertEqual(len(user_temp), len(user_rand))
        for b in user_temp:
            backlog_temp = user_temp[b]
            backlog_rand = user_rand[b]
            self.assertEqual(backlog_temp.get_name(), backlog_rand.get_name())
            for w in backlog_temp:
                workitem_temp = backlog_temp[w]
                workitem_rand = backlog_rand[w]
                self.assertEqual(workitem_temp.get_name(), workitem_rand.get_name())

    def test_import_smart_ok(self):
        total_start, total_end = self._execute_import(False, True)
        self.assertEqual(total_end, 720)

        # We skip the first 7 lines, as the existing user is kept
        dump_imported = _skip_first(self.data_temp['user@local.host'].dump(), 7)
        dump_original = _skip_first(self.data_rand['user@local.host'].dump(), 7)
        print(dump_imported)
        self.assertEqual(dump_imported, dump_original)

    def test_import_smart_twice_ok(self):
        self._execute_import(False, False)
        self._execute_import(False, True)

        # Unlike "classic" import, the smart one should not create any duplicates
        # TODO

    # TODO: Redo those tests with importing half of random.txt
