import copy
import json
import tempfile
import unittest
from embedchain.config import AppConfig
from embedchain import App


class TestYaml(unittest.TestCase):
    def test_sanitize_desanitize(self):
        """
        Test if sanitization and desanitization lead back to the initial result
        """
        
        app = App(AppConfig(collect_metrics=False))

        data = json.loads(app.serialize())
        data_copy = copy.deepcopy(data)

        sanitized_data = app._sanitize_serial(data_copy)

        desanitized_data = app._desanitize_serial(sanitized_data)

        # These keys are ignored in the test.
        IGNORED_KEYS = {"s_id", "u_id"}

        # NOTE: This test is potentially flawed if desanitation produces more keys.
        for key, value in data.items():
            if key in IGNORED_KEYS:
                continue
            self.assertEqual(desanitized_data.get(key), value)

    def test_save_load(self):
        """
        Test that an app state can be saved and loaded.
        """

        app = App(AppConfig(collect_metrics=False))
        original_serial = app.serialize()
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=True) as tmp:
            app.save(tmp.name)
            app.load(tmp.name)
        self.assertEqual(original_serial, app.serialize())
