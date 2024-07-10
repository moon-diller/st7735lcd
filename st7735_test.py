from typing import Optional, Union, Tuple, List, Any, ByteString
import struct
import RPi.GPIO as GPIO
from PIL import Image, ImageDraw, ImageFont
import numpy

def color_int_to_tuple(color: int) -> Tuple[int]:
    '''Returns 8bit color tuple'''
    return (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF


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
    image_size:Tuple[int], 
    font_color: Tuple[int] = (255, 255, 255),
    bg_color: Tuple[int] = (0, 0, 0)
    ) -> Image:
    '''Returns an image containing printed text'''
    # create an image
    out = Image.new("RGB", size=image_size, color=bg_color)

    # get a font
    fnt = ImageFont.truetype("Pillow/Tests/fonts/FreeMono.ttf", text_size)
    # get a drawing context
    d = ImageDraw.Draw(out)

    # draw multiline text
    d.multiline_text(xy=(0, 0), text=text, font=fnt, fill=font_color)
    return out


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
    _BUFFER_SIZE = 256
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
    
    def draw_text(self,
        text: str,
        text_size: int,
        image_size: Tuple[int],
        pos: Tuple[int],
        font_color: int,
        bg_color: int
        ) -> None:
        '''Draws text on screen'''
        self.image(get_text_image(text, text_size, image_size, color_int_to_tuple(font_color), color_int_to_tuple(bg_color)), None, pos[0], pos[1])


class PinWrapper:
    def __init__(self, pin_id, mode=GPIO.OUT, value=0):
        self._pin_id = pin_id
        self._mode = mode
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



class RectWidget:
    def __init__(self,
        lcd: LcdWrapper,
        parent: "Optional[RectWidget]",
        relx: int,
        rely: int,
        width: int,
        height: int,
        color: int,
        ):

        self._parent = parent
        self._children = []
        self._lcd = lcd
        self.color = color
        self.x0 = (self._parent.x0 if self._parent else 0) + relx
        self.x1 = self.x0 + width
        self.y0 = (self._parent.y0 if self._parent else 0) + rely
        self.y1 = self.y0 + height
        assert(self.x0 <= self.x1)
        assert(self.y0 <= self.y1)
        if self._parent:
            self._parent.add_child(self)
        self.need_redraw = True
    
    def add_child(self, child: "RectWidget") -> None:
        self._children.append(child)
    
    def draw(self):
        if self.need_redraw:
            self._lcd.fill_rectangle(self.x0, self.y0, self.x1, self.y1, self.color)
            self.need_redraw = False
        for child in self._children:
            child.draw()

    def bbox(self) -> Tuple[int]:
        return (self.x0, self.y0, self.x1, self.y1)


class TextLabel(RectWidget):
    def __init__(
    self,
    lcd: LcdWrapper,
    parent: RectWidget,
    relx: int,
    rely: int,
    width: int,
    height: int,
    font_color: int,
    bg_color: int,
    text: str = ""
    ):
        super().__init__(lcd, parent, relx, rely, width, height, bg_color)
        self.text = text
        self._font_color = font_color
    
    def draw(self):
        image_size = (self.x1 - self.x0, self.y1 - self.y0)
        text_size = image_size[1] - 1
        self._lcd.draw_text(self.text, text_size, image_size, (self.x0, self.y0), self._font_color, self.color)
    
    @property
    def text(self) -> str:
        """Return current text"""
        return self._text

    @text.setter
    def text(self, value):
        self._text = value
        self._need_redraw = True


