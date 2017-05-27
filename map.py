from kivy.app import App
from kivy.garden.mapview import MapView, MapMarker
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior
from kivy import graphics
from kivy.properties import NumericProperty, ObjectProperty, ListProperty, \
    AliasProperty, BooleanProperty, StringProperty
import os.path
import pandas

# A big hack: we stretch the longitude (x coord) by a constant that makes "circles" in WGS 84 circular
# ideally we'd use another projection, but that would take time
X_STRETCH = 1.531

points = pandas.read_csv('points.csv').set_index(['GPS lat', 'GPS lon'])


class CustomMapView(MapView):
    def __init__(self, *args, **kwargs):
        self.active_marker = None
        super().__init__(*args, **kwargs)

    def on_touch_down(self, touch):
        touch.dz = -touch.dz
        print(self.get_latlon_at(*touch.pos))
        super().on_touch_down(touch)

    def set_active_marker(self, marker):
        if self.active_marker:
            self.active_marker.set_active(False)
        self.active_marker = marker
        if marker:
            marker.set_active(True)


class CustomMapMarker(MapMarker):
    def __init__(self, *args, row, **kwargs):
        self.row = row
        self.lat, self.lon = row.name
        super().__init__(*args, **kwargs)
        self.anchor_x = 0
        self.anchor_y = 0
        self.radius = 20
        self.size = self.radius * 2, self.radius * 2

        self.canvas.clear()

        with self.canvas.after:
            graphics.PushMatrix()
            self.translation = graphics.Translate(0, 0)

            for pos, value in enumerate(reversed(row)):
                rpos = (len(row) - pos) / len(row)
                sz = self.size[0] / len(row) * (len(row) - pos)
                hsz = -sz/2
                graphics.Color(1, 1, 1, 1)
                graphics.Ellipse(size=(sz, sz), pos=(hsz, hsz))
                if value:
                    graphics.Color(0, rpos, 0, 1)
                    graphics.Ellipse(size=(sz, sz), pos=(hsz, hsz), angle_end=360*value)
            graphics.PopMatrix()
        self.bind(pos=self.reposition)
        self.set_active(False)

    def on_touch_down(self, touch):
        if self.collide_point(touch.x, touch.y):
            mapview = self.get_mapview()
            if mapview is None:
                return
            if self.radius_circles:
                mapview.set_active_marker(None)
            else:
                mapview.set_active_marker(self)

    def set_active(self, active):
        self.canvas.before.clear()
        self.radius_circles = None
        if active:
            with self.canvas.before:
                graphics.PushMatrix()
                graphics.Color(1, 0, 0, 0.1)
                self.radius_circles = [graphics.Ellipse() for i in self.row]
                graphics.PopMatrix()
        self.reposition()

    def collide_point(self, x, y):
        mapview = self.get_mapview()
        if mapview is None:
            return
        lat, lon = mapview.get_window_xy_from(self.lat, self.lon, zoom=mapview.zoom)
        x -= self.pos[0]
        y -= self.pos[1]
        return x**2 + y**2 < self.radius ** 2

    def get_mapview(self):
        mapview = self
        while not isinstance(mapview, CustomMapView):
            mapview = mapview.parent
            if mapview is None:
                return
        return mapview

    def reposition(self, *args):
        self.translation.xy = self.pos
        if self.radius_circles:
            mapview = self.get_mapview()
            if mapview is None:
                return
            for i, (r, circle) in enumerate(zip(self.row.index, self.radius_circles)):
                ry = float(r)
                rx = ry * X_STRETCH
                xm, ym, = mapview.get_window_xy_from(self.lat, self.lon, zoom=mapview.zoom)
                x1, y1 = mapview.get_window_xy_from(self.lat - ry, self.lon - rx, zoom=mapview.zoom)
                x2, y2 = mapview.get_window_xy_from(self.lat + ry, self.lon + rx, zoom=mapview.zoom)
                circle.pos = x1 , y1 
                circle.size = x2-x1, y2-y1
                print('CINST', circle.size[0]/circle.size[1])


class MapViewApp(App):
    def build(self):
        self.mapview = CustomMapView(zoom=18, lat=49.22025828658787, lon=16.50821292434091) #49.213795607926734, lon=16.58214582519531)
        self.points_iter = iter(points.iterrows())
        self.add_next_points()
        self.bind(on_touch_down=print)
        return self.mapview

    def add_next_points(self, *args):
        for n in range(5):
            try:
                i, row = next(self.points_iter)
            except StopIteration:
                return
            print('{}/{}'.format(i, len(points)))
            #mark = CustomMapMarker(lon=row['GPS lon'], lat=row['GPS lat'], source='noun_9209_cc_red.png')
            mark = CustomMapMarker(row=row)
            self.mapview.add_marker(mark)
            Clock.schedule_once(self.add_next_points, 0.2)

MapViewApp().run()

