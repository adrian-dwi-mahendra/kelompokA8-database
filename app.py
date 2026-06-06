"""
app.py — Aplikasi GUI berbasis web untuk database SNBT/UTBK
Kelompok A-8 | Database untuk Sains Data TA 2025-2026
Diupdate untuk PostgreSQL (production-ready)
"""

import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql, Error
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, jsonify
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "snbt_a8_2026_secret")

# Database connection string dari environment variable
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("❌ Environment variable DATABASE_URL tidak ditemukan!")


# ══════════════════════════════════════════════════════════════════════════════
# Database helpers untuk PostgreSQL
# ══════════════════════════════════════════════════════════════════════════════
def get_db():
    """Return a PostgreSQL connection with dict-like rows."""
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def qdb(query, args=(), one=False):
    """Execute SELECT query dan return rows."""
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(query, args)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return (rows[0] if rows else None) if one else rows
    except Error as e:
        print(f"Database error: {e}")
        return None if one else []


def xdb(query, args=()):
    """Execute INSERT/UPDATE/DELETE query."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute(query, args)
        conn.commit()
        lastrowid = cur.lastrowid if hasattr(cur, 'lastrowid') else None
        cur.close()
        return lastrowid
    except Error as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# Auto-ID generators — baca max existing lalu +1
# ══════════════════════════════════════════════════════════════════════════════
def _next_id(table, col, prefix, digits):
    """
    Cari ID terakhir di tabel secara NUMERIC (bukan alphabetical),
    parse angkanya, tambah 1.
    Pakai CAST agar PDF10000 > PDF9999 (bukan sebaliknya).
    PostgreSQL: gunakan SUBSTRING dan CAST.
    """
    plen = len(prefix)
    # Ganti SUBSTR dengan SUBSTRING untuk PostgreSQL
    row = qdb(
        f"SELECT {col} AS m FROM {table} "
        f"ORDER BY CAST(SUBSTRING({col}, {plen+1}) AS INTEGER) DESC LIMIT 1",
        one=True
    )
    last = row["m"] if row and row["m"] else None
    if last:
        nums = re.findall(r'\d+', str(last))
        num = int(nums[-1]) + 1 if nums else 1
    else:
        num = 1
    return f"{prefix}{str(num).zfill(digits)}"


def next_no_pendaftaran():
    return _next_id("pendaftaran", "no_pendaftaran", "PDF", 4)

def next_id_hasil():
    return _next_id("hasil_ujian", "id_hasil", "HSL", 4)

def next_id_lokasi():
    return _next_id("lokasi", "id_lokasi", "LK", 3)

def next_id_pengawas():
    return _next_id("pengawas", "id_pengawas", "PGW", 3)

def next_id_prodi():
    return _next_id("program_studi", "id_prodi", "PRD", 3)

def next_id_univ():
    # Universitas pakai angka murni (e.g. 1111, 2931)
    row = qdb("SELECT MAX(CAST(id_univ AS INTEGER)) AS m FROM universitas", one=True)
    num = (int(row["m"]) + 1) if (row and row["m"]) else 1001
    return str(num)

def next_no_sesi():
    row = qdb("SELECT MAX(CAST(no_sesi AS INTEGER)) AS m FROM sesi", one=True)
    num = (int(row["m"]) + 1) if (row and row["m"]) else 1
    return str(num)


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/")
def index():
    ringkas = qdb("""
        SELECT
            COUNT(*) AS total_peserta,
            SUM(CASE WHEN status = 'Lulus' THEN 1 ELSE 0 END) AS total_lulus,
            SUM(CASE WHEN status = 'Tidak Lulus' THEN 1 ELSE 0 END) AS total_tidak_lulus
        FROM hasil_ujian
    """, one=True)

    stats = {
        "total_peserta":     qdb("SELECT COUNT(*) AS c FROM peserta", one=True)["c"],
        "total_pendaftaran": qdb("SELECT COUNT(*) as c FROM pendaftaran", one=True)["c"],
        "total_lulus":       ringkas["total_lulus"],
        "total_tidak_lulus": ringkas["total_tidak_lulus"],
        "avg_skor":          qdb("SELECT ROUND(AVG(skor_rerata)::NUMERIC,2) AS a FROM hasil_ujian", one=True)["a"] or 0,
        "max_skor":          qdb("SELECT MAX(skor_rerata) AS m FROM hasil_ujian", one=True)["m"] or 0,
        "total_universitas": qdb("SELECT COUNT(*) AS c FROM universitas", one=True)["c"],
        "total_prodi":       qdb("SELECT COUNT(*) AS c FROM program_studi", one=True)["c"],
    }

    univ_chart = qdb("""
        SELECT u.nama_univ, ROUND(AVG(h.skor_rerata)::NUMERIC, 2) AS rata_skor
        FROM hasil_ujian h
        JOIN program_studi prodi ON h.id_prodi = prodi.id_prodi
        JOIN universitas u ON prodi.id_univ = u.id_univ
        WHERE h.status = 'Lulus'
        GROUP BY u.nama_univ
        ORDER BY rata_skor DESC
        LIMIT 10
    """)

    angkatan_chart = qdb("""
        SELECT p.angkatan,
               COUNT(*) AS total_peserta,
               SUM(CASE WHEN h.status='Lulus' THEN 1 ELSE 0 END) AS lulus,
               SUM(CASE WHEN h.status='Tidak Lulus' THEN 1 ELSE 0 END) AS tidak_lulus,
               ROUND(SUM(CASE WHEN h.status='Lulus' THEN 1 ELSE 0 END)::NUMERIC*100.0/COUNT(*),1) AS persen_lulus
        FROM peserta p
        JOIN pendaftaran reg ON p.nisn = reg.nisn
        JOIN hasil_ujian h ON reg.no_pendaftaran = h.no_pendaftaran
        GROUP BY p.angkatan
        ORDER BY p.angkatan ASC
    """)

    top_peserta = qdb("""
        SELECT p.nama_peserta, p.asal_sekolah,
               h.skor_rerata,
               prodi.nama_prodi || ' (' || prodi.jenjang || ')' AS jurusan,
               u.nama_univ
        FROM peserta p
        JOIN pendaftaran reg ON p.nisn = reg.nisn
        JOIN hasil_ujian h ON reg.no_pendaftaran = h.no_pendaftaran
        LEFT JOIN program_studi prodi ON h.id_prodi = prodi.id_prodi
        LEFT JOIN universitas u ON prodi.id_univ = u.id_univ
        WHERE h.status = 'Lulus'
        ORDER BY h.skor_rerata DESC
        LIMIT 5
    """)

    return render_template("index.html",
                           stats=stats,
                           univ_chart=[dict(r) for r in univ_chart],
                           angkatan_chart=[dict(r) for r in angkatan_chart],
                           top_peserta=[dict(r) for r in top_peserta])


# ══════════════════════════════════════════════════════════════════════════════
# PESERTA
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/peserta")
def peserta_list():
    search   = request.args.get("q", "").strip()
    angkatan = request.args.get("angkatan", "").strip()
    page     = int(request.args.get("page", 1))
    limit    = 100
    offset   = (page - 1) * limit
    
    # Count total (untuk pagination)
    sql_count = "SELECT COUNT(*) as c FROM peserta WHERE 1=1"
    args_count = []
    if search:
        sql_count += " AND (nama_peserta ILIKE %s OR asal_sekolah ILIKE %s OR nisn ILIKE %s)"
        args_count += [f"%{search}%", f"%{search}%", f"%{search}%"]
    if angkatan:
        sql_count += " AND angkatan = %s"
        args_count.append(int(angkatan))
    total = qdb(sql_count, args_count, one=True)["c"]
    
    # Fetch data
    sql  = "SELECT * FROM peserta WHERE 1=1"
    args = []
    if search:
        sql  += " AND (nama_peserta ILIKE %s OR asal_sekolah ILIKE %s OR nisn ILIKE %s)"
        args += [f"%{search}%", f"%{search}%", f"%{search}%"]
    if angkatan:
        sql  += " AND angkatan = %s"
        args.append(int(angkatan))
    sql += " ORDER BY nama_peserta LIMIT %s OFFSET %s"
    args += [limit, offset]
    rows = qdb(sql, args)
    
    max_page = (total + limit - 1) // limit
    return render_template("peserta.html", rows=rows, search=search, angkatan=angkatan, 
                         page=page, max_page=max_page, total=total)


@app.route("/peserta/tambah", methods=["GET", "POST"])
def peserta_tambah():
    # NISN diisi manual (bukan sequence — ini nomor identitas nasional eksternal)
    if request.method == "POST":
        f = request.form
        if not f["nisn"].isdigit() or len(f["nisn"]) != 10:
            flash("❌ NISN harus 10 angka!", "danger")
            return render_template("form_peserta.html", action="tambah", data=f)
        try:
            xdb("""INSERT INTO peserta
                   (nisn, nama_peserta, tgl_lahir, asal_sekolah, angkatan, alamat_peserta)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (f["nisn"], f["nama_peserta"], f["tgl_lahir"],
                 f["asal_sekolah"], int(f["angkatan"]), f["alamat_peserta"]))
            flash("Peserta berhasil ditambahkan.", "success")
            return redirect(url_for("peserta_list"))
        except Error:
            flash("NISN sudah terdaftar atau data tidak valid.", "danger")
    return render_template("form_peserta.html", action="tambah", data={})