import termios, fcntl, sys, os
class SnakeWidget(RectWidget):
    def __init__(
    self,
    lcd: LcdWrapper,
    parent: RectWidget,
    relx: int,
    rely: int,
    width: int,
    height: int,
    bg_color: int,
    ):
        super().__init__(lcd, parent, relx, rely, width, height, bg_color)
        self.dxdy = (1, 0)
        self.posx = (self.x0 + self.x1) // 2
        self.posy = (self.y0 + self.y1) // 2

        # init pos
        cur_len = 3
        assert(cur_len > (self.y1 - self.y1))
        
        self.snake = []
        for i in range(cur_len):
            self.snake.append((self.posx - i, self.posy))
            self._lcd.pixel(self.posx - i, self.posy, color=self._lcd._COLOR_MAGENTA)

        self.head = cur_len - 1
        self.tail = 0


    def draw(self):
        # color old tail
        tail_pixel_coord = self._rel_to_abs_point(self.snake[self.tail][0], self.snake[self.tail][1])
        self._lcd.pixel(tail_pixel_coord[0], tail_pixel_coord[1], color=self.color)

        # upd dxdy and length
        key = self._getkey()
        if key in [65, 66, 67, 68, 32]:
            status_led.value = 1
        else:
            status_led.value = 0

        if key == 67:
            self.dxdy = (-1, 0)
        if key == 68:
            self.dxdy = (1, 0)
        if key == 65:
            self.dxdy = (0, 1)
        if key == 66:
            self.dxdy = (0, -1)
        if key == 32:
            self.snake.append(self.snake[-1])

        new_head_x = (self.snake[self.head][0] + self.dxdy[0]) % (self.x1 - self.x0)
        new_head_y = (self.snake[self.head][1] + self.dxdy[1]) % (self.y1 - self.y0)
        self.head = (self.head + 1) % len(self.snake)
        self.tail = (self.tail + 1) % len(self.snake)
        self.snake[self.head] = (new_head_x, new_head_y)

        # color new head
        head_pixel_coord = self._rel_to_abs_point(self.snake[self.head][0], self.snake[self.head][1])
        self._lcd.pixel(head_pixel_coord[0], head_pixel_coord[1], color=self._lcd._COLOR_MAGENTA)
    
    def _rel_to_abs_point(self, relx, rely):
        return relx + self.x0, rely + self.y0
            
    
    def _getkey(self):
        fd = sys.stdin.fileno()

        oldterm = termios.tcgetattr(fd)
        newattr = termios.tcgetattr(fd)
        newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, newattr)

        oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)

        c = None

        try:
            c = sys.stdin.read(1)
        except IOError: pass

        termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)
        # print("got key:", c, ord(c))
        return ord(c) if c else None



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

        time.sleep(1)
        status_led.value = 0

        time.sleep(0.5)
        status_led.value = 1

        lcd.fill(color=lcd._COLOR_BLACK)        
        lcd.image(get_text_image("Hello, World!", 10, image_size=(115, 15)), None, 10, 15)
        status_led.value = 0
        
        time.sleep(0.2)
        res = spi.read(LcdWrapper._RDDID, 4)
        spi.write(LcdWrapper._NOP, None)
        print("Display ID:", res)

        main_widget = RectWidget(lcd, None, 0, 0, lcd.width, lcd.height, lcd._COLOR_BLACK)
        date_widget = TextLabel(lcd, main_widget, 0, 0, lcd.width, 10, font_color=0xFFFFFF, bg_color=lcd._COLOR_GREEN)
        text_widget = TextLabel(lcd, main_widget, 0, 150, lcd.width, 10, font_color=0xFFFFFF, bg_color=lcd._COLOR_GREEN, text="Hello, world!")
        snake_widget = SnakeWidget(lcd, main_widget, 0, 10, lcd.width, 140, bg_color=lcd._COLOR_BLACK)
        
        while True:
            date_widget.text = time.ctime()
            snake_widget._need_redraw = True
            main_widget.draw()
            time.sleep(0.05)


        status_led.value = 0
        spi_dev.close()
        GPIO.cleanup()
    except KeyboardInterrupt as e:
        print("Releasing resources... and rethrow exception")
        status_led.value = 0
        GPIO.cleanup()
        spi_dev.close()
        raise e

