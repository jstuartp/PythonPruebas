# This is a sample Python script.
from time import strftime
import obspy
from matplotlib.pyplot import plot
# Press Mayús+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
from obspy.clients.fdsn import Client
from obspy import read, UTCDateTime
from obspy import read_inventory
from obspy.core.inventory import Inventory, Network, Station, Channel, Site
from obspy.clients.nrl import NRL
import datetime
import numpy as np
import pymysql
import sys




def creaXML():
    # We'll first create all the various objects. These strongly follow the
    # hierarchy of StationXML files.
    inv = Inventory(
        # We'll add networks later.
        networks=[],
        # The source should be the id whoever create the file.
        source="MFSTUART")

    net = Network(
        # This is the network code according to the SEED standard.
        code="MF",
        # A list of stations. We'll add one later.
        stations=[],
        description="GURALP.",
        # Start-and end dates are optional.
        start_date=obspy.UTCDateTime(2016, 1, 2))

    sta = Station(
        # This is the station code according to the SEED standard.
        code="CCDN",
        latitude=9.936464,
        longitude=9.936464,
        elevation=1268.0,
        creation_date=obspy.UTCDateTime(2016, 1, 2),
        site=Site(name="Guralp pruebas"))

    chaZ = Channel(
        # This is the channel code according to the SEED standard.
        code="HNZ",
        # This is the location code according to the SEED standard.
        location_code="00",
        # Note that these coordinates can differ from the station coordinates.
        latitude=9.936464,
        longitude=9.936464,
        elevation=1268.0,
        depth=10.0,
        azimuth=0.0,
        dip=-90.0,
        sample_rate=200)
    chaN = Channel(
        # This is the channel code according to the SEED standard.
        code="HNN",
        # This is the location code according to the SEED standard.
        location_code="00",
        # Note that these coordinates can differ from the station coordinates.
        latitude=9.936464,
        longitude=9.936464,
        elevation=1268.0,
        depth=10.0,
        azimuth=0.0,
        dip=-90.0,
        sample_rate=200)
    chaE = Channel(
        # This is the channel code according to the SEED standard.
        code="HNE",
        # This is the location code according to the SEED standard.
        location_code="00",
        # Note that these coordinates can differ from the station coordinates.
        latitude=9.936464,
        longitude=9.936464,
        elevation=1268.0,
        depth=10.0,
        azimuth=0.0,
        dip=-90.0,
        sample_rate=200)

    # By default this accesses the NRL online. Offline copies of the NRL can
    # also be used instead
    nrl = NRL("/home/stuart/Documentos/NRL/")
    #print(nrl.sensors['Nanometrics']['Titan']['4g'])
    # The contents of the NRL can be explored interactively in a Python prompt,
    # see API documentation of NRL submodule:
    # http://docs.obspy.org/packages/obspy.clients.nrl.html
    # Here we assume that the end point of data logger and sensor are already
    # known:
    """"
    response = nrl.get_response(
        sensor_keys=['Streckeisen', 'STS-1', '360 s'],
        datalogger_keys=['REFTEK', '130-SMA', '1', '200 Hz'])
    print(response)
    
    response = nrl.get_response(
        sensor_keys=['Nanometrics', 'Titan', '4g','20Vp','Differential','430 Hz','0.510'],
        datalogger_keys=['Nanometrics', 'TitanSMA','200 Hz','0.001','Linear'])
    print(response)
    """
    response = nrl.get_response(
        sensor_keys=['Guralp', 'CMG-5T', '200 Hz'] ,
        datalogger_keys=['Guralp', 'CMG-DM24-Mk3-Fixed', '19', '1000-200-100-50-25-5', '200 Hz'])
    print(response)


    # Now tie it all together.
    chaZ.response = response
    chaN.response = response
    chaE.response = response
    sta.channels.append(chaZ)
    sta.channels.append(chaE)
    sta.channels.append(chaN)
    net.stations.append(sta)
    inv.networks.append(net)

    # And finally write it to a StationXML file. We also force a validation against
    # the StationXML schema to ensure it produces a valid StationXML file.
    #
    # Note that it is also possible to serialize to any of the other inventory
    # output formats ObsPy supports.
    inv.write("/home/stuart/waves/local/respuestas/CCDNStation.xml", format="stationxml", validate=True)

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    creaXML()


# See PyCharm help at https://www.jetbrains.com/help/pycharm/
