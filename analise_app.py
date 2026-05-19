import os
import uuid
import hashlib
import json
import urllib.request
from datetime import datetime
from flask import Flask, request, jsonify, session, send_from_directory
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = "imperio_analise_2024_secret"

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:hBUoFgiGFXvUHZMRuhcdiNDIbyOiPaBR@postgres.railway.internal:5432/railway")

MP_ACCESS_TOKEN = "APP_USR-6719425973860470-051719-0dba2eadcd461aa80a64231ff92c09ba-2112056378"
MP_PUBLIC_KEY = "APP_USR-90e13660-4204-4f29-9435-55399dfaa19f"

ADMIN_EMAIL = "henry@imperio.com"
ADMIN_SENHA = hashlib.sha256("admin123".encode()).hexdigest()
OWNER_EMAIL = "henymc1128@gmail.com"

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    with get_db() as conn:
        with conn.cursor() as c:
            c.execute('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    email TEXT PRIMARY KEY,
                    nome TEXT,
                    senha TEXT,
                    plano TEXT DEFAULT 'gratuito',
                    criado_em TEXT
                )
            ''')
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
        conn.commit()

def hash_senha(s):
    return hashlib.sha256(s.encode()).hexdigest()

# ================= ROTAS =================

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(".", filename)

@app.route("/")
def index():
    return send_from_directory(".", "analise_site.html")

@app.route("/api/cadastro", methods=["POST"])
def cadastro():
    data = request.json
    email = data.get("email", "").lower().strip()
    nome = data.get("nome", "").strip()
    senha = hash_senha(data.get("senha", ""))
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT email FROM usuarios WHERE email=%s", (email,))
                if c.fetchone():
                    return jsonify({"erro": "Email já cadastrado"}), 400
                plano = "assinatura" if email == OWNER_EMAIL else "gratuito"
                c.execute(
                    "INSERT INTO usuarios (email,nome,senha,plano,criado_em) VALUES (%s,%s,%s,%s,%s)",
                    (email, nome, senha, plano, datetime.now().strftime("%d/%m/%Y %H:%M"))
                )
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email", "").lower().strip()
    senha = hash_senha(data.get("senha", ""))

    if email == ADMIN_EMAIL and senha == ADMIN_SENHA:
        session["user"] = "admin"
        session["admin"] = True
        return jsonify({"ok": True, "admin": True})

    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM usuarios WHERE email=%s", (email,))
                u = c.fetchone()
                if not u:
                    return jsonify({"erro": "Email não encontrado"}), 401
                if u["senha"] != senha:
                    return jsonify({"erro": "Senha incorreta"}), 401
                plano = u["plano"]
                if email == OWNER_EMAIL and plano != "assinatura":
                    c.execute("UPDATE usuarios SET plano='assinatura' WHERE email=%s", (email,))
                    conn.commit()
                    plano = "assinatura"
                session["user"] = email
                session["admin"] = False
                return jsonify({"ok": True, "admin": False, "nome": u["nome"], "plano": plano})
    except Exception as e:
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
        return jsonify({"logado": True, "admin": True})
    email = session["user"]
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM usuarios WHERE email=%s", (email,))
                u = c.fetchone()
                if not u:
                    session.clear()
                    return jsonify({"logado": False})
                return jsonify({"logado": True, "admin": False, "nome": u["nome"], "plano": u["plano"], "email": email})
    except Exception as e:
        return jsonify({"logado": False})

@app.route("/api/solicitar", methods=["POST"])
def solicitar():
    if "user" not in session or session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    email = session["user"]
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM usuarios WHERE email=%s", (email,))
                u = c.fetchone()
                if not u or u["plano"] == "gratuito":
                    return jsonify({"erro": "plano_necessario"}), 403
                data = request.json
                links = data.get("links", [])
                if not links:
                    links = [data.get("link", "")]
                links = [l for l in links if l]
                aid = str(uuid.uuid4())[:8].upper()
                c.execute('''
                    INSERT INTO analises (id,usuario,nome_usuario,link,links,numero,posicao,instagram,nome_adversario,observacoes,status,resultado,criado_em)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ''', (
                    aid, email, u["nome"],
                    links[0] if links else "",
                    json.dumps(links),
                    data.get("numero", ""),
                    data.get("posicao", ""),
                    data.get("instagram", ""),
                    data.get("nome_adversario", ""),
                    data.get("observacoes", ""),
                    "aguardando", "",
                    datetime.now().strftime("%d/%m/%Y %H:%M")
                ))
            conn.commit()
        return jsonify({"ok": True, "id": aid})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/api/minhas_analises")
def minhas_analises():
    if "user" not in session:
        return jsonify({"erro": "Não autorizado"}), 401
    email = session["user"]
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM analises WHERE usuario=%s ORDER BY criado_em DESC", (email,))
                rows = c.fetchall()
                result = []
                for r in rows:
                    row = dict(r)
                    if row.get("links"):
                        try:
                            row["links"] = json.loads(row["links"])
                        except:
                            row["links"] = [row["link"]]
                    result.append(row)
                return jsonify(result)
    except Exception as e:
        return jsonify([])

@app.route("/api/admin/analises")
def admin_analises():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM analises ORDER BY criado_em DESC")
                rows = c.fetchall()
                result = []
                for r in rows:
                    row = dict(r)
                    if row.get("links"):
                        try:
                            row["links"] = json.loads(row["links"])
                        except:
                            row["links"] = [row["link"]]
                    result.append(row)
                return jsonify(result)
    except Exception as e:
        return jsonify([])

@app.route("/api/admin/entregar", methods=["POST"])
def admin_entregar():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute(
                    "UPDATE analises SET resultado=%s, status='entregue' WHERE id=%s",
                    (data.get("resultado", ""), data.get("id"))
                )
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/api/admin/usuarios")
def admin_usuarios():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT email,nome,plano,criado_em FROM usuarios ORDER BY criado_em DESC")
                return jsonify([dict(r) for r in c.fetchall()])
    except Exception as e:
        return jsonify([])

@app.route("/api/admin/upgrade", methods=["POST"])
def admin_upgrade():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("UPDATE usuarios SET plano=%s WHERE email=%s", (data.get("plano"), data.get("email")))
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/api/criar_pagamento", methods=["POST"])
def criar_pagamento():
    if "user" not in session or session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json
    plano = data.get("plano", "avulso")
    email = session["user"]
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT nome FROM usuarios WHERE email=%s", (email,))
                u = c.fetchone()
                nome = u["nome"] if u else "Cliente"
        valor = 10.00 if plano == "avulso" else 60.00
        titulo = "Análise Avulsa" if plano == "avulso" else "Assinatura Mensal Ilimitada"
        payload = {
            "items": [{"title": titulo, "quantity": 1, "currency_id": "BRL", "unit_price": valor}],
            "payer": {"email": email, "name": nome},
            "back_urls": {
                "success": "https://web-production-dc14b.up.railway.app/pagamento/sucesso",
                "failure": "https://web-production-dc14b.up.railway.app/pagamento/falha",
                "pending": "https://web-production-dc14b.up.railway.app/pagamento/pendente"
            },
            "auto_return": "approved",
            "external_reference": f"{email}|{plano}",
            "notification_url": "https://web-production-dc14b.up.railway.app/api/webhook_mp"
        }
        req = urllib.request.Request(
            "https://api.mercadopago.com/checkout/preferences",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read())
            return jsonify({"link": resp["init_point"]})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/api/webhook_mp", methods=["POST"])
def webhook_mp():
    try:
        data = request.json or {}
        topic = data.get("type") or request.args.get("topic", "")
        payment_id = data.get("data", {}).get("id") or request.args.get("id")
        if topic == "payment" and payment_id:
            req = urllib.request.Request(
                f"https://api.mercadopago.com/v1/payments/{payment_id}",
                headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}"}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                payment = json.loads(r.read())
            if payment.get("status") == "approved":
                ref = payment.get("external_reference", "")
                if "|" in ref:
                    email, plano = ref.split("|", 1)
                    with get_db() as conn:
                        with conn.cursor() as c:
                            c.execute("UPDATE usuarios SET plano=%s WHERE email=%s", (plano, email))
                        conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        print("WEBHOOK ERROR:", e)
        return jsonify({"ok": True})

@app.route("/pagamento/sucesso")
def pagamento_sucesso():
    return send_from_directory(".", "analise_site.html")

@app.route("/pagamento/falha")
def pagamento_falha():
    return send_from_directory(".", "analise_site.html")

@app.route("/pagamento/pendente")
def pagamento_pendente():
    return send_from_directory(".", "analise_site.html")

if __name__ == "__main__":
    init_db()
    print("ANALISE.IO RODANDO")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)

init_db()
