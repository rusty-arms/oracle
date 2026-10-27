import struct
import unittest
import zlib

from oracle import inputs, png, watch


class InputsTest(unittest.TestCase):
    def test_example_syntax(self):
        plan = inputs.parse(
            "frames 10  # total\nevery 2\nshot 0 9\nshot 9\n"
            "2 Start\n4-6 A StickX=-0.5 TriggerRight=1\n"
        )
        self.assertEqual((plan.frames, plan.every, plan.shots), (10, 2, (0, 9)))
        self.assertFalse(any(plan.pad_at(0)[b] for b in inputs.BUTTONS))
        self.assertTrue(plan.pad_at(2)["Start"])
        self.assertFalse(plan.pad_at(3)["Start"])
        self.assertEqual(plan.pad_at(5)["StickX"], -0.5)
        self.assertTrue(plan.pad_at(6)["A"])
        self.assertFalse(plan.pad_at(7)["A"])

    def test_every_pad_is_complete(self):
        plan = inputs.parse("frames 3\n1 A\n")
        for frame in range(3):
            self.assertEqual(
                set(plan.pad_at(frame)), set(inputs.BUTTONS + inputs.STICKS + inputs.TRIGGERS)
            )

    def test_errors(self):
        bad = {
            "": "missing 'frames",
            "frames 5\nframes 6": "twice",
            "frames 0": "at least 1",
            "frames 5\n1-3 A\n3 B": "overlaps",
            "frames 5\n4-2 A": "backwards",
            "frames 5\n5 A": "past the last frame",
            "frames 5\nshot 5": "past the last frame",
            "frames 5\n1 Jump": "unknown button",
            "frames 5\n1 Spin=1": "unknown axis",
            "frames 5\n1 StickX=2": "outside",
            "frames 5\n1 TriggerLeft=-0.1": "outside",
            "frames 5\n1 StickX=x": "needs a number",
            "frames 5\nhold A": "expected a frame",
        }
        for text, message in bad.items():
            with self.subTest(text=text), self.assertRaisesRegex(inputs.InputError, message):
                inputs.parse(text)


class WatchTest(unittest.TestCase):
    def test_parse_and_read(self):
        watches = watch.parse(
            "plain 0x80000010 u16\nchain 0x80000020 -> 0x8 -> 4 f32  # two hops\n"
        )
        self.assertEqual(watches[0], watch.Watch("plain", 0x80000010, (), "u16"))
        self.assertEqual(watches[1].offsets, (8, 4))
        memory = {
            ("u16", 0x80000010): 5,
            ("u32", 0x80000020): 0x80001000,
            ("u32", 0x80001008): 0x80002000,
            ("f32", 0x80002004): 1.5,
        }
        reader = lambda kind, addr: memory[(kind, addr)]
        self.assertEqual([w.read(reader) for w in watches], [5, 1.5])

    def test_bad_pointer_reads_empty(self):
        (chain,) = watch.parse("chain 0x80000020 -> 0x8 u32")
        self.assertIsNone(chain.read(lambda kind, addr: 0))
        self.assertIsNone(chain.read(lambda kind, addr: 0x817FFFFE))

    def test_errors(self):
        bad = {
            "a 0x80000000": "expected 'name address type'",
            "a 0x80000000 u24": "unknown type",
            "frame 0x80000000 u8": "usable column name",
            "a-b 0x80000000 u8": "usable column name",
            "a 0x80000000 u8\na 0x80000001 u8": "twice",
            "a 0x7FFFFFFF u8": "outside main memory",
            "a 0x817FFFFE u32": "outside main memory",
            "a 0x80000000 -> u32": "pointer steps",
            "a 0x80000000 => 4 u32": "expected '->'",
            "a zz u8": "not a number",
        }
        for text, message in bad.items():
            with self.subTest(text=text), self.assertRaisesRegex(watch.WatchError, message):
                watch.parse(text)

    def test_values_round_trip(self):
        for value in (None, 0, 4294967295, -3, 0.1, -0.0, float("inf"), 1e-40):
            text = watch.format_value(value)
            self.assertEqual(watch.parse_value(text), value)
            self.assertNotIn(",", text)


class PngTest(unittest.TestCase):
    def _decode(self, blob):
        self.assertEqual(blob[:8], b"\x89PNG\r\n\x1a\n")
        chunks, pos = {}, 8
        while pos < len(blob):
            (length,) = struct.unpack(">I", blob[pos : pos + 4])
            kind = blob[pos + 4 : pos + 8]
            data = blob[pos + 8 : pos + 8 + length]
            (crc,) = struct.unpack(">I", blob[pos + 8 + length : pos + 12 + length])
            self.assertEqual(crc, zlib.crc32(kind + data))
            chunks[kind] = data
            pos += 12 + length
        return chunks

    def test_rgb_and_rgba(self):
        for channels, colour in ((3, 2), (4, 6)):
            data = bytes(range(3 * 2 * channels))
            chunks = self._decode(png.encode(3, 2, data))
            width, height, depth, kind = struct.unpack(">IIBB", chunks[b"IHDR"][:10])
            self.assertEqual((width, height, depth, kind), (3, 2, 8, colour))
            raw = zlib.decompress(chunks[b"IDAT"])
            stride = 3 * channels
            self.assertEqual(raw, b"\x00" + data[:stride] + b"\x00" + data[stride:])

    def test_rejects_wrong_size(self):
        with self.assertRaises(ValueError):
            png.encode(3, 2, bytes(7))


if __name__ == "__main__":
    unittest.main()
