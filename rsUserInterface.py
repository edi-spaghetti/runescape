import logging
import datetime
import subprocess
import numpy
import os
import cv2
import win32gui, win32ui, win32con, win32api
import random
import winsound
import time

from ahk import AHK
from glob import glob
from time import sleep
import pytesseract
from pytesseract import Output

import runescape
from runescape.rsKeys import PressKey, ReleaseKey
from runescape.rsKeyMappings import MAP
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files (x86)\Tesseract-OCR\tesseract'


class MiniMap:

    def __init__(self, test=False):

        self.test = test

        # assumes client window is full size
        self.ahk_centre = 1797, 161
        self.centre = 1797, 161
        self.centre_x, self.centre_y = self.centre
        self.sample_size = 80
        self.radius = 105
        self.pixels_per_tile = 5.578130203130202  # 8.36721611722

        self.top = self.centre_y - self.sample_size
        self.left = self.centre_x - self.sample_size
        self.width = self.sample_size * 2
        self.height = self.sample_size * 2

        self.bottom = self.top + self.height
        self.right = self.left + self.width

        # for vertices which need to be x, y x2, y2
        self.region = {'x1': self.left, 'y1': self.top, 'x2': self.right, 'y2': self.bottom}

        # x,y coords for sample area
        self.left_top = self.left, self.top
        self.right_top = self.right, self.top
        self.right_bottom = self.right, self.bottom
        self.left_bottom = self.left, self.bottom

        self.npc_lower = (0, 200, 200)
        self.npc_upper = (100, 255, 255)

        self.screen = None

    def _reset_coords(self):
        self.top = self.centre_y - self.sample_size
        self.left = self.centre_x - self.sample_size
        self.width = self.sample_size * 2
        self.height = self.sample_size * 2

        self.bottom = self.top + self.height
        self.right = self.left + self.width

        # for vertices which need to be x, y x2, y2
        self.region = {'x1': self.left, 'y1': self.top, 'x2': self.right, 'y2': self.bottom}

    def __str__(self):
        return 'mini_map'

    @property
    def sample_path(self):
        if not self.test:
            path = f'{runescape.__path__[0]}{os.sep}sample'
        else:
            path = f'{runescape.__path__[0]}{os.sep}test{os.sep}images{os.sep}{self}'

        n = len(glob(f'{path}{os.sep}{self}*.png'))
        return f'{path}{os.sep}{self}{n}.png'

        # def masked_img(self):
    #     mask = numpy.zeros_like(self.ui.screen)
    #     cv2.fillPoly(mask, self.mini_map_vertices, 255)
    #     masked = cv2.bitwise_and(self.ui.screen, mask)
    #     return masked
    #
    # def show_mini_map(self):
    #     pass
    #
    @property
    def img(self):
        return grab_screen(**self.region)
        # monitor = {"top": self.top, "left": self.left, "width": self.width, "height": self.height}
        # return numpy.array(mss().grab(monitor))

    @property
    def gray_img(self):
        return grab_screen(**self.region, cvt=cv2.COLOR_BGRA2GRAY)
        # return cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)

    def edge_map(self, map_):
        """
        Use Canny edge detector to create a b/w edge map
        """
        return cv2.Canny(
            self.gray_img,
            map_.config['canny_threshold1'],
            map_.config['canny_threshold2']
        )

    def relative_position(self, x, y):
        """
        Returns x,y screen position of map coords relative to mini map centre
        """
        return self.centre_x + (x * self.pixels_per_tile), self.centre_y + (y * self.pixels_per_tile)

    #
    # def save_img(self, path):
    #     existing_imgs = glob(f'{path}{os.sep}mini_map*.png')
    #     new_img_num = len(existing_imgs)
    #     img = self.img
    #     if img:
    #         cv2.imwrite(f'{path}{os.sep}mini_map{new_img_num}.png', self.img)

class BankPin:

    def __init__(self, x=0, y=0):

        # top left of sample image
        self.img_x, self.img_y = None, None
        self.img = None
        self.pin_entered = False
        self.current_tab = None

        # top left of first pin button
        self.left = x
        self.top = y

        self.x_gap = 47
        self.y_gap = 16

        self.width = 93
        self.height = 93

        self.items_per_row = 3
        self.num_rows = 3

        self.button_color = 10, 19, 98

        # container for pin locations + contents
        self.pins = {}
        #
        # for i in range(9):
        #     x1 = self.left + ((self.width + self.x_gap) * (i % self.items_per_row))
        #     y1 = self.top + ((self.height + self.y_gap) * (i // self.num_rows))
        #     x2 = x1 + self.width
        #     y2 = y1 + self.height
        #
        #     self.pins[i] = {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
        #
        # # add coords for 10th pin slot, which is placed as if 3rd on a 4 item per row grid
        # x1 = self.left + ((self.width + self.x_gap) * (3 % 4))
        # y1 = self.top + ((self.height + self.y_gap) * (3 // 4))
        # x2 = x1 + self.width
        # y2 = y1 + self.height
        # self.pins[9] = {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}

    def hover_off_pin(self):
        y2, x2, _ = self.img.shape
        rx, ry = random.randint(self.img_x, self.img_x + x2), random.randint(self.img_y, self.img_y + y2)
        in_box = False
        for pin, bbox in self.pins.items():
            if bbox['x1'] < rx < bbox['x2'] and bbox['y1'] < ry < bbox['y2']:
                in_box = True

        if in_box:
            return self.hover_off_pin()
        else:
            return rx, ry


