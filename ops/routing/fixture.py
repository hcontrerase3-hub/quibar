"""Write a tiny SYNTHETIC road graph for disposable Docker acceptance only."""
import argparse
from pathlib import Path
import struct


def varint(number):
    out=bytearray()
    while number>127:
        out.append((number&127)|128);number>>=7
    out.append(number)
    return bytes(out)


def integer(field, value):
    return varint(field<<3)+varint(value)


def binary(field, content):
    return varint((field<<3)|2)+varint(len(content))+content


def zigzag(number):
    return number*2 if number>=0 else -number*2-1


def block(kind, payload):
    blob=binary(1,payload)
    header=binary(1,kind.encode())+integer(3,len(blob))
    return struct.pack('>I',len(header))+header+blob


def fixture(path):
    header=binary(4,b'OsmSchema-V0.6')+binary(16,b'Quibar SYNTHETIC TEST ONLY')
    strings=b''.join(binary(1,text.encode()) for text in ['', 'highway','residential','name','Camino sintetico de prueba'])
    group=b''
    for y in range(12):
        for x in range(12):
            identifier=1+y*12+x
            node=integer(1,zigzag(identifier))+integer(8,zigzag(round((-37.67-y*.0002)*1e7)))+integer(9,zigzag(round((-72.02+x*.0002)*1e7)))
            group+=binary(1,node)
    ways=[[1+y*12+x for x in range(12)] for y in range(12)]+[[1+y*12+x for y in range(12)] for x in range(12)]
    for identifier,refs in enumerate(ways,1001):
        deltas=[];previous=0
        for value in refs:deltas.append(varint(zigzag(value-previous)));previous=value
        way=integer(1,identifier)+binary(2,varint(1)+varint(3))+binary(3,varint(2)+varint(4))+binary(8,b''.join(deltas))
        group+=binary(3,way)
    primitive=binary(1,strings)+binary(2,group)
    Path(path).write_bytes(block('OSMHeader',header)+block('OSMData',primitive))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output');fixture(parser.parse_args().output)
