import unittest
from unittest.mock import patch

from amzmail.microsoft_graph import _open_microsoft_login


class MicrosoftBrowserTests(unittest.TestCase):
    def test_prefers_a_new_edge_inprivate_window(self):
        with patch("amzmail.microsoft_graph._edge_executable", return_value=r"C:\\Edge\\msedge.exe"), patch(
            "amzmail.microsoft_graph.subprocess.Popen"
        ) as popen, patch("amzmail.microsoft_graph.webbrowser.open") as default_browser:
            opened_with = _open_microsoft_login("https://login.microsoftonline.com/example")

        self.assertEqual(opened_with, "Edge InPrivate")
        popen.assert_called_once_with(
            [
                r"C:\\Edge\\msedge.exe",
                "--inprivate",
                "--new-window",
                "https://login.microsoftonline.com/example",
            ],
            close_fds=True,
        )
        default_browser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
