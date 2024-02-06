import os
import pandas
import numpy as np
import tkinter as tk
import tkinter.filedialog

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 850

CANVAS_X = 100
CANVAS_Y = 10
CANVAS_WIDTH = 1000
CANVAS_HEIGHT = 700

CENTER = 0
TOP = 1
LEFT = 2
RIGHT = 3
BOTTOM = 4
LEFTTOP = 5
RIGHTTOP = 6
LEFTBOTTOM = 7
RIGHTBOTTOM = 8

Mode = int
MODE_NONE: Mode = 0
MODE_CREATE: Mode = 1
MODE_MOVE: Mode = 2
MODE_REMOVE: Mode = 3

class MouseAction():
    NONE = 0
    START_POINT_SELECTED = 1
    DRAGGING = 2
    def __init__(self, canvas, mode: Mode, active_region):
        self.canvas = canvas
        self.mode = mode
        self.clear()
        self.set_active_region(active_region[0], active_region[1])
        
    def change_mode(self, mode:Mode):
        self.mode = mode
        
    def set_active_region(self, lt, rb):
        self.active_lt = lt
        self.active_rb = rb
        
    def is_active(self, point):
        x = point[0]
        y = point[1]
        if x >= self.active_lt[0] and x <= self.active_rb[0]:
            if y >= self.active_lt[1] and y <= self.active_rb[1]:
                return True
        return False
    
    def clear(self):
        self.state = self.NONE
        self.begin_point = None
        self.current_point = None
        self.end_point = None
        self.canvas.delete('SelectRect')
        
    def left_button_clicled(self, x, y):
        if self.is_active((x, y)) == False:
            return
        if self.mode == MODE_CREATE:
            self.clear()
            self.begin_point = (x, y)
            self.current_point = (x + 1, y + 1)
            self.state = self.START_POINT_SELECTED
            self.create_rect('red')
        elif self.mode == MODE_MOVE:
            figure = self.canvas.find_closest(x, y)
            self.figure = figure
            self.begin_point = (x, y)
            self.last_point = (x, y)
            loc = self.click_location(figure, x, y)
            if loc == CENTER :
                self.change_size_direction = None
            else:
                self.change_size_direction = loc
                
    def dragging(self, x, y):
        if self.mode == MODE_CREATE:
            if self.is_active((x, y)) == False:
                x = self.active_rb[0]
                y = self.active_rb[1]
            self.current_point = (x, y)
            self.canvas.coords('SelectRect', self.begin_point[0], self.begin_point[1], self.current_point[0], self.current_point[1])
        elif self.mode == MODE_MOVE:
            if self.change_size_direction is None:
                dx = x - self.last_point[0]
                dy = y - self.last_point[1]
                if self.is_active((x, y)) == False:
                    return
                self.canvas.move(self.figure, dx, dy)
                self.last_point = (x, y)
            else:
                self.change_size_figure(x, y, self.change_size_direction)
    
    def left_button_released(self, x, y, rect_name='rect'):
        if self.is_active((x, y)) == False:
            x = self.active_rb[0]
            y = self.active_rb[1]
        if self.mode == MODE_CREATE:
            rect = self.get_rect()
            self.canvas.create_rectangle(rect[0], rect[1], rect[2], rect[3], outline='blue', tag=rect_name)
            self.clear()
            
    def change_size_figure(self, x, y, direction):
        points = self.canvas.coords(self.figure)
        lt_x = points[0]
        lt_y = points[1]
        rb_x = points[2]
        rb_y = points[3]
        if direction == TOP:
            x_offset = (lt_x + rb_x) / 2
            y_offset = rb_y
            x_scale = 1.0
            y_scale = 1.0 + (self.begin_point[1] - y) / (rb_y - lt_y) / 50
        elif direction == LEFT:
            x_offset = rb_x
            y_offset = (lt_y + rb_y) / 2
            x_scale = 1.0 + (self.begin_point[0] - x) / (rb_x - lt_x) / 50   
            y_scale = 1.0    
        elif direction == RIGHT:
            x_offset = lt_x
            y_offset = (lt_y + rb_y) / 2
            x_scale = 1.0 + (x - self.begin_point[0]) / (rb_x - lt_x) / 50   
            y_scale = 1.0    
        elif direction == BOTTOM:
            x_offset = (lt_x + rb_x) / 2
            y_offset = lt_y
            x_scale = 1.0
            y_scale = 1.0 + (y - self.begin_point[1]) / (rb_y - lt_y) / 50                            
        else:
            return
        if x_scale > 0.1 and y_scale > 0.1:
            self.canvas.scale(self.figure, x_offset, y_offset, x_scale, y_scale)
            
    def create_rect(self, color):
        self.canvas.create_rectangle( self.begin_point[0], self.begin_point[1], self.current_point[0], self.current_point[1], outline=color, tag='SelectRect')
        
    def update_rect(self, x, y):
        self.current_point = (x, y)
        
    def get_rect(self):
        return (self.begin_point[0], self.begin_point[1], self.current_point[0], self.current_point[1])
    
    def get_relative_point(self):
        x = self.current_point[0] - self.begin_point[0]
        y = self.current_point[1] - self.begin_point[1]
        return (x, y)
    
    def click_location(self, figure, x, y):
        points = self.canvas.coords(figure)
        lt_x = points[0]
        lt_y = points[1]
        rb_x = points[2]
        rb_y = points[3]
        
        if x < lt_x:
            h = LEFT
        elif x >= lt_x and x <= rb_x:
            h = CENTER
        elif x > rb_x:
            h = RIGHT
            
        if y < lt_y:
            v = TOP
        elif y >= lt_y and y <= rb_y:
            v = CENTER
        elif y >= rb_y:
            v = BOTTOM
            
        if h == CENTER and v == CENTER:  
            return CENTER
        elif h == CENTER and v != CENTER:
            return v
        elif h != CENTER and v == CENTER:  
            return h
        else:
            if h == LEFT:
                if v == TOP:
                    return LEFTTOP
                else:
                    return LEFTBOTTOM
            elif h == RIGHT:
                if v == TOP:
                    return RIGHTTOP
                else:
                    return RIGHTBOTTOM
        return None
    
