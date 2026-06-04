-- ============================================================
-- SCHEMA DATABASE SNBT (Seleksi Nasional Berdasarkan Tes)
-- Kelompok A-8 | Database untuk Sains Data TA 2025-2026
-- Disesuaikan dengan Bismillah_benar.sqbpro
-- ============================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS universitas (
    id_univ     VARCHAR(10)  PRIMARY KEY NOT NULL,
    nama_univ   VARCHAR(100) NOT NULL,
    alamat_univ VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS lokasi (
    id_lokasi  VARCHAR(10)  PRIMARY KEY NOT NULL,
    nama_ruang VARCHAR(100) NOT NULL,
    gedung     VARCHAR(100) NOT NULL,
    id_univ    VARCHAR(10)  NOT NULL,
    FOREIGN KEY (id_univ) REFERENCES universitas(id_univ)
);

CREATE TABLE IF NOT EXISTS pengawas (
    id_pengawas   VARCHAR(10)  PRIMARY KEY NOT NULL,
    nama_pengawas VARCHAR(100) NOT NULL,
    id_lokasi     VARCHAR(10)  NOT NULL,
    FOREIGN KEY (id_lokasi) REFERENCES lokasi(id_lokasi)
);

-- NISN sebagai VARCHAR (sesuai sqbpro)
CREATE TABLE IF NOT EXISTS peserta (
    nisn           VARCHAR(15)  PRIMARY KEY NOT NULL,
    nama_peserta   VARCHAR(100) NOT NULL,
    tgl_lahir      DATE         NOT NULL,
    asal_sekolah   VARCHAR(100) NOT NULL,
    angkatan       INTEGER      NOT NULL,
    alamat_peserta VARCHAR(255) NOT NULL
);

-- no_sesi sebagai VARCHAR (sesuai sqbpro)
CREATE TABLE IF NOT EXISTS sesi (
    no_sesi VARCHAR(10)  PRIMARY KEY NOT NULL,
    waktu   VARCHAR(50)  NOT NULL
);

CREATE TABLE IF NOT EXISTS program_studi (
    id_prodi   VARCHAR(10)  PRIMARY KEY NOT NULL,
    nama_prodi VARCHAR(100) NOT NULL,
    jenjang    VARCHAR(10)  NOT NULL,
    kuota      INTEGER      NOT NULL,
    id_univ    VARCHAR(10)  NOT NULL,
    FOREIGN KEY (id_univ) REFERENCES universitas(id_univ)
);

CREATE TABLE IF NOT EXISTS pendaftaran (
    no_pendaftaran  VARCHAR(15) PRIMARY KEY NOT NULL,
    nisn            VARCHAR(15) NOT NULL UNIQUE,
    id_lokasi       VARCHAR(10) NOT NULL,
    no_sesi         VARCHAR(10) NOT NULL,
    tgl_pendaftaran DATE        NOT NULL,
    tgl_ujian       DATE        NOT NULL,
    FOREIGN KEY (nisn)      REFERENCES peserta(nisn),
    FOREIGN KEY (id_lokasi) REFERENCES lokasi(id_lokasi),
    FOREIGN KEY (no_sesi)   REFERENCES sesi(no_sesi)
);

CREATE TABLE IF NOT EXISTS pilihan_prodi (
    no_pendaftaran VARCHAR(15) NOT NULL,
    id_prodi       VARCHAR(10) NOT NULL,
    pilihan_ke     INTEGER     NOT NULL CHECK (pilihan_ke IN (1, 2)),
    PRIMARY KEY (no_pendaftaran, id_prodi),
    FOREIGN KEY (no_pendaftaran) REFERENCES pendaftaran(no_pendaftaran),
    FOREIGN KEY (id_prodi)       REFERENCES program_studi(id_prodi)
);

CREATE TABLE IF NOT EXISTS hasil_ujian (
    id_hasil       VARCHAR(15) PRIMARY KEY NOT NULL,
    no_pendaftaran VARCHAR(15) NOT NULL UNIQUE,
    skor_rerata    REAL        NOT NULL,
    status         VARCHAR(20) NOT NULL,
    id_prodi       VARCHAR(10),
    FOREIGN KEY (no_pendaftaran) REFERENCES pendaftaran(no_pendaftaran),
    FOREIGN KEY (id_prodi)       REFERENCES program_studi(id_prodi)
);
