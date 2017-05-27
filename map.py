import sys
import os.path
import threading
import json
import traceback

from kivy.app import App
from kivy.garden.mapview import MapView, MapMarker
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior
from kivy import graphics
from kivy.properties import NumericProperty, ObjectProperty, ListProperty, \
    AliasProperty, BooleanProperty, StringProperty
import pandas
import click


class MapController:
    def __init__(self, click_callback=None):
        self.process = None
        self.click_callback = click_callback

        thread = threading.Thread(target=self.input_thread)

    def send_command(self, **kwargs):
        proc = self.ensure_process()
        json.dump(kwargs, proc.stdin)

    def ensure_process(self):
        if not self.process:
            self.process = subprocess.Popen(
                [sys.executable, __file__],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
        return self.process

    def input_thread(self):
        try:
            while True:
                try:
                    line = self.ensure_process().stdout.readline()
                except EOFError:
                    return
                try:
                    data = json.loads(line)
                    cmd = data['cmd']
                    if cmd == 'point_selected':
                        if self.click_callback:
                            self.click_callback(data['row'])
                    else:
                        print('ignoring line:', data)
                except Exception:
                    traceback.print_exc()
        finally:
            self.process = None


# A big hack: we stretch the longitude (x coord) by a constant that makes "circles" in WGS 84 circular
# ideally we'd use another projection, but that would take time
X_STRETCH = 1.531


class CustomMapView(MapView):
    def __init__(self, *args, **kwargs):
        self.active_marker = None
        super().__init__(*args, **kwargs)

    def on_touch_down(self, touch):
        touch.dz = -touch.dz
        print(self.get_latlon_at(*touch.pos), file=sys.stderr)
        super().on_touch_down(touch)

    def set_active_marker(self, marker):
        if self.active_marker:
            self.active_marker.set_active(False)
        self.active_marker = marker
        if marker:
            marker.set_active(True)
            send_command(
                cmd='point_selected',
                row=marker.row.to_dict(),
                location=marker.row.name,
            )


class CustomMapMarker(MapMarker):
    def __init__(self, *args, row, radiuses, **kwargs):
        self.row = row
        self.radiuses = radiuses
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

            graphics.Color(0, 0, 0, 0.2)
            sz = self.size[0] + 2
            hsz = -sz/2
            graphics.Ellipse(size=(sz, sz), pos=(hsz, hsz))

            for pos, r in enumerate(reversed(radiuses)):
                value = self.row[str(r)]
                rpos = (len(row) - pos) / len(row)
                sz = self.size[0] / len(row) * (len(row) - pos)
                hsz = -sz/2
                graphics.Color(1-rpos/20, 1-rpos/20, 1, 1)
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
                self.radius_circles = [graphics.Ellipse() for i in self.radiuses]
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
            for i, (r, circle) in enumerate(zip(self.radiuses, self.radius_circles)):
                ry = float(r)
                rx = ry * X_STRETCH
                xm, ym, = mapview.get_window_xy_from(self.lat, self.lon, zoom=mapview.zoom)
                x1, y1 = mapview.get_window_xy_from(self.lat - ry, self.lon - rx, zoom=mapview.zoom)
                x2, y2 = mapview.get_window_xy_from(self.lat + ry, self.lon + rx, zoom=mapview.zoom)
                circle.pos = x1 , y1 
                circle.size = x2-x1, y2-y1


def send_command(**kwargs):
    print(json.dumps(kwargs))


class MapViewApp(App):
    def __init__(self, points, radiuses, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.points = points
        self.radiuses = radiuses

        input_thread = threading.Thread(target=self.do_input)
        input_thread.daemon = True
        input_thread.start()

        self.bind(on_stop=lambda *a: send_command(cmd='stop'))
        send_command(cmd='started')

    def build(self):
        VEJROSTOVA = {'zoom': 18, 'lat': 49.22025828658787, 'lon': 16.50821292434091}
        JINDRICHOVA = {'zoom': 18, 'lat': 49.213795607926734, 'lon': 16.58214582519531}
        BRNO = {'zoom': 13, 'lat': 49.205243666554054, 'lon': 16.58976135996045}
        self.mapview = CustomMapView(**BRNO)
        self.points_iter = iter(enumerate(self.points.iterrows()))
        self.add_next_points()
        return self.mapview

    def add_next_points(self, *args):
        for n in range(5):
            try:
                i, (idx, row) = next(self.points_iter)
            except StopIteration:
                send_command(cmd='loaded')
                return
            print('{}/{}'.format(i, len(self.points)), file=sys.stderr)
            #mark = CustomMapMarker(lon=row['GPS lon'], lat=row['GPS lat'], source='noun_9209_cc_red.png')
            mark = CustomMapMarker(row=row, radiuses=self.radiuses)
            self.mapview.add_marker(mark)
            Clock.schedule_once(self.add_next_points, 0.2)

    def do_input(self):
        for line in sys.stdin:
            try:
                command = json.loads(line)
                if command.get('cmd') == 'stop':
                    self.stop()
                else:
                    print('map: ignoring command', command, file=sys.stderr)
            except Exception:
                traceback.print_exc()


@click.command()
def main():
    radiuses = 0.001, 0.005, 0.01
    adresace = pandas.read_csv('teplarny-adresace.csv').set_index(['GPS lat', 'GPS lon'])
    points = adresace.loc[:, [str(r) for r in radiuses] + ['Adresa']].drop_duplicates()
    MapViewApp(points, radiuses).run()

if __name__ == '__main__':
    main()
