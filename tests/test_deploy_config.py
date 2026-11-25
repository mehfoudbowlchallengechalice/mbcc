import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from cloudrun.config_updates import config_updates, DELIMITER

ROOT = Path(__file__).resolve().parents[1]


class DeploymentConfigTests(unittest.TestCase):
    def test_config_is_additive_and_excludes_private_keywords(self):
        updates = config_updates(ROOT / "cloudrun/env.yaml")
        self.assertTrue(updates.startswith("^" + DELIMITER + "^"))
        values = dict(item.split("=", 1) for item in updates.split("^", 2)[2].split(DELIMITER))
        self.assertEqual(values["MBCC_HISTORY_SHEET_ID"], values["MBCC_CHALLENGE_SHEET_ID"])
        self.assertNotIn("MBCC_SUB_KEYWORD", values)
        self.assertNotIn("MBCC_COMBINED_KEYWORD", values)

    def test_yaml_quoted_values_preserve_json_commas_and_equals(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "env.yaml"
            path.write_text('FIRST: "a=b,c"\nSECOND: \'{"scores":"Player\'\'s scores"}\' # comment\n')
            values = dict(item.split("=", 1) for item in config_updates(path).split("^", 2)[2].split(DELIMITER))
            self.assertEqual(values["FIRST"], "a=b,c")
            self.assertEqual(json.loads(values["SECOND"]), {"scores": "Player's scores"})
            path.write_text('MBCC_SUB_KEYWORD: "do-not-echo-this-value"\n')
            with self.assertRaises(ValueError) as caught:
                config_updates(path)
            self.assertNotIn("do-not-echo", str(caught.exception))
            path.write_text('MBCC_CHRISTOPHER_KEYWORD: "do-not-echo-this-value"\n')
            with self.assertRaises(ValueError):
                config_updates(path)

    def test_update_script_does_not_replace_existing_container_variables(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            command_log = folder / "command.json"
            fake = folder / "gcloud"
            fake.write_text('#!/usr/bin/env python3\nimport json, os, sys\n'
                            'with open(os.environ["MBCC_TEST_COMMAND_LOG"], "w") as f: json.dump(sys.argv[1:], f)\n'
                            'raise SystemExit(19)\n')
            fake.chmod(0o755)
            result = subprocess.run(["bash", "cloudrun/update-live-source.sh"], cwd=ROOT,
                                    env=dict(os.environ, PATH=str(folder) + os.pathsep + os.environ["PATH"],
                                             MBCC_TEST_COMMAND_LOG=str(command_log)), capture_output=True, text=True)
            self.assertEqual(result.returncode, 19)
            args = json.loads(command_log.read_text())
            self.assertIn("deploy", args)
            self.assertTrue(any(arg.startswith("--update-env-vars=") for arg in args))
            self.assertFalse(any(arg.startswith(("--env-vars-file=", "--set-env-vars=")) for arg in args))
            self.assertFalse(any("KEYWORD=" in arg for arg in args))


if __name__ == "__main__":
    unittest.main()
