import st7735lcd

from typing import Tuple
import RPi.GPIO as GPIO
import time

class RectWidget:
    def __init__(self,
        lcd: st7735lcd.LcdWrapper,
        parent: "RectWidget | None",
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
    lcd: st7735lcd.LcdWrapper,
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
        self.need_redraw = True


import termios, fcntl, sys, os
class SnakeWidget(RectWidget):
    def __init__(
    self,
    lcd: st7735lcd.LcdWrapper,
    parent: RectWidget,
    relx: int,
    rely: int,
    width: int,
    height: int,
    bg_color: int,
    snake_color: int
    ):
        super().__init__(lcd, parent, relx, rely, width, height, bg_color)
        self.dxdy = (1, 0)
        self.posx = (self.x0 + self.x1) // 2
        self.posy = (self.y0 + self.y1) // 2
        self._snake_color = snake_color

        # init pos
        cur_len = 3
        assert(cur_len > (self.y1 - self.y1))
        
        self.snake = []
        for i in range(cur_len):
            self.snake.append((self.posx - i, self.posy))
            self._lcd.pixel(self.posx - i, self.posy, color=self._snake_color)

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
        self._lcd.pixel(head_pixel_coord[0], head_pixel_coord[1], color=self._snake_color)
    
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
    status_led = st7735lcd.OutPinWrapper(26)

    try: 
        status_led.value = 1

        spi_dev = spidev.SpiDev()
        spi_dev.open(bus=0, device=0)
        spi_dev.max_speed_hz = 1000000
        dc_pin = st7735lcd.OutPinWrapper(25)
        rst_pin = st7735lcd.OutPinWrapper(24)
        spi_logger = st7735lcd.Logger("spi", verbosity=st7735lcd.Logger.Verbosity.MIN)
        spi = st7735lcd.SpiWrapper(spi_dev, dc_pin, rst_pin, logger=spi_logger)

        lcd = st7735lcd.LcdWrapper(spi, 128, 160, rotation=180, logger=st7735lcd.Logger("lcd"))

        time.sleep(1)
        status_led.value = 0

        time.sleep(0.5)
        status_led.value = 1

        lcd.fill(color=lcd.COLOR_BLACK)

        colors = {
            "pink" : 0xe86c,
            "yellow" : 0xffa1,
            "red" : 0xf800,
            "cyan" : 0x0f5f,
            "blue" : 0x001f,
            "green" : 0x07e0,
            "orange" : 0xfbe1,
            }

        for name, color in colors.items():
            print(f"Color:{color:x} ({color})")
            lcd.fill(color=color)
            lcd.image(st7735lcd.get_text_image(name, 10, image_size=(85, 15)), None, 22, 15)
            lcd.draw_text("Hello\nWorld!", 25, image_size=(85, 60), pos=(21, 50), font_color=color, bg_color=lcd.COLOR_BLACK)
            time.sleep(1)

        status_led.value = 0
        
        lcd.fill(color=lcd.COLOR_BLACK)
        dev_id = lcd.dev_id()
        print("Display ID: {dev_id:x}")
        lcd.draw_text(f"Display ID:\n{dev_id:x}", 15, image_size=(90, 60), pos=(19, 50), font_color=lcd.COLOR_WHITE, bg_color=lcd.COLOR_BLACK)
        time.sleep(2)

        main_widget = RectWidget(lcd, None, 0, 0, lcd.width, lcd.height, lcd.COLOR_BLACK)
        date_widget = TextLabel(lcd, main_widget, 0, 0, lcd.width, 10, font_color=lcd.COLOR_WHITE, bg_color=lcd.COLOR_BLUE)
        text_widget = TextLabel(lcd, main_widget, 0, 150, lcd.width, 10, font_color=lcd.COLOR_WHITE, bg_color=lcd.COLOR_BLUE, text="Hello, world!")
        snake_widget = SnakeWidget(lcd, main_widget, 0, 10, lcd.width, 140, bg_color=lcd.COLOR_BLACK, snake_color=lcd.COLOR_MAGENTA)
        
        while True:
            date_widget.text = time.ctime()
            snake_widget.need_redraw = True
            main_widget.draw()
            time.sleep(0.02)

    finally:
        print("Releasing resources...")
        status_led.value = 0
        GPIO.cleanup()
        spi_dev.close()

