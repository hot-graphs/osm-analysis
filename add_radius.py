#! /usr/bin/env python3
import sys
from pathlib import Path

import click
import pandas
import shapely
import shapely.wkt

# A big hack: we stretch the longitude (x coord) by a constant that makes "circles" in WGS 84 circular
# ideally we'd use another projection, but that would take time
X_STRETCH = 1.531

@click.option('-a', '--lat-column', help='Column with latitude info', default='GPS lat')
@click.option('-o', '--lon-column', help='Column with longitude info', default='GPS lon')
@click.option('-r', '--radiuses', help='Comma-separated radiuses', default=' 0.001,0.005,0.01')
@click.option('-s', '--sep', help='Separator for input CSV', default=',')
@click.argument('shapes', nargs=-1)
@click.command()
def main(lat_column, lon_column, radiuses, sep, shapes):
    """Add columns with info about how much of a point's neighborhood intersects a given shape

    The input CSV is read from standard input.
    Output is written to standard output.
    (And some debug info goes to stderr.)

    Names of shapes to intersect should be given as arguments, and are loaded
    from WKT files.
    For example, if 'park' is specified, the shape is read from the file
    `shapes/park.wkt`.
    If multiple such files are given, all are combined together.
    """
    radiuses = [float(r) for r in radiuses.split(',')]
    if not shapes:
        shapes = ['park', 'forest']

    print('Config:', vars(), file=sys.stderr)

    target_shape = None
    shape_dir = Path('shapes')
    for shape in shapes:
        wkt = (shape_dir/shape).with_suffix('.wkt').read_text()
        new_shape = shapely.wkt.loads(wkt)
        if target_shape:
            target_shape = target_shape.union(new_shape)
        else:
            target_shape = new_shape

    df = pandas.read_csv('teplarny-adresace.csv', sep=sep)
    df = df.set_index([lat_column, lon_column])
    df.sort_index()

    for radius in radiuses:
        df[radius] = float('nan')

    idx = df.index.drop_duplicates()
    for i, (lat, lon) in enumerate(idx):
        if i%10 == 0:
            print('{}/{}'.format(i, len(idx)))
        pt = shapely.geometry.point.Point(lon, lat)
        for radius in radiuses:
            pt_lon, pt_lat = pt.coords[0]
            buf = pt.buffer(radius)
            buf = shapely.geometry.Polygon(
                (pt_lon + X_STRETCH*(lon - pt_lon), lat)
                for lon, lat in buf.boundary.coords)
            intersection = buf.intersection(target_shape)
            df.loc[(lat, lon), radius] = intersection.area / buf.area
    print(df.to_csv())


if __name__ == '__main__':
    main()
