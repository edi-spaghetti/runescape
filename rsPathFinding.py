# a collection of functions for the purpose of creating and interpreting map information
from matplotlib import pyplot
import matplotlib
import numpy
import math
import os
import ctypes
import logging
import datetime
import json
import cv2
import imutils
import time
import random
from collections import defaultdict
from copy import deepcopy

import runescape
from runescape.rsUserInterface import get_logger
from bot_functions import dictate, BLUE, RED, BLACK
# from bot_functions import BLUE, RED, GREEN, BLACK, hypotenuse
# from rsUserInterface import get_auto_hot_key


class GielinorPositioningSystem:

    def __getitem__(self, item):
        if item in self.maps:
            return self.maps[item]

    def __init__(self, ui, search_range='all'):
        self.current_map = None
        self.ui = ui
        self.maps_path = f'{runescape.__path__[0]}{os.sep}maps'
        self.available_maps = os.listdir(self.maps_path)
        self.search_range = search_range
        self.logger = get_logger('gps')

        # init container and all selected maps
        self.maps = {}
        self.add_maps(search_range)

        # tracker for last 100 gps location calls
        self.tracker = [None for _ in range(100)]

    def _add_map(self, map_name):
        if map_name not in self.available_maps:
            raise Exception(f'unrecognised map: {map}')
        self.maps.setdefault(map_name, Map(self, map_name))
        map_ = self.maps.get(map_name)
        if not os.path.exists(map_.img_path) or not os.path.exists(map_.nodes_path):
            raise FileNotFoundError(f'missing map image or nodes files\n{map_.img_path}\n{map_.nodes_path}')

    def add_maps(self, search_range):
        if search_range == 'all':
            map_names = self.available_maps
        elif type(search_range) is list:
            map_names = search_range
        elif type(search_range) is str:
            map_names = [search_range]
        else:
            raise ValueError(f'incorrect format: {search_range}')

        for map_name in map_names:
            self._add_map(map_name)

    def where_am_i(self, auralise=False):
        """
        Checks against all loaded maps and determines which is most likely the correct current location
        :return:
        """
        locations = {}
        matched_map = None
        if self.ui.is_active:
            for map_name, map_ in self.maps.items():
                # perform template match and return confidence value
                # print(f'am i in {map_name}')
                locations[map_name] = self.locate_in_map(map_, update=False)
                if matched_map is None:
                    # print('maybe')
                    matched_map = map_
                elif locations[matched_map.name].get('max_val') < locations[map_name].get('max_val'):
                    # print('maybe')
                    matched_map = map_
                else:
                    pass
                    # print('nope')

        # return name of location most confident to have matched correctly
        if auralise is True:
            t = f"""you're in {matched_map.name}"""
            # print(t)
            dictate(t)
        self.locate_in_map(matched_map)
        self.current_map = matched_map

    def locate_in_map(self, map_, visualise=False, update=True):
        """
        Sample current minimap and return players coords + other info
        For consistency maps must be saved at 100 pixels per inch
        :param map_: Map class object
        :param sweet_spot: TODO: pre-calcualte optimum per map
        :param visualise:
        :param rotate:
        :return:
        """

        # sample minimap and convert to edge map
        mini_map = self.ui.mini_map.edge_map(map_)

        # cv2.imshow('mini_map', mini_map)
        # cv2.waitKey(0)
        # cv2.destroyAllWindows()

        tH, tW = self.ui.mini_map.height, self.ui.mini_map.width

        # initalise bookkeeping variable to keep track of the matched region
        found = None
        max_match = None
        matched_angle = 0

        # check for rotation
        revolutions = [0]
        if map_.config.get('rotate'):
            revolutions = [x for x in range(360) if not x % map_.config.get('rotate')]

        # TODO: cache out canny so we can load that directly
        map = deepcopy(map_.img)
        # calculate coords based on map ratio
        # map_max_x = int(map.shape[1] / MAP_RATIO)
        # map_max_y = int(map.shape[0] / MAP_RATIO)
        # # get centre of map coords
        # centre_image_x = int(map.shape[1] / 2)
        # centre_image_y = int(map.shape[0] / 2)

        scale_lower, scale_upper = map_.config.get('sweet_spot')
        # print('new', scale_lower, scale_upper)

        for angle in revolutions:
            rotated = imutils.rotate_bound(map, angle)
            gray = cv2.cvtColor(rotated, cv2.COLOR_BGR2GRAY)
            loop = 0
            # loop ovr the scales of the image up

            scale20 = numpy.linspace(0.2, 1.0, 20)[::1]
            for scale in scale20[scale_lower:scale_upper]:
                loop += 1
                # resize the image according to the scale
                # keep track of the ratio of resizing
                resized = imutils.resize(gray, width=int(gray.shape[1] * scale))

                r = gray.shape[1] / float(resized.shape[1])

                # make sure minimap is not bigger than map
                if not (resized.shape[0] < tH or resized.shape[1] < tW):

                    # detect edges in the resized, grayscale image
                    # apply template matching to find the template in the image
                    edged = cv2.Canny(resized, 50, 200)
                    result = cv2.matchTemplate(edged, mini_map, cv2.TM_CCOEFF)
                    (_, maxVal, _, maxLoc) = cv2.minMaxLoc(result)

                    # if we have found a new maximum correlation value update bookkeeping variable
                    if found is None or maxVal > found[0]:
                        found = (maxVal, maxLoc, r)
                        max_match = rotated
                        matched_angle = angle

        # unpack the bookkeeping variable
        # compute the (x, y) coordinates of bounding box based on resize ratio
        maxVal, maxLoc, r = found
        startX, startY = int(maxLoc[0] * r), int(maxLoc[1] * r)
        endX, endY = int((maxLoc[0] + tW) * r), int((maxLoc[1] + tH) * r)

        player_centreX = startX + int((endX - startX) / 2)
        player_centreY = startY + int((endY - startY) / 2)
        player_centre = player_centreX, player_centreY

        self_x = int(player_centreX / map_.pixels_per_tile)
        self_y = int(player_centreY / map_.pixels_per_tile)

        if visualise:
            # note: imutils rotates clockwise
            temp_img = imutils.rotate_bound(deepcopy(map_.img), matched_angle)
            # but numpy rotates counterclockwise
            temp_grid = numpy.rot90(map_.grid, -matched_angle // 90)
            # draw player
            cv2.circle(temp_img, player_centre, 2, BLUE, thickness=2, lineType=8, shift=0)

            # draw grid
            for ty, row in enumerate(temp_grid):
                for tx, element in enumerate(row):
                    tx1 = int(tx * map_.pixels_per_tile)
                    ty1 = int(ty * map_.pixels_per_tile)
                    tx2 = int(tx1 + map_.pixels_per_tile)
                    ty2 = int(ty1 + map_.pixels_per_tile)
                    colour = [int(x) for x in element]
                    cv2.rectangle(temp_img, (tx1, ty1), (tx2, ty2), colour, -1)

            cv2.imshow('max_match', temp_img)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        rdict = {
            'self_xy': (self_x, self_y),
            'matched_angle': matched_angle,
            'max_val': maxVal,
            'ratio': r
        }

        if update is True:
            map_.stats = rdict
            map_.xy = rdict['self_xy']
            map_.x, map_.y = rdict['self_xy']
            self._update_tracker(self_x, self_y, map_.name)

            if matched_angle != map_.angle:
                print(f'matched at angle {matched_angle}')
                map_.angle = matched_angle
                map_.current_grid = numpy.rot90(deepcopy(map_.grid), -matched_angle // 90)
        self.logger.info(f" {self.ui.now_string} located at {map_.name} {rdict['self_xy']} at {rdict['matched_angle']}d (conf: {rdict['max_val']})")

        return rdict

    def locate_npcs(self, show=False):
        """
        detects npc yellow dots in minimap and returns coordinates as a list
        :return:
        """
        img = self.ui.mini_map.img
        mask = cv2.inRange(
            img,
            self.ui.mini_map.npc_lower,
            self.ui.mini_map.npc_upper
        )

        r, c = mask.shape
        count = defaultdict(int)
        for y in range(r):
            for x in range(c):
                if mask[y][x] == 255:
                    # calculate coords relative to current position
                    rel_x = int((x - self.ui.mini_map.sample_size) / self.ui.mini_map.pixels_per_tile)
                    rel_y = int((y - self.ui.mini_map.sample_size) / self.ui.mini_map.pixels_per_tile)
                    # cv2.drawMarker(img,(x, y),(255, 0, 0),cv2.MARKER_CROSS,10)

                    # calculate coords in map based on current position
                    map_x = self.current_map.stats['self_xy'][0] + rel_x
                    map_y = self.current_map.stats['self_xy'][1] + rel_y

                    # count number of times we've found a yellow pixel at this location
                    count[map_x, map_y] += 1

        threshold = 7
        npcs = []
        for (x, y), t in count.items():
            if t > threshold:
                npcs.append((x, y))
                if show is True:
                    # back-calculate minimap pixels x,y
                    rel_x = x - self.current_map.stats['self_xy'][0]
                    rel_y = y - self.current_map.stats['self_xy'][1]
                    mm_x = int((rel_x * self.ui.mini_map.pixels_per_tile) + self.ui.mini_map.sample_size)
                    mm_y = int((rel_y * self.ui.mini_map.pixels_per_tile) + self.ui.mini_map.sample_size)

                    # draw on image
                    cv2.circle(img, (mm_x, mm_y), 4, (255, 0, 0), -1)

        if show is True:
            cv2.imshow('npc', img)
            cv2.waitKey(0)
            cv2.destroyWindow('npc')

        return npcs

    def _update_tracker(self, x, y, name):
        """
        Inserts latest tracked location name and time into tracker list
        """
        self.tracker.pop(-1)
        self.tracker.insert(0, (x, y, name, datetime.datetime.now()))

    def is_moving(self):
        """
        Works out the last time we moved
        :return:
        """

        # if tracker hasn't event started updating yet then we must have just logged in
        # and we'll assume we're ok for now
        if self.tracker[0] is None:
            return True

        lx, ly, _, dt = self.tracker[0]
        t = 1
        while self.tracker[t] is not None and t < len(self.tracker):
            nx, ny, _, dt = self.tracker[t]
            if nx != lx or ly != ny:
                break
            t += 1

        # if latest 5 locations are all in the same coords we must have stopped
        last_move = (datetime.datetime.now() - dt).seconds
        print(f'last time we moved was {last_move} seconds ago')
        return last_move < 5

    def is_visible(self, self_xy, target_xy, view_type):
        """
        Checks if target coords can be seen from current position
        :param self_xy: current x,y coords
        :param target_xy: targets x,y coords
        :param view_type: type of viewing port to make assessment
        :return: bool
        """
        if view_type == 'mini_map':
            distance_to_target = hypotenuse(self_xy, target_xy) * self.ui.mini_map.pixels_per_tile
            # returns True if within mini map bounding box else False
            return distance_to_target < self.ui.mini_map.radius
        if view_type == 'main_screen':
            sx, sy = self_xy
            tx, ty = target_xy
            rel_x = tx - sx
            rel_y = ty - sy

            px1, py1, px2, py2 = self.ui.main_screen.pixel_distance(rel_x, rel_y)

            if self.ui.main_screen.safe_box['x1'] < px1 < self.ui.main_screen.safe_box['x2'] and \
                    self.ui.main_screen.safe_box['y1'] < py1 < self.ui.main_screen.safe_box['y2']:
                return True

    def force_go(self, trg_x, trg_y):
        x, y = self.ui.mini_map.relative_position(
            trg_x - self.current_map.x,
            trg_y - self.current_map.y
        )
        self.ui.click_position(x, y)

    def go_to(self, trg_x, trg_y, visualise=False, min_distance=5):
        """
        Will take the player from current position to target position as per node map
        TODO: add more checks like making sure runescape client is active, adding timeout etc.
        """

        # load and rotate variables per current map
        self.locate_in_map(self.current_map, visualise=visualise)
        current_position = self.current_map.stats['self_xy']

        # print current_map['matched_angle']
        # self.current_map.current_grid
        # nodes_grid = numpy.rot90(self.current_map.current_grid, self.current_map.stats['matched_angle'] / 90)

        # TODO: re-implement this when ready to go to essence mine
        # trg_x, trg_y = calculate_rotated_position(nodes_grid, (), self.current_map.stats['matched_angle'])

        while hypotenuse(self.current_map.xy, (trg_x, trg_y)) > min_distance:
            print(f'current: {self.current_map.xy} target: {(trg_x, trg_y)}, {int(hypotenuse(self.current_map.xy, (trg_x, trg_y)))} nodes away from target')
            self.locate_in_map(self.current_map)

            try:
                route = self.calculate_route((trg_x, trg_y), visualise=visualise)
            except KeyError:
                route = self.calculate_route((trg_x, trg_y), visualise=True)

            subroute = [(rx, ry) for rx, ry in route if self.is_visible(self.current_map.xy, (rx, ry), 'mini_map')]
            rx, ry = subroute[-1]
            chk_x, chk_y = self.ui.mini_map.relative_position(
                rx - self.current_map.x,
                ry - self.current_map.y
            )
            self.ui.click_position(chk_x, chk_y)
            if rx == trg_x and ry == trg_y:
                while abs(self.current_map.x - rx) > min_distance and abs(self.current_map.y - ry) > min_distance:
                    time.sleep(0.1)
                    self.locate_in_map(self.current_map)

                    # check we didn't mis-click and break out if so
                    if not self.is_moving():
                        print('not moving, checking route')
                        break


            while len(subroute) > min_distance * 2:

                print(f'going to checkpoint {rx}, {ry}, currently at {self.current_map.xy}')
                self.locate_in_map(self.current_map)
                try:
                    subroute = self.calculate_route((rx, ry), visualise=visualise)
                except KeyError:
                    subroute = self.calculate_route((rx, ry), visualise=True)

                time.sleep(0.1)

                # if we somehow get stuck, break out from this loop and make a new checkpoint
                if not self.is_moving():
                    print('giddyup horsey!')
                    break

        print('arrived at', trg_x, trg_y)
        import winsound
        winsound.Beep(200, 200)

    def calculate_route(self, target, visualise=False):

        try:
            origins = breadth_first_search(
                self.current_map.current_grid,
                self.current_map.xy,
                target
            )
        except:
            # assume we the route is possible if map is incomplete/inaccurate
            print('normal routing failed')
            origins = breadth_first_search(
                self.current_map.current_grid,
                self.current_map.xy,
                target,
                passable=[self.current_map.WHITE, self.current_map.BLACK]
            )

        last = target
        route = [target]
        while origins[last]:
            route.insert(0, origins[last])
            last = origins[last]

        # TODO: add this to map/gps class to allow access to colors?
        if visualise:
            # visual with colour

            self.current_map.temp_img = imutils.rotate_bound(deepcopy(self.current_map.img), self.current_map.angle)  #.copy()
            self.current_map.temp_grid = deepcopy(self.current_map.current_grid)

            for x, y in route:
                self.current_map.temp_grid[y][x] = self.current_map.YELLOW

            self.current_map.temp_grid[self.current_map.y][self.current_map.x] = self.current_map.RED
            self.current_map.temp_grid[target[1]][target[0]] = self.current_map.GREEN

            for r, row in enumerate(self.current_map.temp_grid):
                for c, element in enumerate(row):
                    if list(element) != self.current_map.BLACK:

                        colour = [int(x) for x in element]
                        pixels_per_tile = self.current_map.pixels_per_tile
                        x1, y1 = int(c * pixels_per_tile), int(r * pixels_per_tile)
                        x2, y2 = int(x1 + pixels_per_tile), int(y1 + pixels_per_tile)
                        cv2.rectangle(self.current_map.temp_img, (x1, y1), (x2, y2), colour, -1)
            cv2.imshow('route', self.current_map.temp_img)
            cv2.waitKey(0)
            cv2.destroyWindow('route')

        return route

    def find_node(self, node_type, search_type='random'):
        """
        Finds the x,y coords of a specified node on current map
        """

        matches = []
        for y, row in enumerate(self.current_map.current_grid):
            for x, element in enumerate(row):
                if list(element) == node_type:
                    matches.append((x, y, hypotenuse(
                        self.current_map.xy,
                        (x, y),

                    )))

        if search_type == 'random':
            return matches[random.randint(0, len(matches)-1)][:2]
        if search_type == 'nearest':
            node_x, node_y, _ = sorted(matches, key=lambda x: x[2])[0]
            n = get_neighbours(self.current_map.current_grid, (node_x, node_y))
            tile_x, tile_y = n[random.randint(0, len(n)-1)]
            return (node_x, node_y), (tile_x, tile_y)

class Map:

    def __init__(self, gps, name):
        self.name = name
        self.gps = gps
        self.ui = self.gps.ui
        self.ahk = self.ui.ahk

        # TODO: rewrite these as Node objects
        # TODO: write Node objects class with toggling functions, node connections etc.
        # colors
        self.BLUE = [0, 0, 255]
        self.GREEN = [0, 255, 0]
        self.RED = [255, 0, 0]  # item
        self.YELLOW = [255, 255, 0]  # npc
        self.WHITE = [255, 255, 255]  # passable tile
        self.BLACK = [0, 0, 0]  # impassable tile

        # special colors
        self.BANK = [200, 0, 0]  # bank stalls or bank chests
        self.PORTAL = [0, 200, 0]  # e.g. anything that will take you to a new map e.g. ladders, portals, etc.
        self.RUNE_ESSENCE = [0, 0, 200]

        # configure paths
        self.base_dir = f'{gps.maps_path}{os.sep}{name}'
        self.img_path = f'{self.base_dir}{os.sep}{name}.png'
        self.canny_img_path = f'{self.base_dir}{os.sep}{name}_canny.png'
        self.nodes_path = f'{self.base_dir}{os.sep}{name}.npy'
        self.config_path = self._set_config_path()

        # set up logger
        self.log_file = f'{runescape.__path__[0]}\\logs\\{self.name}.log'
        logging.basicConfig(filename=self.log_file, level=logging.INFO)
        self.logger = logging.getLogger(self.name)

        # load images from paths
        self.img = cv2.imread(self.img_path)
        self.img_rgb = cv2.cvtColor(self.img, cv2.COLOR_BGR2RGB)
        self.temp_img = None
        self.canny_img = cv2.imread(self.canny_img_path)

        # get stats about map
        self.config = self._load_config()
        self.pixels_per_tile = self.config.get('pixels_per_tile')
        self.coord_max_x = int(self.img.shape[1] / self.pixels_per_tile)
        self.coord_max_y = int(self.img.shape[0] / self.pixels_per_tile)
        self.centre_image_x = int(self.img.shape[1] / 2)
        self.centre_image_y = int(self.img.shape[0] / 2)
        self.stats = {}
        self.heuristics = {}
        self.angle = None

        # node grid stuff
        self.grid = numpy.load(self.nodes_path)
        self.current_grid = self.grid  # this will change when we pick up rotations

    def update_img(self):
        self.img = cv2.imread(self.img_path)
        return self.img

    def update_canny_img(self):
        self.canny_img = cv2.imread(self.canny_img_path)
        return self.canny_img

    def _set_config_path(self):
        custom_config_path = f'{self.base_dir}{os.sep}{self.name}_config.json'
        if os.path.exists(custom_config_path):
            return custom_config_path
        else:
            return f'{self.gps.maps_path}{os.sep}default_config.json'

    def _load_config(self):
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def make_node_map(self):
        grid = numpy.array(
            [
                [
                    BLACK for column in range(self.coord_max_x)
                ] for row in range(self.coord_max_y)
             ]
        )
        numpy.save(self.nodes_path, grid)

    def on_click(self, event, grid):
        # print('%s click: button=%d, x=%d, y=%d, xdata=%f, ydata=%f' %
        #       ('double' if event.dblclick else 'single', event.button,
        #        event.x, event.y, event.xdata, event.ydata))
        event_x = int(event.xdata)
        event_y = int(event.ydata)

        # TODO: set up class that deals with now strings in one place
        now = datetime.datetime.now()
        now_string = now.strftime('%x %X.%f')

        if self.ahk.key_state('Ctrl'):
            self.logger.info(f' {now_string} node ({event_x}, {event_y}) -> BANK')
            self.grid[event_y][event_x] = self.BANK
        elif self.ahk.key_state('Alt'):
            self.logger.info(f' {now_string} node ({event_x}, {event_y}) -> PORTAL')
            self.grid[event_y][event_x] = self.PORTAL
        elif event.dblclick:
            self.logger.info(f' {now_string} resetting node ({event_x}, {event_y}) -> BLACK')
            self.grid[event_y][event_x] = self.BLACK
        else:
            if all(grid[event_y][event_x] == self.BLACK):
                self.logger.info(f' {now_string} node ({event_x}, {event_y}) -> WHITE')
                self.grid[event_y][event_x] = self.WHITE
            elif all(grid[event_y][event_x] == self.WHITE):
                self.logger.info(f' {now_string} node ({event_x}, {event_y}) -> BLACK')
                self.grid[event_y][event_x] = self.BLACK

    def manipulate_grid(self):
        """
        TODO: -- DEPRECATED --
        Loads node map to be adjusted by hand.
        :param map_name: name of the map to be adjusted
        :return: None
        """

        # initiate figure and axes objects
        fig, ax = pyplot.subplots()

        cid = fig.canvas.mpl_connect(
            'button_press_event',
            lambda evt, grid=self.grid: self.on_click(evt, self.grid)
        )

        while True:
            # keep refreshing the image until done by pressing shift
            if self.ahk.key_state('LShift'):
                break

            ax.imshow(self.grid)
            pyplot.draw()
            pyplot.pause(0.0001)

        # ask to save result
        save_result = ctypes.windll.user32.MessageBoxW(0, "Save Result?", "Yo!", 1)
        if save_result == 1:
            numpy.save(self.nodes_path, self.grid)


def get_neighbours(nodes_grid, tuple, diagonals=False, passable=[[255, 255, 255]]):
    # tuple as x, y coordinates
    x, y = tuple

    neighbours = []
    if diagonals:
        translations = range(-1, 2)
    else:
        translations = [-1, 1]

    for translation in translations:
        neighbours.append((x + translation, y))
        neighbours.append((x, y + translation))

    valid_neighbours = []
    for n in neighbours:
        tx, ty = n

        # check if node is BLACK
        if list(nodes_grid[ty][tx]) not in passable:
            continue

        valid_neighbours.append(n)

    return valid_neighbours


def hypotenuse(coord1, coord2):
    """
    Calculates coordinate distance between two points as the crow flies
    """
    return math.sqrt(
        math.pow(abs(coord1[0] - coord2[0]), 2) +
        math.pow(abs(coord1[1] - coord2[1]), 2)
    )


def breadth_first_search(nodes_grid, start, goal, passable=[[255, 255, 255]]):
    came_from = {start: None}
    frontier = [start]

    # TODO: fix this if frontier is only one long
    while frontier:
        current = frontier.pop(0)

        if current == goal:
            break

        for next in get_neighbours(nodes_grid, current, passable=passable):
            if next not in came_from:
                frontier.append(next)
                came_from[next] = current

    return came_from


def rotate_coordinates(x, y, cx, cy, angle):
    """
    Finds rotated position of coordinates
    :param x, y: coordinates to be rotated
    :param cx, cy: centre point around which to rotate. note, this does not
    mean a coordinate position if e.g. a 2x2 grid has an even number of nodes
    so centre point would be .5
    """

    rotated_x = int(math.cos(math.radians(angle)) * (x - cx) -
                    math.sin(math.radians(angle)) * (y - cy) +
                    cx
                    )

    rotated_y = int(math.sin(math.radians(angle)) * (x - cx) +
                    math.cos(math.radians(angle)) * (y - cy) +
                    cy
                    )

    return rotated_x, rotated_y
