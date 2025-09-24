#!/usr/bin/env python

import sys
from lxml import etree
import json
import re
from util import STAXML_NS, createNetworkSid, createStationSid, AbstractStationJson
from abc import ABC
from mostBasic import MostBasic

DATA="data"
META="meta"

class FlatItemsJsonLD(MostBasic):
    def name(self):
        return "flat_items_jsonld"

    def createEnvelope(self, staxml):
        envelope = {
            "@context": {
                "name": "http://fdsn.org"
            },
            META: {
            }
        }
        meta = envelope[META]

        for child in staxml:
            tag = etree.QName(child)
            if tag.namespace == STAXML_NS:
                if tag.localname == "Source":
                    meta["source"] = child.text

                if tag.localname == "Sender":
                    meta["sender"] = child.text

                if tag.localname == "Module":
                    meta["module"] = child.text

                if tag.localname == "ModuleURI":
                    meta["moduleUri"] = child.text

                if tag.localname == "Created":
                    meta["created"] = child.text

            else:
                print(f"Non-staml namespace element found: {tag.text}")
        return envelope
    def createNetwork(self, xmlnetwork):
        netData = super().createNetwork(xmlnetwork)
        sid = netData["sourceid"]
        network=  {
            "@type": "network",
            "@id": f"{sid}@{netData['startDate']}/3",
            DATA: netData,
            META: {
                "pubVersion": "3",
                "otherNS": "stuff here"
            }
        }

        if "totalNumberStations" in netData:
            network[META]["totalNumberStations"] = netData["totalNumberStations"]
            netData.pop("totalNumberStations", None)

        if "selectedNumberStations" in netData:
            network[META]["selectedNumberStations"] = netData["selectedNumberStations"]
            netData.pop("selectedNumberStations", None)
        return network
    def createStation(self, xmlstation, xmlnetwork):
        stationData =  super().createStation(xmlstation, xmlnetwork)
        sid = stationData["sourceid"]

        station = {
            "@type": "station",
            "@id": f"{sid}@{stationData['startDate']}/4",
            DATA: stationData,
            META: {
                "pubVersion": "4",
                "otherNS": "other stuff for station too"
                }
            }
        return station

    def addStationToNetwork(self, station, net, envelope):
        if DATA not in envelope:
            envelope[DATA] = []
        envelope[DATA].append(station)

    def addNetworkToEnvelope(self, net, envelope):
        if DATA not in envelope:
            envelope[DATA] = []
        envelope[DATA].append(net)

def main():
    converter = FlatItemsJsonLD()
    file = "CO_XD.staxml"
    if len(sys.argv) > 1:
        file = sys.argv[1]
    with open(file, "rb") as inxml:
        jsonObj = converter.toJson(inxml.read())

    with open(f"{converter.name()}.json", "w") as outjson:
        json.dump(jsonObj, outjson, indent=2)
    print(json.dumps(jsonObj, indent=2))

if __name__ == "__main__":
    sys.exit(main())