@app.route("/peserta/edit/<nisn>", methods=["GET", "POST"])
def peserta_edit(nisn):
    row = qdb("SELECT * FROM peserta WHERE nisn=%s", (nisn,), one=True)
    if not row:
        flash("Peserta tidak ditemukan.", "warning")
        return redirect(url_for("peserta_list"))
    if request.method == "POST":
        f = request.form
        xdb("""UPDATE peserta SET nama_peserta=%s, tgl_lahir=%s, asal_sekolah=%s,
               angkatan=%s, alamat_peserta=%s WHERE nisn=%s""",
            (f["nama_peserta"], f["tgl_lahir"], f["asal_sekolah"],
             int(f["angkatan"]), f["alamat_peserta"], nisn))
        flash("Data peserta berhasil diperbarui.", "success")
        return redirect(url_for("peserta_list"))
    return render_template("form_peserta.html", action="edit", data=dict(row))


@app.route("/peserta/hapus/<nisn>", methods=["POST"])
def peserta_hapus(nisn):
    try:
        xdb("DELETE FROM peserta WHERE nisn=%s", (nisn,))
        flash("Peserta berhasil dihapus.", "success")
    except Error:
        flash("Peserta tidak dapat dihapus karena masih memiliki data terkait.", "danger")
    return redirect(url_for("peserta_list"))


# ══════════════════════════════════════════════════════════════════════════════
# UNIVERSITAS
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/universitas")
def universitas_list():
    search = request.args.get("q", "").strip()
    page   = int(request.args.get("page", 1))
    limit  = 100
    offset = (page - 1) * limit
    
    sql_count = "SELECT COUNT(*) as c FROM universitas WHERE 1=1"
    args_count = []
    if search:
        sql_count += " AND (nama_univ ILIKE %s OR alamat_univ ILIKE %s)"
        args_count += [f"%{search}%", f"%{search}%"]
    total = qdb(sql_count, args_count, one=True)["c"]
    
    sql  = "SELECT * FROM universitas WHERE 1=1"
    args = []
    if search:
        sql  += " AND (nama_univ ILIKE %s OR alamat_univ ILIKE %s)"
        args += [f"%{search}%", f"%{search}%"]
    sql += " ORDER BY nama_univ LIMIT %s OFFSET %s"
    args += [limit, offset]
    rows = qdb(sql, args)
    
    max_page = (total + limit - 1) // limit
    return render_template("universitas.html", rows=rows, search=search, page=page, max_page=max_page, total=total)


@app.route("/universitas/tambah", methods=["GET", "POST"])
def universitas_tambah():
    auto_id = next_id_univ()
    if request.method == "POST":
        f = request.form
        id_univ = f.get("id_univ", auto_id)
        try:
            xdb("INSERT INTO universitas VALUES (%s,%s,%s)",
                (id_univ, f["nama_univ"], f["alamat_univ"]))
            flash("Universitas berhasil ditambahkan.", "success")
            return redirect(url_for("universitas_list"))
        except Error:
            flash("ID universitas sudah ada.", "danger")
    return render_template("form_universitas.html", action="tambah", data={}, auto_id=auto_id)


@app.route("/universitas/edit/<id_univ>", methods=["GET", "POST"])
def universitas_edit(id_univ):
    row = qdb("SELECT * FROM universitas WHERE id_univ=%s", (id_univ,), one=True)
    if not row:
        flash("Universitas tidak ditemukan.", "warning")
        return redirect(url_for("universitas_list"))
    if request.method == "POST":
        f = request.form
        xdb("UPDATE universitas SET nama_univ=%s, alamat_univ=%s WHERE id_univ=%s",
            (f["nama_univ"], f["alamat_univ"], id_univ))
        flash("Data universitas berhasil diperbarui.", "success")
        return redirect(url_for("universitas_list"))
    return render_template("form_universitas.html", action="edit", data=dict(row), auto_id=id_univ)


@app.route("/universitas/hapus/<id_univ>", methods=["POST"])
def universitas_hapus(id_univ):
    try:
        xdb("DELETE FROM universitas WHERE id_univ=%s", (id_univ,))
        flash("Universitas berhasil dihapus.", "success")
    except Error:
        flash("Universitas tidak dapat dihapus karena masih memiliki data terkait.", "danger")
    return redirect(url_for("universitas_list"))


# ══════════════════════════════════════════════════════════════════════════════
# PROGRAM STUDI
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/program-studi")
def prodi_list():
    search  = request.args.get("q", "").strip()
    jenjang = request.args.get("jenjang", "").strip()
    id_univ = request.args.get("id_univ", "").strip()
    page    = int(request.args.get("page", 1))
    limit   = 100
    offset  = (page - 1) * limit
    
    base = """FROM program_studi ps JOIN universitas u ON ps.id_univ = u.id_univ WHERE 1=1"""
    args = []
    if search:
        base += " AND ps.nama_prodi ILIKE %s"
        args.append(f"%{search}%")
    if jenjang:
        base += " AND ps.jenjang = %s"
        args.append(jenjang)
    if id_univ:
        base += " AND ps.id_univ = %s"
        args.append(id_univ)
    
    total = qdb(f"SELECT COUNT(*) as c {base}", args, one=True)["c"]
    rows = qdb(f"SELECT ps.*, u.nama_univ {base} ORDER BY u.nama_univ, ps.nama_prodi LIMIT %s OFFSET %s", 
               args + [limit, offset])
    univs = qdb("SELECT id_univ, nama_univ FROM universitas ORDER BY nama_univ")
    
    max_page = (total + limit - 1) // limit
    return render_template("program_studi.html", rows=rows, univs=univs,
                           search=search, jenjang=jenjang, id_univ=id_univ, 
                           page=page, max_page=max_page, total=total)


