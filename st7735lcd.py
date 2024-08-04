# SPDX-FileCopyrightText: 2017 Radomir Dopieralski for Adafruit Industries
# SPDX-FileCopyrightText: 2023 Matt Land
# SPDX-FileCopyrightText: 2024 Ivan Lipatov
#
# SPDX-License-Identifier: MIT

from typing import Optional, Union, Tuple, List, Any, ByteString
import struct
import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont
import numpy
import time
from enum import Enum


class Logger:
    '''Logger with verbosity control'''
    class Verbosity(Enum):
        MIN = 1
        MED = 2
        MAX = 3

    def __init__(self, prefix: str, verbosity: "Logger.Verbosity" = Verbosity.MAX) -> None:
        '''Verbosity controls amount of messages to be printed. Higher verbosity => more messages.'''
        self._verbosity = verbosity
        self._prefix = prefix
    
    @property
    def verbosity(self) -> "Logger.Verbosity":
        """Return current verbosity"""
        return self._verbosity

    @verbosity.setter
    def verbosity(self, verbosity: "Logger.Verbosity") -> None:
        '''Changes logger min verbosity level'''
        self._verbosity = verbosity

    def info(self, *args, **kwargs) -> None:
        '''Logging an info message. Minumum message verbosity => message is always printed.
        Default message verbosity is MAX to limit amount of messages.'''
        message_verbosity = kwargs.pop('verbosity', Logger.Verbosity.MAX)
        if message_verbosity.value <= self._verbosity.value:
            if kwargs.pop('no_prefix', False):
                print(*args, **kwargs)
            else:
                print(f"{self._prefix} info: ", *args, **kwargs)

    def warning(self, *args, **kwargs) -> None:
        '''Logging a warning message'''
        raise NotImplementedError("Please Implement this method")
    
    def fatal(self, *args, **kwargs) -> None:
        '''Logging a fatal message'''
        raise NotImplementedError("Please Implement this method")


class OutPinWrapper:
    '''Output GPIO pin'''
    def __init__(self, pin_id, value=0):
        self._pin_id = pin_id
        self._mode = GPIO.OUT
        GPIO.setup(self._pin_id, self._mode)
        self._value = value
    
    @property
    def value(self) -> int:
        """Return current pin value"""
        return self._value

    @value.setter
    def value(self, val: int) -> None:
        self._value = val
        GPIO.output(self._pin_id, GPIO.HIGH if self._value else GPIO.LOW)


class SpiDriver:
    '''SPI interface with D/C pin driver'''
    def __init__(self, spi_device, dc_pin: OutPinWrapper, logger: Logger):
        self._spi_device = spi_device
        self._dc_pin = dc_pin
        self._logger = logger

    def write(
        self, command: Optional[int] = None, data: Optional[ByteString] = None
    ) -> None:
        """SPI write to the device: commands and data. Arg data should be either None or non-empty byte string"""
        self._logger.info(f"wr: commmand={command if command else 0:02x}, data={[hex(i) for i in data] if data else None}")
        if command is not None:
            self._dc_pin.value = 0
            self._spi_device.writebytes(bytearray([command]))
        if data is not None:
            self._dc_pin.value = 1
            self._spi_device.writebytes(data)
    
    def read(self, command: Optional[int] = None, count: int = 0) -> ByteString:
        """SPI read from device with optional command"""
        answer = bytearray(count)
        self._logger.info(f"rd: commmand={command if command else 0:02x}, ", end='')

        if command is not None:
            self._dc_pin.value = 0
            self._spi_device.writebytes(bytearray([command]))
        self._dc_pin.value = 1
        # answer = self._spi_device.readbytes(count)
        answer = bytes(self._spi_device.xfer2(bytes(count)))
        self._logger.info(f"data={[hex(i) for i in answer]}", no_prefix=True)
        return answer

def color565(
    r: Union[int, Tuple[int, int, int], List[int]],
    g: Optional[int] = 0,
    b: Optional[int] = 0,
) -> int:
    """Convert red, green and blue values (0-255) into a 16-bit 565 encoding"""
    if isinstance(r, (tuple, list)):  # see if the first var is a tuple/list
        if len(r) >= 3:
            red, g, b = r[0:3]
        else:
            raise ValueError(
                "Not enough values to unpack (expected 3, got %d)" % len(r)
            )
    else:
        red = r
    return (red & 0xF8) << 8 | (g & 0xFC) << 3 | b >> 3

def color_int_to_tuple(color: int) -> Tuple[int, int, int]:
    '''Returns 8bit color tuple from 16bit RGB565 int by left shift and last bit copy'''
    r = ((color >> 11) & 0x1F) << 3 | ((color >> 11) & 0x1 << 2) | ((color >> 11) & 0x1 << 1) | ((color >> 11) & 0x1)
    g = (((color >> 5) & 0x3F) << 2) | (((color >> 5) & 0x1) << 1) | ((color >> 5) & 0x1)
    b = ((color & 0x1F) << 3) | ((color & 0x1) << 2) | ((color & 0x1) << 1) | (color & 0x1)
    return r, g, b


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


