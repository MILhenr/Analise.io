import os
import uuid
import json
import hashlib
import urllib.request
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, session, send_from_directory
import psycopg2
from psycopg2.extras import RealDictCursor
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "analiseio_super_secret_2024_fixo")
app.permanent_session_lifetime = timedelta(days=7)

DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_USER = "admin"
ADMIN_SENHA = hashlib.sha256("admin123".encode()).hexdigest()
OWNER_EMAIL = "henymc1128@gmail.com"

MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN", "APP_USR-6719425973860470-051719-0dba2eadcd461aa80a64231ff92c09ba-2112056378")
MP_PUBLIC_KEY = os.environ.get("MP_PUBLIC_KEY", "APP_USR-90e13660-4204-4f29-9435-55399dfaa19f")
BASE_URL = os.environ.get("BASE_URL", "https://www.analiselo.com.br")

# ================= CLOUDINARY =================
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)

# ================= DB =================
def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode="require")

def init_db():
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                    email TEXT PRIMARY KEY, nome TEXT, senha TEXT,
                    plano TEXT DEFAULT 'gratuito', criado_em TEXT)''')
                c.execute('''CREATE TABLE IF NOT EXISTS atletas (
                    id TEXT PRIMARY KEY, nome TEXT, idade INTEGER,
                    posicao TEXT, modalidade TEXT DEFAULT 'Futsal',
                    clube TEXT, agencia TEXT, contrato TEXT, pe TEXT,
                    altura INTEGER, peso INTEGER, disponivel BOOLEAN DEFAULT TRUE,
                    instagram TEXT, whatsapp TEXT, forte TEXT, fraco TEXT,
                    video TEXT, foto TEXT,
                    stats_gols TEXT, stats_assists TEXT, stats_passes TEXT,
                    stats_dribles TEXT, stats_nota TEXT, stats_jogos TEXT,
                    status TEXT DEFAULT 'pendente', criado_em TEXT)''')
                c.execute('''CREATE TABLE IF NOT EXISTS correcoes (
                    id TEXT PRIMARY KEY, atleta_id TEXT, atleta_nome TEXT,
                    campo TEXT, detalhe TEXT, contato TEXT,
                    status TEXT DEFAULT 'pendente', criado_em TEXT)''')
                c.execute('''CREATE TABLE IF NOT EXISTS clubes (
                    id TEXT PRIMARY KEY, nome TEXT, cidade TEXT, posicao TEXT,
                    idade TEXT, detalhes TEXT, contato TEXT,
                    status TEXT DEFAULT 'pendente', criado_em TEXT)''')
            conn.commit()
        print("✅ Tabelas verificadas/criadas")
    except Exception as e:
        print("❌ ERRO init_db:", e)

init_db()

# ================= HELPERS =================
def hash_senha(s):
    return hashlib.sha256(s.encode()).hexdigest()

def upload_foto(base64_image):
    if not base64_image:
        return None
    try:
        result = cloudinary.uploader.upload(
            base64_image,
            folder="analiseio_atletas",
            resource_type="image"
        )
        url = result.get("secure_url", "")
        if url:
            url = url.replace("/upload/", "/upload/f_auto,q_auto,w_400,h_400,c_fill/")
        print(f"✅ FOTO UPLOAD OK: {url}")
        return url
    except Exception as e:
        print(f"❌ ERRO CLOUDINARY: {e}")
        return None

# ================= STATIC =================
@app.route("/")
def index():
    return send_from_directory(".", "analise_site.html")

@app.route("/pagamento/sucesso")
@app.route("/pagamento/falha")
@app.route("/pagamento/pendente")
def pagamento():
    return send_from_directory(".", "analise_site.html")

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(".", filename)

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
                c.execute("SELECT email FROM usuarios WHERE email=%s", (email,))
                if c.fetchone():
                    return jsonify({"erro": "Email já cadastrado"}), 400
                plano = "assinatura" if email == OWNER_EMAIL else "gratuito"
                c.execute("INSERT INTO usuarios (email,nome,senha,plano,criado_em) VALUES (%s,%s,%s,%s,%s)",
                    (email, nome, senha, plano, datetime.now().strftime("%d/%m/%Y %H:%M")))
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
    if user == ADMIN_USER and senha == ADMIN_SENHA:
        session.permanent = True
        session["user"] = "admin"
        session["admin"] = True
        return jsonify({"ok": True, "admin": True, "nome": "Admin"})
    email = user.lower()
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM usuarios WHERE email=%s", (email,))
                u = c.fetchone()
                if not u:
                    return jsonify({"erro": "Usuário não encontrado"}), 401
                if u["senha"] != senha:
                    return jsonify({"erro": "Senha incorreta"}), 401
                plano = u["plano"]
                if email == OWNER_EMAIL and plano != "assinatura":
                    c.execute("UPDATE usuarios SET plano='assinatura' WHERE email=%s", (email,))
                    conn.commit()
                    plano = "assinatura"
                session.permanent = True
                session["user"] = email
                session["admin"] = False
                return jsonify({"ok": True, "admin": False, "nome": u["nome"], "plano": plano})
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
        return jsonify({"logado": True, "admin": True, "nome": "Admin"})
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

# ================= ATLETAS PÚBLICO =================
@app.route("/api/atletas", methods=["GET"])
def listar_atletas():
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM atletas WHERE status='aprovado' ORDER BY criado_em DESC")
                return jsonify([dict(r) for r in c.fetchall()])
    except Exception as e:
        print("ERRO LISTAR ATLETAS:", e)
        return jsonify([])

@app.route("/api/atletas/solicitar", methods=["POST"])
def solicitar_atleta():
    data = request.json
    try:
        aid = str(uuid.uuid4())[:8].upper()
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute('''INSERT INTO atletas (id,nome,idade,posicao,modalidade,clube,pe,altura,peso,
                    instagram,whatsapp,agencia,forte,video,status,criado_em)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (aid, data.get("nome",""), int(data.get("idade") or 0),
                     data.get("posicao",""), data.get("modalidade","Futsal"),
                     data.get("clube",""), data.get("pe","Direito"),
                     int(data.get("altura") or 0), int(data.get("peso") or 0),
                     data.get("instagram",""), data.get("whatsapp",""),
                     data.get("agencia",""), data.get("forte",""),
                     data.get("video",""), "pendente",
                     datetime.now().strftime("%d/%m/%Y %H:%M")))
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        print("ERRO SOLICITAR ATLETA:", e)
        return jsonify({"erro": str(e)}), 500

