
## Strawmen StationXML to JSON

See also [strawmen in wiki](https://github.com/FDSN/JSON-metadata/wiki/Strawmen)

Requirements:

Via Conda:
```
conda create -n strawman python=3.13 simplemseed lxml -y
```

or with pip:
```
pip install simplemseed lxml
```

[Simplemseed](https://pypi.org/project/simplemseed/) contains parser/creator for FDSN SourceIds that may be useful.

Each variant corresponds to a .py file. If run with no args, these will use
the `CO_XD.staxml` file that contains 2 networks with 1 station each. If an
argument is given, it will read that file as the StationXML file.

Example:
```
./mostBasic.py
```
or
```
./mostBasic.py mynetwork.staxml
```
