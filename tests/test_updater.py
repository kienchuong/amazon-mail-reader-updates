from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from amzmail.updater import _build_update_script


@unittest.skipUnless(sys.platform == "win32", "The updater is Windows-only.")
class UpdaterScriptTests(unittest.TestCase):
    def run_script(self, script: str, root: Path) -> subprocess.CompletedProcess[str]:
        script_path = root / "apply-update.ps1"
        script_path.write_text(script, encoding="utf-8-sig")
        return subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
            ],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )

    @staticmethod
    def make_package(path: Path, launcher_name: str = "run_app.bat") -> None:
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(launcher_name, "@exit /b 0\r\n")
            archive.writestr("new-version.txt", "installed")

    def test_unrelated_process_command_line_does_not_block_update(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            program = root / "amazon-mail-reader-0.6.8-win64"
            program.mkdir()
            (program / "old-version.txt").write_text("old", encoding="utf-8")
            package = root / "amazon-mail-reader-0.6.9-win64.zip"
            self.make_package(package)

            holders = [
                subprocess.Popen(
                    [sys.executable, "-c", "import time; time.sleep(10)", str(program)],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                for _ in range(2)
            ]
            started = time.monotonic()
            try:
                result = self.run_script(_build_update_script(package, program, "run_app.bat", 999999), root)
            finally:
                for process in holders:
                    process.terminate()
                    process.wait(timeout=5)

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertLess(time.monotonic() - started, 5)
            self.assertTrue((program / "new-version.txt").exists())
            self.assertFalse(package.exists())
            backups = list(root.glob(program.name + ".backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertTrue((backups[0] / "old-version.txt").exists())

    def test_failed_extraction_restores_old_program_and_keeps_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            program = root / "amazon-mail-reader-0.6.8-win64"
            program.mkdir()
            marker = program / "old-version.txt"
            marker.write_text("old", encoding="utf-8")
            package = root / "broken.zip"
            package.write_text("not a zip archive", encoding="utf-8")

            result = self.run_script(_build_update_script(package, program, "missing.bat", 999999), root)

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(marker.read_text(encoding="utf-8"), "old")
            self.assertTrue(package.exists())
            self.assertTrue((root / "update-error.txt").exists())


if __name__ == "__main__":
    unittest.main()
