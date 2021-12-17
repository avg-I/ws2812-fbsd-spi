
from fcntl import ioctl
from mmap import mmap
from random import randint, sample
from struct import calcsize, pack
from time import sleep

class spi_grb:
    # dir  grp num len
    # IN    'S'  3 4
    SPIGENIOC_SET_CLOCK_SPEED = 0x80045303

    # dir  grp num len
    # IN    'S'  1 sizeof(size_t) * 2
    SPIGENIOC_TRANSFER_MMAPPED = 0x80005301 + (calcsize("NN") << 16)

    # Need 3MHz for proper pulse timings
    SPI_SPEED = 3000000

    # A controller may hold MOSI line in high state while it's idle,
    # so always send some zero-s first, so that the start of real
    # data can be properly detected by the LEDs.
    LED_INDEX_OFFSET = 1

    # Send a sufficiently long zero pulse at the end of transfer.
    TRAILING_ZERO_COUNT = 3

    # Zero is a short high pulse followed by a long low pulse
    ZERO = 0b100
    # One is a long high pulse followed by a short low pulse
    ONE = 0b110

    def __init__(self, led_count, spi_dev="/dev/spigen0.0"):
        # Three bytes per LED: green, red, blue.
        # Each bit of GRB is sent over SPI using 3 bits.
        # We need to keep LED data in a separate array, because spigen(4)
        # treats each transfer as read+write and overwrites the mmap-ed buffer.
        self._dev_size = 3 * 3 * (led_count +
                self.LED_INDEX_OFFSET + self.TRAILING_ZERO_COUNT)
        self._dev = open(spi_dev, "r+b")
        self._dev_mem = mmap(self._dev.fileno(), self._dev_size)
        self._led_data = bytearray(self._dev_size)

        req = pack("I", self.SPI_SPEED) # uint32_t
        ioctl(
                self._dev.fileno(),
                self.SPIGENIOC_SET_CLOCK_SPEED,
                req
        )

    def refresh(self):
        # struct spigen_transfer_mmapped {
        #   size_t stm_command_length; /* at offset 0 in mmap(2) area */
        #   size_t stm_data_length;    /* at offset stm_command_length */
        # };
        req = pack("NN", 0, self._dev_size)
        self._dev_mem[:] = self._led_data
        ioctl(
                self._dev.fileno(),
                self.SPIGENIOC_TRANSFER_MMAPPED,
                req
        )

    @classmethod
    def _spi_encode(cls, byte):
        res = 0
        for b in range(8):
            if (byte & (1 << b)):
                code = cls.ONE
            else:
                code = cls.ZERO
            res = res | (code << (3 * b))
        return res

    def set_rgb(self, index, rgb):
        red, green, blue = rgb.to_bytes(3, byteorder='big')
        self.set_rgb(index, red, green, blue)

    def set_rgb(self, index, red, green, blue):
        # rgb -> grb
        colors = [green, red, blue]
        # encode for SPI transfer
        colors = map(lambda color: self._spi_encode(color), colors)

        dev_index = index * 9
        for i, color in enumerate(colors):
            idx = dev_index + 3 * (self.LED_INDEX_OFFSET + i)
            self._led_data[idx : idx + 3] = color.to_bytes(3, byteorder='big')


MAX_BRIGHTNESS = 40 # R + G + B maximum

def test_patterns(led):
    led.set_rgb(0, MAX_BRIGHTNESS, 0, 0)
    led.refresh()
    sleep(1)

    led.set_rgb(0, 0, MAX_BRIGHTNESS, 0)
    led.refresh()
    sleep(1)

    led.set_rgb(0, 0, 0, MAX_BRIGHTNESS)
    led.refresh()
    sleep(1)

    led.set_rgb(
            0,
            MAX_BRIGHTNESS // 3,
            MAX_BRIGHTNESS // 3,
            MAX_BRIGHTNESS // 3
    )
    led.refresh()
    sleep(1.5)

    led.set_rgb(0, 0, 0, 0)
    led.refresh()
    sleep(0.5)

    for i in range(MAX_BRIGHTNESS + 1):
        led.set_rgb(0, MAX_BRIGHTNESS - i, i, 0)
        led.refresh()
        sleep(0.4)
        led.set_rgb(0, 0, 0, 0)
        led.refresh()
        sleep(0.1)
    for i in range(MAX_BRIGHTNESS + 1):
        led.set_rgb(0, 0, MAX_BRIGHTNESS - i, i)
        led.refresh()
        sleep(0.4)
        led.set_rgb(0, 0, 0, 0)
        led.refresh()
        sleep(0.1)

    led.set_rgb(0, 0, 0, 0)
    led.refresh()
    sleep(0.5)

    while True:
        x = randint(0, MAX_BRIGHTNESS)
        y = MAX_BRIGHTNESS - x
        r, g, b = sample([x, y, 0], 3)
        led.set_rgb(0, r, g, b)
        led.refresh()
        sleep(1)

if __name__ == '__main__':
    led = spi_grb(1)
    try:
        test_patterns(led)
    except KeyboardInterrupt:
        pass
    finally:
        led.set_rgb(0, 0, 0, 0)
        led.refresh()

