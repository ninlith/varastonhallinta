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

    def add_range(self, column, start=None, end=None):
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
    sort = request.args.get("sort") or "saapumispvm"
    if sort in {"id", "saapumispvm", "kuvaus", "hinta", "toimituspvm",
                "lisätiedot"}:
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
          T.toimituspvm,
          T.lisätiedot,
          COUNT(*) OVER() AS total
        FROM
          Tuotteet T LEFT JOIN Sijainnit ON T.sijainti_id = Sijainnit.id
                     LEFT JOIN Tilat ON T.tila_id = Tilat.id
                     LEFT JOIN Toimitustavat ON
                               T.toimitustapa_id = Toimitustavat.id
        """)
    regex_data = ("""
        IFNULL(T.saapumispvm, '-')
        || '¶' || IFNULL(T.kuvaus, '-')
        || '¶' || IFNULL(T.koodi, '-')
        || '¶' || IFNULL(sijainti, '-')
        || '¶' || tila
        || '¶' || IFNULL(toimitustapa, '-')
        || '¶' || IFNULL(T.toimituspvm, '-')
        """)
    if search == "(tarkennettu haku)":
        query.add_range("CAST(T.koodi AS INTEGER)",
                        *request.args.get("numero").split(","))
        query.add_range("T.saapumispvm",
                        *request.args.get("saapumispvm").split(","))
        query.add_range("T.toimituspvm",
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
    koodi = request.form["koodi"] or None
    tila_id = request.form["tila_id"]
    toimitustapa_id = request.form["toimitustapa_id"] or None
    toimituspvm = request.form["toimituspvm"] or None

    args = [saapumispvm, kuvaus, koodi, tila_id, toimitustapa_id, toimituspvm]
    if product_id is not None:
        args.append(product_id)

    if not kuvaus:
        flash("Kuvaus on pakollinen.", "alert-danger")
    else:
        try:
            conn.execute(command, args)
            conn.commit()
        except sqlite3.IntegrityError as e:
            if str(e) == "UNIQUE constraint failed: Tuotteet.koodi":
                flash("Tuotteen numero on jo olemassa.", "alert-danger")
            else:
                flash(str(e), "alert-danger")
        else:
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
                              koodi,
                              tila_id,
                              toimitustapa_id,
                              toimituspvm)
                  VALUES (?, ?, ?, ?, ?, ?)
                  """
        redirect_url = product_form_submit(conn, command)
        if redirect_url:
            flash('Lisättiin tuote "{}".'.format(request.form["kuvaus"]),
                  "alert-success")
            return redirect_url

    tilat = conn.execute("SELECT * FROM Tilat").fetchall()
    toimitustavat = conn.execute("SELECT * FROM Toimitustavat").fetchall()
    return render_template("create.html", tilat=tilat,
                           toimitustavat=toimitustavat)

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
                    koodi = ?,
                    tila_id = ?,
                    toimitustapa_id = ?,
                    toimituspvm = ?
                  WHERE id = ?
                  """
        redirect_url = product_form_submit(conn, command, product_id)
        if redirect_url:
            flash('Muokattiin tuotetta "{}".'.format(request.form["kuvaus"]),
                  "alert-success")
            return redirect_url

    product = get_product(product_id)
    tilat = conn.execute("SELECT * FROM Tilat").fetchall()
    toimitustavat = conn.execute("SELECT * FROM Toimitustavat").fetchall()
    return render_template("edit.html", product=product, tilat=tilat,
                           toimitustavat=toimitustavat)

@app.route("/<int:product_id>/delete", methods=("POST",))
def delete(product_id):
    product = get_product(product_id)
    conn = get_db_connection()
    conn.execute("DELETE FROM tuotteet WHERE id = ?", (product_id,))
    conn.commit()
    flash('Poistettiin tuote "{}".'.format(product["kuvaus"]), "alert-warning")
    return redirect(url_for("index"))
