try:
    import asyncio
except ImportError:
    raise RuntimeError("This example requries Python3 / asyncio")

import json
from datetime import timedelta
from io import StringIO
from threading import Thread

import holoviews as hv
import pandas as pd
from bokeh.application import Application
from bokeh.application.handlers import FunctionHandler
from bokeh.embed import server_document
from bokeh.layouts import layout
from bokeh.models import (CustomJS, ColumnDataSource, Slider, Select, LinearAxis, Range1d, DateRangeSlider,
                          Button, DataTable, DateFormatter, TableColumn, SelectEditor, CellEditor, CDSView, GroupFilter,
                          IndexFilter, CheckboxButtonGroup)
from bokeh.tile_providers import CARTODBPOSITRON, get_provider
from bokeh.plotting import figure
from bokeh.server.server import BaseServer
from bokeh.server.tornado import BokehTornado
from bokeh.server.util import bind_sockets
from flask import Flask, render_template, request
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from pyproj import Proj, transform, Transformer

hv.extension('bokeh')

app = Flask(__name__)

import os

path = "data/"

# creating a dict that contain all the netcdf files
datasets = {}
files = os.listdir(path)
files.sort()
for f in files:
    fichier = open(path + f, "r")
    save = fichier.read()
    fichier.close()
    dfColoc = pd.read_csv(StringIO(save), sep="\s+")
    dfColoc.columns = ['date_Argo', 'heure_Argo', 'lon', 'lat', 'numero_Argo', 'n_profil_Argo', 'jsp', 'profondeur',
                       'flag', 'SSS_Argo', 'flag2', 'temp_Argo', 'flag3', 'profil1', 'profil2', 'difference', 'dist',
                       'nbr_de_TSG', 'SSS_TSG', 'STR_SSS_TSG', 'donnee_eau', 'temp_entree', 'STR_temp_entree',
                       'nbr_de_TSG2', 'temp_TSG', 'STR_temp_TSG']
    dfColoc['date'] = dfColoc['date_Argo'] + ' ' + dfColoc['heure_Argo']
    dfColoc['date'] = pd.to_datetime(dfColoc['date'], format="%Y-%m-%d %H:%M:%S")
    dfColoc['difference'] = dfColoc['SSS_TSG'] - dfColoc['SSS_Argo']
    dfColoc = dfColoc[dfColoc['SSS_Argo'].notna()]
    dfColoc = dfColoc[dfColoc['SSS_TSG'].notna()]
    trans = Transformer.from_crs(
        "epsg:4326",
        "epsg:3857",
        always_xy=True,
    )
    xx, yy = trans.transform(dfColoc["lon"], dfColoc["lat"])
    dfColoc['mercatorX'] = xx
    dfColoc['mercatorY'] = yy
    datasets[f] = dfColoc

# Get a list of all file names
fileNames = list(datasets.keys())

# Innitiating containero.js
SelectedFile = fileNames[0]

# Set all the data in a dict
optionData = {
    'file': SelectedFile
}
# writing the data in the json
json_string = json.dumps(optionData)
with open('containero.json', 'w') as outfile:
    outfile.write(json_string)

LABELS = ["Argo", "TSG", "Difference"]


# Bokeh app function
def viz(doc):
    f2 = open("containero.json")
    selected = json.load(f2)
    dfPlot = datasets[selected['file']].copy()
    f2.close()

    source1 = ColumnDataSource(data=dict(dfPlot))

    p1 = figure(x_axis_type="datetime", width=800, height=800,
                tools="pan,wheel_zoom,box_zoom,lasso_select,tap,reset,hover",
                title="Salinité TSG et Argo en fonction du temps : ")
    p1.toolbar.active_drag = None
    p1.extra_y_ranges = {
        "différence TSG - Argo": Range1d(start=min(source1.data['difference']), end=max(source1.data['difference']))}
    glyph5 = p1.circle('date', 'SSS_TSG', source=source1, alpha=0.5, color="green")
    glyph6 = p1.line('date', 'SSS_TSG', source=source1, color="green")
    glyph4 = p1.circle('date', 'SSS_Argo', source=source1, alpha=0.5, color="blue")
    glyph7 = p1.line('date', 'SSS_Argo', source=source1, color="blue")
    glyph8 = p1.line('date', 'difference', source=source1, y_range_name="différence TSG - Argo")
    p1.add_layout(LinearAxis(y_range_name="différence TSG - Argo"), 'left')

    tile_provider = get_provider(CARTODBPOSITRON)

    # range bounds supplied in web mercator coordinates
    p = figure(x_axis_type="mercator", y_axis_type="mercator", width=1000, height=800)
    p.add_tile(tile_provider)

    glyph = p.circle(x='mercatorX', y='mercatorY', source=source1)

    def callback(attr, old, new):

        actives = checkbox_button_group.active
        if 0 in actives:
            glyph.visible = True
            glyph4.visible = True
            glyph7.visible = True
        else:
            glyph.visible = False
            glyph4.visible = False
            glyph7.visible = False
            '''
        if "TSG" in CheckboxButtonGroup.value:
            glyph2.visible = True
        else:
            glyph2.visible = False
        if 'Difference' in CheckboxButtonGroup.value:
            glyph3.visible = True
        else:
            glyph3.visible = False
        '''
    checkbox_button_group = CheckboxButtonGroup(labels=LABELS, active=[0, 1])
    checkbox_button_group.on_change("active", callback)

    grid = layout([[checkbox_button_group],
                   [p1, p]])
    doc.add_root(grid)


sockets, port = bind_sockets("localhost", 0)

hvapp = Application(FunctionHandler(viz))


# locally creates a page
@app.route('/', methods=['GET', 'POST'])
def hv_page():
    # just set default selected values
    selected_file = fileNames[0]

    # update the json after submit
    if request.method == 'POST':
        # update the file selected
        selected_file = request.form['file']
        option_data = {
            'file': selected_file
        }
        json_string = json.dumps(option_data)
        with open('containero.json', 'w') as OUTFILE:
            OUTFILE.write(json_string)

    # script containing the app
    script = server_document('http://localhost:%d/hvapp' % port)
    return render_template("index.html", script=script, template="Flask",
                           files=fileNames, savedFileOpt=selected_file)


def hv_worker():
    asyncio.set_event_loop(asyncio.new_event_loop())
    bokeh_tornado = BokehTornado({'/hvapp': hvapp}, extra_websocket_origins=["127.0.0.1:8000"])
    bokeh_http = HTTPServer(bokeh_tornado)
    bokeh_http.add_sockets(sockets)

    server = BaseServer(IOLoop.current(), bokeh_tornado, bokeh_http)
    server.start()
    server.io_loop.start()


@app.route('/propos')
def propos():
    return render_template("propos.html")


t = Thread(target=hv_worker)
t.daemon = True
t.start()

if __name__ == '__main__':
    print('This script is intended to be run with gunicorn. e.g.')
    print()
    print('    gunicorn -w 4 flaskAppMultiThread:app')
    print()
    print('will start the app on four processes')
    import sys

    sys.exit()
