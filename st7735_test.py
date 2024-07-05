from typing import Optional, Union, Tuple, List, Any, ByteString
import struct
import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont
import numpy

def image_to_data(image: Image) -> Any:
    """Generator function to convert a PIL image to 16-bit 565 RGB bytes."""
    # NumPy is much faster at doing this. NumPy code provided by:
    # Keith (https://www.blogger.com/profile/02555547344016007163)
    data = numpy.array(image.convert("RGB")).astype("uint16")
    color = (
        ((data[:, :, 0] & 0xF8) << 8)
        | ((data[:, :, 1] & 0xFC) << 3)
        | (data[:, :, 2] >> 3)
    )
    return numpy.dstack(((color >> 8) & 0xFF, color & 0xFF)).flatten().tolist()


class LcdWrapper:
    _NOP = 0x00
    _SWRESET = 0x01
    _RDDID = 0x04
    _RDDST = 0x09

    _SLPIN = 0x10
    _SLPOUT = 0x11
    _PTLON = 0x12
    _NORON = 0x13

    _INVOFF = 0x20
    _INVON = 0x21
    _DISPOFF = 0x28
    _DISPON = 0x29
    _CASET = 0x2A
    _RASET = 0x2B
    _RAMWR = 0x2C
    _RAMRD = 0x2E

    _PTLAR = 0x30
    _COLMOD = 0x3A
    _MADCTL = 0x36

    _FRMCTR1 = 0xB1
    _FRMCTR2 = 0xB2
    _FRMCTR3 = 0xB3
    _INVCTR = 0xB4
    _DISSET5 = 0xB6

    _PWCTR1 = 0xC0
    _PWCTR2 = 0xC1
    _PWCTR3 = 0xC2
    _PWCTR4 = 0xC3
    _PWCTR5 = 0xC4
    _VMCTR1 = 0xC5

    _RDID1 = 0xDA
    _RDID2 = 0xDB
    _RDID3 = 0xDC
    _RDID4 = 0xDD

    _PWCTR6 = 0xFC

    _GMCTRP1 = 0xE0
    _GMCTRN1 = 0xE1


    _COLUMN_SET = _CASET
    _PAGE_SET = _RASET
    _RAM_WRITE = _RAMWR
    _RAM_READ = _RAMRD
    _ENCODE_PIXEL = ">I"
    _ENCODE_POS = ">HH"
    _BUFFER_SIZE = 1024
    _DECODE_PIXEL = ">BBB"
    _X_START = 0
    _Y_START = 0

    _RDDPM = 0x0A


    # Colours for convenience
    _COLOR_BLACK = 0x0000  # 0b 00000 000000 00000
    _COLOR_BLUE = 0x001F  # 0b 00000 000000 11111
    _COLOR_GREEN = 0x07E0  # 0b 00000 111111 00000
    _COLOR_RED = 0xF800  # 0b 11111 000000 00000
    _COLOR_CYAN = 0x07FF  # 0b 00000 111111 11111
    _COLOR_MAGENTA = 0xF81F  # 0b 11111 000000 11111
    _COLOR_YELLOW = 0xFFE0  # 0b 11111 111111 00000
    _COLOR_WHITE = 0xFFFF  # 0b 11111 111111 11111


    def __init__(self, spi, width: int, height: int, rotation:int) -> None:
        self._spi = spi
        self.width = width
        self.height = height
        self.rotation = rotation
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
        time.sleep(0.150)                         # delay 150 ms

        self._spi.write(command=self._SLPOUT)     # Out of sleep mode
        time.sleep(0.500)                         # delay 500 ms

         # Frame rate ctrl - normal mode
         # Rate = fosc/(1x2+40) * (LINE+2C+2D)
        self._spi.write(command=self._FRMCTR1, data=b"\x01\x2C\x2D")

        # Frame rate ctrl - idle mode
        # Rate = fosc/(1x2+40) * (LINE+2C+2D)
        self._spi.write(command=self._FRMCTR2, data=b"\x01\x2C\x2D")    

        self._spi.write(command=self._FRMCTR3)    # Frame rate ctrl - partial mode
        self._spi.write(data=b"\x01\x2C\x2D")     # Dot inversion mode
        self._spi.write(data=b"\x01\x2C\x2D")     # Line inversion mode

        self._spi.write(command=self._INVCTR)     # Display inversion ctrl
        self._spi.write(data=b"\x07")             # No inversion

        self._spi.write(command=self._PWCTR1)     # Power control
        self._spi.write(data=b"\xA2\x02\x84")     # -4.6V, auto mode

        self._spi.write(command=self._PWCTR2)     # Power control
        self._spi.write(data=b"\x0A\x00")         # Opamp current small, Boost frequency

        self._spi.write(command=self._PWCTR4)     # Power control
        self._spi.write(data=b"\x8A\x2A")         # BCLK/2, Opamp current small & Medium low

        self._spi.write(command=self._PWCTR5)     # Power control
        self._spi.write(data=b"\x8A\xEE")

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
        self._spi.write(data=b"\x02\x1c\x07\x12\x37\x32\x29\x2d")
        self._spi.write(data=b"\x29\x25\x2B\x39\x00\x01\x03\x10")
       

        self._spi.write(command=self._GMCTRN1)    # Set Gamma
        self._spi.write(data=b"\x03\x1d\x07\x06\x2E\x2C\x29\x2D")
        self._spi.write(data=b"\x2E\x2E\x37\x3F\x00\x00\x02\x10")

        self._spi.write(command=self._NORON)      # Normal display on
        time.sleep(0.10)                # 10 ms

        self.display_on()
        time.sleep(0.100)               # 100 ms

        print("lcd: initialized")

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

    def image(
        self,
        img: Image,
        rotation: Optional[int] = None,
        x: int = 0,
        y: int = 0,
    ) -> None:
        """Set buffer to value of Python Imaging Library image. The image should
        be in 1 bit mode and a size not exceeding the display size when drawn at
        the supplied origin."""
        if rotation is None:
            rotation = self.rotation
        if not img.mode in ("RGB", "RGBA"):
            raise ValueError("Image must be in mode RGB or RGBA")
        if rotation not in (0, 90, 180, 270):
            raise ValueError("Rotation must be 0/90/180/270")
        if rotation != 0:
            img = img.rotate(rotation, expand=True)
        imwidth, imheight = img.size
        if x + imwidth > self.width or y + imheight > self.height:
            raise ValueError(f"Image must not exceed dimensions of display ({self.width}x{self.height}).")
        pixels = bytes(image_to_data(img))
        self._block(x, y, x + imwidth - 1, y + imheight - 1, pixels)
    
    def draw_text(self, text: str, size: int, posx: int, posy: int) -> None:
        '''Draws text on screen'''
        self.image(get_text_image(text, size), None, posx, posy)


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


