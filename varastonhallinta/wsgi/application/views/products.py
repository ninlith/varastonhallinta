# Copyright 2021 Okko Hartikainen <okko.hartikainen@gmail.com>
#
# This work is licensed under the GNU GPLv3 only. See LICENSE.

"""Routes related to products."""

import logging
import sqlite3
from flask import (render_template, request, url_for, flash, redirect, jsonify,
                   abort)
from wsgi.application.flask_app import app, get_db_connection
from wsgi.application.search import SearchHelper

logger = logging.getLogger(__name__)

def get_product(product_id) -> sqlite3.Row:
    """Get product by given id."""
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM tuotteet WHERE id = ?",
                           (product_id,)).fetchone()
    if product is None:
        abort(404)
    return product

def product_form_submit(conn, command, product_id=None):
    saapumispvm = request.form["saapumispvm"] or None  # "" or None => None
    kuvaus = request.form["kuvaus"]
    hinta = request.form["hinta"] or None
    koodi = request.form["koodi"] or None
    sijainti_id = request.form["sijainti_id"] or None
    tila_id = request.form["tila_id"]
    lisätiedot = request.form["lisätiedot"] or None
    tilaus_id = request.form["tilaus_id"] or None
    uusi_tilaus = tilaus_id == "-1"
    if not kuvaus:
        flash("Kuvaus on pakollinen.", "alert-danger")
    else:
        if uusi_tilaus:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO asiakkaat DEFAULT VALUES")
            conn.commit()
            asiakas_id = cursor.lastrowid
            cursor.execute("INSERT INTO Tilaukset (asiakas_id) VALUES (?)",
                           (asiakas_id,))
            tilaus_id = cursor.lastrowid
            conn.commit()
            flash(f"Lisättiin tilaus #{tilaus_id}.", "alert-success")
        args = [saapumispvm, kuvaus, hinta, koodi, sijainti_id, tila_id,
                lisätiedot, tilaus_id]
        if product_id is not None:
            args.append(product_id)
        conn.execute(command, args)
        conn.commit()
        if uusi_tilaus:
            return redirect(url_for("order_edit", order_id=tilaus_id))
        return redirect(url_for("index"))
    return None

@app.route("/")
def index():
    return render_template("products/index.html")

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
          Tilaukset.varausnumero AS varausnumero,
          T.arkistoitu,
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
    regex_data = ("""
                  (REG(IFNULL(T.saapumispvm, '-'))
                  OR REG(IFNULL(T.kuvaus, '-'))
                  OR REG(IFNULL(T.hinta, '-'))
                  OR REG(IFNULL(T.koodi, '-'))
                  OR REG(IFNULL(sijainti, '-'))
                  OR REG(tila)
                  OR REG(IFNULL(toimitustapa, '-'))
                  OR REG(IFNULL(toimituspvm, '-'))
                  OR REG(IFNULL(CAST(varausnumero AS TEXT), '-'))
                  OR REG(IFNULL(T.lisätiedot, '-')))
                  """)
    if search == "(tarkennettu haku)":
        query.add_range("CAST(T.koodi AS INTEGER)",
                        *request.args.get("numero").split(","))
        query.add_range("T.saapumispvm",
                        *request.args.get("saapumispvm").split(","))
        query.add_range("toimituspvm",
                        *request.args.get("toimituspvm").split(","))
        query.add_range("varausnumero",
                        *request.args.get("varausnumero").split(","))
        query.add_range("T.hinta",
                        *request.args.get("hinta").split(","))
        query.add_multiselect("sijainti", request.args.get("sijainti"), 3)
        query.add_multiselect("tila", request.args.get("tila"), 3)
        query.add_multiselect("toimitustapa",
                              request.args.get("toimitustapa"),
                              3)
        query.add_multiselect("T.arkistoitu",
                              request.args.get("arkistoitu"),
                              2)
        regex_search = request.args.get("regex_search")
        if regex_search:
            query.set_regex(regex_data,
                            regex_search,
                            request.args.get("ignore_case") == 'true')
    elif search:
        query.add_range("T.arkistoitu", "0", "0")
        query.set_regex(regex_data, search, True)
    else:
        query.add_range("T.arkistoitu", "0", "0")
    if query.no_results:
        return jsonify({"total": 0, "rows": []})
    query.append_where_clause()
    query.append(
        f"""
        ORDER BY {sort} COLLATE NOCASE {order}
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
    tilaukset = conn.execute(
        "SELECT * FROM Tilaukset LEFT JOIN Asiakkaat ON Tilaukset.asiakas_id "
        "= Asiakkaat.id WHERE Tilaukset.arkistoitu = 0").fetchall()
    return render_template("products/create.html", tilat=tilat,
                           sijainnit=sijainnit, tilaukset=tilaukset)

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
    tilaukset = conn.execute(
        "SELECT * FROM Tilaukset LEFT JOIN Asiakkaat ON "
        "Tilaukset.asiakas_id = Asiakkaat.id WHERE Tilaukset.arkistoitu = 0 "
        "ORDER BY Tilaukset.id DESC").fetchall()
    return render_template("products/edit.html", product=product, tilat=tilat,
                           sijainnit=sijainnit, tilaukset=tilaukset)

@app.route("/<int:product_id>/archive", methods=("POST",))
def archive(product_id):
    product = get_product(product_id)
    conn = get_db_connection()
    conn.execute("UPDATE tuotteet SET arkistoitu = ? WHERE id = ?",
                 (1, product_id))
    conn.commit()
    flash('Arkistoitiin tuote "{}".'.format(product["kuvaus"]), "alert-warning")
    return redirect(url_for("index"))

@app.route("/<int:product_id>/unarchive", methods=("POST",))
def unarchive(product_id):
    product = get_product(product_id)
    conn = get_db_connection()
    conn.execute("UPDATE tuotteet SET arkistoitu = ? WHERE id = ?",
                 (0, product_id))
    conn.commit()
    flash('Palautettiin tuote "{}" arkistosta.'.format(product["kuvaus"]),
          "alert-warning")
    return redirect(url_for("index"))
