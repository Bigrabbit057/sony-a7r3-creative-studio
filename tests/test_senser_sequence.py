"""Exercise the real transport packer at its 16-bit boundary, without USB."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'vendor'))
from pmca.usb.sony import SonySenserDevice

class EchoDriver:
    def __init__(self, mismatch=False):
        self.sequences = []
        self.mismatch = mismatch
    def getId(self): return 0x054c, 0x0336
    def reset(self): pass
    def write(self, raw):
        h = SonySenserDevice.SenserPacketHeader.unpack(raw)
        self.sequences.append(h.sequence)
        self.reply = SonySenserDevice.SenserPacketHeader.pack(size=0, pFunc=h.pFunc,
            sequence=(h.sequence + int(self.mismatch)) & 0xffff,
            version=0, miconType=0, offsetType=0, response=0)
    def read(self, size): return self.reply

class Sequence(unittest.TestCase):
    def test_wrap_and_initial_sequence(self):
        driver = EchoDriver(); camera = SonySenserDevice(driver)
        camera.sendSenserPacket(1, b'x')
        self.assertEqual(driver.sequences, [1])
        camera._sequence = 65534
        for _ in range(4): self.assertEqual(camera.sendSenserPacket(1, b'x'), (0, b''))
        self.assertEqual(driver.sequences, [1, 65534, 65535, 0, 1])
    def test_wrong_response_still_rejected(self):
        camera = SonySenserDevice(EchoDriver(mismatch=True))
        camera._sequence = 65535
        with self.assertRaisesRegex(Exception, 'Wrong senser sequence'):
            camera.sendSenserPacket(1, b'x')
        self.assertEqual(camera._sequence, 65535)

if __name__ == '__main__': unittest.main()
