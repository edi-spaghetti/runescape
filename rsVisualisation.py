import os
import cv2
import numpy
import tkinter
from tkinter import Tk
from PIL import ImageTk, Image
from copy import deepcopy
import imutils
import ctypes


class Cursor:
    """
    keeps track of cursor for GUI
    """
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y


class GUthIx:

    def __init__(self, gps, map_name=None, live=True):
        # set up map
        self.gps = gps
        self.render_nodes = True
        self.destroyed = False

        if map_name:
            self.map_ = gps.maps[map_name]
        else:
            self.map_ = gps.current_map
        self.ppt = self.map_.config.get('pixels_per_tile')

        # load grid, images and set up output paths
        self.live = live
        if live:
            self.map_.vis_grid = deepcopy(self.map_.current_grid)
            self.map_.temp_img = imutils.rotate_bound(deepcopy(self.map_.img_rgb), self.map_.angle)
            self.map_.vis_grid_path = self.map_.nodes_path
        else:
            test_output_path = r'C:\Users\Edi\Desktop\programming\runescape\test\scripts\sample'
            self.map_.vis_grid_path = f'{test_output_path}{os.sep}{map_name}_tkinter.npy'
            if os.path.exists(self.map_.nodes_path):
                self.map_.vis_grid = numpy.load(self.map_.nodes_path)
            else:
                self.map_.vis_grid = numpy.array(
                    [[self.map_.BLACK for _ in range(self.map_.coord_max_x)] for _ in range(self.map_.coord_max_y)]
                )
            self.map_.temp_img = deepcopy(self.map_.img_rgb)

        # add cursor starting position
        cur_y, cur_x, _ = [int(x/2) for x in self.map_.vis_grid.shape]
        self.cursor = Cursor(x=cur_x, y=cur_y)

        # tkinter window says it's 10 nodes off what it actually. Only seems to affect print statements though, the
        # actual nodes seem to be in the right place
        self.tk_offset = 10

        # create tkinter objects
        self.root = Tk()
        panel = tkinter.Label(self.root)

        # add to label widget
        panel.pack()

        # bind arrow keys
        panel.bind('<Button-1>', self.on_left_click)
        panel.bind('<Left>', self.left_key)
        panel.bind('<Right>', self.right_key)
        panel.bind('<Up>', self.up_key)
        panel.bind('<Down>',self.down_key)
        # toggling colours
        panel.bind('<space>', lambda evt, c=self.map_.WHITE: self.toggle(evt, c))
        panel.bind('<b>', lambda evt, c=self.map_.BANK: self.toggle(evt, c))
        panel.bind('<p>', lambda evt, c=self.map_.PORTAL: self.toggle(evt, c))
        panel.bind('<r>', lambda evt, c=self.map_.RUNE_ESSENCE: self.toggle(evt, c))
        # control settings
        panel.bind('<0>', self.toggle_nodes)
        panel.bind('<s>', self.save)
        panel.bind('<q>', self.quit)
        panel.bind('<Tab>', self.rotate)
        panel.bind('<u>', self.update_map)
        panel.bind('<g>', self.go)

        panel.focus_set()

        # run draw image onto screen
        self.panel = panel
        self.draw_nodes()

        self.root.mainloop()

    def draw_nodes(self, override_grid=None):
        """
        recalculate image, adding nodes and cursor then loading into tkinter panel
        :param map_: GPS Map Object
        :return: None
        """

        img = deepcopy(self.map_.temp_img)
        if override_grid is None:
            grid = self.map_.vis_grid
        else:
            grid = override_grid

        if self.render_nodes:
            for r, row in enumerate(grid):
                for c, element in enumerate(row):
                    if list(element) != self.map_.BLACK:

                        # cast numpy array elements as python integers (instead of numpy.int64s)
                        colour = [int(x) for x in element]

                        x1, y1 = int(c * self.ppt), int(r * self.ppt)
                        x2, y2 = int(x1 + self.ppt), int(y1 + self.ppt)
                        cv2.rectangle(img, (x1, y1), (x2, y2), colour, -1)

        # draw cursor
        cur_x1, cur_y1 = int(self.cursor.x * self.ppt), int(self.cursor.y * self.ppt)
        cur_x2, cur_y2 = int(cur_x1 + self.ppt), int(cur_y1 + self.ppt)
        cv2.rectangle(img, (cur_x1, cur_y1), (cur_x2, cur_y2), self.map_.RED, 1)

        # draw player
        if self.live:
            px, py = int((self.map_.x * self.ppt) + (self.ppt / 2)), int((self.map_.y * self.ppt) + (self.ppt / 2))
            # testing coords need to be rotated?
            # from rsPathFinding import rotate_coordinates
            # rx, ry = rotate_coordinates(px, py, self.map_.centre_image_x, self.map_.centre_image_y, -self.map_.angle)
            cv2.drawMarker(img, (px, py), (0, 0, 255), cv2.MARKER_CROSS, int(self.ppt))

        im = Image.fromarray(img)
        imgtk = ImageTk.PhotoImage(image=im)
        # map_.panel.create_image(0, 0, image=imgtk, anchor='nw')
        self.panel.configure(image=imgtk)
        self.panel.image = imgtk

    def update_map(self, event):
        if self.live:
            self.gps.locate_in_map(self.gps.current_map)
            self.draw_nodes()
        else:
            print('cannot update map unless live')

    def go(self, event):
        if self.live:
            self.gps.go_to(self.cursor.x, self.cursor.y, min_distance=1)
            self.draw_nodes()
        else:
            print('cannot go unless live')

    def toggle_nodes(self, event):
        self.render_nodes = not self.render_nodes
        self.draw_nodes()

    def on_left_click(self, event):
        """
        moves the cursor to the clicked location
        """
        # print(f"click at {event.x}, {event.y - tk_offset}")
        x = int(event.x / self.ppt)
        y = int(event.y / self.ppt)
        self.cursor.x, self.cursor.y = x, y
        print('redrawing cursor at', x, y) # - tk_offset)
        self.draw_nodes()

    def left_key(self, event):
        self.cursor.x -= 1
        self.draw_nodes()
    
    def right_key(self, event):
        self.cursor.x += 1
        self.draw_nodes()
    
    def up_key(self, event):
        self.cursor.y -= 1
        self.draw_nodes()
    
    def down_key(self, event):
        self.cursor.y += 1
        self.draw_nodes()
    
    def space_key(self, event):
        x, y = self.cursor.x, self.cursor.y
        if list(self.map_.vis_grid[y][x]) == self.map_.WHITE:
            self.map_.vis_grid[y][x] = self.map_.BLACK
        elif list(self.map_.vis_grid[y][x]) == self.map_.BLACK:
            self.map_.vis_grid[y][x] = self.map_.WHITE
    
        print('toggling node at', x, y) # - tk_offset)
        self.draw_nodes()
    
    def toggle(self, event, colour):
        x, y = self.cursor.x, self.cursor.y
        if list(self.map_.vis_grid[y][x]) == colour:
            self.map_.vis_grid[y][x] = self.map_.BLACK
        else:
            self.map_.vis_grid[y][x] = colour
    
        print('toggling at', x, y) # - tk_offset)
        self.draw_nodes()
    
    def bank(self, event):
        x, y = self.cursor.x, self.cursor.y
        if list(self.map_.vis_grid[y][x]) == self.map_.BANK:
            self.map_.vis_grid[y][x] = self.map_.BLACK
        elif list(self.map_.vis_grid[y][x]) != self.map_.BANK:
            self.map_.vis_grid[y][x] = self.map_.BANK
    
        print('toggling bank at', x, y) # - tk_offset)
        self.draw_nodes()
    
    def rotate(self, event):
        self.map_.vis_grid = numpy.rot90(self.map_.vis_grid, 1)
        self.draw_nodes()
    
    def save(self, event):
        s = ctypes.windll.user32.MessageBoxW(0, "Save Result?", "Yo!", 1)
        if s == 1:
            print('saving to', self.map_.vis_grid_path)
            # rotate the grid back to original position
            grid = numpy.rot90(self.map_.vis_grid, self.map_.angle // 90)
            # and then save
            numpy.save(self.map_.vis_grid_path, grid)

    def quit(self, event):
        print('bye bye')
        self.root.destroy()
        self.destroyed = True