def get_text_image(text:str, text_size:int):
    # create an image
    # out = Image.new("RGB", size=(10+text_size*5, 35), color=(255, 0, 0))
    out = Image.new("RGB", size=(115, 15), color=(255, 0, 0))

    # get a font
    fnt = ImageFont.truetype("Pillow/Tests/fonts/FreeMono.ttf", text_size)
    # get a drawing context
    d = ImageDraw.Draw(out)

    # draw multiline text
    d.multiline_text(xy=(0, 0), text=text, font=fnt, fill=(0, 0, 0))
    return out



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

        lcd = LcdWrapper(spi, 128, 160, rotation=180)

        time.sleep(2)
        status_led.value = 0

        time.sleep(1)
        status_led.value = 1

        lcd.fill(color=lcd._COLOR_BLACK)
        # lcd.fill_rectangle(10, 20, width=30, height=20, color=lcd._COLOR_MAGENTA)
        # lcd.fill_rectangle(50, 80, width=30, height=20, color=lcd._COLOR_CYAN)
        
        # for i in range(64):
        #     lcd.pixel(i, i, color=lcd._COLOR_MAGENTA)
        #     lcd.pixel(i + 1, i, color=lcd._COLOR_MAGENTA)
        
        lcd.image(get_text_image("Hello, World!", 10), None, 10, 15)

        # lcd.fill(color=lcd._COLOR_BLACK)
        time.sleep(1)
        res = spi.read(LcdWrapper._RDDID, 4)
        spi.write(LcdWrapper._NOP, None)
        print("Display ID:", res)


        while True:
            lcd.draw_text(time.ctime(), 10, 0, 0)
            time.sleep(0.2)


        status_led.value = 0
        spi_dev.close()
        GPIO.cleanup()
    except Exception as e:
        print("Releasing resources... and rethrow exception")
        status_led.value = 0
        GPIO.cleanup()
        spi_dev.close()
        raise e

