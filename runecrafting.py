from rsUserInterface import UserInterface, BankPin, grab_screen, distribute_normally, find_anchor
from rsPathFinding import *
from time import sleep
import random
import math
from rsVisualisation import GUthIx
import winsound
import traceback

script_start = datetime.datetime.now()

class NopeDead(Exception):
    print('nope, you died of boredom.')

def time_out(t, m=10):
    if (datetime.datetime.now() - t).seconds > m:
        raise NopeDead()

class RuneCrafter:

    def __init__(self, rune_type=None):
        self.started_at = datetime.datetime.now()
        self.rune_type = rune_type

        # TODO: cache this out elsewhere
        self.maps = {
            None: ['varrock_east', 'essence_mine'],
            'chaos': ['varrock_east', 'chaos_tunnel', 'chaos_alter_2', 'chaos_alter_1']
        }

        self.ui = UserInterface()
        self.gps = GielinorPositioningSystem(self.ui, search_range=self.maps[self.rune_type])
        self.actions = []
        self.job_done = False
        self.logged_in = False
        self.trg_x, self.trg_y = None, None
        self.logger = get_logger('rcbot')

        # TODO: cache these out somewhere (and encrypt?)
        self.username = os.environ['RS_USERNAME']
        self.password = os.environ['RS_PASSWORD']
        self.pin = os.environ['RS_PIN']

    def thinking_time(self):
        sleep(random.randint(150, 400) / 1000)

    def full_start(self):

        if not self.logged_in:
            # navigate log in screen
            self.ui.log_in(self.username, self.password)

            # wait for game to load (assume area where minimap will be is all black on login screen)
            m = self.ui.mini_map.gray_img
            while not cv2.countNonZero(m):
                sleep(0.5)
                m = self.ui.mini_map.gray_img
        else:
            self.ui.activate_runescape()

        # calibrate maps and inventory
        self.gps.where_am_i()
        print(f"OK, so I'm in {self.gps.current_map.name}")
        self.ui.what_do_i_have()
        print(f"Hmm, I have {self.ui.inventory['contents']}")

    def go_to_bank(self):
        (bank_x, bank_y), (tx, ty) = self.gps.find_node(
            self.gps.current_map.BANK,
            search_type='nearest'
        )
        self.trg_x, self.trg_y = bank_x, bank_y
        self.gps.go_to(tx, ty)

        # give some time to catch up to last checkpoint
        sleeps = 0
        while hypotenuse(self.gps.locate_in_map(self.gps.current_map)['self_xy'], (tx, ty)) > 5:
            if sleeps < 3:
                break
            print('sleeping')
            time.sleep(0.5)
            sleeps += 0.5

        # set target back to none?
        print('we are are at the bank now')
        # self.trg_x, self.trg_y = None, None

    def which_bank_screen(self):
        t = datetime.datetime.now()
        while True:
            for n in [1, 2]:
                if n == 1:
                    print('are we on screen 1?')
                    screen = self.ui.read_screen(
                        **self.ui.bank_screen1,
                        thresh_mode=[self.ui.main_screen.red_text],
                        output_type='string',
                        # show=True
                    ).lower()
                    if 'bank of gielinor' in screen:
                        print('yup')
                        return n
                    print('nope')
                elif n == 2:
                    print('are we on screen 2?')
                    screen = self.ui.read_screen(
                        **self.ui.bank_screen2,
                        thresh_mode=[self.ui.main_screen.orange_text],
                        output_type='string',
                        # show=True
                    ).lower()
                    if 'the bank of gielinor' in screen:
                        print('yup')
                        return n
                    elif 'tab 1' in screen:
                        print('pretty much')
                        return n+1
                    print('nope', screen)
                time_out(t)

    def click_target(self, target_texts, thresh_mode):
        """
        Uses ocr to check if mouse left click option at current target position is the one
         we want to click and then clicks it verified it
        :param target_texts: string or list of strings always lower case
        :param thresh_mode: list of upper, lower bounds for colour threshing on text
        """

        if type(target_texts) is str:
            target_texts = [target_texts]

        found_target = False
        check_count = 0

        dt = datetime.datetime.now()
        while not found_target:
            # calculate position of target relative to self
            self.gps.locate_in_map(self.gps.current_map)
            self_x, self_y = self.gps.current_map.xy
            rel_x, rel_y = self.trg_x - self_x, self.trg_y - self_y
            if self.gps.is_visible((self_x, self_y), (self.trg_x, self.trg_y), 'main_screen'):
                px, py = self.ui.main_screen.relative_position(rel_x, rel_y)
            elif hypotenuse((self_x, self_y), (self.trg_x, self.trg_y)) > 1:
                self.gps.force_go(self.trg_x, self.trg_y)
            else:
                # if we can't see it, back it up
                self.ui.change_zoom(random.randint(-5, 0))
                continue

            # move mouse there and read mouse screen
            # print(f'looking for essence at {self.trg_x},{self.trg_y}')
            self.ui.ahk.mouse_move(px, py)
            self.thinking_time()
            text = self.ui.read_screen(
                thresh_mode=thresh_mode,
                output_type='string',
                config='--psm 7',
            )

            for t in target_texts:
                if t in text.lower():

                    self.ui.ahk.click()
                    found_target = True
                    break
            print(f'cannot find {target_texts} in {text}')
            check_count += 1
            time_out(dt)

            if check_count > 3:
                # we should be able to see it but can't
                # give a little wiggle
                self.ui.change_zoom(random.randint(-check_count, check_count))

            # if check_count > 5:
            #     # TODO: add some better exception handling here
            #     # either the mouse is in the wrong position (try circling around?)
            #     # 'walk here' is the default option in most cases if the mouse is off, so this would tip this off
            #     # or the text is being obscured by what's behind it (try different ocr settings / moving the camera?)
            #     print(f'what the fuck does {text} mean?')
            #     self.ui.ahk.click()
            #     return 1
        print(f'found after {check_count} tries')

    def open_bank(self):
        print('opening the bank')

        # while not found_booth:
        tm = [self.ui.main_screen.white_text, self.ui.main_screen.cyan_text]
        self.click_target(['bank', 'bank booth'], tm)

        # check pin buttons and enter pin
        if not self.ui.bank_pin.pin_entered or self.ui.current_tab != 1:

            # wait for pin screen to load / check if we somehow jump straight to screen 2
            s = self.which_bank_screen()
            if s > 1:
                self.ui.bank_pin.pin_entered = True

            # if we're on screen 1 then we should enter the pin
            if not self.ui.bank_pin.pin_entered:
                # locate pins screen
                self.ui.pin_buttons()
                for d in self.pin:
                    # check what's in the each box
                    self.ui.update_pin()
                    # time.sleep(1)
                    if d in self.ui.bank_pin.pins:
                        # print(self.ui.bank_pin.pins[d])
                        self.ui.click_box(**self.ui.bank_pin.pins[d])

                        rx, ry = self.ui.bank_pin.hover_off_pin()
                        self.ui.ahk.mouse_move(rx, ry)
                        self.thinking_time() # give the rs ui a second to update
                    else:
                        return 1
                self.ui.bank_pin.pin_entered = True

            if self.ui.bank_pin.current_tab != 1 and s == 2:
                t = datetime.datetime.now()
                while 'the bank of gielinor' not in self.ui.read_screen(
                        **self.ui.bank_screen2,
                        thresh_mode=[self.ui.main_screen.orange_text],
                        output_type='string').lower():
                    self.thinking_time()
                    time_out(t)
                rs_data = self.ui.read_screen(**self.ui.bank_tabs)
                for t, w in enumerate(rs_data['text']):
                    if '1' in w:
                        self.ui.click_position(
                            self.ui.bank_tabs['x1'] + rs_data['left'][t],
                            self.ui.bank_tabs['y1'] + rs_data['top'][t]
                        )
                        self.ui.bank_pin.current_tab = 1
                        break
        print('the bank is open now')

    def deposit_item(self, item_name):
        """
        Assumes 'deposit all' is already configured and bank is already open
        """

        # double check contents of inventory
        self.ui.check_inventory()

        # pick a random inventory slot that has the item
        i = random.randint(0, 27)
        while self.ui.inventory['contents'][i] != item_name:
            i = random.randint(0, 27)


        x, y = distribute_normally(**self.ui.inventory_coords(i))

        self.ui.ahk.mouse_move(x, y)
        self.thinking_time()
        self.ui.ahk.click()
        self.thinking_time()

        # # check inventory has been emptied
        # # TODO: find a better way of checking for empty slots and then implement this
        # self.ui.check_inventory()
        # while item_name in self.ui.inventory['contents']:
        #     print(f'''the {item_name} is not gone yet... see: f{self.ui.inventory['contents']}''')
        #     self.ui.check_inventory()

    def deposit_essence(self):
        print('depositing essence')
        self.deposit_item('pure_essence')
        print('essence deposited')

    def go_to_aubrey(self):
        print('''going to aubrey's shop''')

        # get aubrey coords
        # TODO: add support for camera rotation
        coords = self.gps.current_map.config.get('aubrey_shop')
        self.trg_x, self.trg_y = coords[random.randint(0, len(coords)-1)]

        self.gps.go_to(self.trg_x, self.trg_y, min_distance=2)
        # TODO: add in check for door

        print('''we are at aubrey's shop now''')

    def teleport_aubrey(self):
        """
        Finds aubrey on screen, right clicks and selects 'teleport aubrey' option
        """
        coords = self.gps.maps['varrock_east'].config['aubrey_shop']
        found_aubrey = False
        t = datetime.datetime.now()

        while not found_aubrey:

            # search mini map for yellow dots
            if self.gps.is_moving():
                self.gps.locate_in_map(self.gps.current_map)
            elif self.gps.current_map.xy not in coords:
                self.gps.force_go(self.trg_x, self.trg_y)
                self.thinking_time()
                self.gps.locate_in_map(self.gps.current_map)


            # assume closest yellow dot is aubrey
            npcs = self.gps.locate_npcs()
            print('new batch of npcs')
            for npc_x, npc_y in npcs:
                if npc_x in [x for x, y in coords] and npc_y in [y for x, y in coords]:
                    # convert npc coords relative to player
                    rel_x = npc_x - self.gps.current_map.x
                    rel_y = npc_y - self.gps.current_map.y

                    if not self.gps.is_visible(self.gps.current_map.xy, (npc_x, npc_y), 'main_screen'):
                        self.ui.change_zoom(random.randint(-5, 0))
                        continue
                    # print(rel_x, rel_y)

                    # convert to screen coords
                    px, py = self.ui.main_screen.relative_position(rel_x, rel_y)
                    # right-click there
                    self.ui.click_position(px, py, button='right', pause=False)

                    self.thinking_time()
                    screen = self.ui.read_screen(
                        x1=px-150, y1=py, x2=px+100, y2=py+100,
                        thresh_mode='white text'
                    )

                    # look for 'teleport aubrey' option
                    if 'teleport' in ' '.join(screen['text']).lower():
                        found_aubrey = True
                        break
                    # if it's not there, try again
                    else:
                        # move the mouse off the right click box
                        self.ui.ahk.mouse_move(
                            random.randint(px-20, px+20), random.randint(py-50, py-20))
            time_out(t)

        # click dat shit
        n = find_anchor(['Teleport'], screen['text'])
        px2_min = px-150 + screen['left'][n]
        py2 = py + screen['top'][n]
        x, y = distribute_normally(px2_min, px2_min + 50, py2 - 5, py2 + 5)

        self.ui.click_position(x, y)
        print('teleportation baby!')
        t = datetime.datetime.now()

        while self.gps.current_map.name != 'essence_mine':
            self.gps.where_am_i()
            print(f'still in {self.gps.current_map.name} :(')
            time_out(t)
        print('we are down the mines!')

    def go_to_essence_rock(self):
        (ess_x, ess_y), (tile_x, tile_y) = self.gps.find_node(
            self.gps.current_map.RUNE_ESSENCE, search_type='nearest'
        )
        self.trg_x, self.trg_y = ess_x, ess_y
        if hypotenuse((ess_x, ess_y), (self.gps.current_map.xy)) > 3:
            print(f'going to {tile_x}, {tile_y} next to essence at {ess_x}, {ess_y}')
            self.gps.go_to(tile_x, tile_y, min_distance=2)
            print('we have arrived!')
        else:
            print('shazam bitch, we already here!')

    def mine_pure_essence(self):
        print('starting mining')

        waits = 0
        while abs(self.trg_x - self.gps.current_map.x) > 1 or abs(self.trg_y - self.gps.current_map.y) > 1:
            self.gps.locate_in_map(self.gps.current_map)
            self.thinking_time()

            waits += 1
            if waits > 3:
                if not self.gps.is_moving():
                    print('I thought we were there already!?')
                    if hypotenuse((self.trg_x, self.trg_y), self.gps.current_map.xy) > 1:
                        self.gps.force_go(self.trg_x, self.trg_y)
                    else:
                        print('eh, close enough')
                        break
                waits = 0

        colours = [self.ui.main_screen.white_text, self.ui.main_screen.cyan_text]
        self.click_target(['rune essence', 'rune', 'ess'], colours)
        self.ui.check_inventory()

        checked_at = self.ui.inventory['checked_at']
        mining_start_at = datetime.datetime.now()
        # TODO: write a function that checks for full inventory (specifying what constitutes 'full')
        t = datetime.datetime.now()
        while 'empty' in self.ui.inventory['contents']:
            self.ui.check_inventory()
            time.sleep(1)
            time_out(t, m=30)

            if (datetime.datetime.now() - mining_start_at).seconds > 3:
                if (datetime.datetime.now() - max(checked_at)).seconds > 3:
                    print('must mine harder!')
                    self.click_target('rune essence', colours)
                    self.ui.check_inventory()

        print(f"full load: {self.ui.inventory['contents']}")
        winsound.Beep(200, 200)

    def go_to_portal(self):
        (px, py), (tx, ty) = self.gps.find_node(self.gps.current_map.PORTAL, search_type='nearest')
        print(f'going to portal at {px}, {py}')
        self.trg_x, self.trg_y = px, py
        self.gps.go_to(tx, ty, min_distance=2)
        print('preparing for teleportation')

    def enter_portal(self):
        print('entering the void')
        colours = [self.ui.main_screen.white_text, self.ui.main_screen.cyan_text]
        self.click_target(['portal', 'use', 'exit'], colours)
        t = datetime.datetime.now()
        while self.gps.current_map.name != 'varrock_east':
            self.gps.where_am_i()
            time_out(t)
        print('we are back in varrock, baby!')

    def craft_chaos_runes(self):

        self.actions = [
            self.open_bank,
            self.deposit_chaos_runes,
            self.withdraw_pure_essence,
            self.go_to_statue,
            self.enter_statue,
            self.go_to_portal1,
            self.enter_portal1,
            self.go_to_ladder,
            self.go_down_ladder,
            self.go_to_alter,
            self.craft_runes,
            self.go_up_ladder,
            self.go_to_portal2,
            self.enter_portal2,
            self.climb_stairs,
            self.go_to_bank
        ]

        # determine first action
        first_action = None

        self.do_actions(first_action)

        # open bank
        # deposit runes (if any)
        # withdraw pure essence (if remaining)
        # go to mysterious ruins
        # enter mysterious ruins
        # go to altar
        # craft runes
        # go to portal
        # enter portal
        # go to bank



    def mine_essence(self):

        self.actions = [
            self.open_bank,
            self.deposit_essence,
            self.go_to_aubrey,  # 45 83
            # check door     is open
            self.teleport_aubrey,
            self.go_to_essence_rock,
            self.mine_pure_essence,
            self.go_to_portal,
            self.enter_portal,
            self.go_to_bank
        ]

        # determine first action
        current_location = self.gps.current_map.name
        if current_location == 'varrock_east':
            one_item = set(self.ui.inventory['contents']) == 1
            all_essence = 'pure_essence' in self.ui.inventory['contents']
            if all_essence:
                first_action = 'go_to_bank'
            elif 'empty' in self.ui.inventory['contents']:
                first_action = 'go_to_aubrey'
            else:
                first_action = 'bank_shit'
        elif current_location == 'essence_mine':
            # one_item = set(self.ui.inventory['contents']) == 1
            # all_essence = 'pure_essence' in self.ui.inventory['contents']
            if 'empty' not in self.ui.inventory['contents']:
                print("we are full of essence(?), let's go bank it")
                first_action = 'go_to_portal'
            else:
                print("we've got space left, let's mine up a storm")
                first_action = 'go_to_essence_rock'
        else:
            first_action = 'complain_loudly'

        if first_action in ['bank_shit', 'bank_shit2', 'complain_loudly']:
            # TODO: implement these actions
            print(f"how do I {first_action}???")
            for _ in range(10):
                print("loud noises!!")
                winsound.Beep(200, 200)
            import sys
            sys.exit()

        self.do_actions(first_action)

    def do_actions(self, first_action):
        while self.actions[0].__name__ != first_action:
            self.actions.append(self.actions.pop(0))

        while not self.job_done:
            action = self.actions[0]
            action()
            self.actions.append(self.actions.pop(0))

