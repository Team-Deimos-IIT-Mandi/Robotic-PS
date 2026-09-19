import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_drone import simulation


class TestVisualPlayback(unittest.TestCase):
    def test_slow_steps_draw_between_catch_up_updates_and_record_speed(self):
        clock = [0.0]
        steps = [0]
        rendered_steps = []

        def schedule(*args):
            steps[0] += 1
            clock[0] += 0.08  # A slow step exceeds the display's frame budget.

        def wait_key(delay):
            clock[0] += delay / 1000
            return -1

        with tempfile.TemporaryDirectory() as logs, contextlib.redirect_stdout(io.StringIO()):
            with patch.object(simulation.time, "monotonic", side_effect=lambda: clock[0]), \
                 patch.object(simulation.assignment, "schedule_packages", side_effect=schedule), \
                 patch.object(simulation.cv2, "namedWindow"), \
                 patch.object(simulation.cv2, "imshow", side_effect=lambda *args: rendered_steps.append(steps[0])), \
                 patch.object(simulation.cv2, "waitKey", side_effect=wait_key), \
                 patch.object(simulation.cv2, "destroyAllWindows"):
                simulation.run_demo(duration=1, time_scale=5, log_dir=logs)
            timing = json.loads(next(Path(logs).glob("*.json")).read_text())["timing"]

        self.assertEqual(rendered_steps[0], 0)  # Initial display precedes scheduling.
        self.assertEqual(rendered_steps[-1], 4)
        self.assertTrue(all(b - a <= 1 for a, b in zip(rendered_steps, rendered_steps[1:])))
        self.assertEqual(timing["simulated_seconds"], 1)
        self.assertEqual(timing["requested_speed"], 5)
        self.assertAlmostEqual(timing["actual_speed"], 1 / timing["real_seconds"])
        self.assertFalse(timing["headless"])

    def test_missing_qt_fonts_use_system_directory(self):
        with patch.dict(os.environ, {"QT_QPA_FONTDIR": "/missing/opencv/fonts"}), \
             patch.object(Path, "is_dir", autospec=True,
                          side_effect=lambda path: str(path) == "/usr/share/fonts/truetype/dejavu"):
            simulation.configure_gui_fonts()
            self.assertEqual(os.environ["QT_QPA_FONTDIR"], "/usr/share/fonts/truetype/dejavu")

    def test_existing_qt_font_directory_is_preserved(self):
        with patch.dict(os.environ, {"QT_QPA_FONTDIR": "/custom/fonts"}), \
             patch.object(Path, "is_dir", return_value=True):
            simulation.configure_gui_fonts()
            self.assertEqual(os.environ["QT_QPA_FONTDIR"], "/custom/fonts")


if __name__ == "__main__":
    unittest.main()
