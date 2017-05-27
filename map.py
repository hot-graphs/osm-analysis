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

points = pandas.read_csv('points.csv').set_index(['GPS lat', 'GPS lon'])


class CustomMapView(MapView):
    def on_touch_down(self, touch):
        touch.dz = -touch.dz
        print(self.get_latlon_at(*touch.pos))
        super().on_touch_down(touch)


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
            print(row)
            for pos, value in enumerate(reversed(row)):
                rpos = (len(row) - pos) / len(row)
                print(rpos)
                sz = self.size[0] / len(row) * (len(row) - pos)
                hsz = -sz/2
                graphics.Color(1, 1, 1, 1)
                graphics.Ellipse(size=(sz, sz), pos=(hsz, hsz))
                if value:
                    graphics.Color(0, rpos, 0, 1)
                    graphics.Ellipse(size=(sz, sz), pos=(hsz, hsz), angle_end=360*value)
            graphics.PopMatrix()
        self.bind(pos=self.reposition)

    def reposition(self, *args):
        self.translation.xy = self.pos


class MapViewApp(App):
    def build(self):
        self.mapview = CustomMapView(zoom=18, lat=49.213795607926734, lon=16.58214582519531)
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

