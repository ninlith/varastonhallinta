# Copyright 2021 Okko Hartikainen <okko.hartikainen@gmail.com>
#
# This work is licensed under the GNU GPLv3. See LICENSE.

"""Flask application."""

import logging
import secrets
import sqlite3
from time import perf_counter
import regex as re
from flask import (Flask, render_template, request, url_for, flash, redirect,
                   jsonify, abort, g)
from auxiliary.conf import PROJECT_NAME, VERSION

logger = logging.getLogger(__name__)

def get_db_connection() -> sqlite3.Connection:
    """Open database connection."""
    conn = getattr(g, '_database', None)
    if conn is None:
        logger.debug("Opening database connection...")
        conn = g._database = sqlite3.connect(app.config["database"])
    conn.row_factory = sqlite3.Row  # enables access by index or key
    return conn

def get_product(product_id) -> sqlite3.Row:
    """Get product by given id."""
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM tuotteet WHERE id = ?",
                           (product_id,)).fetchone()
    if product is None:
        abort(404)
    return product

def get_order(order_id) -> sqlite3.Row:
    """Get order by given id."""
    conn = get_db_connection()
    order = conn.execute(
        """
        SELECT
	      Tilaukset.id,
	      Tilaukset.toimitustapa_id,
	      Tilaukset.toimituspvm,
	      Tilaukset.varausnumero,
	      Tilaukset.lisätiedot,
	      Asiakkaat.nimi,
	      Asiakkaat.puhelinnumero,
	      Asiakkaat.osoite,
          GROUP_CONCAT(Tuotteet.kuvaus, ', ') AS tuotteet
        FROM
          Tilaukset LEFT JOIN Asiakkaat ON Tilaukset.asiakas_id = Asiakkaat.id
                    LEFT JOIN Tuotteet ON Tilaukset.id = Tuotteet.tilaus_id
        WHERE
          Tilaukset.id = ?
        LIMIT
          1
        """, (order_id,)).fetchone()
    if order is None:
        abort(404)
    return order

class SearchHelper:
    def __init__(self):
        self.command_parts = []
        self.search_conditions = []
        self.parameters = []
        self.precompiled_regex_pattern = None
        self.no_results = False

    def execute(self, conn):
        reg = self.precompiled_regex_pattern
        if reg:
            conn.create_function(
                "REGEXP", 2,
                lambda _, item: reg.search(item or "") is not None)
        conn.set_trace_callback(logger.debug)
        command = "".join(self.command_parts)
        start = perf_counter()
        rows = conn.execute(command, self.parameters).fetchall()
        stop = perf_counter()
        logger.debug(f"Query time: {stop - start} s")
        return rows

    def append(self, part, parameters=None):
        self.command_parts.append(part)
        if parameters is not None:
            self.parameters.extend(parameters)

    def append_where_clause(self):
        if self.search_conditions:
            self.command_parts.append(
                "WHERE " + " AND ".join(self.search_conditions))

    def add_multiselect(self, column, valuestring, maxvalues):
        values = valuestring.split(",")
        if len(values) < maxvalues:
            try:
                values.remove("-")
            except ValueError:
                nullstring = ""
            else:
                nullstring = f" OR {column} IS NULL"
            qmarks = ", ".join(["?"]*len(values))
            self.search_conditions.append(
                f"({column} IN ({qmarks}){nullstring})")
            self.parameters.extend(values)
        elif not values:
            self.no_results = True

    def add_range(self, column, start: str = None, end: str = None):
        if start and end:
            if start == end:
                self.search_conditions.append(f"{column} = ?")
                self.parameters.append(start)
            else:
                self.search_conditions.append(f"{column} BETWEEN ? AND ?")
                self.parameters.extend([start, end])
        elif start:
            self.search_conditions.append(f"{column} >= ?")
            self.parameters.append(start)
        elif end:
            self.search_conditions.append(f"{column} <= ?")
            self.parameters.append(end)

    def set_regex(self, data, pattern, ignore_case):
        flags = (re.IGNORECASE,) if ignore_case else ()
        try:
            self.precompiled_regex_pattern = re.compile(pattern, *flags)
        except re.error as e:
            logger.debug(f"Invalid regular expression: {e}")
            self.no_results = True
        else:
            self.search_conditions.append(f"{data} REGEXP ?")
            self.parameters.append(pattern)

