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
RELATE="networkstations"
NETID="networkid"
STAID="stationids"

class TopLevelRelatedJsonLD(RelateJsonLD):
    def name(self):
        return "toplevel_network_station_jsonld"


    def addNetworkToEnvelope(self, net, envelope):
        pass

    def addStationToNetwork(self, station, net, envelope):
        #envelope[DATA].append(station)
        if DATA not in envelope:
            envelope[DATA] = []
        netsta = None
        for ns in envelope[DATA]:
            if ns['@id'] == net['@id']:
                netsta = ns
        if netsta is None:
            netsta = {
                '@type': "networkstation",
                '@id': net['@id'],
                'data': {
                    STAID: []
                }
            }
            envelope[DATA].append(netsta)
        netsta[DATA][STAID].append( f"{station['@id']}")


def main():
    converter = TopLevelRelatedJsonLD()
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
