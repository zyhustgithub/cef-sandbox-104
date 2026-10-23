import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import cef_build


class BuildConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.config = cef_build.load_config()

    def test_default_and_supported_profiles_are_explicit(self):
        self.assertEqual("macos12", self.config["default_profile"])
        self.assertEqual({"macos11", "macos12"}, set(self.config["profiles"]))
        self.assertEqual(["arm64", "x64"], self.config["architectures"])
        parsed = cef_build.parser().parse_args(["build"])
        self.assertIsNone(parsed.profile)

    def test_profiles_generate_expected_deployment_targets(self):
        for profile, target in (("macos11", "11.0"), ("macos12", "12.0")):
            for arch in self.config["architectures"]:
                rendered = cef_build.render_gn_args(self.config, profile, arch)
                self.assertIn(f'mac_deployment_target="{target}"', rendered)
                self.assertIn(f'mac_min_system_version="{target}"', rendered)
                self.assertIn('mac_sdk_path="', rendered)
                self.assertIn(f'target_cpu="{arch}"', rendered)

    def test_tracked_configuration_has_no_machine_absolute_path(self):
        raw = cef_build.CONFIG_PATH.read_text()
        self.assertNotIn("/Users/", raw)
        self.assertNotIn("/Applications/", raw)
        parsed = json.loads(raw)
        self.assertEqual("12.3", parsed["sdk_version"])

    def test_obsolete_cleanup_never_selects_reusable_profile_caches(self):
        obsolete = set(cef_build.managed_clean_paths("obsolete"))
        for profile in ("macos11", "macos12"):
            for arch in ("arm64", "x64"):
                self.assertNotIn(cef_build.output_dir(profile, arch), obsolete)

    def test_wrong_tool_architecture_is_rejected(self):
        with tempfile.NamedTemporaryFile() as stream:
            with mock.patch.object(cef_build, "binary_arches", return_value=["x86_64"]):
                with self.assertRaisesRegex(cef_build.BuildError, "expected arm64"):
                    cef_build._check_tool_arch("gn", Path(stream.name), "arm64")

    def test_sdk_version_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            sdk = Path(temporary)
            (sdk / "SDKSettings.plist").write_bytes(
                b'<?xml version="1.0" encoding="UTF-8"?>\n'
                b'<plist version="1.0"><dict><key>Version</key><string>15.0</string></dict></plist>'
            )
            with mock.patch.object(cef_build, "SDK", sdk):
                with self.assertRaisesRegex(cef_build.BuildError, "expected 12.3"):
                    cef_build._check_sdk(self.config)


if __name__ == "__main__":
    unittest.main()