app = Flask(__name__)
app.config["SECRET_KEY"] = secrets.token_urlsafe(16)  # for the session cookie

@app.teardown_appcontext
def close_connection(exception):
    """Close database connection on application context destruction."""
    conn = getattr(g, '_database', None)
    if conn is not None:
        logger.debug("Closing database connection...")
        conn.close()

@app.context_processor
def inject_variables():
    """Inject variables into the template context."""
    return dict(project_name=PROJECT_NAME.capitalize(), version=VERSION)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/products_json")
def products_json():
    search = request.args.get("search")
    order = request.args.get("order") or "DESC"
    sort = request.args.get("sort") or "id"
    if sort in {"id", "saapumispvm", "kuvaus", "hinta", "lisätiedot"}:
        sort = "T." + sort
    elif sort == "koodi":
        sort = "CAST(T.koodi AS INTEGER)"

    query = SearchHelper()
    query.append(
        """
        SELECT
          T.id,
          T.saapumispvm,
          T.kuvaus,
          T.hinta,
          T.koodi,
          Sijainnit.kuvaus AS sijainti,
          Tilat.kuvaus AS tila,
          Toimitustavat.kuvaus AS toimitustapa,
          Tilaukset.toimituspvm AS toimituspvm,
          T.poistettu,
          T.lisätiedot,
          COUNT(*) OVER() AS total
        FROM
          Tuotteet T LEFT JOIN Sijainnit ON T.sijainti_id = Sijainnit.id
                     LEFT JOIN Tilat ON T.tila_id = Tilat.id
                     LEFT JOIN Tilaukset ON T.tilaus_id = Tilaukset.id
                     LEFT JOIN Toimitustavat ON
                               Tilaukset.toimitustapa_id = Toimitustavat.id
                     LEFT JOIN Asiakkaat ON Tilaukset.asiakas_id = Asiakkaat.id
        """)
    query.add_range("T.poistettu", "0", "0")
    regex_data = ("""
        IFNULL(T.saapumispvm, '-')
        || '¶' || IFNULL(T.kuvaus, '-')
        || '¶' || IFNULL(T.koodi, '-')
        || '¶' || IFNULL(sijainti, '-')
        || '¶' || tila
        || '¶' || IFNULL(toimitustapa, '-')
        || '¶' || IFNULL(toimituspvm, '-')
        """)
    if search == "(tarkennettu haku)":
        query.add_range("CAST(T.koodi AS INTEGER)",
                        *request.args.get("numero").split(","))
        query.add_range("T.saapumispvm",
                        *request.args.get("saapumispvm").split(","))
        query.add_range("toimituspvm",
                        *request.args.get("toimituspvm").split(","))
        query.add_multiselect("sijainti", request.args.get("sijainti"), 3)
        query.add_multiselect("tila", request.args.get("tila"), 3)
        query.add_multiselect("toimitustapa",
                              request.args.get("toimitustapa"),
                              3)
        regex_search = request.args.get("regex_search")
        if regex_search:
            query.set_regex(regex_data,
                            regex_search,
                            request.args.get("ignore_case") == 'true')
    elif search:
        query.set_regex(regex_data, search, True)
    if query.no_results:
        return jsonify({"total": 0, "rows": []})
    query.append_where_clause()
    query.append(
        f"""
        ORDER BY {sort} {order}
        LIMIT ?
        OFFSET ?
        """,
        [request.args.get("limit"), request.args.get("offset")])
    rows = query.execute(get_db_connection())
    return jsonify(
        {"total": rows and rows[0]["total"] or 0,
         "rows": [{k:v for k, v in dict(row).items() if k != "total"}
                  for row in rows]})

@app.route("/<int:product_id>")
def product_json(product_id):
    return jsonify(dict(get_product(product_id)))

