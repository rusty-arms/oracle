"""End-to-end runs of the launcher against tests/fake_dolphin.py."""

import contextlib
import csv
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock

from oracle import compare, replay

HERE = os.path.dirname(os.path.abspath(__file__))
WATCH = (
    "disc_id 0x80000000 u32\n"
    "presses 0x80400000 u32\n"
    "stick_sum 0x80400004 f32\n"
    "chained 0x80400008 -> 0x4 u32\n"
)


@unittest.skipIf(os.name == "nt", "the fake Dolphin wrapper is a shell script")
class ReplayTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = self.temp.name
        self.dolphin = self.path("dolphin")
        with open(self.dolphin, "w") as handle:
            handle.write(f'#!/bin/sh\nexec "{sys.executable}" "{HERE}/fake_dolphin.py" "$@"\n')
        os.chmod(self.dolphin, os.stat(self.dolphin).st_mode | stat.S_IXUSR)
        self.disc = self.write("disc.iso", "not a real disc")
        self.watch = self.write("test.watch", WATCH)

    def tearDown(self):
        self.temp.cleanup()

    def path(self, name):
        return os.path.join(self.dir, name)

    def write(self, name, text):
        with open(self.path(name), "w") as handle:
            handle.write(text)
        return self.path(name)

    def run_replay(self, script, *extra, mode=""):
        inputs = self.write("test.inputs", script)
        args = [
            inputs,
            "--out",
            self.path("out"),
            "--watch",
            self.watch,
            "--dolphin",
            self.dolphin,
            "--disc",
            self.disc,
            "--timeout",
            "30",
            *extra,
        ]
        out, err = io.StringIO(), io.StringIO()
        env = mock.patch.dict(os.environ, {"FAKE_DOLPHIN_MODE": mode})
        with env, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = replay.main(args)
        return code, out.getvalue(), err.getvalue()

    def trace(self):
        with open(self.path("out/trace.csv"), newline="") as handle:
            return list(csv.reader(handle))

    def run_json(self):
        with open(self.path("out/run.json")) as handle:
            return json.load(handle)

    def test_trace_follows_inputs(self):
        code, _out, err = self.run_replay("frames 6\n1-2 A\n3 StickX=0.5\n")
        self.assertEqual(code, 0, err)
        rows = self.trace()
        self.assertEqual(rows[0], ["frame", "disc_id", "presses", "stick_sum", "chained"])
        disc_id = str(int.from_bytes(b"TEST", "big"))
        # Row k reflects the inputs of frames 0 to k - 1.
        self.assertEqual([r[2] for r in rows[1:]], ["0", "0", "1", "2", "2", "2"])
        self.assertEqual([r[3] for r in rows[1:]], ["0.0", "0.0", "0.0", "0.0", "0.5", "0.5"])
        self.assertTrue(all(r[1] == disc_id and r[4] == "7" for r in rows[1:]))
        record = self.run_json()
        self.assertIsNone(record["error"])
        self.assertEqual(record["host"]["inputs"]["file"], "test.inputs")
        self.assertIn("Dolphin.Core.CPUThread=False", record["host"]["settings"])
        self.assertFalse(os.path.exists(self.path("out/result.json")))

    def test_every_and_screenshots(self):
        code, _, err = self.run_replay(
            "frames 10\nevery 3\nshot 0 9\n", "--shots", self.path("shots")
        )
        self.assertEqual(code, 0, err)
        self.assertEqual([r[0] for r in self.trace()[1:]], ["0", "3", "6", "9"])
        self.assertEqual(
            sorted(os.listdir(self.path("shots"))), ["frame_000000.png", "frame_000009.png"]
        )
        shot = self.run_json()["shots"]["9"]
        self.assertEqual((shot["width"], shot["height"]), (4, 2))

    def test_repeat_identical(self):
        code, out, err = self.run_replay(
            "frames 5\n0-4 A\nshot 2\n", "--shots", self.path("shots"), "--repeat", "2"
        )
        self.assertEqual(code, 0, err)
        self.assertIn("2 runs identical", out)
        self.assertTrue(self.run_json()["repeat"]["identical"])

    def test_repeat_catches_nondeterminism(self):
        code, out, _ = self.run_replay("frames 40\n0-39 A\n", "--repeat", "3", mode="random")
        self.assertEqual(code, 1)
        self.assertIn("DIFFER", out)
        self.assertFalse(self.run_json()["repeat"]["identical"])

    def test_dolphin_crash_is_reported(self):
        code, _, err = self.run_replay("frames 50\n", mode="crash")
        self.assertEqual(code, 1)
        self.assertIn("exited with code 3", err)
        self.assertIn("Last lines of", err)

    def test_crash_names_the_signal_and_shows_the_log(self):
        code, _, err = self.run_replay("frames 50\n", mode="trap")
        self.assertEqual(code, 1)
        self.assertIn("crashed (SIGILL, exit code -4)", err)
        self.assertIn("fake dolphin: about to trap", err)

    def test_timeout(self):
        code, _, err = self.run_replay("frames 5\n", "--timeout", "1", mode="hang")
        self.assertEqual(code, 1)
        self.assertIn("did not finish", err)

    def test_refuses_to_overwrite(self):
        os.makedirs(self.path("out"))
        self.write("out/trace.csv", "frame\n")
        code, _, err = self.run_replay("frames 5\n")
        self.assertEqual(code, 1)
        self.assertIn("already has files", err)
        with open(self.path("out/trace.csv")) as handle:
            self.assertEqual(handle.read(), "frame\n")

    def test_shots_need_a_folder(self):
        code, _, err = self.run_replay("frames 5\nshot 1\n")
        self.assertEqual(code, 1)
        self.assertIn("--shots", err)

    def test_dry_run_launches_nothing(self):
        code, out, _ = self.run_replay("frames 5\n", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("--script", out)
        self.assertFalse(os.path.exists(self.path("out")))


class CompareTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, text):
        path = os.path.join(self.temp.name, name)
        with open(path, "w") as handle:
            handle.write(text)
        return path

    def test_reports_first_divergence(self):
        a = self.write("a.csv", "frame,x,y,z\n0,1,0.5,\n1,2,0.5,nan\n2,3,0.75,4\n")
        b = self.write("b.csv", "frame,x,y,z\n0,1,0.5,\n1,2,0.5,nan\n2,4,0.8,\n")
        mismatches, notes = compare.compare(a, b, {})
        self.assertEqual(
            mismatches, [("x", 2, "3", "4"), ("y", 2, "0.75", "0.8"), ("z", 2, "4", "")]
        )
        mismatches, _ = compare.compare(a, b, {"x": 1, "y": 0.1})
        self.assertEqual([m[0] for m in mismatches], ["z"])
        self.assertEqual(notes, [])

    def test_column_and_frame_checks(self):
        a = self.write("a.csv", "frame,x\n0,1\n1,1\n")
        b = self.write("b.csv", "frame,y\n0,1\n")
        c = self.write("c.csv", "frame,x\n0,1\n")
        with self.assertRaisesRegex(ValueError, "columns differ"):
            compare.compare(a, b, {})
        with self.assertRaisesRegex(ValueError, "unknown column"):
            compare.compare(a, c, {"nope": 1})
        mismatches, notes = compare.compare(a, c, {})
        self.assertEqual(mismatches, [])
        self.assertIn("1 frame(s)", notes[0])


if __name__ == "__main__":
    unittest.main()
