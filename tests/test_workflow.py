import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import monitor


class StockTransitionTests(unittest.TestCase):
    def test_first_stock_then_unknown_does_not_spam_and_confirmed_out_rearms(self):
        shop = {'id': 'lyon_partdieu', 'name': 'Pharmacie test', 'mode': 'product', 'url': 'https://example.org/exact-product', 'region': 'Lyon / métropole'}
        phase = ['in_stock']
        alert_batches = []

        def fake_fetch(item):
            return {**item, 'checked_at': monitor.utcnow(), 'status': phase[0], 'reason': 'Résultat simulé'}

        def fake_notify(shops, settings=None, test=False):
            alert_batches.append([s['id'] for s in shops])
            return {'sent': ['ntfy'], 'errors': []}

        with TemporaryDirectory() as folder:
            f = Path(folder)
            (f / 'shops.json').write_text(json.dumps([shop]))
            with patch.object(monitor, 'SHOPS', f/'shops.json'), patch.object(monitor, 'DATA', f/'status.json'), patch.object(monitor, 'CONFIG', f/'config.json'), patch.object(monitor, 'fetch_shop', side_effect=fake_fetch), patch.object(monitor, 'configured_channels', return_value=['ntfy']), patch.object(monitor, 'notify', side_effect=fake_notify):
                monitor.check_all()
                self.assertEqual(len(alert_batches), 1)
                phase[0] = 'unknown'
                monitor.check_all()
                phase[0] = 'in_stock'
                monitor.check_all()
                self.assertEqual(len(alert_batches), 1)
                phase[0] = 'out_of_stock'
                monitor.check_all()
                phase[0] = 'in_stock'
                monitor.check_all()
                self.assertEqual(len(alert_batches), 2)

    def test_failed_delivery_is_retried(self):
        shop = {'id':'test', 'name':'Test', 'mode':'product','url':'https://example.org','region':'France'}
        batches = []
        with TemporaryDirectory() as folder:
            f = Path(folder)
            (f/'shops.json').write_text(json.dumps([shop]))
            with patch.object(monitor, 'SHOPS', f/'shops.json'), patch.object(monitor, 'DATA', f/'status.json'), patch.object(monitor, 'CONFIG', f/'config.json'), patch.object(monitor, 'fetch_shop', return_value={**shop,'status':'in_stock','reason':'test','checked_at':monitor.utcnow()}), patch.object(monitor, 'configured_channels', return_value=['ntfy']), patch.object(monitor, 'notify', side_effect=[{'sent':[],'errors':['ntfy: ConnectionError']},{'sent':['ntfy'],'errors':[]}] ) as send:
                monitor.check_all()
                monitor.check_all()
                self.assertEqual(send.call_count, 2)


if __name__ == '__main__':
    unittest.main()
