
#!/usr/bin/env python3
import json, sys
mp = json.load(open('mappings/icdm-to-owl.json','r',encoding='utf-8'))
iri = mp.get('iriPolicy', {})
ok = True
if 'resourceBaseId' not in iri:
    print('ERROR: iriPolicy.resourceBaseId missing'); ok=False
if iri.get('networkIri','').find('${resourceBaseId}') < 0:
    print('ERROR: networkIri does not use ${resourceBaseId}'); ok=False
if iri.get('stationIri','').find('${resourceBaseId}') < 0:
    print('ERROR: stationIri does not use ${resourceBaseId}'); ok=False
print('IRI Policy:', iri)
sys.exit(0 if ok else 2)