def anywhere(r):

    import random
    max_y, max_x, _ = r.gps.current_map.current_grid.shape
    trg_x = random.randint(0, max_x-1)
    trg_y = random.randint(0, max_y-1)

    while list(r.gps.current_map.current_grid[trg_y][trg_x]) != r.gps.current_map.WHITE:
        trg_x = random.randint(0, max_x-1)
        trg_y = random.randint(0, max_y-1)

    print('random target selected', trg_x, trg_y)
    return trg_x, trg_y


def polygon(sides, radius=1, rotation=0, translation=None):
    one_segment = math.pi * 2 / sides

    points = [
        (math.sin(one_segment * i + rotation) * radius,
         math.cos(one_segment * i + rotation) * radius)
        for i in range(sides)]

    if translation:
        points = [[sum(pair) for pair in zip(point, translation)]
                  for point in points]

    return points


def go_anywhere(r):
    r.gps.go_to(*anywhere(r))

# r = RuneCrafter()
# ui = UserInterface()
# gps = GielinorPositioningSystem(ui, search_range=['varrock_east'])
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

bc = bcolors()

# ====================================================================
# the actual bot
# self = RuneCrafter()
# self.ui.bank_pin.pin_entered = True
# self.ui.main_screen.zoom = 1
# self.logged_in = True
# self.ui.current_tab = 'inventory'
# while not self.job_done:
#     try:
#         self.full_start()
#         self.mine_essence()
#     except:
#         t = datetime.datetime.now() - self.started_at
#         traceback.print_exc()
#         print(f'{bc.WARNING} bot died after {t.seconds // 60}m {t.seconds % 60}s{bc.ENDC}')
#         self.logger.warning(f'bot died after {t.seconds // 60}m {t.seconds % 60}s{bc.ENDC}')
#         self.started_at = datetime.datetime.now()
#         self.ui.change_zoom(random.randint(-30, -20))
# ====================================================================



