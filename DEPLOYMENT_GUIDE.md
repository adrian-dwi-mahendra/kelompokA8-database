# 🚀 PANDUAN DEPLOYMENT KE RAILWAY (PostgreSQL Edition)

## 📋 Overview

Aplikasi SNBT telah diupdate menggunakan **PostgreSQL** untuk production, bukan SQLite.
Database akan **persistent** (data tidak hilang saat redeploy).

---

## ✅ STEP 1: SETUP RAILWAY + PostgreSQL

**1.** Buka https://railway.app → login dengan GitHub

**2.** Klik **"+ New Project"**

**3.** Pilih **"Provision PostgreSQL"**

**4.** Tunggu loading... database PostgreSQL akan ready

**5.** Klik service **"Postgres"** yang muncul

**6.** Buka tab **"Variables"**

**7.** Cari variabel **`DATABASE_URL`** → **copy** value-nya

**8.** Simpan di Notepad (nanti akan dipakai di Step 5)

---

## ✅ STEP 2: SETUP GITHUB

**1.** Buat repository baru di GitHub: https://github.com/new
   - Name: `snbt-app`
   - Visibility: **Public**
   - Jangan centang apapun
   - Klik **Create repository**

**2.** Jangan tutup halaman repo (nanti perlu URL-nya)

---

## ✅ STEP 3: PUSH CODE KE GITHUB

**1.** Buka CMD di folder project `snbt-app`

**2.** Setup Git (sekali saja):
```bash
git config --global user.name "Nama Kamu"
git config --global user.email "email@kamu.com"
```

**3.** Inisialisasi & push:
```bash
git init
git add .
git commit -m "SNBT PostgreSQL Edition"
git branch -M main
git remote add origin https://github.com/NAMAKAMU/snbt-app.git
git push -u origin main
```

**4.** Refresh halaman GitHub repo — semua file seharusnya sudah ada ✅

---

## ✅ STEP 4: IMPORT DATA KE PostgreSQL

Ini adalah LANGKAH PENTING! Data dari SQLite harus di-import ke PostgreSQL.

### Opsi A: Import via Railway CLI (Recommended)

**1.** Install Railway CLI: https://docs.railway.app/guides/cli

**2.** Login ke Railway:
```bash
railway login
```

**3.** Link project:
```bash
railway link
```

**4.** Download data schema & import (detailed guide di database_migration.sql)

### Opsi B: Manual Import (Pakai Python)

Saya akan buatkan script `migrate_to_postgresql.py` yang otomatis migrate data.

---

## ✅ STEP 5: DEPLOY KE RAILWAY

**1.** Klik **"+ New"** di project Railway kamu

**2.** Pilih **"GitHub Repo"**

**3.** Pilih repository **`snbt-app`**

**4.** Railway akan auto-detect Procfile dan build app

**5.** Setelah selesai (2-3 menit), klik service **`snbt-app`**

**6.** Buka tab **"Variables"**

**7.** Tambah environment variable:
```
DATABASE_URL = [PASTE DATABASE_URL dari PostgreSQL service]
SECRET_KEY = snbt_a8_2026_secret
FLASK_ENV = production
```

**8.** Klik **Save** → Railway otomatis redeploy

**9.** Buka tab **"Settings"** → scroll ke **"Domains"** → klik **"Generate Domain"**

**10.** Muncul URL seperti: `snbt-app-production.up.railway.app`

**11.** Klik URL → **APLIKASI ONLINE! 🎉**

---

## 📝 PERBEDAAN UTAMA (SQLite → PostgreSQL)

| Aspek | SQLite | PostgreSQL |
|-------|--------|-----------|
| **Database File** | `ayam.db` (local) | Server terpisah di Railway |
| **Data Persistence** | ❌ Hilang saat redeploy | ✅ Permanent |
| **Connection** | File | Network (TCP) |
| **Production Ready** | ❌ Tidak | ✅ Ya |

---

## 🆘 TROUBLESHOOTING

### Error: `DATABASE_URL not found`
→ Pastikan sudah set environment variable `DATABASE_URL` di Railway

### Error: `psycopg2.OperationalError: could not connect to server`
→ Cek DATABASE_URL benar-benar di-copy dengan lengkap

### Error: `table does not exist`
→ Jalankan migration script untuk import data ke PostgreSQL

### App running but no data
→ Lakukan import data (Step 4)

---

## 📚 File Penting

- **app.py** — Main Flask app (sudah diupdate untuk PostgreSQL)
- **requirements.txt** — Dependencies (Flask, psycopg2, gunicorn)
- **Procfile** — Tell Railway cara run app
- **.env.example** — Template environment variables
- **schema.sql** — Database schema

---

**Mulai dari STEP 1! 🚀**