@app.route("/program-studi/tambah", methods=["GET", "POST"])
def prodi_tambah():
    univs   = qdb("SELECT id_univ, nama_univ FROM universitas ORDER BY nama_univ")
    auto_id = next_id_prodi()
    if request.method == "POST":
        f = request.form
        id_prodi = f.get("id_prodi", auto_id)
        try:
            xdb("INSERT INTO program_studi VALUES (%s,%s,%s,%s,%s)",
                (id_prodi.upper(), f["nama_prodi"],
                 f["jenjang"], int(f["kuota"]), f["id_univ"]))
            flash("Program studi berhasil ditambahkan.", "success")
            return redirect(url_for("prodi_list"))
        except Error:
            flash("ID prodi sudah ada.", "danger")
    return render_template("form_prodi.html", action="tambah", data={}, univs=univs, auto_id=auto_id)


@app.route("/program-studi/edit/<id_prodi>", methods=["GET", "POST"])
def prodi_edit(id_prodi):
    row   = qdb("SELECT * FROM program_studi WHERE id_prodi=%s", (id_prodi,), one=True)
    univs = qdb("SELECT id_univ, nama_univ FROM universitas ORDER BY nama_univ")
    if not row:
        flash("Program studi tidak ditemukan.", "warning")
        return redirect(url_for("prodi_list"))
    if request.method == "POST":
        f = request.form
        xdb("UPDATE program_studi SET nama_prodi=%s, jenjang=%s, kuota=%s, id_univ=%s WHERE id_prodi=%s",
            (f["nama_prodi"], f["jenjang"], int(f["kuota"]), f["id_univ"], id_prodi))
        flash("Program studi berhasil diperbarui.", "success")
        return redirect(url_for("prodi_list"))
    return render_template("form_prodi.html", action="edit", data=dict(row), univs=univs, auto_id=id_prodi)


@app.route("/program-studi/hapus/<id_prodi>", methods=["POST"])
def prodi_hapus(id_prodi):
    try:
        xdb("DELETE FROM program_studi WHERE id_prodi=%s", (id_prodi,))
        flash("Program studi berhasil dihapus.", "success")
    except Error:
        flash("Program studi tidak dapat dihapus karena masih memiliki data terkait.", "danger")
    return redirect(url_for("prodi_list"))


# ══════════════════════════════════════════════════════════════════════════════
# LOKASI
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/lokasi")
def lokasi_list():
    search  = request.args.get("q", "").strip()
    id_univ = request.args.get("id_univ", "").strip()
    page    = int(request.args.get("page", 1))
    limit   = 100
    offset  = (page - 1) * limit
    
    base = """FROM lokasi l JOIN universitas u ON l.id_univ=u.id_univ WHERE 1=1"""
    args = []
    if search:
        base += " AND (l.nama_ruang ILIKE %s OR l.gedung ILIKE %s OR u.nama_univ ILIKE %s)"
        args += [f"%{search}%", f"%{search}%", f"%{search}%"]
    if id_univ:
        base += " AND l.id_univ = %s"
        args.append(id_univ)
    
    total = qdb(f"SELECT COUNT(*) as c {base}", args, one=True)["c"]
    rows = qdb(f"SELECT l.*, u.nama_univ {base} ORDER BY u.nama_univ, l.gedung LIMIT %s OFFSET %s",
               args + [limit, offset])
    univs = qdb("SELECT id_univ, nama_univ FROM universitas ORDER BY nama_univ")
    
    max_page = (total + limit - 1) // limit
    return render_template("lokasi.html", rows=rows, search=search, id_univ=id_univ, univs=univs,
                          page=page, max_page=max_page, total=total)


@app.route("/lokasi/tambah", methods=["GET", "POST"])
def lokasi_tambah():
    univs   = qdb("SELECT id_univ, nama_univ FROM universitas ORDER BY nama_univ")
    auto_id = next_id_lokasi()
    if request.method == "POST":
        f = request.form
        id_lokasi = f.get("id_lokasi", auto_id)
        try:
            xdb("INSERT INTO lokasi VALUES (%s,%s,%s,%s)",
                (id_lokasi.upper(), f["nama_ruang"], f["gedung"], f["id_univ"]))
            flash("Lokasi berhasil ditambahkan.", "success")
            return redirect(url_for("lokasi_list"))
        except Error:
            flash("ID lokasi sudah ada.", "danger")
    return render_template("form_lokasi.html", action="tambah", data={}, univs=univs, auto_id=auto_id)


@app.route("/lokasi/edit/<id_lokasi>", methods=["GET", "POST"])
def lokasi_edit(id_lokasi):
    univs = qdb("SELECT id_univ, nama_univ FROM universitas ORDER BY nama_univ")
    row   = qdb("SELECT * FROM lokasi WHERE id_lokasi=%s", (id_lokasi,), one=True)
    if not row:
        flash("Lokasi tidak ditemukan.", "warning")
        return redirect(url_for("lokasi_list"))
    if request.method == "POST":
        f = request.form
        xdb("UPDATE lokasi SET nama_ruang=%s, gedung=%s, id_univ=%s WHERE id_lokasi=%s",
            (f["nama_ruang"], f["gedung"], f["id_univ"], id_lokasi))
        flash("Lokasi berhasil diperbarui.", "success")
        return redirect(url_for("lokasi_list"))
    return render_template("form_lokasi.html", action="edit", data=dict(row), univs=univs, auto_id=id_lokasi)


@app.route("/lokasi/hapus/<id_lokasi>", methods=["POST"])
def lokasi_hapus(id_lokasi):
    try:
        xdb("DELETE FROM lokasi WHERE id_lokasi=%s", (id_lokasi,))
        flash("Lokasi berhasil dihapus.", "success")
    except Error:
        flash("Lokasi tidak dapat dihapus karena masih memiliki data terkait.", "danger")
    return redirect(url_for("lokasi_list"))


# ══════════════════════════════════════════════════════════════════════════════
# PENGAWAS
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/pengawas")
def pengawas_list():
    search  = request.args.get("q", "").strip()
    id_univ = request.args.get("id_univ", "").strip()
    page    = int(request.args.get("page", 1))
    limit   = 100
    offset  = (page - 1) * limit
    
    base = """FROM pengawas pg
              JOIN lokasi l ON pg.id_lokasi = l.id_lokasi
              JOIN universitas u ON l.id_univ = u.id_univ
              WHERE 1=1"""
    args = []
    if search:
        base += " AND (pg.nama_pengawas ILIKE %s OR u.nama_univ ILIKE %s)"
        args += [f"%{search}%", f"%{search}%"]
    if id_univ:
        base += " AND u.id_univ = %s"
        args.append(id_univ)
    
    total = qdb(f"SELECT COUNT(*) as c {base}", args, one=True)["c"]
    rows = qdb(f"SELECT pg.*, l.nama_ruang, l.gedung, u.nama_univ, u.id_univ {base} ORDER BY pg.nama_pengawas LIMIT %s OFFSET %s",
               args + [limit, offset])
    univs = qdb("SELECT id_univ, nama_univ FROM universitas ORDER BY nama_univ")
    
    max_page = (total + limit - 1) // limit
    return render_template("pengawas.html", rows=rows, search=search, id_univ=id_univ, univs=univs,
                          page=page, max_page=max_page, total=total)


@app.route("/pengawas/tambah", methods=["GET", "POST"])
def pengawas_tambah():
    lokasis = qdb("""SELECT l.id_lokasi, l.nama_ruang, l.gedung, u.nama_univ
                     FROM lokasi l JOIN universitas u ON l.id_univ=u.id_univ
                     ORDER BY u.nama_univ""")
    auto_id = next_id_pengawas()
    if request.method == "POST":
        f = request.form
        id_pengawas = f.get("id_pengawas", auto_id)
        try:
            xdb("INSERT INTO pengawas VALUES (%s,%s,%s)",
                (id_pengawas.upper(), f["nama_pengawas"], f["id_lokasi"]))
            flash("Pengawas berhasil ditambahkan.", "success")
            return redirect(url_for("pengawas_list"))
        except Error:
            flash("ID pengawas sudah ada.", "danger")
    return render_template("form_pengawas.html", action="tambah", data={}, lokasis=lokasis, auto_id=auto_id)


