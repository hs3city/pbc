FROM ubuntu:16.04

RUN apt-get update && apt-get install -y djvulibre-bin libxml2-dev libxslt-dev python3-dev python3-future python3-pip sqlite3 lib32z1-dev

COPY requirements.txt /src/pbc/

WORKDIR /src/pbc

RUN pip3 install -r requirements.txt

COPY . /src/pbc/