class MainScreen:

    def __init__(self):
        self.centre_x, self.centre_y = 955, 530  # assumes camera at max height on a flat surface
        self.pixels_per_tile = 29.157540200000007
        self.ht = self.pixels_per_tile/2
        self.radius = 350
        self.safe_box = {'x1': 165, 'y1': 218, 'x2': 1594, 'y2': 889}

        # tile positions at centre assuming cam at max height and zoom
        self.zoom = 1
        self.max_zoom = 33
        self.cx1, self.cy1, self.cx2, self.cy2 = 943, 514, 968, 540
        # at max zoom (10)
        self.cx10, self.cy10, self.cx20, self.cy20 = 814, 512, 1053, 763
        # self.ppt = 25 * self.zoom

        # bounding box of centre square at each level of zoom
        self.x1 = [(1, 943), (2, 943), (3, 942), (4, 940), (5, 938), (6, 938), (7, 935), (8, 932), (9, 931), (10, 932),
              (11, 928), (12, 927), (13, 923), (14, 922), (15, 917), (16, 915), (17, 911), (18, 907), (19, 905),
              (20, 900), (21, 895), (22, 892), (23, 889), (24, 883), (25, 879), (26, 874), (27, 869), (28, 862),
              (29, 856), (30, 850), (31, 843), (32, 833), (33, 826), (34, 818), (35, 818)]
        self.y1 = [(1, 522), (2, 522), (3, 522), (4, 523), (5, 520), (6, 519), (7, 520), (8, 518), (9, 519), (10, 519),
              (11, 519), (12, 520), (13, 518), (14, 519), (15, 518), (16, 518), (17, 519), (18, 518), (19, 519),
              (20, 518), (21, 519), (22, 517), (23, 521), (24, 517), (25, 518), (26, 520), (27, 520), (28, 520),
              (29, 522), (30, 522), (31, 523), (32, 526), (33, 526), (34, 526), (35, 526)]

        self.x2 = [(1, 969), (2, 969), (3, 972), (4, 973), (5, 973), (6, 976), (7, 978), (8, 976), (9, 976), (10, 977),
              (11, 979), (12, 982), (13, 982), (14, 984), (15, 984), (16, 986), (17, 990), (18, 991), (19, 995),
              (20, 996), (21, 997), (22, 1000), (23, 1003), (24, 1009), (25, 1010), (26, 1015), (27, 1019), (28, 1022),
              (29, 1026), (30, 1034), (31, 1035), (32, 1042), (33, 1048), (34, 1050), (35, 1050)]
        self.y2 = [(1, 549), (2, 549), (3, 551), (4, 551), (5, 553), (6, 554), (7, 557), (8, 560), (9, 562), (10, 566),
              (11, 570), (12, 572), (13, 577), (14, 579), (15, 585), (16, 590), (17, 594), (18, 598), (19, 605),
              (20, 610), (21, 615), (22, 622), (23, 629), (24, 638), (25, 647), (26, 657), (27, 665), (28, 675),
              (29, 693), (30, 700), (31, 714), (32, 725), (33, 743), (34, 745), (35, 745)]

        # colours for various things on UI main screen
        self.white_text = (150, 150, 150), (255, 255, 255)
        self.cyan_text = (180, 180, 0), (255, 255, 80)
        self.red_text = (0, 0, 150), (0, 0, 255)
        self.orange_text = (0, 120, 200), (50, 200, 255)
        self.bank_pin_orange = (0, 80, 180), (80, 220, 255)

    @property
    def ppx(self):
        return self.x2[self.zoom-1][1] - self.x1[self.zoom-1][1]

    @property
    def ppy(self):
        return self.y2[self.zoom-1][1] - self.y1[self.zoom-1][1]

    def pixel_distance(self, rx, ry):
        x1 = self.x1[self.zoom-1][1] + (rx * self.ppx)# self.centre_x + (x * self.ppt)
        y1 = self.y1[self.zoom-1][1] + (ry * self.ppy)
        x2 = self.x2[self.zoom-1][1] + (rx * self.ppx)
        y2 = self.y2[self.zoom-1][1] + (ry * self.ppy)
        return x1, y1, x2, y2

    def relative_position(self, rel_x, rel_y):
        """
        Returns x,y screen position of map coords relative to main screen centre
        :param x, y: relative to player
        """
        x1, y1, x2, y2 = self.pixel_distance(rel_x, rel_y)
        return distribute_normally(x1=x1, y1=y1, x2=x2, y2=y2)