@app.route("/pengawas/edit/<id_pengawas>", methods=["GET", "POST"])
def pengawas_edit(id_pengawas):
    lokasis = qdb("""SELECT l.id_lokasi, l.nama_ruang, l.gedung, u.nama_univ
                     FROM lokasi l JOIN universitas u ON l.id_univ=u.id_univ
                     ORDER BY u.nama_univ""")
    row = qdb("SELECT * FROM pengawas WHERE id_pengawas=%s", (id_pengawas,), one=True)
    if not row:
        flash("Pengawas tidak ditemukan.", "warning")
        return redirect(url_for("pengawas_list"))
    if request.method == "POST":
        f = request.form
        xdb("UPDATE pengawas SET nama_pengawas=%s, id_lokasi=%s WHERE id_pengawas=%s",
            (f["nama_pengawas"], f["id_lokasi"], id_pengawas))
        flash("Pengawas berhasil diperbarui.", "success")
        return redirect(url_for("pengawas_list"))
    return render_template("form_pengawas.html", action="edit", data=dict(row), lokasis=lokasis, auto_id=id_pengawas)


@app.route("/pengawas/hapus/<id_pengawas>", methods=["POST"])
def pengawas_hapus(id_pengawas):
    xdb("DELETE FROM pengawas WHERE id_pengawas=%s", (id_pengawas,))
    flash("Pengawas berhasil dihapus.", "success")
    return redirect(url_for("pengawas_list"))


# ══════════════════════════════════════════════════════════════════════════════
# PENDAFTARAN
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/pendaftaran")
def pendaftaran_list():
    search  = request.args.get("q", "").strip()
    no_sesi = request.args.get("no_sesi", "").strip()
    id_univ = request.args.get("id_univ", "").strip()
    page    = int(request.args.get("page", 1))
    limit   = 50  # lebih kecil karena query berat (6 JOIN)
    offset  = (page - 1) * limit
    
    base = """FROM pendaftaran pd
              JOIN peserta     p  ON pd.nisn       = p.nisn
              JOIN lokasi      l  ON pd.id_lokasi  = l.id_lokasi
              JOIN universitas u  ON l.id_univ     = u.id_univ
              JOIN sesi        s  ON pd.no_sesi    = s.no_sesi
              WHERE 1=1"""
    args = []
    if search:
        base += " AND (p.nama_peserta ILIKE %s OR pd.no_pendaftaran ILIKE %s)"
        args += [f"%{search}%", f"%{search}%"]
    if no_sesi:
        base += " AND pd.no_sesi = %s"
        args.append(no_sesi)
    if id_univ:
        base += " AND u.id_univ = %s"
        args.append(id_univ)
    
    total = qdb(f"SELECT COUNT(*) as c {base}", args, one=True)["c"]
    rows = qdb(f"""SELECT pd.*, p.nama_peserta, l.nama_ruang, l.gedung,
                          u.nama_univ, u.id_univ, s.waktu {base}
                   ORDER BY pd.tgl_ujian DESC, pd.no_pendaftaran DESC LIMIT %s OFFSET %s""",
               args + [limit, offset])
    sesis = qdb("SELECT * FROM sesi ORDER BY no_sesi")
    univs = qdb("SELECT id_univ, nama_univ FROM universitas ORDER BY nama_univ")
    
    max_page = (total + limit - 1) // limit
    return render_template("pendaftaran.html", rows=rows, search=search,
                           no_sesi=no_sesi, id_univ=id_univ,
                           sesis=sesis, univs=univs,
                           page=page, max_page=max_page, total=total)


