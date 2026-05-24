import os
import uuid
import hashlib
import json
import urllib.request
from datetime import datetime
from flask import Flask, request, jsonify, session, send_from_directory

import psycopg2
from psycopg2.extras import RealDictCursor

import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.secret_key = "imperio_analise_2024_secret"

# ================= CONFIG =================

DATABASE_URL = os.environ.get("DATABASE_URL")

MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN")
MP_PUBLIC_KEY = os.environ.get("MP_PUBLIC_KEY")

ADMIN_USER = "admin"
ADMIN_SENHA = hashlib.sha256("admin123".encode()).hexdigest()

OWNER_EMAIL = "henymc1128@gmail.com"

# ================= CLOUDINARY =================

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)

# ================= DB =================

def get_db():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=RealDictCursor,
        sslmode="require"
    )

def init_db():
    with get_db() as conn:
        with conn.cursor() as c:

            # ================= USUÁRIOS =================

            c.execute('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    email TEXT PRIMARY KEY,
                    nome TEXT,
                    senha TEXT,
                    plano TEXT DEFAULT 'gratuito',
                    criado_em TEXT
                )
            ''')

            # ================= ANÁLISES =================

            c.execute('''
                CREATE TABLE IF NOT EXISTS analises (
                    id TEXT PRIMARY KEY,
                    usuario TEXT,
                    nome_usuario TEXT,
                    link TEXT,
                    links TEXT,
                    numero TEXT,
                    posicao TEXT,
                    instagram TEXT,
                    nome_adversario TEXT,
                    observacoes TEXT,
                    status TEXT DEFAULT 'aguardando',
                    resultado TEXT DEFAULT '',
                    criado_em TEXT
                )
            ''')

            # ================= ATLETAS =================

            c.execute('''
                CREATE TABLE IF NOT EXISTS atletas (
                    id TEXT PRIMARY KEY,
                    nome TEXT,
                    idade INTEGER,
                    posicao TEXT,
                    modalidade TEXT DEFAULT 'Futsal',
                    clube TEXT,
                    agencia TEXT,
                    contrato TEXT,
                    pe TEXT,
                    altura INTEGER,
                    peso INTEGER,
                    disponivel BOOLEAN DEFAULT TRUE,
                    instagram TEXT,
                    whatsapp TEXT,
                    forte TEXT,
                    fraco TEXT,
                    video TEXT,
                    foto TEXT,
                    stats_gols TEXT,
                    stats_assists TEXT,
                    stats_passes TEXT,
                    stats_dribles TEXT,
                    stats_nota TEXT,
                    stats_jogos TEXT,
                    status TEXT DEFAULT 'pendente',
                    criado_em TEXT
                )
            ''')

            # ================= CLUBES =================

            c.execute('''
                CREATE TABLE IF NOT EXISTS clubes (
                    id TEXT PRIMARY KEY,
                    nome TEXT,
                    cidade TEXT,
                    posicao TEXT,
                    idade TEXT,
                    detalhes TEXT,
                    contato TEXT,
                    status TEXT DEFAULT 'pendente',
                    criado_em TEXT
                )
            ''')

        conn.commit()

# ================= HELPERS =================

def hash_senha(s):
    return hashlib.sha256(s.encode()).hexdigest()

def upload_image_cloudinary(base64_image):
    try:
        if not base64_image:
            return None

        result = cloudinary.uploader.upload(
            base64_image,
            folder="analiseio_atletas"
        )

        url = result.get("secure_url")

        url = url.replace(
            "/upload/",
            "/upload/f_auto,q_auto/"
        )

        return url

    except Exception as e:
        print("ERRO CLOUDINARY:", e)
        return None

# ================= STATIC =================

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(".", filename)

@app.route("/")
def index():
    return send_from_directory(".", "analise_site.html")

@app.route("/pagamento/sucesso")
def pagamento_sucesso():
    return send_from_directory(".", "analise_site.html")

@app.route("/pagamento/falha")
def pagamento_falha():
    return send_from_directory(".", "analise_site.html")

@app.route("/pagamento/pendente")
def pagamento_pendente():
    return send_from_directory(".", "analise_site.html")

# ================= AUTH =================

@app.route("/api/cadastro", methods=["POST"])
def cadastro():
    data = request.json

    email = data.get("email", "").lower().strip()
    nome = data.get("nome", "").strip()
    senha = hash_senha(data.get("senha", ""))

    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute(
                    "SELECT email FROM usuarios WHERE email=%s",
                    (email,)
                )

                if c.fetchone():
                    return jsonify({"erro": "Email já cadastrado"}), 400

                plano = "assinatura" if email == OWNER_EMAIL else "gratuito"

                c.execute(
                    """
                    INSERT INTO usuarios
                    (email, nome, senha, plano, criado_em)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        email,
                        nome,
                        senha,
                        plano,
                        datetime.now().strftime("%d/%m/%Y %H:%M")
                    )
                )

            conn.commit()

        return jsonify({"ok": True})

    except Exception as e:
        print("ERRO CADASTRO:", e)
        return jsonify({"erro": str(e)}), 500

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json

    user = data.get("user", "").strip()
    senha = hash_senha(data.get("senha", ""))

    # ================= ADMIN =================

    if user == ADMIN_USER and senha == ADMIN_SENHA:
        session["user"] = "admin"
        session["admin"] = True

        return jsonify({
            "ok": True,
            "admin": True,
            "nome": "Admin"
        })

    # ================= EMAIL =================

    email = user.lower()

    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute(
                    "SELECT * FROM usuarios WHERE email=%s",
                    (email,)
                )

                u = c.fetchone()

                if not u:
                    return jsonify({"erro": "Usuário não encontrado"}), 401

                if u["senha"] != senha:
                    return jsonify({"erro": "Senha incorreta"}), 401

                plano = u["plano"]

                if email == OWNER_EMAIL and plano != "assinatura":
                    c.execute(
                        "UPDATE usuarios SET plano='assinatura' WHERE email=%s",
                        (email,)
                    )
                    conn.commit()
                    plano = "assinatura"

                session["user"] = email
                session["admin"] = False

                return jsonify({
                    "ok": True,
                    "admin": False,
                    "nome": u["nome"],
                    "plano": plano
                })

    except Exception as e:
        print("ERRO LOGIN:", e)
        return jsonify({"erro": str(e)}), 500

@app.route("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/me")
def me():
    if "user" not in session:
        return jsonify({"logado": False})

    if session.get("admin"):
        return jsonify({
            "logado": True,
            "admin": True,
            "nome": "Admin"
        })

    email = session["user"]

    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute(
                    "SELECT * FROM usuarios WHERE email=%s",
                    (email,)
                )

                u = c.fetchone()

                if not u:
                    session.clear()
                    return jsonify({"logado": False})

                return jsonify({
                    "logado": True,
                    "admin": False,
                    "nome": u["nome"],
                    "plano": u["plano"],
                    "email": email
                })

    except Exception as e:
        print("ERRO ME:", e)
        return jsonify({"logado": False})

# ================= ATLETAS =================

@app.route("/api/atletas", methods=["GET"])
def listar_atletas():
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("""
                    SELECT *
                    FROM atletas
                    WHERE status='aprovado'
                    ORDER BY criado_em DESC
                """)

                rows = [dict(r) for r in c.fetchall()]

                return jsonify(rows)

    except Exception as e:
        print("ERRO LISTAR ATLETAS:", e)
        return jsonify([])

@app.route("/api/admin/atletas", methods=["GET"])
def admin_listar_atletas():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401

    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("""
                    SELECT *
                    FROM atletas
                    ORDER BY criado_em DESC
                """)

                rows = [dict(r) for r in c.fetchall()]

                return jsonify(rows)

    except Exception as e:
        print("ERRO ADMIN LISTAR ATLETAS:", e)
        return jsonify([])

# ================= CRIAR ATLETA =================

@app.route("/api/admin/atletas", methods=["POST"])
def admin_criar_atleta():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401

    data = request.json

    try:
        aid = str(uuid.uuid4())[:8].upper()

        foto_base64 = data.get("foto")
        foto = upload_image_cloudinary(foto_base64)

        with get_db() as conn:
            with conn.cursor() as c:
                c.execute('''
                    INSERT INTO atletas (
                        id,
                        nome,
                        idade,
                        posicao,
                        modalidade,
                        clube,
                        agencia,
                        contrato,
                        pe,
                        altura,
                        peso,
                        disponivel,
                        instagram,
                        whatsapp,
                        forte,
                        fraco,
                        video,
                        foto,
                        stats_gols,
                        stats_assists,
                        stats_passes,
                        stats_dribles,
                        stats_nota,
                        stats_jogos,
                        status,
                        criado_em
                    )
                    VALUES (
                        %s,%s,%s,%s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s,%s,
                        %s,%s,%s,%s,
                        %s,%s,%s,%s,%s,%s,
                        %s,%s
                    )
                ''', (
                    aid,
                    data.get("nome", ""),
                    int(data.get("idade") or 0),
                    data.get("posicao", ""),
                    data.get("modalidade", "Futsal"),
                    data.get("clube", ""),
                    data.get("agencia", ""),
                    data.get("contrato", ""),
                    data.get("pe", "Direito"),
                    int(data.get("altura") or 0),
                    int(data.get("peso") or 0),
                    data.get("disponivel", True),
                    data.get("instagram", ""),
                    data.get("whatsapp", ""),
                    data.get("forte", ""),
                    data.get("fraco", ""),
                    data.get("video", ""),
                    foto,
                    data.get("stats_gols", ""),
                    data.get("stats_assists", ""),
                    data.get("stats_passes", ""),
                    data.get("stats_dribles", ""),
                    data.get("stats_nota", ""),
                    data.get("stats_jogos", ""),
                    "aprovado",
                    datetime.now().strftime("%d/%m/%Y %H:%M")
                ))

            conn.commit()

        return jsonify({
            "ok": True,
            "id": aid,
            "foto": foto
        })

    except Exception as e:
        print("ERRO CRIAR ATLETA:", e)
        return jsonify({"erro": str(e)}), 500

# ================= EDITAR ATLETA =================

@app.route("/api/admin/atletas/<aid>", methods=["PUT"])
def admin_editar_atleta(aid):
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401

    data = request.json

    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("""
                    UPDATE atletas SET
                        nome=%s,
                        idade=%s,
                        posicao=%s,
                        modalidade=%s,
                        clube=%s,
                        agencia=%s,
                        contrato=%s,
                        pe=%s,
                        altura=%s,
                        peso=%s,
                        disponivel=%s,
                        instagram=%s,
                        whatsapp=%s,
                        forte=%s,
                        fraco=%s,
                        video=%s,
                        stats_gols=%s,
                        stats_assists=%s,
                        stats_passes=%s,
                        stats_dribles=%s,
                        stats_nota=%s,
                        stats_jogos=%s,
                        status=%s
                    WHERE id=%s
                """, (
                    data.get("nome", ""),
                    int(data.get("idade") or 0),
                    data.get("posicao", ""),
                    data.get("modalidade", "Futsal"),
                    data.get("clube", ""),
                    data.get("agencia", ""),
                    data.get("contrato", ""),
                    data.get("pe", "Direito"),
                    int(data.get("altura") or 0),
                    int(data.get("peso") or 0),
                    data.get("disponivel", True),
                    data.get("instagram", ""),
                    data.get("whatsapp", ""),
                    data.get("forte", ""),
                    data.get("fraco", ""),
                    data.get("video", ""),
                    data.get("stats_gols", ""),
                    data.get("stats_assists", ""),
                    data.get("stats_passes", ""),
                    data.get("stats_dribles", ""),
                    data.get("stats_nota", ""),
                    data.get("stats_jogos", ""),
                    data.get("status", "aprovado"),
                    aid
                ))

            conn.commit()

        return jsonify({"ok": True})

    except Exception as e:
        print("ERRO EDITAR ATLETA:", e)
        return jsonify({"erro": str(e)}), 500

# ================= DELETAR ATLETA =================

@app.route("/api/admin/atletas/<aid>", methods=["DELETE"])
def admin_deletar_atleta(aid):
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401

    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute(
                    "DELETE FROM atletas WHERE id=%s",
                    (aid,)
                )

            conn.commit()

        return jsonify({"ok": True})

    except Exception as e:
        print("ERRO DELETAR ATLETA:", e)
        return jsonify({"erro": str(e)}), 500

# ================= CLUBES =================

@app.route("/api/clubes", methods=["GET"])
def listar_clubes():
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("""
                    SELECT *
                    FROM clubes
                    WHERE status='aprovado'
                    ORDER BY criado_em DESC
                """)

                rows = [dict(r) for r in c.fetchall()]

                return jsonify(rows)

    except Exception as e:
        print("ERRO LISTAR CLUBES:", e)
        return jsonify([])

@app.route("/api/admin/clubes", methods=["GET"])
def admin_listar_clubes():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401

    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("""
                    SELECT *
                    FROM clubes
                    ORDER BY criado_em DESC
                """)

                rows = [dict(r) for r in c.fetchall()]

                return jsonify(rows)

    except Exception as e:
        print("ERRO ADMIN LISTAR CLUBES:", e)
        return jsonify([])

@app.route("/api/admin/clubes", methods=["POST"])
def admin_criar_clube():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401

    data = request.json

    try:
        cid = str(uuid.uuid4())[:8].upper()

        with get_db() as conn:
            with conn.cursor() as c:
                c.execute('''
                    INSERT INTO clubes (
                        id,
                        nome,
                        cidade,
                        posicao,
                        idade,
                        detalhes,
                        contato,
                        status,
                        criado_em
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ''', (
                    cid,
                    data.get("nome", ""),
                    data.get("cidade", ""),
                    data.get("posicao", ""),
                    data.get("idade", ""),
                    data.get("detalhes", ""),
                    data.get("contato", ""),
                    "aprovado",
                    datetime.now().strftime("%d/%m/%Y %H:%M")
                ))

            conn.commit()

        return jsonify({"ok": True, "id": cid})

    except Exception as e:
        print("ERRO CRIAR CLUBE:", e)
        return jsonify({"erro": str(e)}), 500

@app.route("/api/admin/clubes/<cid>", methods=["DELETE"])
def admin_deletar_clube(cid):
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401

    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute(
                    "DELETE FROM clubes WHERE id=%s",
                    (cid,)
                )

            conn.commit()

        return jsonify({"ok": True})

    except Exception as e:
        print("ERRO DELETAR CLUBE:", e)
        return jsonify({"erro": str(e)}), 500

# ================= START =================

if __name__ == "__main__":

    init_db()

    try:
        conn = get_db()
        conn.close()
        print("✅ PostgreSQL conectado")
    except Exception as e:
        print("❌ ERRO POSTGRES:", e)

    print("ANALISE.IO MARKETPLACE RODANDO")

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
