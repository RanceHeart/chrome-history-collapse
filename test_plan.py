import datetime
import sqlite3
import unittest

from plan import EPOCH_US, make_plan, page_key


class PlanTests(unittest.TestCase):
    def test_scoping(self):
        self.assertIsNone(page_key('https://other.example/read/1#2', 'example.org'))
        self.assertIsNone(page_key('https://example.org/app#/different-content', 'example.org'))
        self.assertNotEqual(page_key('https://example.org/read/a#2', 'example.org')[0], page_key('https://example.org/read/b#2', 'example.org')[0])
        self.assertIsNone(page_key('https://example.org/list?page=2&page=3', 'example.org', 'page'))
        self.assertEqual(page_key('https://example.org/list?category=a&page=2', 'example.org', 'page'), ('https://example.org/list?category=a', 2))

    def test_first_page_and_cross_day_visits(self):
        db = sqlite3.connect(':memory:')
        db.executescript('CREATE TABLE urls(id INTEGER, url TEXT); CREATE TABLE visits(url INTEGER, visit_time INTEGER);')
        for ident, suffix in enumerate(('', '#1', '#2', '#3'), 1):
            db.execute('INSERT INTO urls VALUES (?, ?)', (ident, 'https://example.org/read/demo' + suffix))
            for day in (5, 6):
                timestamp = int(datetime.datetime(2025, 1, day, 12).timestamp() * 1000000) + EPOCH_US
                db.execute('INSERT INTO visits VALUES (?, ?)', (ident, timestamp))
        plan = make_plan(db, 'example.org', minimum=3)
        self.assertEqual(plan['groups'][0]['keep'], 'https://example.org/read/demo#1')
        self.assertEqual(len(plan['groups'][0]['remove']), 3)
        self.assertEqual(len(plan['items']), 6)
        self.assertTrue(all(len(item['timestamps']) == 1 for item in plan['items']))
        self.assertEqual(make_plan(db, 'example.org', minimum=4)['groups'], [])


if __name__ == '__main__':
    unittest.main()
