#!/usr/bin/env seiscomp-python
# -*- coding: utf-8 -*-
from obspy.clients.fdsn import Client
from obspy import read, UTCDateTime
import sys
import traceback
import datetime
from seiscomp import core, client, io, math, logging
from seiscomp import client, datamodel
from seiscomp.client import Protocol

#Se crea el objeto cliente FDSN para obtener datos y el inventario
host = ("http://163.178.171.47:8080")  # SEISCOMP servidor Virtual
#host = ("http://localhost:8080")  # SEISCOMP computadora local
myClient = Client(host)
total = client.get_stations()
networks = client.get_stations(level="network")



class EventListener(client.Application):

    def __init__(self, argc, argv):
        client.Application.__init__(self, argc, argv)
        self.setMessagingEnabled(True)
        self.setDatabaseEnabled(False, False)
        self.setPrimaryMessagingGroup(Protocol.LISTENER_GROUP)
        self.addMessagingSubscription("EVENT")
        self.setLoggingToStdErr(True)

    def doSomethingWithEvent(self, event):
        try:
            tiempo = event.creationInfo.creationTime()
            now = core.Time.GMT()
            # Substract 5 minutes for the start time
            #start = now - core.TimeSpan(300, 0)
            inicio = tiempo - datetime.timedelta(minutes=5)  # resta 5 minutos a la hora fija

            fin = tiempo + datetime.timedelta(minutes=5)  # suma 5 minutos a la hora fija
            lista = []

            for n in range(len(networks)):
                # print(total[n].code)
                for s in range(len(total.networks[n].stations)):
                    # print(total.networks[n].stations[s].code)
                    try:
                        st = myClient.get_waveforms(total[n].code, total.networks[n].stations[s].code, "**", "HN*",
                                                  inicio, fin, attach_response=True)
                        # print(st)
                    except:
                        print("No hay datos para la estación " + total.networks[n].stations[s].code)

                    else:  # de existir datos continua con el calculo
                        st.merge()
                        # copia para quitar respuesta
                        strNew = st.copy()
                        try:
                            rutaArchivo = "/home/stuart/waves/ver3/" + tiempo.strftime("%m-%d-%Y_%H:%M:%S") + "_" + \
                                          total.networks[n].stations[s].code + ".mseed"
                            # guardar el stream en archivo mseed
                            strNew.write(rutaArchivo, format="MSEED")

                        except:
                            print("Error en lectura de datos para la estación " + total.networks[n].stations[s].code)
        except Exception:
            traceback.print_exc()

    def updateObject(self, parentID, scobject):
        # called if an updated object is received
        event = datamodel.Event.Cast(scobject)
        if event:
            print("received update for event {}".format(event.publicID()))
            self.doSomethingWithEvent(event)

    def addObject(self, parentID, scobject):
        # called if a new object is received
        event = datamodel.Event.Cast(scobject)
        if event:
            print("received new event {}".format(event.publicID()))
            self.doSomethingWithEvent(event)

    def run(self):
        # does not need to be reimplemented. it is just done to illustrate
        # how to override methods
        print("Hi! The EventListener is now running.")
        return client.Application.run(self)


def main():
    app = EventListener(len(sys.argv), sys.argv)
    return app()


if __name__ == "__main__":
    sys.exit(main())