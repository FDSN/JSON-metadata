#!/usr/bin/env python

import sys
from lxml import etree
import json
import re
from util import STAXML_NS, createNetworkSid, createStationSid, AbstractStationJson
from abc import ABC
from mostBasic import MostBasic

class FlatItemsWithType(MostBasic):
    def name(self):
        return "flat_items"
    def createNetwork(self, xmlnetwork):
        network=  super().createNetwork(xmlnetwork)
        network["type"] = "network"
        return network
    def createStation(self, xmlstation, xmlnetwork):
        station=  super().createStation(xmlstation, xmlnetwork)
        station["type"] = "station"
        return station
    def addStationToNetwork(self, station, net, envelope):
        if "items" not in envelope:
            envelope["items"] = []
        envelope["items"].append(station)

    def addNetworkToEnvelope(self, net, envelope):
        if "items" not in envelope:
            envelope["items"] = []
        envelope["items"].append(net)

def main():
    converter = FlatItemsWithType()
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
