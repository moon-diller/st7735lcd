from typing import Optional, Union, Tuple, List, Any, ByteString
import struct
import RPi.GPIO as GPIO


class LcdWrapper:
    const = lambda x: x
    _NOP = const(0x00)
    _SWRESET = const(0x01)
    _RDDID = const(0x04)
    _RDDST = const(0x09)

    _SLPIN = const(0x10)
    _SLPOUT = const(0x11)
    _PTLON = const(0x12)
    _NORON = const(0x13)

    _INVOFF = const(0x20)
    _INVON = const(0x21)
    _DISPOFF = const(0x28)
    _DISPON = const(0x29)
    _CASET = const(0x2A)
    _RASET = const(0x2B)
    _RAMWR = const(0x2C)
    _RAMRD = const(0x2E)

    _PTLAR = const(0x30)
    _COLMOD = const(0x3A)
    _MADCTL = const(0x36)

    _FRMCTR1 = const(0xB1)
    _FRMCTR2 = const(0xB2)
    _FRMCTR3 = const(0xB3)
    _INVCTR = const(0xB4)
    _DISSET5 = const(0xB6)

    _PWCTR1 = const(0xC0)
    _PWCTR2 = const(0xC1)
    _PWCTR3 = const(0xC2)
    _PWCTR4 = const(0xC3)
    _PWCTR5 = const(0xC4)
    _VMCTR1 = const(0xC5)

    _RDID1 = const(0xDA)
    _RDID2 = const(0xDB)
    _RDID3 = const(0xDC)
    _RDID4 = const(0xDD)

    _PWCTR6 = const(0xFC)

    _GMCTRP1 = const(0xE0)
    _GMCTRN1 = const(0xE1)


    _COLUMN_SET = _CASET
    _PAGE_SET = _RASET
    _RAM_WRITE = _RAMWR
    _RAM_READ = _RAMRD
    _INIT = (
        (_SWRESET, None),
        (_SLPOUT, None),
        (_COLMOD, b"\x05"),  # 16bit color
        # fastest refresh, 6 lines front porch, 3 line back porch
        (_FRMCTR1, b"\x00\x06\x03"),
        (_MADCTL, b"\x08"),  # bottom to top refresh
        # 1 clk cycle nonoverlap, 2 cycle gate rise, 3 sycle osc equalie,
        # fix on VTL
        (_DISSET5, b"\x15\x02"),
        (_INVCTR, b"0x00"),  # line inversion
        (_PWCTR1, b"\x02\x70"),  # GVDD = 4.7V, 1.0uA
        (_PWCTR2, b"\x05"),  # VGH=14.7V, VGL=-7.35V
        (_PWCTR3, b"\x01\x02"),  # Opamp current small, Boost frequency
        (_VMCTR1, b"\x3c\x38"),  # VCOMH = 4V, VOML = -1.1V
        (_PWCTR6, b"\x11\x15"),
        (
            _GMCTRP1,
            b"\x09\x16\x09\x20\x21\x1b\x13\x19" b"\x17\x15\x1e\x2b\x04\x05\x02\x0e",
        ),  # Gamma
        (
            _GMCTRN1,
            b"\x08\x14\x08\x1e\x22\x1d\x18\x1e" b"\x18\x1a\x24\x2b\x06\x06\x02\x0f",
        ),
        (_CASET, b"\x00\x02\x00\x81"),  # XSTART = 2, XEND = 129
        (_RASET, b"\x00\x02\x00\x81"),  # XSTART = 2, XEND = 129
        (_NORON, None),
        (_DISPON, None),
    )  # type: Tuple[Tuple[int, Union[ByteString, None]], ...]
    _ENCODE_PIXEL = ">H"
    _ENCODE_POS = ">HH"
    _BUFFER_SIZE = 1024
    _DECODE_PIXEL = ">BBB"
    _X_START = 0  # pylint: disable=invalid-name
    _Y_START = 0  # pylint: disable=invalid-name

    _RDDPM = const(0x0A)

    def __init__(self, spi, width: int, height: int) -> None:
        self._spi = spi
        self.width = width
        self.height = height
        self._invert = False
        self._offset_left = 0
        self._offset_top = 0
        self.init()

    def init(self) -> None:
        """Run the initialization commands."""
        # for command, data in self._INIT:
        #     self._spi.write(command, data, delay=0.1)
        # return
        self._spi.write(command=self._SWRESET)    # Software reset
        time.sleep(0.150)               # delay 150 ms

        self._spi.write(command=self._SLPOUT)     # Out of sleep mode
        time.sleep(0.500)               # delay 500 ms

        self._spi.write(command=self._FRMCTR1)    # Frame rate ctrl - normal mode
        self._spi.write(data=b"\x01")                 # Rate = fosc/(1x2+40) * (LINE+2C+2D)
        self._spi.write(data=b"\x2C")
        self._spi.write(data=b"\x2D")

        self._spi.write(command=self._FRMCTR2)    # Frame rate ctrl - idle mode
        self._spi.write(data=b"\x01")                 # Rate = fosc/(1x2+40) * (LINE+2C+2D)
        self._spi.write(data=b"\x2C")
        self._spi.write(data=b"\x2D")

        self._spi.write(command=self._FRMCTR3)    # Frame rate ctrl - partial mode
        self._spi.write(data=b"\x01")                 # Dot inversion mode
        self._spi.write(data=b"\x2C")
        self._spi.write(data=b"\x2D")
        self._spi.write(data=b"\x01")                 # Line inversion mode
        self._spi.write(data=b"\x2C")
        self._spi.write(data=b"\x2D")

        self._spi.write(command=self._INVCTR)     # Display inversion ctrl
        self._spi.write(data=b"\x07")                 # No inversion

        self._spi.write(command=self._PWCTR1)     # Power control
        self._spi.write(data=b"\xA2")
        self._spi.write(data=b"\x02")                 # -4.6V
        self._spi.write(data=b"\x84")                 # auto mode

        self._spi.write(command=self._PWCTR2)     # Power control
        self._spi.write(data=b"\x0A")                 # Opamp current small
        self._spi.write(data=b"\x00")                 # Boost frequency

        self._spi.write(command=self._PWCTR4)     # Power control
        self._spi.write(data=b"\x8A")                 # BCLK/2, Opamp current small & Medium low
        self._spi.write(data=b"\x2A")

        self._spi.write(command=self._PWCTR5)     # Power control
        self._spi.write(data=b"\x8A")
        self._spi.write(data=b"\xEE")

        self._spi.write(command=self._VMCTR1)     # Power control
        self._spi.write(data=b"\x0E")

        if self._invert:
            self._spi.write(command=self._INVON)   # Invert display
        else:
            self._spi.write(command=self._INVOFF)  # Don't invert display

        self._spi.write(command=self._MADCTL)     # Memory access control (directions)
        self._spi.write(data=b"\xC0")             # row addr/col addr, bottom to top refresh; Set D3 RGB Bit to 0 for format RGB

        self._spi.write(command=self._COLMOD)     # set color mode
        self._spi.write(data=b"\x05")                 # 16-bit color

        self._spi.write(command=self._CASET)      # Column addr set
        self._spi.write(data=b"\x00")                 # XSTART = 0
        self._spi.write(data=str(self._offset_left).encode())
        self._spi.write(data=b"\x00")                 # XEND = ROWS - height
        self._spi.write(data=str(self.width + self._offset_left - 1).encode())

        self._spi.write(command=self._RASET)      # Row addr set
        self._spi.write(data=b"\x00")                 # XSTART = 0
        self._spi.write(data=str(self._offset_top).encode())
        self._spi.write(data=b"\x00")                 # XEND = COLS - width
        self._spi.write(data=str(self.height + self._offset_top - 1).encode())

        self._spi.write(command=self._GMCTRP1)    # Set Gamma
        self._spi.write(data=b"\x02")
        self._spi.write(data=b"\x1c")
        self._spi.write(data=b"\x07")
        self._spi.write(data=b"\x12")
        self._spi.write(data=b"\x37")
        self._spi.write(data=b"\x32")
        self._spi.write(data=b"\x29")
        self._spi.write(data=b"\x2d")
        self._spi.write(data=b"\x29")
        self._spi.write(data=b"\x25")
        self._spi.write(data=b"\x2B")
        self._spi.write(data=b"\x39")
        self._spi.write(data=b"\x00")
        self._spi.write(data=b"\x01")
        self._spi.write(data=b"\x03")
        self._spi.write(data=b"\x10")

        self._spi.write(command=self._GMCTRN1)    # Set Gamma
        self._spi.write(data=b"\x03")
        self._spi.write(data=b"\x1d")
        self._spi.write(data=b"\x07")
        self._spi.write(data=b"\x06")
        self._spi.write(data=b"\x2E")
        self._spi.write(data=b"\x2C")
        self._spi.write(data=b"\x29")
        self._spi.write(data=b"\x2D")
        self._spi.write(data=b"\x2E")
        self._spi.write(data=b"\x2E")
        self._spi.write(data=b"\x37")
        self._spi.write(data=b"\x3F")
        self._spi.write(data=b"\x00")
        self._spi.write(data=b"\x00")
        self._spi.write(data=b"\x02")
        self._spi.write(data=b"\x10")

        self._spi.write(command=self._NORON)      # Normal display on
        time.sleep(0.10)                # 10 ms

        self.display_on()
        time.sleep(0.100)               # 100 ms

        print("initialized")

    def display_off(self):
        self._spi.write(command=self._DISPOFF)

    def display_on(self):
        self._spi.write(command=self._DISPON)

    def sleep(self):
        self._spi.write(command=self._SLPIN)

    def wake(self):
        self._spi.write(command=self._SLPOUT)

    def fill_rectangle(
        self, x: int, y: int, width: int, height: int, color: Union[int, Tuple]
    ) -> None:
        """Draw a rectangle at specified position with specified width and
        height, and fill it with the specified color."""
        print(f"lcd rect: {x},{y},{x+width},{y+height}")
        x = min(self.width - 1, max(0, x))
        y = min(self.height - 1, max(0, y))
        width = min(self.width - x, max(1, width))
        height = min(self.height - y, max(1, height))
        self._block(x, y, x + width - 1, y + height - 1, b"0")
        chunks, rest = divmod(width * height, self._BUFFER_SIZE)
        pixel = self._encode_pixel(color)
        if chunks:
            data = pixel * self._BUFFER_SIZE
            for _ in range(chunks):
                self._spi.write(None, data)
        if pixel * rest:
            self._spi.write(None, pixel * rest)

    def fill(self, color: Union[int, Tuple] = 0) -> None:
        """Fill the whole display with the specified color."""
        self.fill_rectangle(0, 0, self.width, self.height, color)

    def _block(
        self, x0: int, y0: int, x1: int, y1: int, data: Optional[ByteString] = None
    ) -> Optional[ByteString]:
        """Read or write a block of data."""
        self._spi.write(
            self._COLUMN_SET, self._encode_pos(x0 + self._X_START, x1 + self._X_START)
        )
        self._spi.write(
            self._PAGE_SET, self._encode_pos(y0 + self._Y_START, y1 + self._Y_START)
        )
        if data is None:
            size = struct.calcsize(self._DECODE_PIXEL)
            return self._spi.read(self._RAM_READ, (x1 - x0 + 1) * (y1 - y0 + 1) * size)
        self._spi.write(self._RAM_WRITE, data)
        return None

    # pylint: enable-msg=invalid-name,too-many-arguments

    def _encode_pos(self, x: int, y: int) -> bytes:
        """Encode a position into bytes."""
        return struct.pack(self._ENCODE_POS, x, y)

    def _encode_pixel(self, color: Union[int, Tuple]) -> bytes:
        """Encode a pixel color into bytes."""
        return struct.pack(self._ENCODE_PIXEL, color)

    def pixel(
        self, x: int, y: int, color: Optional[Union[int, Tuple]] = None
    ) -> Optional[int]:
        """Read or write a pixel at a given position."""
        if color is None:
            return self._decode_pixel(self._block(x, y, x, y))  # type: ignore[arg-type]

        if 0 <= x < self.width and 0 <= y < self.height:
            self._block(x, y, x, y, self._encode_pixel(color))
        return None
    