class UserInterface:
    """
    Contains and updates information about what's going on in the runescape UI
    """

    def __init__(self, test=False, items='all'):
        self.test = test
        self.ahk_full_screen = (-12, -12, 1944, 1044)
        self.full_screen = {'x1': 0, 'y1': 40, 'x2': 1920, 'y2': 1020}
        self.ahk = get_auto_hot_key()
        self.logger = get_logger('rsui')
        self.window_name = b'Old School RuneScape'
        self.window = self.update_window()
        self.mini_map = MiniMap(test=test)
        self.main_screen = MainScreen()
        self.bank_pin = BankPin()
        self.screen = None
        self.current_tab = None
        self.items_path = f'{runescape.__path__[0]}{os.sep}items'
        self.items = self._load_items(items)


        # some handy ui coords as top left bottom right
        self.login_existing_user = {'x1': 980, 'y1': 450, 'x2': 1180, 'y2': 525}
        # self.login_name = {'x1': 791, 'y1': 424, 'x2': 1148, 'y2': 450}
        self.login_screen = {'x1': 700, 'y1': 315, 'x2': 1200, 'y2': 575}
        self.welcome_screen = {'x1': 775, 'y1': 475, 'x2': 1125, 'y2': 625}
        self.bank_screen1 = {'x1': 400, 'y1': 150, 'x2': 800, 'y2': 250}
        self.bank_screen2 = {'x1': 495, 'y1': 25, 'x2': 1000, 'y2': 85}
        self.bank_screen = {'x1': 425, 'y1': 275, 'x2': 1000, 'y2': 650}
        self.bank_tabs = {'x1': 438, 'y1': 86, 'x2': 869, 'y2': 150}
        # self.bank_screen = {'x1': 400, 'y1': 150, 'x2': 1200, 'y2': 700}
        self.tab_locations = {
            'inventory': {'x1': 1430, 'y1': 970, 'x2': 1465, 'y2': 1015},
            'magic': {'x1': 1580, 'y1': 970, 'x2': 1620, 'y2': 1015},
            'equipment': {'x1': 1480, 'y1': 970, 'x2': 1520, 'y2': 1015},
            'skills': {'x1': 1330, 'y1': 970, 'x2': 1370, 'y2': 1015}
        }
        self.inventory = {
            'location': {'x1': 1625, 'y1': 570, 'x2': 1905, 'y2': 950},
            'contents': [None for _ in range(28)],
            'checked_at': [datetime.datetime.now() for _ in range(28)],
            'slot1_x': 1648,
            'slot1_y': 577,
            'items_per_row': 4,
            'slot_width': 45,
            'slot_width_offset': 18,
            'slot_height': 46,
            'slot_height_offset': 8
        }

    def __str__(self):
        return 'user_interface'

    def save_screen(self):
        cv2.imwrite(self.sample_path, self.screen)

    # def save_mini_map(self):
    #     # crop_img = self.get_mini_map()[
    #     #            self.mini_map.top:(self.mini_map.top + 2 * self.mini_map.sample_size),
    #     #            self.mini_map.left:(self.mini_map.left + 2 * self.mini_map.sample_size)
    #     #            ]
    #
    #     cv2.imwrite(self.mini_map.sample_path, self.get_mini_map())
    #
    # def get_mini_map(self):
    #     return process_img(self.screen, self.mini_map.vertices)
    #
    # def update_mini_map(self):
    #     self.mini_map.screen = grab_screen(self.mini_map)

    def update_screen(self):
        self.screen = grab_screen(**self.full_screen)

    @property
    def sample_path(self):
        if not self.test:
            path = f'{runescape.__path__[0]}{os.sep}sample'
        else:
            path = f'{runescape.__path__[0]}{os.sep}test{os.sep}images{os.sep}{self}'

        n = len(glob(f'{path}{os.sep}{self}*.png'))
        return f'{path}{os.sep}{self}{n}.png'

    @property
    def now(self):
        return datetime.datetime.now()

    @property
    def now_string(self):
        return self.now.strftime('%x %X.%f')

    @property
    def is_open(self):
        if self.ahk.win_get(title=self.window_name):
            return True
        # if self.ahk.find_window(title=self.window_name):
        #     return True
        else:
            return False

    @property
    def is_active(self):
        if self.ahk.active_window.title == self.window_name:
            return True
        else:
            return False

    @property
    def is_full_screen(self):
        if self.window:
            if self.window.rect == self.ahk_full_screen:
                return True
        # else:
        return False

    @property
    def ready(self):
        if self.is_active and self.is_full_screen:
            return True
        else:
            return False

    def change_zoom(self, value):
        if value > 0:
            direction = 'up'
            mod = 1
        else:
            direction = 'down'
            mod = -1

        for v in range(abs(value)):
            self.ahk.mouse_wheel(direction)
            time.sleep(0.1)

            # this will add or remove one depending on the zoom
            new_zoom = self.main_screen.zoom + (1 * mod)
            if 0 < new_zoom < 32:
                self.main_screen.zoom = new_zoom


    def update_window(self):
        for w in self.ahk.windows():
            if self.window_name.lower() in w.title.lower():
                return w
        # return [w for w in self.ahk.windows() if b'old school runescape' in w.title.lower()][0]
        # return self.ahk.find_window(title=self.window_name)

    def read_existing_user(self):
        """
        expect to find this on screen:
        {
            'level': [1, 2, 3, 4, 5, 2, 3, 4, 5, 5, 5, 2, 3, 4, 5, 5, 5, 5],
            'page_num': [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'block_num': [0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3],
            'par_num': [0, 0, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1],
            'line_num': [0, 0, 0, 1, 1, 0, 0, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1],
            'word_num': [0, 0, 0, 0, 1, 0, 0, 0, 1, 2, 3, 0, 0, 0, 1, 2, 3, 4],
            'left': [0, 0, 0, 0, 0, 149, 149, 149, 149, 237, 264, 92, 92, 92, 92, 137, 312, 398],
            'top': [0, 0, 0, 0, 0, 81, 81, 81, 81, 83, 82, 147, 147, 147, 147, 147, 147, 147],
            'width': [501, 82, 82, 82, 82, 219, 219, 219, 80, 19, 104, 350, 350, 350, 36, 44, 77, 44],
            'height': [261, 65, 65, 65, 65, 22, 22, 22, 16, 14, 21, 22, 22, 22, 16, 16, 22, 16],
            'conf': ['-1', '-1', '-1', '-1', 95, '-1', '-1', '-1', 95, 96, 72, '-1', '-1', '-1', 96, 96, 95, 96],
            'text': ['', '', '', '', ' ', '', '', '', 'Welcome', 'to', 'RuneScape', '', '', '', 'New', 'User', 'Existing', 'User']
        }
        :return: randomised coords of within existing user button bounding box
        """
        # cv2.imshow('login', grab_screen(**self.login_screen))
        # cv2.waitKey(0)
        # cv2.destroyWindow('login')

        # cv2.imwrite(r'C:\Users\Edi\Desktop\programming\runescape\test\images\login1.png', grab_screen(**self.login_screen))

        screen = self.read_screen(**self.login_screen, thresh_mode='white text')
        text = ' '.join(screen['text'])
        detected_login = False
        while not detected_login:
            if 'new user' in text.lower() or 'existing user' in text.lower():
                detected_login = True

            print(' '.join(screen['text']))
            screen = self.read_screen(**self.login_screen, thresh_mode='white text')
        return screen

    def read_click_here_to_play(self):
        # screen_img = grab_screen(region=self.welcome_screen.values())
        screen = self.read_screen(**self.welcome_screen, thresh_mode='white text')

        while 'click here to play' not in ' '.join(screen['text']).lower():
            # print(screen)
            # cv2.imwrite(self.sample_path, screen_img)
            # screen_img = grab_screen(region=self.welcome_screen.values())
            screen = self.read_screen(**self.welcome_screen, thresh_mode='white text')
        return screen

    def click_existing_user(self, screen):

        x, y = distribute_normally(
            x1=screen['left'][-2] + self.login_screen['x1'] - 20,
            y1=screen['top'][-2] + self.login_screen['y1'] - 5,
            x2=screen['left'][-1] + screen['width'][-1] + self.login_screen['x1'] + 20,
            y2=screen['top'][-1] + screen['height'][-1] + self.login_screen['y1'] + 5
        )
        self.ahk.mouse_move(x, y)
        sleep(random.randint(200, 500)/1000)
        self.ahk.click()

    def click_here_to_play(self, screen):
        """
        Scans through detected words on screen to find 'CLICK HERE TO PLAY' button, then clicks it
        :param screen:
        :return:
        """
        phrase = ['CLICK', 'HERE', 'TO', 'PLAY']
        n = find_anchor(phrase, screen['text'])

        # find a suitable location on the button to press, and click it
        x, y = distribute_normally(
            x1=screen['left'][n] + self.welcome_screen['x1'] - 80,
            y1=screen['top'][n] + self.welcome_screen['y1'] - 30,
            x2=screen['left'][n] + self.welcome_screen['x1'] + 80,
            y2=screen['top'][n] + self.welcome_screen['y1'] + 30
        )
        self.ahk.mouse_move(x, y)
        sleep(random.randint(200, 500) / 1000)
        self.ahk.click()
        winsound.Beep(300, 50)

    def enter_username_and_password(self, username='hello', password='world'):
        screen = self.read_screen(**self.login_screen, thresh_mode='white text')
        words = screen['text']

        # find positions of buttons on screen
        for n, word in enumerate(words):
            if n == len(words) -1:
                continue

            if word.startswith('Login:'):
                input_x, input_y = distribute_normally(
                    x1=screen['left'][n] + screen['width'][n] + self.login_screen['x1'] + 10,
                    x2=screen['left'][n] + screen['width'][n] + self.login_screen['x1'] + 200,
                    y1=screen['top'][n] + self.login_screen['y1'],
                    y2=screen['top'][n] + screen['height'][n] + self.login_screen['y1']
                )
            if word == 'Login' and screen['text'][n+1] == 'Cancel':
                button_x, button_y = distribute_normally(
                    x1=screen['left'][n] + screen['width'][n] + self.login_screen['x1'] - 20,
                    x2=screen['left'][n] + screen['width'][n] + self.login_screen['x1'] + 20,
                    y1=screen['top'][n] + screen['height'][n] + self.login_screen['y1'] - 5,
                    y2=screen['top'][n] + screen['height'][n] + self.login_screen['y1'] + 5
                )

        # sometimes click into username input box
        r = random.randint(0, 10)
        if r > 8:
            self.ahk.mouse_move(input_x, input_y)

        # type username
        for l in username:
            if l == '@':
                PressKey(MAP['DIK_LSHIFT'])
                sleep(random.randint(400, 600) / 1000)
                PressKey(MAP['DIK_2'])
                sleep(random.randint(200, 300) / 1000)

                keys = ['DIK_LSHIFT', 'DIK_2']
                random.shuffle(keys)
                for k in keys:
                    ReleaseKey(MAP[k])
                    sleep(random.randint(100, 200) / 1000)

            elif l == '.':
                humanly_enter_key('PERIOD')
            else:
                humanly_enter_key(l.upper())

        # press enter
        humanly_enter_key('RETURN')

        # type password
        for l in password:
            humanly_enter_key(l.upper())

        sleep(random.randint(200, 500) / 1000)

        # press enter or click login
        r = random.randint(0, 1)
        if r:
            humanly_enter_key('RETURN')
        else:
            self.ahk.mouse_move(button_x, button_y)
            sleep(random.randint(200, 500) / 1000)
            self.ahk.click()

    def log_in(self, username, password):
        # open / activate runescape client
        self.activate_runescape()
        # confirm login screen is ready
        # (980, 475), (1180, 525)

        # read first button on screen
        screen = self.read_existing_user()

        # select login
        self.click_existing_user(screen)
        sleep(random.randint(200, 500)/1000)

        # type in username and password
        self.enter_username_and_password(username, password)

        # read 'CLICK HERE TO PLAY'
        screen = self.read_click_here_to_play()

        # click here to bot... err... play!
        self.click_here_to_play(screen)

    def pin_buttons(self):
        """
        Locates pin buttons in an image and returns a dictionary of their number and location
        """

        # get image and find horizontal / vertical lines
        img = grab_screen(**self.bank_screen)  # cv2.imread(test_img_path)
        self.bank_pin.img = img
        self.bank_pin.img_x, self.bank_pin.img_y = self.bank_screen['x1'], self.bank_screen['y1']
        edges = cv2.Canny(img, 50, 200, apertureSize=3)
        minLineLength = 90
        lines = cv2.HoughLinesP(image=edges, rho=0.6, theta=numpy.pi / 180, threshold=110, lines=numpy.array([]),
                                minLineLength=minLineLength, maxLineGap=50)

        # separate lines into horizontals and verticals
        a, b, c = lines.shape
        segmented = [[], []]  # horizontal, vertical
        for i in range(a):
            h_length = abs(lines[i][0][0] - lines[i][0][2])
            v_length = abs(lines[i][0][1] - lines[i][0][3])

            x1, y1 = lines[i][0][0], lines[i][0][1]
            x2, y2 = lines[i][0][2], lines[i][0][3]
            if h_length > v_length:
                segmented[0].append(((x1, y1), (x2, y2)))
            else:
                segmented[1].append(((x1, y1), (x2, y2)))

        # find intersections between lines
        intersections = []
        for hline in segmented[0]:
            for vline in segmented[1]:
                intersection = line_intersection(hline, vline)
                if intersection:
                    intersections.append(intersection)

        # find top left of first pin button
        moe = 5  # margin of error
        for x1, y1 in intersections:
            pp = []  # potential points
            for i in range(9):
                # get the target x, y based on grid position
                ix1 = x1 + ((self.bank_pin.width + self.bank_pin.x_gap) * (i % self.bank_pin.items_per_row))
                iy1 = y1 + ((self.bank_pin.height + self.bank_pin.y_gap) * (i // self.bank_pin.items_per_row))

                # check potential x,y coords in list
                for px1, py1 in intersections:

                    # if coords are too far away they can't possibly be correct
                    if px1 > (x1 + (self.bank_pin.width + self.bank_pin.x_gap) * self.bank_pin.items_per_row + moe) or px1 < x1:
                        continue
                    if py1 > (y1 + (self.bank_pin.height + self.bank_pin.y_gap) * self.bank_pin.items_per_row + moe) or py1 < y1:
                        continue

                    # if potential point fits in grid then append to list
                    if abs(px1 - ix1) < moe and abs(py1 - iy1) < moe:
                        pp.append((px1, py1))
                        break

            # check 3x3 grid of points for have the appropriate colour
            if len(pp) == 9:
                colours = set()
                for x, y in pp:
                    x, y = int(x), int(y)
                    sub_img = img[y:y + self.bank_pin.height, x:x + self.bank_pin.width]
                    colours.add(bincount_app(sub_img))

                if len(colours) == 1 and self.bank_pin.button_color in colours:
                    self.bank_pin.left, self.bank_pin.top = x1, y1
                    return

    def update_pin(self, visualise=False, logging=False):
        x, y = self.bank_pin.left, self.bank_pin.top

        if visualise or logging:
            img_copy = self.bank_pin.img.copy()

        ocr_config = '--oem 0 --psm 10 tessedit_char_whitelist=0123456789'
        num_results = []
        for i in range(9):
            # get the target x, y based on grid position
            ix = int(x + ((self.bank_pin.width + self.bank_pin.x_gap) * (i % self.bank_pin.items_per_row)))
            iy = int(y + ((self.bank_pin.height + self.bank_pin.y_gap) * (i // self.bank_pin.items_per_row)))

            location = {
                'x1': self.bank_pin.img_x + ix,
                'y1': self.bank_pin.img_y + iy,
                'x2': self.bank_pin.img_x + ix + self.bank_pin.width,
                'y2': self.bank_pin.img_y + iy + self.bank_pin.height,
                'index': i
            }

            # use an optimised ocr setting for this rather than read_screen()
            # sub_img = self.bank_pin.img[iy:iy + self.bank_pin.height, ix:ix + self.bank_pin.width]
            # threshold = 180  # to be determined
            # _, img_binarized = cv2.threshold(sub_img, threshold, 255, cv2.THRESH_BINARY)

            ocr_result = self.read_screen(
                **location,
                thresh_mode=[self.main_screen.bank_pin_orange],
                config=ocr_config)

            for n, num in enumerate(ocr_result['text']):
                try:
                    number = int(num)
                    confidence = ocr_result['conf'][n]
                    break
                except ValueError:
                    number = num
                    confidence = 0
            original_number = number
            if number == 'q':
                number = '9'
            num_results.append((number, confidence, location))

            self.bank_pin.pins[number] = location
            # # number = ui.read_screen(x1=ix, y1=iy, x2=ix + width, y2=iy + height, output_type='string', config='--psm 10')
            if visualise or logging:
                if original_number != number:
                    num_string = f'{number} > {original_number}'
                else:
                    num_string = f'{number} > {original_number} ({confidence})'

                cv2.putText(
                    img_copy,
                    num_string,
                    (ix + 15, iy + 15), cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, (255, 255, 255), lineType=cv2.LINE_AA
                )
                cv2.rectangle(
                    img_copy,
                    (ix, iy), (ix + self.bank_pin.width, iy + self.bank_pin.height),
                    (255, 255, 255), 2
                )

        # once more for 10th bank pin slot
        ix = int(x + ((self.bank_pin.width + self.bank_pin.x_gap) * (3 % 4)) - 10)
        iy = int(y + ((self.bank_pin.height + self.bank_pin.y_gap) * (3 // 4)))

        location = {
            'x1': self.bank_pin.img_x + ix,
            'y1': self.bank_pin.img_y + iy,
            'x2': self.bank_pin.img_x + ix + self.bank_pin.width,
            'y2': self.bank_pin.img_y + iy + self.bank_pin.height,
            'index': 10
        }

        ocr_result = self.read_screen(
            **location,
            thresh_mode=[self.main_screen.bank_pin_orange],
            config=ocr_config)

        for n, num in enumerate(ocr_result['text']):
            try:
                number = int(num)
                confidence = ocr_result['conf'][n]
                break
            except ValueError:
                number = num
                confidence = 0
        original_number = number
        if number == 'q':
            number = '9'

        num_results.append((number, confidence, location))

        if visualise or logging:
            if original_number != number:
                num_string = f'{number} > {original_number}'
            else:
                num_string = f'{number} > {original_number} ({confidence})'

            cv2.putText(
                img_copy,
                num_string,
                (ix + 25, iy + 25), cv2.FONT_HERSHEY_SIMPLEX,
                1.0, (255, 255, 255), lineType=cv2.LINE_AA
            )
            cv2.rectangle(
                img_copy,
                (ix, iy), (ix + self.bank_pin.width, iy + self.bank_pin.height),
                (255, 255, 255), 2
            )

            if logging:
                cv2.imwrite(self.sample_path, img_copy)

        for i in range(10):
            # get number match that corresponds to number
            matches = [(n, c, l) for n, c, l in num_results if str(i) == n]
            if len(matches) == 1:
                # if we only have one match then add it in
                number, confidence, location = matches[0]
            elif len(matches) > 1:
                # if we have more than one match pick the one we're most confident in
                number, confidence, location = max(matches, key=lambda x: x[1])
            else:
                number = None

            if number is not None:
                self.bank_pin.pins[number] = location

        print([(n, l['index']) for n, l in self.bank_pin.pins.items()])

        if visualise:
            cv2.imshow('pins', img_copy)
            cv2.waitKey(0)
            cv2.destroyWindow('pins')

    def click_box(self, **bbox):
        x, y = distribute_normally(**bbox)
        self.click_position(x, y)

    def click_position(self, x, y, button='left', pause=True):
        self.ahk.mouse_move(x, y)
        if pause:
            sleep(random.randint(100, 200) / 1000)
        if button == 'left':
            self.ahk.click()
        elif button == 'right':
            self.ahk.right_click()

    def _load_items(self, items):
        """
        Loads item images into memory
        :return: dictionary of image matrixes
        """
        d = {}
        p = f'{self.items_path}{os.sep}*.png'
        if items == 'all':
            for fpath in glob(p):
                item_name = os.path.splitext(os.path.basename(fpath))[0]
                d[item_name] = cv2.imread(fpath)
        elif type(items) is list:
            for item_name in items:
                fpath = f'{self.items_path}{os.sep}{item_name}.png'
                d[item_name] = cv2.imread(fpath)
        else:
            raise ValueError('unrecognised item specification')

        return d

    def what_do_i_have(self):
        # see if inventory is open
        if self.current_tab != 'inventory':
            # open if not
            x, y = distribute_normally(**self.tab_locations['inventory'])
            self.ahk.mouse_move(x, y)
            sleep(random.randint(200, 500) / 1000)
            self.ahk.click()

        # assume correct equipment is on (for now)

        # check inventory contents
        sleep(random.randint(200, 500) / 1000)
        self.check_inventory()

    def inventory_coords(self, p):
        """
        returns x1, y1, x2, y2 for inventory slot in position p
        x = INVENTORY_TOP_LEFT[0] + ((INVENTORY_WIDTH + INVENTORY_WIDTH_OFFSET) * (i % ITEMS_PER_ROW))
        y = INVENTORY_TOP_LEFT[1] + ((INVENTORY_HEIGHT + INVENTORY_HEIGHT_OFFSET) * (i // ITEMS_PER_ROW))
        :param p: index of inventory slot
        :return: dict
        """
        x1 = self.inventory['slot1_x'] + (
                (self.inventory['slot_width'] + self.inventory['slot_width_offset']) * (
                p % self.inventory['items_per_row'])
        )
        y1 = self.inventory['slot1_y'] + (
                (self.inventory['slot_height'] + self.inventory['slot_height_offset']) * (
                p // self.inventory['items_per_row'])
        )
        x2 = x1 + self.inventory['slot_width']
        y2 = y1 + self.inventory['slot_height']

        return {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}

    def inventory_set(self):
        s = set()
        for item in self.inventory['contents']:
            s.add(item)
        return s

    def check_inventory(self, logging=False):
        # TODO: add edge detection to check if unknown objects are in inventory

        for i in range(28):

            contents = self.inventory['contents']
            checked_at = self.inventory['checked_at']

            slot_img = grab_screen(**self.inventory_coords(i))
            slot_img_gray = cv2.cvtColor(slot_img, cv2.COLOR_BGRA2GRAY)

            # check if slot image is empty
            slot_img_canny = cv2.Canny(slot_img, 50, 200)
            if not cv2.countNonZero(slot_img_canny):
                contents[i] = 'empty'
                checked_at[i] = datetime.datetime.now()
                continue
            # logging = True
            if logging:
                cv2.imwrite(f'{runescape.__path__[0]}{os.sep}sample{os.sep}slot{i}.png', slot_img)

            max_match = None
            matched_item = None
            for item_name, item_img in self.items.items():
                item_img_gray = cv2.cvtColor(item_img, cv2.COLOR_BGRA2GRAY)
                match = cv2.matchTemplate(slot_img_gray, item_img_gray, cv2.TM_CCOEFF_NORMED)[0][0]

                if max_match is None:
                    max_match = match
                    matched_item = item_name
                elif match > max_match:
                    max_match = match
                    matched_item = item_name

            threshold = 0.8
            if max_match > threshold:
                if contents[i] != matched_item:
                    contents[i] = matched_item
                    checked_at[i] = datetime.datetime.now()
            else:
                # print(f" came up unknown: {cv2.countNonZero(slot_img_canny)}")
                contents[i] = 'empty'  # assume it's empty for now
                checked_at[i] = datetime.datetime.now()
        self.logger.info(f" inventory: {self.now_string} {self.inventory['contents']}")

    def read_screen(self, y1=37, x1=0, x2=200, y2=62, **kwargs):
        """
        Reads a section of the screen using OCR and returns the text it finds.
        By default it is used to read what the left mouse click option currently reads in the RuneScape client
        It can be configured to read any area on screen, but works best one line at a time.
        :param top: bounding box top left y coordinate
        :param left: bounding box top left x coordinate
        :param width: width of bounding box in pixels
        :param height: height of bounding box in pixels
        :return: dict of values in lists
        """
        output_type = kwargs.get('output_type') if kwargs.get('output_type') is not None else 'data'
        show = kwargs.get('show') is True # defaults to false
        thresh_mode = kwargs.get('thresh_mode') if kwargs.get('output_type') is not None else 'normal'
        config = kwargs.get('config')

        # convert to gryay and threshhold
        if thresh_mode == 'normal':
            img = grab_screen(x1=x1, y1=y1, x2=x2, y2=y2, cvt=cv2.COLOR_BGR2GRAY)
            gray = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        elif thresh_mode == 'white text':
            img = grab_screen(x1=x1, y1=y1, x2=x2, y2=y2)
            gray = cv2.inRange(img, (150, 150, 150), (255, 255, 255))
        elif type(thresh_mode) is list or type(thresh_mode) is tuple:
            img = grab_screen(x1=x1, y1=y1, x2=x2, y2=y2)
            masks = []  # new_img = numpy.zeros_like(img)
            for lower, upper in thresh_mode:
                mask = cv2.inRange(img, lower, upper)
                masks.append(mask)

            # combine masks
            if len(masks) > 1:
                gray = cv2.bitwise_or(*masks)
            else:
                gray = masks[0]
            # masked = cv2.bitwise_and(img, img, mask=m)
            # gray = cv2.cvtColor(masked, cv2.COLOR_BGR2GRAY)
        # resize
        # cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_LINEAR)

        if show is True:
            cv2.imshow('read', gray)
            cv2.waitKey(0)
            cv2.destroyWindow('read')
        if kwargs.get('logging'):
            cv2.imwrite(self.sample_path, img)
        # if config is None:
        #     config = ''

        # grab text with tesseract
        if output_type == 'string':
            if config:
                return pytesseract.image_to_string(gray, config=config)
            else:
                return pytesseract.image_to_string(gray)
        elif output_type == 'data':
            if config:
                return pytesseract.image_to_data(gray, output_type=Output.DICT, config=config)
            else:
                return pytesseract.image_to_data(gray, output_type=Output.DICT)

    def activate_runescape(self):
        if not self.is_open:
            self.launch_client()
            self.window = self.update_window()
        if not self.is_active:
            self.window = self.update_window()
            self.window.activate()
        if not self.is_full_screen:
            full_x, full_y, full_w, full_h = self.ahk_full_screen
            self.window.move(full_x, full_y, width=full_w, height=full_h)

    def launch_client(self):
        self.logger.info(f' {self.now_string} launching runescape client')
        subprocess.Popen([r'C:\Users\Edi\jagexcache\jagexlauncher\bin\JagexLauncher.exe', 'oldschool'])
        launch_time = datetime.datetime.now()
        # wait until client window available
        while not self.is_active:
            # check for timeout
            if (self.now - launch_time).seconds > 30:
                self.logger.error(f' {self.now_string} jagex launcher time out')
                raise Exception('Could not open jagex launcher')


def roi(img, vertices):
    mask = numpy.zeros_like(img)
    cv2.fillPoly(mask, vertices, 255)
    masked = cv2.bitwise_and(img, mask)
    return masked


def process_img(original_image, vertices):
    processed_img = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY)
    processed_img = cv2.Canny(processed_img, threshold1=200, threshold2=300)
    # vertices = numpy.array([[10,500],[10,300], [300,200], [500,200], [800,300], [800,500]], numpy.int32)
    processed_img = roi(processed_img, [vertices])
    return processed_img


def grab_screen(x1=0, y1=0, x2=0, y2=0, cvt=cv2.COLOR_BGRA2BGR):
    hwin = win32gui.GetDesktopWindow()

    width = x2 - x1 + 1
    height = y2 - y1 + 1

    hwindc = win32gui.GetWindowDC(hwin)
    srcdc = win32ui.CreateDCFromHandle(hwindc)
    memdc = srcdc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(srcdc, width, height)
    memdc.SelectObject(bmp)
    memdc.BitBlt((0, 0), (width, height), srcdc, (x1, y1), win32con.SRCCOPY)

    signedIntsArray = bmp.GetBitmapBits(True)
    img = numpy.fromstring(signedIntsArray, dtype='uint8')
    img.shape = (height, width, 4)

    srcdc.DeleteDC()
    memdc.DeleteDC()
    win32gui.ReleaseDC(hwin, hwindc)
    win32gui.DeleteObject(bmp.GetHandle())

    # grabs BGRA by default so choose BGRA2<something>
    return cv2.cvtColor(img, cvt)  # cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)

def humanly_enter_key(key):
    PressKey(MAP[f'DIK_{key.upper()}'])
    sleep(random.randint(200, 500) / 1000)
    ReleaseKey(MAP[f'DIK_{key.upper()}'])


def rs_active(ahk, logger, force_activate=True):
    """
    Checks if runescape client is active window, activates if not active, starts app if not open
    :return: True/False
    """

    # check windows
    rs_win_name = b'Old School RuneScape'
    win = ahk.find_window(title=rs_win_name)
    current_active_window_title = ahk.active_window.title

    # record time for logging
    now = datetime.datetime.now()
    now_string = now.strftime('%x %X.%f')

    if not win:
        # launch jagex client
        subprocess.Popen([r'C:\Users\Edi\jagexcache\jagexlauncher\bin\JagexLauncher.exe', 'oldschool'])
        launch_time = datetime.datetime.now()
        # wait until client window available
        while not win:
            win = ahk.find_window(title=rs_win_name)
            now = datetime.datetime.now()
            now_string = now.strftime('%x %X.%f')
            # check for timeout
            if (now - launch_time).seconds > 30:
                logger.error(f' {now_string} TIMEOUT: JagexLauncher taking too long')
                return False
        # activate!
        logger.info(f' {now_string} activating runescape client window from launch')
        win.activate()
        return True
    elif current_active_window_title != rs_win_name and force_activate:
        # activate!
        logger.info(f' {now_string} activating runescape client window')
        win.activate()
        return True
    elif current_active_window_title != rs_win_name and not force_activate:
        # don't activate!
        return False
    else:
        # all good in the good
        return True


def get_auto_hot_key():
    return AHK(executable_path=r'C:\Program Files\AutoHotkey\AutoHotKey.exe')


def distribute_normally(x1=0, x2=1950, y1=0, y2=1050):
    centre = x1 + (x2 - x1) / 2, y1 + (y2 - y1) / 2

    x = numpy.random.normal(loc=centre[0], scale=(x2 - x1) / 8)
    y = numpy.random.normal(loc=centre[1], scale=(y2 - y1) / 8)

    # failsafe to make sure not out of bounds
    if x < x1:
        x = x1
    if x > x2:
        x = x2
    if y < y1:
        y = y1
    if y > y2:
        y = y2

    return int(x), int(y)


def bincount_app(a):
    a2D = a.reshape(-1,a.shape[-1])
    col_range = (256, 256, 256) # generically : a2D.max(0)+1
    a1D = numpy.ravel_multi_index(a2D.T, col_range)
    return numpy.unravel_index(numpy.bincount(a1D).argmax(), col_range)


def line_intersection(line1, line2):
    xdiff = (line1[0][0] - line1[1][0], line2[0][0] - line2[1][0])
    ydiff = (line1[0][1] - line1[1][1], line2[0][1] - line2[1][1])

    def det(a, b):
        return a[0] * b[1] - a[1] * b[0]

    div = det(xdiff, ydiff)
    if div == 0:
       return
       # raise Exception('lines do not intersect')

    d = (det(*line1), det(*line2))
    x = det(d, xdiff) / div
    y = det(d, ydiff) / div
    return x, y


def find_anchor(anchor, text):
    index = 0
    while len(text) > len(anchor):
        if text[:len(anchor)] == anchor:
            print(text[:len(anchor)])
            return index
        index += 1
        text = text[1:]


def get_logger(logger_name):
    # TODO: does this belong in a different module? System functions?
    logging_path = f'C:\\Users\\Edi\\Desktop\\programming\\runescape\\logs\\{logger_name}.log'
    logging.basicConfig(filename=logging_path, level=logging.INFO)
    return logging.getLogger(logger_name)