class GraphDraw:
    def __init__(self, canvas, size, origin):
        self.canvas = canvas
        self.size = size
        self.width = size[0]
        self.height = size[1]
        self.origin = origin
        self.canvas.create_rectangle(origin[0], origin[1], origin[0] + self.width, origin[1] + self.height, outline='#aaaaaa', fill='#eeeeee', width=2.0)
        
    def set_limit(self, xlimit, ylimit):
        self.xlimit = xlimit
        self.ylimit = ylimit
        
    def screen_point(self, point):
        if point[0] < self.xlimit[0]:
            return (None, None)
        if point[0] > self.xlimit[1]:
            return (None, None)
        if point[1] < self.ylimit[0]:
            return (None, None)
        if point[1] > self.ylimit[1]:
            return (None, None)
        x = (point[0] - self.xlimit[0]) * self.width / (self.xlimit[1] - self.xlimit[0]) + self.origin[0]
        y = self.height - (point[1] - self.ylimit[0]) / (self.height - self.ylimit[0]) + self.origin[1]
        return (x, y)
    
    def distance_x(self, distance):
        return distance * self.width / (self.xlimit[1] - self.xlimit[0])
    
    def distance_y(self, distance):
        return distance * self.height / (self.ylimit[1] - self.ylimit[0])
    
    def draw_rect(self, x, y, width, height, color, fill_color, linewidth):
        xx, yy = self.screen_point((x, y))
        w = self.distance_x(width)
        h = self.distance_y(height)
        lt = (xx - w / 2, yy + h)
        rb = (xx + w /2, yy)
        id = self.canvas.create_rectangle(lt[0], lt[1], rb[0], rb[1], outline=color, fill=fill_color, width=linewidth)
        return id
    
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        window_size = f'{WINDOW_WIDTH}x{WINDOW_HEIGHT}'
        self.title('')
        self.geometry(window_size)
        
        self.top = tk.Toplevel()
        self.top.wm_attributes('-topmost', True)
        self.top.overrideredirect(True)
        self.top.geometry(window_size)
        self.top.forward = tk.Canvas(self.top, background='white', width=WINDOW_WIDTH, height=WINDOW_HEIGHT)
        self.top.forward.pack(fill=tk.BOTH, expand=False)
        self.top.wm_attributes('-transparentcolor', 'white')
        
        self.back = tk.Canvas(self, background='white', width=WINDOW_WIDTH, height=WINDOW_HEIGHT)
        self.back.pack(fill=tk.BOTH, expand=False)
        
        self.back.bind('<Unmap>', self.unmap)
        self.back.bind('<Map>', self.map)
        
        self.graph_draw = GraphDraw(self.back, (CANVAS_WIDTH, CANVAS_HEIGHT), (120, 20))
        
        self.bind('<Configure>', self.change)
        self.mouse_action = MouseAction(self.top.forward, MODE_NONE, ((CANVAS_X, CANVAS_Y), (CANVAS_X + CANVAS_WIDTH - 1, CANVAS_Y + CANVAS_HEIGHT -1)))
        self.bind('<ButtonPress-1>', self.mouse_button_clicked)
        self.bind('<Button1-Motion>', self.mouse_dragging)
        self.bind('<ButtonRelease>', self.mouse_button_released)
        
        self.create_parts()
        
    def unmap(self, event):
        self.top.withdraw()
        
    def map(self, event):
        self.lift()
        self.top.wm_deiconify()
        self.top.attributes('-topmost', True)
        
    def change(self, event):
        x, y = self.back.winfo_rootx(), self.back.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        self.top.geometry(f'{w}x{h}+{x}+{y}') 
        
    def mouse_button_clicked(self, event):
        self.mouse_action.left_button_clicled(event.x, event.y)

    def mouse_dragging(self, event):
        self.mouse_action.dragging(event.x, event.y)
        
    def mouse_button_released(self, event):
        self.mouse_action.left_button_released(event.x, event.y)
        
    def create_parts(self):
        self.button_load_data = tk.Button(self.master, text='Load data', command=self.load_data)             
        self.button_create_region = tk.Button(self.master, text='Create Region', command=self.create_region)    
        self.button_move_region = tk.Button(self.master, text='Move Region', command=self.move_region)    
        self.button_remove_region = tk.Button(self.master, text='Remove Region', command=self.remove_region)
        
        self.button_load_data.place(x=10, y=10)     
        self.button_create_region.place(x=10, y=50)     
        self.button_move_region.place(x=10, y=90)    
        self.button_remove_region.place(x=10, y=130) 
        
    def load_data(self):
        pass
    def create_region(self):
        self.mouse_action.change_mode(MODE_CREATE)
    def move_region(self):
        self.mouse_action.change_mode(MODE_MOVE)       
    def remove_region(self):
        self.mouse_action.change_mode(MODE_REMOVE)
        
if __name__ == '__main__':
    app = App()
    app.mainloop()
           
           
        