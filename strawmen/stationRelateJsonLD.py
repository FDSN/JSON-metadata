#!/usr/bin/env python

import sys
from lxml import etree
import json
import re
from util import STAXML_NS, createNetworkSid, createStationSid, AbstractStationJson
from abc import ABC
from mostBasic import MostBasic
from relationshipsJsonLD import RelateJsonLD

DATA="data"
META="meta"
RELATE="stations"

class StationRelateJsonLD(RelateJsonLD):
    def name(self):
        return "station_relate_jsonld"


    def addStationToNetwork(self, station, net, envelope):
        if DATA not in envelope:
            envelope[DATA] = []
        #envelope[DATA].append(station)
        if RELATE not in net[DATA]:
            net[DATA][RELATE] = []
        net[DATA][RELATE].append( f"{station['@id']}")
        station["network"] = net['@id']


def main():
    converter = StationRelateJsonLD()
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