# ====================================================================
# testing a map  (65, 60)
self = RuneCrafter()
self.ui.activate_runescape()
self.gps.where_am_i()
GUthIx(self.gps, self.gps.current_map.name)
# ====================================================================



# self.ui.check_inventory()
# self.gps.current_tab = 'inventory'

# self.ui.what_do_i_have()
# self.go_to_bank()
# self.open_bank()
# self.deposit_essence()
# self.go_to_aubrey()
# self.teleport_aubrey()

# go_anywhere(self)

# self.go_to_essence_rock()
# self.mine_pure_essence()
# self.go_to_portal()
# self.enter_portal()
#



# self.ui.log_in(self.username, self.password)
# a = set()
# while self.ui.is_active:
#     x, y = self.gps.locate_in_map(self.gps.maps['varrock_east'])['self_xy']
#     print(x, y)
# import sys
# sys.exit()
#     a.add((x, y))
#
# print(a)
# self.gps.where_am_i()
# self.gps.locate_npcs()
# self.full_start()
# self.go_to_bank()
# self.open_bank()
# self.deposit_essence()
# go_anywhere(self)
# self.go_to_aubrey()
# self.teleport_aubrey()
# self.open_bank()

# r.ui.log_in(r.username, r.password)
# self.gps.where_am_i()
# r.full_start()
# time.sleep(2)
# title = {'x1': 420, 'x2': 640, 'y1': 180, 'y2': 230}
#
# cv2.imshow('bank', grab_screen(**self.ui.bank_screen))
# cv2.waitKey(0)
# cv2.destroyWindow('bank')
#
# rs_data = self.ui.read_screen(**self.ui.bank_screen)
# # for k, v in rs_data.items():
# #     print(k, ':', v)
#
# anchor = ['Please', 'enter', 'your', 'PIN', 'using', 'the', 'buttons', 'below.']
# text = rs_data['text']
#
# for i, word in enumerate(text):
#     if word == 'enter' and text[i+1] == 'your' and text[i+2] == 'PIN':
#         self.ui.ahk.mouse_move(rs_data['left'][i], rs_data['top'][i])
#         break
# print(self.ui.ahk.mouse_position)
#
# print(text)
# i = find_anchor(anchor, text)
# print(i)
# mx, my = self.ui.bank_screen['x1'], self.ui.bank_screen['y1']
# pin_x, pin_y = mx + rs_data['left'][i], my + rs_data['top'][i]
#
# bp = BankPin(pin_x, pin_y)
#
# import winsound
# for d in self.pin:
#     for i in range(10):
#
#         if i == 0 or i == 9:
#             cv2.imshow(f'pin{i}', grab_screen(**bp.pins[i]))
#             cv2.waitKey(0)
#             cv2.destroyWindow(f'pin{i}')
#
#         value = self.ui.read_screen(**bp.pins[i], config='--psm 10', output_type='string')
#         print(i, value)
#         if value.strip() == d:
#             print(f'click pin slot {d}')
#             break
#         winsound.Beep(200, 200)
#     break
#
# winsound.Beep(200, 200)
#
# # self.ui.ahk.mouse_move(mx + rs_data['left'][i], my + rs_data['top'][i])
# # print(self.ui.ahk.mouse_position)
# #
# # bank1_x1, bank1_y1 = 464, 307
# # px1, py1 = 567, 242
# # bank1_x2, bank1_y2 = 557, 400
# # prel_x, prel_y = -103, 65
# #
# # bank4_x1, bank4_y1 = 462, 416
# # bank2_x1, bank2_y1 = 604, 307
# #
# #
# #
# # import winsound
# # winsound.Beep(200, 200)
# #
# # # go_anywhere(self)