class PinWrapper:
    def __init__(self, pin_id, mode=GPIO.OUT, value=0):
        self._pin_id = pin_id
        self._mode = mode
        GPIO.setup(self._pin_id, self._mode)
        self._value = value
    
    @property
    def value(self) -> int:
        """Set the default value"""
        return self._value

    @value.setter
    def value(self, val: int) -> None:
        self._value = val
        GPIO.output(self._pin_id, GPIO.HIGH if self._value else GPIO.LOW)

class SpiWrapper:
    def __init__(self, spi_device, dc_pin, rst_pin):
        self._spi_device = spi_device
        self._dc_pin = dc_pin
        self._rst_pin = rst_pin
        self.reset()

    def reset(self) -> None:
        """Reset the device"""
        if not self._rst_pin:
            raise RuntimeError("a reset pin was not provided")
        self._rst_pin.value = 0
        time.sleep(0.050)  # 50 milliseconds
        self._rst_pin.value = 1
        time.sleep(0.050)  # 50 milliseconds

    def write(
        self, command: Optional[int] = None, data: Optional[ByteString] = None, delay: Optional[float] = None
    ) -> None:
        """SPI write to the device: commands and data"""
        # self.write(command, data)
        print(f"spi wr: commmand={command if command else 0:02x}, data={[hex(i) for i in data] if data else None}")
        if command is not None:
            self._dc_pin.value = 0
            self._spi_device.writebytes(bytearray([command]))
        if data is not None:
            self._dc_pin.value = 1
            self._spi_device.writebytes(data)
        if delay: time.sleep(delay)
    
    def read(self, command: Optional[int] = None, count: int = 0) -> ByteString:
        """SPI read from device with optional command"""
        answer = bytearray(count)
        print(f"spi rd: commmand={command if command else 0:02x}, ", end='')

        if command is not None:
            self._dc_pin.value = 0
            self._spi_device.writebytes(bytearray([command]))
        self._dc_pin.value = 1
        # answer = self._spi_device.readbytes(count)
        answer = self._spi_device.xfer2(bytes(count))
        print(f"data={[hex(i) for i in answer]}")
        return answer

if __name__ == "__main__":
    import time
    import spidev

    GPIO.setmode(GPIO.BCM)
    status_led = PinWrapper(26)

    try: 
        status_led.value = 1

        spi_dev = spidev.SpiDev()
        spi_dev.open(bus=0, device=0)
        spi_dev.max_speed_hz = 1000000
        dc_pin = PinWrapper(25)
        rst_pin = PinWrapper(24)
        spi = SpiWrapper(spi_dev, dc_pin, rst_pin)

        lcd = LcdWrapper(spi, 128, 160)

        time.sleep(2)
        status_led.value = 0

        time.sleep(1)
        status_led.value = 1

        lcd.fill(color=0)
        lcd.fill_rectangle(10, 20, width=30, height=20, color=0x7521)
        
        # for i in range(64):
        #     lcd.pixel(i, i, 0x7521)

        time.sleep(1)
        res = spi.read(LcdWrapper._RDDID, 4)
        spi.write(LcdWrapper._NOP, None)
        print("Display ID:", res)


        status_led.value = 0
        spi_dev.close()
        GPIO.cleanup()
    except Exception as e:
        print("Releasing resources... and rethrow exception")
        status_led.value = 0
        GPIO.cleanup()
        spi_dev.close()
        raise e