# ================= ATLETAS ADMIN =================
@app.route("/api/admin/atletas", methods=["GET"])
def admin_listar_atletas():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM atletas ORDER BY criado_em DESC")
                return jsonify([dict(r) for r in c.fetchall()])
    except Exception as e:
        print("ERRO ADMIN LISTAR:", e)
        return jsonify([])

@app.route("/api/admin/atletas", methods=["POST"])
def admin_criar_atleta():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json
    try:
        aid = str(uuid.uuid4())[:8].upper()
        foto_url = upload_foto(data.get("foto"))
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute('''INSERT INTO atletas (
                    id,nome,idade,posicao,modalidade,clube,agencia,contrato,
                    pe,altura,peso,disponivel,instagram,whatsapp,forte,fraco,
                    video,foto,stats_gols,stats_assists,stats_passes,stats_dribles,
                    stats_nota,stats_jogos,status,criado_em)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (aid, data.get("nome",""), int(data.get("idade") or 0),
                     data.get("posicao",""), data.get("modalidade","Futsal"),
                     data.get("clube",""), data.get("agencia",""),
                     data.get("contrato",""), data.get("pe","Direito"),
                     int(data.get("altura") or 0), int(data.get("peso") or 0),
                     bool(data.get("disponivel", True)),
                     data.get("instagram",""), data.get("whatsapp",""),
                     data.get("forte",""), data.get("fraco",""),
                     data.get("video",""), foto_url,
                     data.get("stats_gols",""), data.get("stats_assists",""),
                     data.get("stats_passes",""), data.get("stats_dribles",""),
                     data.get("stats_nota",""), data.get("stats_jogos",""),
                     "aprovado", datetime.now().strftime("%d/%m/%Y %H:%M")))
            conn.commit()
        print(f"✅ ATLETA CRIADO: id={aid} nome={data.get('nome')} foto={'SIM' if foto_url else 'NAO'}")
        return jsonify({"ok": True, "id": aid, "foto": foto_url})
    except Exception as e:
        print("❌ ERRO CRIAR ATLETA:", e)
        return jsonify({"erro": str(e)}), 500

@app.route("/api/admin/atletas/<aid>", methods=["PUT"])
def admin_editar_atleta(aid):
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json
    try:
        nova_foto_base64 = data.get("foto")
        nova_foto_url = None
        if nova_foto_base64 and not nova_foto_base64.startswith("http"):
            nova_foto_url = upload_foto(nova_foto_base64)
        elif nova_foto_base64 and nova_foto_base64.startswith("http"):
            nova_foto_url = nova_foto_base64
        with get_db() as conn:
            with conn.cursor() as c:
                if nova_foto_url:
                    c.execute("""UPDATE atletas SET
                        nome=%s,idade=%s,posicao=%s,modalidade=%s,clube=%s,
                        agencia=%s,contrato=%s,pe=%s,altura=%s,peso=%s,
                        disponivel=%s,instagram=%s,whatsapp=%s,forte=%s,fraco=%s,
                        video=%s,foto=%s,stats_gols=%s,stats_assists=%s,stats_passes=%s,
                        stats_dribles=%s,stats_nota=%s,stats_jogos=%s,status=%s
                        WHERE id=%s""",
                        (data.get("nome",""), int(data.get("idade") or 0),
                         data.get("posicao",""), data.get("modalidade","Futsal"),
                         data.get("clube",""), data.get("agencia",""),
                         data.get("contrato",""), data.get("pe","Direito"),
                         int(data.get("altura") or 0), int(data.get("peso") or 0),
                         bool(data.get("disponivel", True)),
                         data.get("instagram",""), data.get("whatsapp",""),
                         data.get("forte",""), data.get("fraco",""),
                         data.get("video",""), nova_foto_url,
                         data.get("stats_gols",""), data.get("stats_assists",""),
                         data.get("stats_passes",""), data.get("stats_dribles",""),
                         data.get("stats_nota",""), data.get("stats_jogos",""),
                         data.get("status","aprovado"), aid))
                else:
                    c.execute("""UPDATE atletas SET
                        nome=%s,idade=%s,posicao=%s,modalidade=%s,clube=%s,
                        agencia=%s,contrato=%s,pe=%s,altura=%s,peso=%s,
                        disponivel=%s,instagram=%s,whatsapp=%s,forte=%s,fraco=%s,
                        video=%s,stats_gols=%s,stats_assists=%s,stats_passes=%s,
                        stats_dribles=%s,stats_nota=%s,stats_jogos=%s,status=%s
                        WHERE id=%s""",
                        (data.get("nome",""), int(data.get("idade") or 0),
                         data.get("posicao",""), data.get("modalidade","Futsal"),
                         data.get("clube",""), data.get("agencia",""),
                         data.get("contrato",""), data.get("pe","Direito"),
                         int(data.get("altura") or 0), int(data.get("peso") or 0),
                         bool(data.get("disponivel", True)),
                         data.get("instagram",""), data.get("whatsapp",""),
                         data.get("forte",""), data.get("fraco",""),
                         data.get("video",""),
                         data.get("stats_gols",""), data.get("stats_assists",""),
                         data.get("stats_passes",""), data.get("stats_dribles",""),
                         data.get("stats_nota",""), data.get("stats_jogos",""),
                         data.get("status","aprovado"), aid))
            conn.commit()
        print(f"✅ ATLETA EDITADO: id={aid}")
        return jsonify({"ok": True})
    except Exception as e:
        print("❌ ERRO EDITAR ATLETA:", e)
        return jsonify({"erro": str(e)}), 500

@app.route("/api/admin/atletas/<aid>", methods=["DELETE"])
def admin_deletar_atleta(aid):
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("DELETE FROM atletas WHERE id=%s", (aid,))
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        print("❌ ERRO DELETAR ATLETA:", e)
        return jsonify({"erro": str(e)}), 500

# ================= USUARIOS ADMIN =================
@app.route("/api/admin/usuarios", methods=["GET"])
def admin_listar_usuarios():
    if not session.get("admin"):
        return jsonify({"erro": "Nao autorizado"}), 401
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT nome,email,plano,criado_em FROM usuarios ORDER BY criado_em DESC")
                return jsonify([dict(r) for r in c.fetchall()])
    except Exception as e:
        return jsonify([])

# ================= CLUBES =================
@app.route("/api/clubes", methods=["GET"])
def listar_clubes():
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM clubes WHERE status='aprovado' ORDER BY criado_em DESC")
                return jsonify([dict(r) for r in c.fetchall()])
    except Exception as e:
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
                c.execute('''INSERT INTO clubes (id,nome,cidade,posicao,idade,detalhes,contato,status,criado_em)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (cid, data.get("nome",""), data.get("cidade",""),
                     data.get("posicao",""), data.get("idade",""),
                     data.get("detalhes",""), data.get("contato",""),
                     "aprovado", datetime.now().strftime("%d/%m/%Y %H:%M")))
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
                c.execute("DELETE FROM clubes WHERE id=%s", (cid,))
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# ================= CORREÇÕES =================
@app.route("/api/solicitar_correcao", methods=["POST"])
def solicitar_correcao():
    data = request.json
    try:
        cid = str(uuid.uuid4())[:8].upper()
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute('''INSERT INTO correcoes (id,atleta_id,atleta_nome,campo,detalhe,contato,status,criado_em)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (cid, data.get('atleta_id',''), data.get('atleta_nome',''),
                     data.get('campo',''), data.get('detalhe',''),
                     data.get('contato',''), 'pendente',
                     datetime.now().strftime("%d/%m/%Y %H:%M")))
            conn.commit()
        print(f"✅ CORRECAO RECEBIDA: atleta={data.get('atleta_nome')} campo={data.get('campo')}")
        return jsonify({"ok": True})
    except Exception as e:
        print("ERRO CORRECAO:", e)
        return jsonify({"erro": str(e)}), 500

@app.route("/api/admin/correcoes", methods=["GET"])
def admin_correcoes():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM correcoes ORDER BY criado_em DESC")
                return jsonify([dict(r) for r in c.fetchall()])
    except Exception as e:
        return jsonify([])

# ================= PAGAMENTO MERCADO PAGO =================
@app.route("/api/criar_pagamento", methods=["POST"])
def criar_pagamento():
    if "user" not in session or session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    try:
        data = request.json
        plano = data.get("plano", "assinatura")
        email = session["user"]

        # Busca nome do usuario
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT nome FROM usuarios WHERE email=%s", (email,))
                u = c.fetchone()
                nome = u["nome"] if u else "Usuario"

        valor = 19.90
        titulo = "Assinatura Mensal ANALISE.IO"

        payload = {
            "items": [{
                "title": titulo,
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": valor
            }],
            "payer": {
                "email": email,
                "name": nome
            },
            "back_urls": {
                "success": BASE_URL + "/pagamento/sucesso",
                "failure": BASE_URL + "/pagamento/falha",
                "pending": BASE_URL + "/pagamento/pendente"
            },
            "auto_return": "approved",
            "external_reference": email + "|" + plano,
            "notification_url": BASE_URL + "/api/webhook_mp"
        }

        req = urllib.request.Request(
            "https://api.mercadopago.com/checkout/preferences",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
                "Content-Type": "application/json"
            }
        )

        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())

        link = resp.get("init_point", "")
        print(f"✅ PAGAMENTO CRIADO: {link}")
        return jsonify({"link": link})

    except Exception as e:
        print("❌ ERRO PAGAMENTO:", e)
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
                    print(f"✅ ASSINATURA ATIVADA: {email} plano={plano}")

        return jsonify({"ok": True})
    except Exception as e:
        print("ERRO WEBHOOK:", e)
        return jsonify({"ok": True})

# ================= START =================
if __name__ == "__main__":
    try:
        conn = get_db()
        conn.close()
        print("✅ PostgreSQL conectado")
    except Exception as e:
        print("❌ ERRO POSTGRES:", e)
    print("ANALISE.IO RODANDO")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
