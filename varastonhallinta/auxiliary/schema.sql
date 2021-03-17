CREATE TABLE Tuotteet (
    id INTEGER PRIMARY KEY,  -- alias for the rowid column
    saapumispvm TEXT,  -- local ISO 8601
    kuvaus TEXT NOT NULL CHECK (kuvaus <> ''),
    hinta TEXT CHECK (hinta <> ''),
    koodi TEXT UNIQUE CHECK (koodi <> ''),
    sijainti_id INTEGER REFERENCES Sijainnit(id),
    tila_id INTEGER NOT NULL REFERENCES Tilat(id),
    toimitustapa_id INTEGER REFERENCES Toimitustavat(id),
    toimituspvm TEXT,  -- local ISO 8601
    lisätiedot TEXT);

CREATE TABLE Sijainnit (id INTEGER PRIMARY KEY, kuvaus TEXT);

CREATE TABLE Tilat (id INTEGER PRIMARY KEY, kuvaus TEXT);

CREATE TABLE Toimitustavat (id INTEGER PRIMARY KEY, kuvaus TEXT);

CREATE TABLE Muuttolaatikkovuokrat (
    id INTEGER PRIMARY KEY,
    vuokralainen_id INTEGER NOT NULL REFERENCES Henkilöt(id),
    laatikoiden_määrä INTEGER NOT NULL,
    vastike TEXT,
    alku_pvm TEXT,  -- local ISO 8601
    loppu_pvm TEXT,  -- local ISO 8601
    lisätiedot TEXT,
    CHECK (alku_pvm <= loppu_pvm));

CREATE TABLE Henkilöt (
    id INTEGER PRIMARY KEY, 
    nimi TEXT NOT NULL CHECK(nimi <> ''));

CREATE TABLE Muuttujat (
    id INTEGER PRIMARY KEY CHECK (id = 0),  -- allow only one row
    muuttolaatikoiden_määrä INTEGER);

CREATE TABLE Tapahtumaloki (
    id INTEGER PRIMARY KEY, 
    aikaleima TEXT,  -- local ISO 8601 date and time w/ UTC offset
    komento TEXT);