@app.route("/pendaftaran/tambah", methods=["GET", "POST"])
def pendaftaran_tambah():
    peserta_rows = qdb("SELECT nisn, nama_peserta FROM peserta ORDER BY nama_peserta")
    lokasi_rows  = qdb("""SELECT l.id_lokasi, l.nama_ruang, l.gedung, u.nama_univ
                          FROM lokasi l JOIN universitas u ON l.id_univ=u.id_univ
                          ORDER BY u.nama_univ""")
    sesi_rows    = qdb("SELECT * FROM sesi ORDER BY no_sesi")
    auto_id      = next_no_pendaftaran()
    if request.method == "POST":
        f = request.form
        no_pend = f.get("no_pendaftaran", auto_id)
        try:
            xdb("""INSERT INTO pendaftaran
                   (no_pendaftaran, nisn, id_lokasi, no_sesi, tgl_pendaftaran, tgl_ujian)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (no_pend.upper(), f["nisn"], f["id_lokasi"],
                 f["no_sesi"], f["tgl_pendaftaran"], f["tgl_ujian"]))
            flash("Pendaftaran berhasil ditambahkan.", "success")
            return redirect(url_for("pendaftaran_list"))
        except Error:
            flash("NISN sudah terdaftar atau data tidak valid.", "danger")
    return render_template("form_pendaftaran.html",
                           action="tambah", data={},
                           peserta_rows=peserta_rows,
                           lokasi_rows=lokasi_rows,
                           sesi_rows=sesi_rows,
                           auto_id=auto_id)


@app.route("/pendaftaran/hapus/<no_pendaftaran>", methods=["POST"])
def pendaftaran_hapus(no_pendaftaran):
    try:
        xdb("DELETE FROM pendaftaran WHERE no_pendaftaran=%s", (no_pendaftaran,))
        flash("Pendaftaran berhasil dihapus.", "success")
    except Error:
        flash("Pendaftaran tidak dapat dihapus karena masih memiliki data hasil ujian.", "danger")
    return redirect(url_for("pendaftaran_list"))


@app.route("/pendaftaran/edit/<no_pendaftaran>", methods=["GET", "POST"])
def pendaftaran_edit(no_pendaftaran):
    peserta_rows = qdb("SELECT nisn, nama_peserta FROM peserta ORDER BY nama_peserta")
    lokasi_rows  = qdb("""SELECT l.id_lokasi, l.nama_ruang, l.gedung, u.nama_univ
                          FROM lokasi l JOIN universitas u ON l.id_univ=u.id_univ
                          ORDER BY u.nama_univ""")
    sesi_rows    = qdb("SELECT * FROM sesi ORDER BY no_sesi")
    row = qdb("SELECT * FROM pendaftaran WHERE no_pendaftaran=%s", (no_pendaftaran,), one=True)
    if not row:
        flash("Pendaftaran tidak ditemukan.", "warning")
        return redirect(url_for("pendaftaran_list"))
    if request.method == "POST":
        f = request.form
        xdb("""UPDATE pendaftaran SET nisn=%s, id_lokasi=%s, no_sesi=%s, tgl_pendaftaran=%s, tgl_ujian=%s
               WHERE no_pendaftaran=%s""",
            (f["nisn"], f["id_lokasi"], f["no_sesi"], f["tgl_pendaftaran"], f["tgl_ujian"], no_pendaftaran))
        flash("Pendaftaran berhasil diperbarui.", "success")
        return redirect(url_for("pendaftaran_list"))
    return render_template("form_pendaftaran.html",
                           action="edit", data=dict(row),
                           peserta_rows=peserta_rows,
                           lokasi_rows=lokasi_rows,
                           sesi_rows=sesi_rows,
                           auto_id=no_pendaftaran)


# ══════════════════════════════════════════════════════════════════════════════
# HASIL UJIAN
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/hasil-ujian")
def hasil_list():
    search   = request.args.get("q", "").strip()
    status   = request.args.get("status", "").strip()
    id_univ  = request.args.get("id_univ", "").strip()
    skor_min = request.args.get("skor_min", "").strip()
    skor_max = request.args.get("skor_max", "").strip()
    page     = int(request.args.get("page", 1))
    limit    = 50  # kecil karena query berat
    offset   = (page - 1) * limit

    base = """FROM hasil_ujian hu
        JOIN pendaftaran pd ON hu.no_pendaftaran = pd.no_pendaftaran
        JOIN peserta p ON pd.nisn = p.nisn
        LEFT JOIN sesi s ON pd.no_sesi = s.no_sesi
        LEFT JOIN program_studi ps_diterima ON hu.id_prodi = ps_diterima.id_prodi
        LEFT JOIN universitas u_diterima ON ps_diterima.id_univ = u_diterima.id_univ
        WHERE 1=1"""
    args = []
    if search:
        base += " AND (p.nama_peserta ILIKE %s OR p.nisn ILIKE %s)"
        args += [f"%{search}%", f"%{search}%"]
    if status:
        base += " AND hu.status = %s"
        args.append(status)
    if id_univ:
        base += " AND u_diterima.id_univ = %s"
        args.append(id_univ)
    if skor_min:
        base += " AND hu.skor_rerata >= %s"
        args.append(float(skor_min))
    if skor_max:
        base += " AND hu.skor_rerata <= %s"
        args.append(float(skor_max))

    total = qdb(f"SELECT COUNT(*) as c {base}", args, one=True)["c"]
    rows = qdb(f"""SELECT hu.id_hasil, hu.no_pendaftaran, hu.skor_rerata, hu.status,
               hu.id_prodi,
               p.nama_peserta, p.nisn, p.angkatan,
               pd.no_sesi, s.waktu AS waktu_sesi,
               ps_diterima.nama_prodi AS prodi_diterima,
               ps_diterima.jenjang   AS jenjang_diterima,
               u_diterima.id_univ    AS univ_id_diterima,
               u_diterima.nama_univ  AS univ_diterima {base}
        ORDER BY hu.skor_rerata DESC LIMIT %s OFFSET %s""",
              args + [limit, offset])
    univs = qdb("SELECT id_univ, nama_univ FROM universitas ORDER BY nama_univ")
    
    max_page = (total + limit - 1) // limit
    return render_template("hasil_ujian.html", rows=rows, univs=univs,
                           search=search, status=status, id_univ=id_univ,
                           skor_min=skor_min, skor_max=skor_max,
                           page=page, max_page=max_page, total=total)


@app.route("/hasil-ujian/tambah", methods=["GET", "POST"])
def hasil_tambah():
    pend_rows = qdb("""
        SELECT pd.no_pendaftaran, p.nama_peserta
        FROM pendaftaran pd JOIN peserta p ON pd.nisn = p.nisn
        WHERE pd.no_pendaftaran NOT IN (SELECT no_pendaftaran FROM hasil_ujian)
        ORDER BY p.nama_peserta
    """)
    prodi_rows = qdb("""SELECT ps.id_prodi, ps.nama_prodi, ps.jenjang, u.nama_univ
                        FROM program_studi ps JOIN universitas u ON ps.id_univ=u.id_univ
                        ORDER BY u.nama_univ, ps.nama_prodi""")
    auto_id = next_id_hasil()
    if request.method == "POST":
        f = request.form
        id_hasil = f.get("id_hasil", auto_id)
        id_prodi = f.get("id_prodi") or None
        try:
            xdb("""INSERT INTO hasil_ujian
                   (id_hasil, no_pendaftaran, skor_rerata, status, id_prodi)
                   VALUES (%s,%s,%s,%s,%s)""",
                (id_hasil.upper(), f["no_pendaftaran"],
                 float(f["skor_rerata"]), f["status"], id_prodi))
            flash("Hasil ujian berhasil ditambahkan.", "success")
            return redirect(url_for("hasil_list"))
        except Error:
            flash("ID hasil sudah ada atau data tidak valid.", "danger")
    return render_template("form_hasil.html", action="tambah", data={},
                           pend_rows=pend_rows, prodi_rows=prodi_rows, auto_id=auto_id)


@app.route("/hasil-ujian/edit/<id_hasil>", methods=["GET", "POST"])
def hasil_edit(id_hasil):
    pend_rows  = qdb("""SELECT pd.no_pendaftaran, p.nama_peserta
                        FROM pendaftaran pd JOIN peserta p ON pd.nisn = p.nisn
                        ORDER BY p.nama_peserta""")
    prodi_rows = qdb("""SELECT ps.id_prodi, ps.nama_prodi, ps.jenjang, u.nama_univ
                        FROM program_studi ps JOIN universitas u ON ps.id_univ=u.id_univ
                        ORDER BY u.nama_univ, ps.nama_prodi""")
    row = qdb("SELECT * FROM hasil_ujian WHERE id_hasil=%s", (id_hasil,), one=True)
    if not row:
        flash("Hasil ujian tidak ditemukan.", "warning")
        return redirect(url_for("hasil_list"))
    if request.method == "POST":
        f = request.form
        id_prodi = f.get("id_prodi") or None
        xdb("""UPDATE hasil_ujian SET no_pendaftaran=%s, skor_rerata=%s, status=%s, id_prodi=%s
               WHERE id_hasil=%s""",
            (f["no_pendaftaran"], float(f["skor_rerata"]), f["status"], id_prodi, id_hasil))
        flash("Hasil ujian berhasil diperbarui.", "success")
        return redirect(url_for("hasil_list"))
    return render_template("form_hasil.html", action="edit", data=dict(row),
                           pend_rows=pend_rows, prodi_rows=prodi_rows, auto_id=id_hasil)


@app.route("/hasil-ujian/hapus/<id_hasil>", methods=["POST"])
def hasil_hapus(id_hasil):
    xdb("DELETE FROM hasil_ujian WHERE id_hasil=%s", (id_hasil,))
    flash("Hasil ujian berhasil dihapus.", "success")
    return redirect(url_for("hasil_list"))


# ══════════════════════════════════════════════════════════════════════════════
# SESI
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/sesi")
def sesi_list():
    rows = qdb("SELECT * FROM sesi ORDER BY no_sesi")
    return render_template("sesi.html", rows=rows)

@app.route("/sesi/tambah", methods=["GET", "POST"])
def sesi_tambah():
    auto_id = next_no_sesi()
    if request.method == "POST":
        f = request.form
        no_sesi = f.get("no_sesi", auto_id)
        try:
            xdb("INSERT INTO sesi (no_sesi, waktu) VALUES (%s,%s)",
                (no_sesi.strip(), f["waktu"].strip()))
            flash("Sesi berhasil ditambahkan.", "success")
            return redirect(url_for("sesi_list"))
        except Error:
            flash("No. sesi sudah ada.", "danger")
    return render_template("form_sesi.html", action="tambah", data={}, auto_id=auto_id)

@app.route("/sesi/edit/<no_sesi>", methods=["GET", "POST"])
def sesi_edit(no_sesi):
    data = qdb("SELECT * FROM sesi WHERE no_sesi=%s", (no_sesi,))
    if not data:
        flash("Sesi tidak ditemukan.", "danger")
        return redirect(url_for("sesi_list"))
    if request.method == "POST":
        f = request.form
        xdb("UPDATE sesi SET waktu=%s WHERE no_sesi=%s",
            (f["waktu"].strip(), no_sesi))
        flash("Sesi berhasil diperbarui.", "success")
        return redirect(url_for("sesi_list"))
    return render_template("form_sesi.html", action="edit", data=data[0], auto_id=no_sesi)

@app.route("/sesi/hapus/<no_sesi>", methods=["POST"])
def sesi_hapus(no_sesi):
    try:
        xdb("DELETE FROM sesi WHERE no_sesi=%s", (no_sesi,))
        flash("Sesi berhasil dihapus.", "success")
    except Error:
        flash("Sesi tidak bisa dihapus karena masih digunakan.", "danger")
    return redirect(url_for("sesi_list"))


# ══════════════════════════════════════════════════════════════════════════════
# PILIHAN PRODI
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/pilihan-prodi")
def pilihan_prodi_list():
    search     = request.args.get("q", "").strip()
    pilihan_ke = request.args.get("pilihan_ke", "").strip()
    id_univ    = request.args.get("id_univ", "").strip()
    page       = int(request.args.get("page", 1))
    limit      = 100
    offset     = (page - 1) * limit
    
    base = """FROM pilihan_prodi pp
             JOIN pendaftaran pd ON pp.no_pendaftaran = pd.no_pendaftaran
             JOIN peserta p ON pd.nisn = p.nisn
             JOIN program_studi ps ON pp.id_prodi = ps.id_prodi
             JOIN universitas u ON ps.id_univ = u.id_univ
             WHERE 1=1"""
    args = []
    if search:
        base += " AND (p.nama_peserta ILIKE %s OR pp.no_pendaftaran ILIKE %s)"
        args += [f"%{search}%", f"%{search}%"]
    if pilihan_ke:
        base += " AND pp.pilihan_ke = %s"
        args.append(pilihan_ke)
    if id_univ:
        base += " AND u.id_univ = %s"
        args.append(id_univ)
    
    total = qdb(f"SELECT COUNT(*) as c {base}", args, one=True)["c"]
    rows = qdb(f"""SELECT pp.no_pendaftaran, pp.id_prodi, pp.pilihan_ke,
                    p.nama_peserta,
                    ps.nama_prodi, ps.jenjang,
                    u.nama_univ, u.id_univ {base}
             ORDER BY pp.no_pendaftaran, pp.pilihan_ke LIMIT %s OFFSET %s""",
               args + [limit, offset])
    univs = qdb("SELECT id_univ, nama_univ FROM universitas ORDER BY nama_univ")
    
    max_page = (total + limit - 1) // limit
    return render_template("pilihan_prodi.html", rows=rows,
                           search=search, pilihan_ke=pilihan_ke,
                           id_univ=id_univ, univs=univs,
                           page=page, max_page=max_page, total=total)

@app.route("/pilihan-prodi/tambah", methods=["GET", "POST"])
def pilihan_prodi_tambah():
    pendaftaran_rows = qdb("""SELECT pd.no_pendaftaran, p.nama_peserta
                               FROM pendaftaran pd JOIN peserta p ON pd.nisn=p.nisn
                               ORDER BY pd.no_pendaftaran""")
    prodi_rows = qdb("""SELECT ps.id_prodi, ps.nama_prodi, ps.jenjang, u.nama_univ
                        FROM program_studi ps JOIN universitas u ON ps.id_univ=u.id_univ
                        ORDER BY u.nama_univ, ps.nama_prodi""")
    if request.method == "POST":
        f = request.form
        # ← TAMBAH VALIDATION DI SINI (4 baris)
        existing = qdb(
            "SELECT * FROM pilihan_prodi WHERE no_pendaftaran=%s AND pilihan_ke=%s",
            (f["no_pendaftaran"], int(f["pilihan_ke"])),
            one=True
        )
        if existing:
            flash(f"❌ Pilihan ke-{f['pilihan_ke']} sudah ada untuk pendaftaran ini!", "danger")
            return render_template("form_pilihan_prodi.html", action="tambah", data=f,
                                   pendaftaran_rows=pendaftaran_rows, prodi_rows=prodi_rows)
        # Validation 2: harus isi Pilihan 1 dulu ← TAMBAH INI
        if int(f["pilihan_ke"]) > 1:
            existing_pilihan_1 = qdb(
                "SELECT * FROM pilihan_prodi WHERE no_pendaftaran=%s AND pilihan_ke=1",
                (f["no_pendaftaran"],),
                one=True
            )
            if not existing_pilihan_1:
                flash("❌ Harus isi Pilihan 1 dulu sebelum Pilihan 2!", "danger")
                return render_template("form_pilihan_prodi.html", action="tambah", data=f,
                                       pendaftaran_rows=pendaftaran_rows, prodi_rows=prodi_rows)
        try:
            xdb("INSERT INTO pilihan_prodi (no_pendaftaran, id_prodi, pilihan_ke) VALUES (%s,%s,%s)",
                (f["no_pendaftaran"], f["id_prodi"], int(f["pilihan_ke"])))
            flash("Pilihan prodi berhasil ditambahkan.", "success")
            return redirect(url_for("pilihan_prodi_list"))
        except Error:
            flash("Kombinasi no. pendaftaran + prodi sudah ada, atau pilihan ke sudah terisi.", "danger")
    return render_template("form_pilihan_prodi.html", action="tambah", data={},
                           pendaftaran_rows=pendaftaran_rows, prodi_rows=prodi_rows)

@app.route("/pilihan-prodi/hapus/<no_pendaftaran>/<id_prodi>", methods=["POST"])
def pilihan_prodi_hapus(no_pendaftaran, id_prodi):
    xdb("DELETE FROM pilihan_prodi WHERE no_pendaftaran=%s AND id_prodi=%s",
        (no_pendaftaran, id_prodi))
    flash("Pilihan prodi berhasil dihapus.", "success")
    return redirect(url_for("pilihan_prodi_list"))


@app.route("/pilihan-prodi/edit/<no_pendaftaran>/<id_prodi>", methods=["GET", "POST"])
def pilihan_prodi_edit(no_pendaftaran, id_prodi):
    pendaftaran_rows = qdb("""SELECT pd.no_pendaftaran, p.nama_peserta
                               FROM pendaftaran pd JOIN peserta p ON pd.nisn=p.nisn
                               ORDER BY pd.no_pendaftaran""")
    prodi_rows = qdb("""SELECT ps.id_prodi, ps.nama_prodi, ps.jenjang, u.nama_univ
                        FROM program_studi ps JOIN universitas u ON ps.id_univ=u.id_univ
                        ORDER BY u.nama_univ, ps.nama_prodi""")
    row = qdb("SELECT * FROM pilihan_prodi WHERE no_pendaftaran=%s AND id_prodi=%s",
              (no_pendaftaran, id_prodi), one=True)
    if not row:
        flash("Pilihan prodi tidak ditemukan.", "warning")
        return redirect(url_for("pilihan_prodi_list"))
    if request.method == "POST":
        f = request.form
        new_id_prodi = f["id_prodi"]
        new_pilihan_ke = int(f["pilihan_ke"])
        try:
            xdb("""UPDATE pilihan_prodi SET id_prodi=%s, pilihan_ke=%s
                   WHERE no_pendaftaran=%s AND id_prodi=%s""",
                (new_id_prodi, new_pilihan_ke, no_pendaftaran, id_prodi))
            flash("Pilihan prodi berhasil diperbarui.", "success")
        except Error:
            flash("Kombinasi sudah ada atau pilihan ke sudah terisi.", "danger")
        return redirect(url_for("pilihan_prodi_list"))
    return render_template("form_pilihan_prodi.html", action="edit", data=dict(row),
                           pendaftaran_rows=pendaftaran_rows, prodi_rows=prodi_rows)


# ══════════════════════════════════════════════════════════════════════════════
# ANALISIS
# ══════════════════════════════════════════════════════════════════════════════
@app.route("/analisis")
def analisis():
    nisn_cari = request.args.get("nisn_cari", "").strip()

    q1 = qdb("""
        SELECT p.nisn, p.nama_peserta, p.asal_sekolah,
               h.skor_rerata, h.status,
               prodi.nama_prodi || ' (' || prodi.jenjang || ')' AS jurusan,
               u.nama_univ
        FROM peserta p
        JOIN pendaftaran reg ON p.nisn = reg.nisn
        JOIN hasil_ujian h ON reg.no_pendaftaran = h.no_pendaftaran
        LEFT JOIN program_studi prodi ON h.id_prodi = prodi.id_prodi
        LEFT JOIN universitas u ON prodi.id_univ = u.id_univ
        WHERE h.status = 'Lulus'
        ORDER BY h.skor_rerata DESC
        LIMIT 10
    """)
    q2 = qdb("""
        SELECT p.angkatan, COUNT(*) AS jumlah_lulus
        FROM peserta p
        JOIN pendaftaran reg ON p.nisn = reg.nisn
        JOIN hasil_ujian h ON reg.no_pendaftaran = h.no_pendaftaran
        WHERE h.status = 'Lulus'
        GROUP BY p.angkatan
        ORDER BY jumlah_lulus DESC
    """)
    q3 = qdb("""
        SELECT u.nama_univ, COUNT(*) AS jumlah_pendaftar
        FROM pilihan_prodi pp
        JOIN program_studi prodi ON pp.id_prodi = prodi.id_prodi
        JOIN universitas u ON prodi.id_univ = u.id_univ
        GROUP BY u.nama_univ
        ORDER BY jumlah_pendaftar DESC
        LIMIT 10
    """)
    q4 = qdb("""
        SELECT u.nama_univ, ROUND(AVG(h.skor_rerata)::NUMERIC, 2) AS rata_skor
        FROM hasil_ujian h
        JOIN program_studi prodi ON h.id_prodi = prodi.id_prodi
        JOIN universitas u ON prodi.id_univ = u.id_univ
        WHERE h.status = 'Lulus'
        GROUP BY u.nama_univ
        ORDER BY rata_skor DESC
        LIMIT 10
    """)
    q5 = []
    if nisn_cari:
        q5 = qdb("""
            SELECT p.nisn, p.nama_peserta, p.tgl_lahir, p.asal_sekolah,
                   p.angkatan, p.alamat_peserta,
                   reg.no_pendaftaran, reg.tgl_pendaftaran, reg.tgl_ujian,
                   s.no_sesi, s.waktu AS waktu_sesi,
                   l.nama_ruang, l.gedung,
                   u_lokasi.nama_univ AS univ_lokasi,
                   h.skor_rerata, h.status,
                   prodi_diterima.nama_prodi AS prodi_diterima,
                   prodi_diterima.jenjang AS jenjang_diterima,
                   u_diterima.nama_univ AS univ_diterima,
                   ps1.nama_prodi AS pilihan1_prodi, ps1.jenjang AS pilihan1_jenjang,
                   u1.nama_univ AS pilihan1_univ,
                   ps2.nama_prodi AS pilihan2_prodi, ps2.jenjang AS pilihan2_jenjang,
                   u2.nama_univ AS pilihan2_univ
            FROM peserta p
            JOIN pendaftaran reg ON p.nisn = reg.nisn
            JOIN sesi s ON reg.no_sesi = s.no_sesi
            JOIN lokasi l ON reg.id_lokasi = l.id_lokasi
            JOIN universitas u_lokasi ON l.id_univ = u_lokasi.id_univ
            JOIN hasil_ujian h ON reg.no_pendaftaran = h.no_pendaftaran
            LEFT JOIN program_studi prodi_diterima ON h.id_prodi = prodi_diterima.id_prodi
            LEFT JOIN universitas u_diterima ON prodi_diterima.id_univ = u_diterima.id_univ
            LEFT JOIN pilihan_prodi pp1 ON reg.no_pendaftaran = pp1.no_pendaftaran AND pp1.pilihan_ke = 1
            LEFT JOIN program_studi ps1 ON pp1.id_prodi = ps1.id_prodi
            LEFT JOIN universitas u1 ON ps1.id_univ = u1.id_univ
            LEFT JOIN pilihan_prodi pp2 ON reg.no_pendaftaran = pp2.no_pendaftaran AND pp2.pilihan_ke = 2
            LEFT JOIN program_studi ps2 ON pp2.id_prodi = ps2.id_prodi
            LEFT JOIN universitas u2 ON ps2.id_univ = u2.id_univ
            WHERE p.nisn = %s
        """, (nisn_cari,))
    q6 = qdb("""
        SELECT s.no_sesi, s.waktu, COUNT(DISTINCT reg.nisn) AS jumlah_peserta
        FROM pendaftaran reg
        JOIN sesi s ON reg.no_sesi = s.no_sesi
        GROUP BY s.no_sesi, s.waktu
        ORDER BY jumlah_peserta DESC
    """)
    q7 = qdb("""
        SELECT COUNT(*) AS total_peserta,
               SUM(CASE WHEN status='Lulus' THEN 1 ELSE 0 END) AS total_lulus,
               SUM(CASE WHEN status='Tidak Lulus' THEN 1 ELSE 0 END) AS total_tidak_lulus
        FROM hasil_ujian
    """, one=True)
    q8 = qdb("""
        SELECT p.asal_sekolah, COUNT(*) AS jumlah_lulus
        FROM peserta p
        JOIN pendaftaran reg ON p.nisn = reg.nisn
        JOIN hasil_ujian h ON reg.no_pendaftaran = h.no_pendaftaran
        WHERE h.status = 'Lulus'
        GROUP BY p.asal_sekolah
        ORDER BY jumlah_lulus DESC
        LIMIT 10
    """)
    q9 = qdb("""
        SELECT prodi.nama_prodi, prodi.jenjang, u.nama_univ,
               prodi.kuota, COUNT(pp.no_pendaftaran) AS jumlah_peminat,
               ROUND(COUNT(pp.no_pendaftaran)::NUMERIC*1.0/prodi.kuota, 2) AS rasio_ketatan
        FROM pilihan_prodi pp
        JOIN program_studi prodi ON pp.id_prodi = prodi.id_prodi
        JOIN universitas u ON prodi.id_univ = u.id_univ
        WHERE pp.pilihan_ke = 1
        GROUP BY prodi.id_prodi, prodi.nama_prodi, prodi.jenjang, u.nama_univ, prodi.kuota
        ORDER BY rasio_ketatan DESC
        LIMIT 10
    """)
    q10 = qdb("""
        SELECT pp.pilihan_ke,
               CASE WHEN pp.pilihan_ke=1 THEN 'Pilihan Pertama'
                    WHEN pp.pilihan_ke=2 THEN 'Pilihan Kedua' END AS keterangan,
               COUNT(*) AS jumlah_lulus,
               ROUND(COUNT(*)::NUMERIC*100.0/(SELECT COUNT(*) FROM hasil_ujian WHERE status='Lulus'),1) AS persentase
        FROM peserta p
        JOIN pendaftaran reg ON p.nisn = reg.nisn
        JOIN hasil_ujian h ON reg.no_pendaftaran = h.no_pendaftaran
        JOIN pilihan_prodi pp ON reg.no_pendaftaran = pp.no_pendaftaran
            AND h.id_prodi = pp.id_prodi
        WHERE h.status = 'Lulus'
        GROUP BY pp.pilihan_ke
        ORDER BY pp.pilihan_ke ASC
    """)
    q11 = qdb("""
        SELECT p.angkatan, COUNT(*) AS total_peserta,
               SUM(CASE WHEN h.status='Lulus' THEN 1 ELSE 0 END) AS lulus,
               SUM(CASE WHEN h.status='Tidak Lulus' THEN 1 ELSE 0 END) AS tidak_lulus,
               ROUND(SUM(CASE WHEN h.status='Lulus' THEN 1 ELSE 0 END)::NUMERIC*100.0/COUNT(*),1) AS persen_lulus
        FROM peserta p
        JOIN pendaftaran reg ON p.nisn = reg.nisn
        JOIN hasil_ujian h ON reg.no_pendaftaran = h.no_pendaftaran
        GROUP BY p.angkatan
        ORDER BY p.angkatan ASC
    """)
    q12 = qdb("""
        SELECT pgw.nama_pengawas, l.nama_ruang, l.gedung, u.nama_univ,
               COUNT(DISTINCT reg.nisn) AS jumlah_peserta
        FROM pengawas pgw
        JOIN lokasi l ON pgw.id_lokasi = l.id_lokasi
        JOIN pendaftaran reg ON reg.id_lokasi = l.id_lokasi
        JOIN universitas u ON l.id_univ = u.id_univ
        GROUP BY pgw.nama_pengawas, l.nama_ruang, l.gedung, u.nama_univ
        ORDER BY jumlah_peserta DESC
        LIMIT 10
    """)

    return render_template("analisis.html",
                           q1=q1, q2=q2, q3=q3, q4=q4,
                           q5=q5, nisn_cari=nisn_cari,
                           q6=q6, q7=q7, q8=q8, q9=q9,
                           q10=q10, q11=q11, q12=q12,
                           q11_json=[dict(r) for r in q11],
                           q3_json=[dict(r) for r in q3])


# ══════════════════════════════════════════════════════════════════════════════
# AUTOCOMPLETE API — JSON endpoints untuk typeahead di semua form
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/search/peserta")
def api_search_peserta():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    rows = qdb("""SELECT nisn, nama_peserta, asal_sekolah, angkatan
                  FROM peserta
                  WHERE nisn ILIKE %s OR nama_peserta ILIKE %s
                  ORDER BY CASE WHEN nisn ILIKE %s THEN 0 ELSE 1 END, nama_peserta
                  LIMIT 8""",
               (f"{q}%", f"%{q}%", f"{q}%"))
    return jsonify([dict(r) for r in rows])

@app.route("/api/search/lokasi")
def api_search_lokasi():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    rows = qdb("""SELECT l.id_lokasi, l.nama_ruang, l.gedung, u.nama_univ
                  FROM lokasi l JOIN universitas u ON l.id_univ = u.id_univ
                  WHERE l.id_lokasi ILIKE %s OR l.nama_ruang ILIKE %s OR l.gedung ILIKE %s OR u.nama_univ ILIKE %s
                  ORDER BY CASE WHEN l.id_lokasi ILIKE %s THEN 0 ELSE 1 END, u.nama_univ
                  LIMIT 8""",
               (f"{q}%", f"%{q}%", f"%{q}%", f"%{q}%", f"{q}%"))
    return jsonify([dict(r) for r in rows])

@app.route("/api/search/pendaftaran")
def api_search_pendaftaran():
    q = request.args.get("q", "").strip()
    only_tanpa_hasil = request.args.get("tanpa_hasil", "0") == "1"
    if not q:
        return jsonify([])
    base = """SELECT pd.no_pendaftaran, p.nama_peserta, p.nisn
              FROM pendaftaran pd JOIN peserta p ON pd.nisn = p.nisn"""
    if only_tanpa_hasil:
        base += " WHERE pd.no_pendaftaran NOT IN (SELECT no_pendaftaran FROM hasil_ujian)"
        base += " AND (pd.no_pendaftaran ILIKE %s OR p.nama_peserta ILIKE %s)"
    else:
        base += " WHERE (pd.no_pendaftaran ILIKE %s OR p.nama_peserta ILIKE %s)"
    base += " ORDER BY CASE WHEN pd.no_pendaftaran ILIKE %s THEN 0 ELSE 1 END, pd.no_pendaftaran LIMIT 8"
    rows = qdb(base, (f"{q}%", f"%{q}%", f"{q}%"))
    return jsonify([dict(r) for r in rows])

@app.route("/api/search/prodi")
def api_search_prodi():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    rows = qdb("""SELECT ps.id_prodi, ps.nama_prodi, ps.jenjang, u.nama_univ
                  FROM program_studi ps JOIN universitas u ON ps.id_univ = u.id_univ
                  WHERE ps.id_prodi ILIKE %s OR ps.nama_prodi ILIKE %s OR u.nama_univ ILIKE %s
                  ORDER BY CASE WHEN ps.id_prodi ILIKE %s THEN 0 ELSE 1 END, u.nama_univ
                  LIMIT 8""",
               (f"{q}%", f"%{q}%", f"%{q}%", f"{q}%"))
    return jsonify([dict(r) for r in rows])

@app.route("/api/validate/pendaftaran/<no_pendaftaran>")
def api_validate_pendaftaran(no_pendaftaran):
    row = qdb("SELECT pd.no_pendaftaran, p.nama_peserta FROM pendaftaran pd JOIN peserta p ON pd.nisn=p.nisn WHERE pd.no_pendaftaran=%s",
              (no_pendaftaran.upper(),), one=True)
    if row:
        return jsonify({"valid": True, "nama_peserta": row["nama_peserta"]})
    return jsonify({"valid": False})

@app.route("/api/validate/lokasi/<id_lokasi>")
def api_validate_lokasi(id_lokasi):
    row = qdb("SELECT l.id_lokasi, l.nama_ruang, l.gedung, u.nama_univ FROM lokasi l JOIN universitas u ON l.id_univ=u.id_univ WHERE l.id_lokasi=%s",
              (id_lokasi.upper(),), one=True)
    if row:
        return jsonify({"valid": True, "label": f"{row['nama_univ']} — {row['gedung']} / {row['nama_ruang']}"})
    return jsonify({"valid": False})

@app.route("/api/validate/peserta/<nisn>")
def api_validate_peserta(nisn):
    row = qdb("SELECT nisn, nama_peserta, asal_sekolah FROM peserta WHERE nisn=%s", (nisn,), one=True)
    if row:
        return jsonify({"valid": True, "nama_peserta": row["nama_peserta"], "asal_sekolah": row["asal_sekolah"]})
    return jsonify({"valid": False})

@app.route("/api/validate/prodi/<id_prodi>")
def api_validate_prodi(id_prodi):
    row = qdb("SELECT ps.id_prodi, ps.nama_prodi, ps.jenjang, u.nama_univ FROM program_studi ps JOIN universitas u ON ps.id_univ=u.id_univ WHERE ps.id_prodi=%s",
              (id_prodi.upper(),), one=True)
    if row:
        return jsonify({"valid": True, "label": f"{row['nama_univ']} — {row['nama_prodi']} ({row['jenjang']})"})
    return jsonify({"valid": False})


@app.route("/api/prodi-by-pendaftaran/<no_pendaftaran>")
def api_prodi_by_pendaftaran(no_pendaftaran):
    """Return list of prodi choices (pilihan_prodi) for a given no_pendaftaran."""
    rows = qdb("""SELECT pp.id_prodi, pp.pilihan_ke,
                         ps.nama_prodi, ps.jenjang,
                         u.id_univ, u.nama_univ
                  FROM pilihan_prodi pp
                  JOIN program_studi ps ON pp.id_prodi = ps.id_prodi
                  JOIN universitas u ON ps.id_univ = u.id_univ
                  WHERE pp.no_pendaftaran = %s
                  ORDER BY pp.pilihan_ke""", (no_pendaftaran.upper(),))
    return jsonify([dict(r) for r in rows])


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT — PRODUCTION READY
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "="*50)
    print("  SNBT Database Management System")
    print("  Kelompok A-8 | TA 2025-2026")
    print("  PostgreSQL Edition (Production Ready)")
    print("="*50)

    try:
        peserta_count = qdb("SELECT COUNT(*) as c FROM peserta", one=True)
        if peserta_count:
            print(f"\n✅ Database terhubung — {peserta_count['c']:,} peserta")
        else:
            print("\n⚠️  Database connected but no data found")
        print("🚀 Buka: http://127.0.0.1:5000\n")
        
        # Production mode: host 0.0.0.0, port dari env, debug=False
        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port, debug=False)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("   Pastikan DATABASE_URL environment variable sudah diset dengan benar\n")