def product_form_submit(conn, command, product_id=None):
    saapumispvm = request.form["saapumispvm"] or None  # "" or None => None
    kuvaus = request.form["kuvaus"]
    hinta = request.form["hinta"] or None
    koodi = request.form["koodi"] or None
    sijainti_id = request.form["sijainti_id"] or None
    tila_id = request.form["tila_id"]
    lisätiedot = request.form["lisätiedot"] or None
    tilaus_id = request.form["tilaus_id"] or None

    args = [saapumispvm, kuvaus, hinta, koodi, sijainti_id, tila_id,
            lisätiedot, tilaus_id]
    if product_id is not None:
        args.append(product_id)

    if not kuvaus:
        flash("Kuvaus on pakollinen.", "alert-danger")
    else:
        conn.execute(command, args)
        conn.commit()
        return redirect(url_for("index"))
    return None

@app.route("/create", methods=("GET", "POST"))
def create():
    conn = get_db_connection()
    if request.method == "POST":
        command = """
                  INSERT INTO
                    tuotteet (saapumispvm,
                              kuvaus,
                              hinta,
                              koodi,
                              sijainti_id,
                              tila_id,
                              lisätiedot,
                              tilaus_id)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                  """
        redirect_url = product_form_submit(conn, command)
        if redirect_url:
            flash('Lisättiin tuote "{}".'.format(request.form["kuvaus"]),
                  "alert-success")
            return redirect_url

    tilat = conn.execute("SELECT * FROM Tilat").fetchall()
    sijainnit = conn.execute("SELECT * FROM Sijainnit").fetchall()
    return render_template("create.html", tilat=tilat,
                           sijainnit=sijainnit)

@app.route("/<int:product_id>/edit", methods=("GET", "POST"))
def edit(product_id):
    conn = get_db_connection()
    if request.method == "POST":
        command = """
                  UPDATE
                    tuotteet
                  SET
                    saapumispvm = ?,
                    kuvaus = ?,
                    hinta = ?,
                    koodi = ?,
                    sijainti_id = ?,
                    tila_id = ?,
                    lisätiedot = ?,
                    tilaus_id = ?
                  WHERE id = ?
                  """
        redirect_url = product_form_submit(conn, command, product_id)
        if redirect_url:
            flash('Muokattiin tuotetta "{}".'.format(request.form["kuvaus"]),
                  "alert-success")
            return redirect_url

    product = get_product(product_id)
    tilat = conn.execute("SELECT * FROM Tilat").fetchall()
    sijainnit = conn.execute("SELECT * FROM Sijainnit").fetchall()
    return render_template("edit.html", product=product, tilat=tilat,
                           sijainnit=sijainnit)

@app.route("/<int:product_id>/delete", methods=("POST",))
def delete(product_id):
    product = get_product(product_id)
    conn = get_db_connection()
    conn.execute("UPDATE tuotteet SET poistettu = ? WHERE id = ?",
                 (1, product_id))
    conn.commit()
    flash('Poistettiin tuote "{}".'.format(product["kuvaus"]), "alert-warning")
    return redirect(url_for("index"))

@app.route("/orders_json")
def orders_json():
    search = request.args.get("search")
    order = request.args.get("order") or "DESC"
    sort = request.args.get("sort") or "Tilaukset.id"
    query = SearchHelper()
    query.append(
        """
        SELECT
          Tilaukset.id,
          Tilaukset.toimituspvm,
          Tilaukset.varausnumero,
          Tilaukset.lisätiedot,
          Tilaukset.poistettu,
          Toimitustavat.kuvaus AS toimitustapa,
          Asiakkaat.nimi AS asiakas,
          Asiakkaat.puhelinnumero AS asiakkaan_puhelinnumero,
          Asiakkaat.osoite AS asiakkaan_osoite,
          Asiakkaat.lisätiedot AS asiakkaan_lisätiedot,
          GROUP_CONCAT(Tuotteet.kuvaus, ', ') AS tuotteet,
          COUNT(*) OVER() AS total
        FROM
          Tilaukset LEFT JOIN Toimitustavat ON
                              Tilaukset.toimitustapa_id = Toimitustavat.id
                    LEFT JOIN Asiakkaat ON Tilaukset.asiakas_id = Asiakkaat.id
                    LEFT JOIN Tuotteet ON Tilaukset.id = Tuotteet.tilaus_id
        """)
    query.add_range("Tilaukset.poistettu", "0", "0")
    query.append_where_clause()
    query.append(
        f"""
        GROUP BY
          Tilaukset.id
        ORDER BY {sort} {order}
        LIMIT ?
        OFFSET ?
        """,
        [request.args.get("limit"), request.args.get("offset")])
    rows = query.execute(get_db_connection())
    return jsonify(
        {"total": rows and rows[0]["total"] or 0,
         "rows": [{k:v for k, v in dict(row).items() if k != "total"}
                  for row in rows]})