def get_text_image(
    text:str, 
    text_size:int, 
    image_size:Tuple[int, int], 
    text_offset: Tuple[int, int] = (0, 0),
    font_color: Tuple[int, int, int] = (255, 255, 255),
    bg_color: Tuple[int, int, int] = (0, 0, 0)
    ) -> Image:
    '''Returns an image containing printed text'''
    # create an image
    out = Image.new("RGB", size=image_size, color=bg_color)

    # get a font
    fnt = ImageFont.truetype("Pillow/Tests/fonts/FreeMono.ttf", text_size)
    # get a drawing context
    d = ImageDraw.Draw(out)

    # draw multiline text
    d.multiline_text(xy=text_offset, text=text, font=fnt, fill=font_color, align="center")
    return out


class LcdDisplay:
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
    _ENCODE_PIXEL = ">H"
    _ENCODE_POS = ">HH"
    _BUFFER_SIZE = 256
    _DECODE_PIXEL = ">BBB"
    _X_START = 0
    _Y_START = 0

    _RDDPM = 0x0A


    # Colors
    COLOR_BLACK = 0x0000  # 0b 00000 000000 00000
    COLOR_BLUE = 0x001F  # 0b 00000 000000 11111
    COLOR_GREEN = 0x07E0  # 0b 00000 111111 00000
    COLOR_RED = 0xF800  # 0b 11111 000000 00000
    COLOR_CYAN = 0x07FF  # 0b 00000 111111 11111
    COLOR_MAGENTA = 0xF81F  # 0b 11111 000000 11111
    COLOR_YELLOW = 0xFFE0  # 0b 11111 111111 00000
    COLOR_WHITE = 0xFFFF  # 0b 11111 111111 11111

    def __init__(self, spi: SpiDriver, rst_pin: OutPinWrapper, width: int, height: int, rotation: int, logger: Logger) -> None:
        self._spi = spi
        self._rst_pin = rst_pin
        self.width = width
        self.height = height
        self.rotation = rotation
        self._logger = logger
        self._invert = False
        self._offset_left = 0
        self._offset_top = 0
 
    def reset(self) -> None:
        """Reset the device"""
        if not self._rst_pin:
            raise RuntimeError("Reset pin was not provided")
        self._rst_pin.value = 0
        time.sleep(0.050)  # 50 milliseconds
        self._rst_pin.value = 1
        time.sleep(0.050)  # 50 milliseconds

    def write(
        self, command: Optional[int] = None, data: Optional[ByteString] = None
    ) -> None:
        """SPI write to the device: commands and data. Arg data should be either None or non-empty byte string"""
        self._spi.write(command, data)
    
    def read(self, command: Optional[int] = None, count: int = 0) -> ByteString:
        """SPI read from device with optional command"""
        return self._spi.read(command, count)

    def init(self) -> None:
        """Run the initialization commands."""
        self.reset()
        time.sleep(0.500)                         # delay 500 ms
        self.write(command=self._SWRESET)    # Software reset
        time.sleep(0.150)                         # delay 150 ms

        self.write(command=self._SLPOUT)     # Out of sleep mode
        time.sleep(0.500)                         # delay 500 ms

        # Frame rate ctrl - normal mode
        # Rate = fosc/(1x2+40) * (LINE+2C+2D)
        self.write(command=self._FRMCTR1, data=b"\x01\x2C\x2D")

        # Frame rate ctrl - idle mode
        # Rate = fosc/(1x2+40) * (LINE+2C+2D)
        self.write(command=self._FRMCTR2, data=b"\x01\x2C\x2D")    

        self.write(command=self._FRMCTR3)    # Frame rate ctrl - partial mode
        self.write(data=b"\x01\x2C\x2D")     # Dot inversion mode
        self.write(data=b"\x01\x2C\x2D")     # Line inversion mode

        self.write(command=self._INVCTR)     # Display inversion ctrl
        self.write(data=b"\x07")             # No inversion

        self.write(command=self._PWCTR1)     # Power control
        self.write(data=b"\xA2\x02\x84")     # -4.6V, auto mode

        self.write(command=self._PWCTR2)     # Power control
        self.write(data=b"\x0A\x00")         # Opamp current small, Boost frequency

        self.write(command=self._PWCTR4)     # Power control
        self.write(data=b"\x8A\x2A")         # BCLK/2, Opamp current small & Medium low

        self.write(command=self._PWCTR5)     # Power control
        self.write(data=b"\x8A\xEE")

        self.write(command=self._VMCTR1)     # Power control
        self.write(data=b"\x0E")

        if self._invert:
            self.write(command=self._INVON)   # Invert display
        else:
            self.write(command=self._INVOFF)  # Don't invert display

        self.write(command=self._MADCTL)     # Memory access control (directions)
        self.write(data=b"\xC0")             # row addr/col addr, bottom to top refresh; Set D3 RGB Bit to 0 for format RGB

        self.write(command=self._COLMOD)     # set color mode
        self.write(data=b"\x05")                 # 16-bit color

        self.write(command=self._CASET)      # Column addr set
        self.write(data=b"\x00")                 # XSTART = 0
        self.write(data=str(self._offset_left).encode())
        self.write(data=b"\x00")                 # XEND = ROWS - height
        self.write(data=str(self.width + self._offset_left - 1).encode())

        self.write(command=self._RASET)      # Row addr set
        self.write(data=b"\x00")                 # XSTART = 0
        self.write(data=str(self._offset_top).encode())
        self.write(data=b"\x00")                 # XEND = COLS - width
        self.write(data=str(self.height + self._offset_top - 1).encode())

        self.write(command=self._GMCTRP1)    # Set Gamma
        self.write(data=b"\x02\x1c\x07\x12\x37\x32\x29\x2d")
        self.write(data=b"\x29\x25\x2B\x39\x00\x01\x03\x10")

        self.write(command=self._GMCTRN1)    # Set Gamma
        self.write(data=b"\x03\x1d\x07\x06\x2E\x2C\x29\x2D")
        self.write(data=b"\x2E\x2E\x37\x3F\x00\x00\x02\x10")

        self.write(command=self._NORON)      # Normal display on
        time.sleep(0.1)

        self.display_on()
        time.sleep(0.1)

        self._logger.info("initialized", verbosity=Logger.Verbosity.MED)

    def display_off(self):
        self.write(command=self._DISPOFF)

    def display_on(self):
        self.write(command=self._DISPON)

    def sleep(self):
        self.write(command=self._SLPIN)

    def wake(self):
        self.write(command=self._SLPOUT)

    def dev_id(self) -> int:
        devid_bytes = self.read(self._RDDID, 4)
        return struct.unpack(">I", devid_bytes)[0]

    def fill_rectangle(
        self, x: int, y: int, width: int, height: int, color: Union[int, Tuple]
    ) -> None:
        """Draw a rectangle at specified position with specified width and
        height, and fill it with the specified color."""
        self._logger.info(f"rect: {x},{y},{x+width},{y+height}")
        x = min(self.width - 1, max(0, x))
        y = min(self.height - 1, max(0, y))
        width = min(self.width - x, max(1, width))
        height = min(self.height - y, max(1, height))
        self._block(x, y, x + width - 1, y + height - 1, b"")
        chunks, rest = divmod(width * height, self._BUFFER_SIZE)
        pixel = self._encode_pixel(color)
        
        if chunks:
            data = pixel * self._BUFFER_SIZE
            for _ in range(chunks):
                self.write(None, data)
        if rest:
            self.write(None, pixel * rest)

    def fill(self, color: Union[int, Tuple] = 0) -> None:
        """Fill the whole display with the specified color."""
        self.fill_rectangle(0, 0, self.width, self.height, color)

    def _block(
        self, x0: int, y0: int, x1: int, y1: int, data: Optional[ByteString] = None
    ) -> Optional[ByteString]:
        """Read or write a block of data."""
        self.write(
            self._COLUMN_SET, self._encode_pos(x0 + self._X_START, x1 + self._X_START)
        )
        self.write(
            self._PAGE_SET, self._encode_pos(y0 + self._Y_START, y1 + self._Y_START)
        )
        if data is None:
            size = struct.calcsize(self._DECODE_PIXEL)
            return self.read(self._RAM_READ, (x1 - x0 + 1) * (y1 - y0 + 1) * size)
        self.write(self._RAM_WRITE, data if len(data) else None)
        return None

    def _encode_pos(self, x: int, y: int) -> bytes:
        """Encode a position into bytes."""
        return struct.pack(self._ENCODE_POS, x, y)

    def _encode_pixel(self, color: Union[int, Tuple]) -> bytes:
        """Encode a pixel color into bytes."""
        return struct.pack(self._ENCODE_PIXEL, color)

    def _decode_pixel(self, data: Union[bytes, Union[bytearray, memoryview]]) -> int:
        """Decode bytes into a pixel color."""
        return color565(*struct.unpack(self._DECODE_PIXEL, data))

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
        self._block(x, y, x + imwidth - 1, y + imheight - 1, "")
        
        chunks, rest = divmod(len(pixels), self._BUFFER_SIZE)
        self._logger.info(f"block chunks={chunks}, rest={rest}")
        if chunks:
            for c in range(chunks):
                self.write(None, pixels[c * self._BUFFER_SIZE: (c + 1) * self._BUFFER_SIZE])
        if rest:
            self.write(None, pixels[chunks * self._BUFFER_SIZE:])
    
    def draw_text(self,
        text: str,
        text_size: int,
        image_size: Tuple[int],
        pos: Tuple[int, int],
        text_offset: Tuple[int, int] = (0, 0),
        font_color: int = color_int_to_tuple(COLOR_WHITE),
        bg_color: int = color_int_to_tuple(COLOR_BLACK)
        ) -> None:
        '''Draws text on screen. Front and bg are 16-bit 565RBG colors.'''
        self.image(get_text_image(text, text_size, image_size, text_offset, color_int_to_tuple(font_color), color_int_to_tuple(bg_color)), None, pos[0], pos[1])



