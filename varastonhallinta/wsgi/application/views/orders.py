# Copyright 2021 Okko Hartikainen <okko.hartikainen@gmail.com>
#
# This work is licensed under the GNU GPLv3 only. See LICENSE.

"""Routes related to orders."""

import logging
import sqlite3
from flask import (render_template, request, url_for, flash, redirect, jsonify,
                   abort)
from wsgi.application.flask_app import app, get_db_connection
from wsgi.application.search import SearchHelper

logger = logging.getLogger(__name__)

def get_order(order_id) -> sqlite3.Row:
    """Get order and client by given id."""
    conn = get_db_connection()
    order = conn.execute(
        """
        SELECT
	      Tilaukset.id,
	      Tilaukset.toimitustapa_id,
	      Tilaukset.toimituspvm,
	      Tilaukset.varausnumero,
	      Tilaukset.lisätiedot,
	      Tilaukset.arkistoitu,
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

def order_form_submit(conn, commands: list, order_id=None):
    nimi = request.form["nimi"] or None
    puhelinnumero = request.form["puhelinnumero"] or None
    osoite = request.form["osoite"] or None
    args = [nimi, puhelinnumero, osoite]
    if order_id is not None:
        args.append(order_id)
    if not nimi:
        flash("Asiakkaan nimi on pakollinen.", "alert-danger")
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
          Tilaukset.arkistoitu,
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
    query.add_range("Tilaukset.arkistoitu", "0", "0")
    query.append_where_clause()
    query.append(
        f"""
        GROUP BY
          Tilaukset.id
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

@app.route("/order_index")
def order_index():
    return render_template("orders/index.html")

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
    return render_template("orders/create.html", toimitustavat=toimitustavat)

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
            flash(f"Muokattiin tilausta #{order_id}.", "alert-success")
            return redirect_url

    order = get_order(order_id)
    toimitustavat = conn.execute("SELECT * FROM Toimitustavat").fetchall()
    return render_template("orders/edit.html", order=order,
                           toimitustavat=toimitustavat)

@app.route("/<int:order_id>/order_archive", methods=("POST",))
def order_archive(order_id):
    order = get_order(order_id)
    conn = get_db_connection()
    conn.execute("UPDATE tilaukset SET arkistoitu = ? WHERE id = ?",
                 (1, order_id))
    conn.commit()
    flash(f"Arkistoitiin tilaus #{order_id}.", "alert-warning")
    return redirect(url_for("order_index"))

@app.route("/<int:order_id>/order_unarchive", methods=("POST",))
def order_unarchive(order_id):
    order = get_order(order_id)
    conn = get_db_connection()
    conn.execute("UPDATE tilaukset SET arkistoitu = ? WHERE id = ?",
                 (0, order_id))
    conn.commit()
    flash(f"Palautettiin tilaus #{order_id} arkistosta.", "alert-warning")
    return redirect(url_for("order_index"))