@app.route("/order_index")
def order_index():
    return render_template("order_index.html")

def order_form_submit(conn, commands: list, order_id=None):
    nimi = request.form["nimi"] or None
    puhelinnumero = request.form["puhelinnumero"] or None
    osoite = request.form["osoite"] or None
    args = [nimi, puhelinnumero, osoite]
    if order_id is not None:
        args.append(order_id)
    if not nimi:
        flash("Nimi on pakollinen.", "alert-danger")
        return None
    else:
        cursor = conn.cursor()
        cursor.execute(commands[0], args)
        conn.commit()
        asiakas_id = cursor.lastrowid

    toimitustapa_id = request.form["toimitustapa_id"] or None
    toimituspvm = request.form["toimituspvm"] or None
    varausnumero = request.form["varausnumero"] or None
    lisätiedot = request.form["lisätiedot"] or None
    if order_id is None:
        args = [asiakas_id, toimitustapa_id, toimituspvm, varausnumero,
                lisätiedot]
    else:
        args = [toimitustapa_id, toimituspvm, varausnumero, lisätiedot,
                order_id]
    conn.execute(commands[1], args)
    conn.commit()
    return redirect(url_for("order_index"))

@app.route("/order_create", methods=("GET", "POST"))
def order_create():
    conn = get_db_connection()
    if request.method == "POST":
        commands = ["""
                    INSERT INTO
                      Asiakkaat (nimi,
                                 puhelinnumero,
                                 osoite)
                    VALUES (?, ?, ?)
                    """,
                    """
                    INSERT INTO
                      Tilaukset (asiakas_id,
                                 toimitustapa_id,
                                 toimituspvm,
                                 varausnumero,
                                 lisätiedot)
                    VALUES (?, ?, ?, ?, ?)
                    """]
        redirect_url = order_form_submit(conn, commands)
        if redirect_url:
            flash("Lisättiin tilaus.", "alert-success")
            return redirect_url

    toimitustavat = conn.execute("SELECT * FROM Toimitustavat").fetchall()
    return render_template("order_create.html", toimitustavat=toimitustavat)

@app.route("/<int:order_id>/order_edit", methods=("GET", "POST"))
def order_edit(order_id):
    conn = get_db_connection()
    if request.method == "POST":
        commands = ["""
                    UPDATE
                      Asiakkaat
                    SET
                      nimi = ?,
                      puhelinnumero = ?,
                      osoite = ?
                    WHERE
                      id = (SELECT asiakas_id
                            FROM Tilaukset WHERE id = ? LIMIT 1)
                    """,
                    """
                    UPDATE
                      Tilaukset
                    SET
                      toimitustapa_id = ?,
                      toimituspvm = ?,
                      varausnumero = ?,
                      lisätiedot = ?
                    WHERE
                      id = ?
                    """]
        redirect_url = order_form_submit(conn, commands, order_id)
        if redirect_url:
            flash("Muokattiin tilausta.", "alert-success")
            return redirect_url

    order = get_order(order_id)
    toimitustavat = conn.execute("SELECT * FROM Toimitustavat").fetchall()
    return render_template("order_edit.html", order=order,
                           toimitustavat=toimitustavat)

@app.route("/<int:order_id>/order_delete", methods=("POST",))
def order_delete(order_id):
    order = get_order(order_id)
    conn = get_db_connection()
    conn.execute("UPDATE tilaukset SET poistettu = ? WHERE id = ?",
                 (1, order_id))
    conn.commit()
    flash("Poistettiin tilaus", "alert-warning")
    return redirect(url_for("order_index"))
