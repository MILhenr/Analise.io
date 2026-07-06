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

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)

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
                c.execute('''CREATE TABLE IF NOT EXISTS eventos (
                    id TEXT PRIMARY KEY, atleta_id TEXT, tipo TEXT, competicao TEXT,
                    data TEXT, adversario TEXT, quantidade INTEGER DEFAULT 1, criado_em TEXT)''')

                novas_colunas = [
                    ("cat1", "TEXT DEFAULT ''"),
                    ("comp1", "TEXT DEFAULT ''"),
                    ("cat2", "TEXT DEFAULT ''"),
                    ("comp2", "TEXT DEFAULT ''"),
                    ("cat3", "TEXT DEFAULT ''"),
                    ("comp3", "TEXT DEFAULT ''"),
                    ("stats_gols1", "TEXT DEFAULT ''"),
                    ("stats_assists1", "TEXT DEFAULT ''"),
                    ("stats_jogos1", "TEXT DEFAULT ''"),
                    ("stats_gols2", "TEXT DEFAULT ''"),
                    ("stats_assists2", "TEXT DEFAULT ''"),
                    ("stats_jogos2", "TEXT DEFAULT ''"),
                    ("stats_gols3", "TEXT DEFAULT ''"),
                    ("stats_assists3", "TEXT DEFAULT ''"),
                    ("stats_jogos3", "TEXT DEFAULT ''"),
                    ("camisa", "TEXT DEFAULT ''"),
                    ("video2", "TEXT DEFAULT ''"),
                    ("video3", "TEXT DEFAULT ''"),
                    ("video4", "TEXT DEFAULT ''"),
                    ("video5", "TEXT DEFAULT ''"),
                ]
                for col, col_type in novas_colunas:
                    try:
                        c.execute(f"ALTER TABLE atletas ADD COLUMN {col} {col_type}")
                    except Exception:
                        pass
            conn.commit()
        print("✅ Tabelas verificadas/criadas")
    except Exception as e:
        print("❌ ERRO init_db:", e)

init_db()

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
        return url
    except Exception as e:
        print(f"❌ ERRO CLOUDINARY: {e}")
        return None

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

@app.route("/api/atletas", methods=["GET"])
def listar_atletas():
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM atletas WHERE status='aprovado' ORDER BY criado_em DESC")
                return jsonify([dict(r) for r in c.fetchall()])
    except Exception as e:
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
        return jsonify({"erro": str(e)}), 500

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
                    stats_nota,stats_jogos,
                    cat1,comp1,cat2,comp2,cat3,comp3,
                    stats_gols1,stats_assists1,stats_jogos1,
                    stats_gols2,stats_assists2,stats_jogos2,
                    stats_gols3,stats_assists3,stats_jogos3,
                    camisa,video2,video3,video4,video5,
                    status,criado_em)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
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
                     data.get("cat1",""), data.get("comp1",""),
                     data.get("cat2",""), data.get("comp2",""),
                     data.get("cat3",""), data.get("comp3",""),
                     data.get("stats_gols1",""), data.get("stats_assists1",""), data.get("stats_jogos1",""),
                     data.get("stats_gols2",""), data.get("stats_assists2",""), data.get("stats_jogos2",""),
                     data.get("stats_gols3",""), data.get("stats_assists3",""), data.get("stats_jogos3",""),
                     data.get("camisa",""),
                     data.get("video2",""), data.get("video3",""), data.get("video4",""), data.get("video5",""),
                     "aprovado", datetime.now().strftime("%d/%m/%Y %H:%M")))
            conn.commit()
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
                        video=%s,foto=%s,
                        stats_gols=%s,stats_assists=%s,stats_passes=%s,
                        stats_dribles=%s,stats_nota=%s,stats_jogos=%s,
                        cat1=%s,comp1=%s,cat2=%s,comp2=%s,cat3=%s,comp3=%s,
                        stats_gols1=%s,stats_assists1=%s,stats_jogos1=%s,
                        stats_gols2=%s,stats_assists2=%s,stats_jogos2=%s,
                        stats_gols3=%s,stats_assists3=%s,stats_jogos3=%s,
                        camisa=%s,video2=%s,video3=%s,video4=%s,video5=%s,
                        status=%s WHERE id=%s""",
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
                         data.get("cat1",""), data.get("comp1",""),
                         data.get("cat2",""), data.get("comp2",""),
                         data.get("cat3",""), data.get("comp3",""),
                         data.get("stats_gols1",""), data.get("stats_assists1",""), data.get("stats_jogos1",""),
                         data.get("stats_gols2",""), data.get("stats_assists2",""), data.get("stats_jogos2",""),
                         data.get("stats_gols3",""), data.get("stats_assists3",""), data.get("stats_jogos3",""),
                         data.get("camisa",""),
                         data.get("video2",""), data.get("video3",""), data.get("video4",""), data.get("video5",""),
                         data.get("status","aprovado"), aid))
                else:
                    c.execute("""UPDATE atletas SET
                        nome=%s,idade=%s,posicao=%s,modalidade=%s,clube=%s,
                        agencia=%s,contrato=%s,pe=%s,altura=%s,peso=%s,
                        disponivel=%s,instagram=%s,whatsapp=%s,forte=%s,fraco=%s,
                        video=%s,
                        stats_gols=%s,stats_assists=%s,stats_passes=%s,
                        stats_dribles=%s,stats_nota=%s,stats_jogos=%s,
                        cat1=%s,comp1=%s,cat2=%s,comp2=%s,cat3=%s,comp3=%s,
                        stats_gols1=%s,stats_assists1=%s,stats_jogos1=%s,
                        stats_gols2=%s,stats_assists2=%s,stats_jogos2=%s,
                        stats_gols3=%s,stats_assists3=%s,stats_jogos3=%s,
                        camisa=%s,video2=%s,video3=%s,video4=%s,video5=%s,
                        status=%s WHERE id=%s""",
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
                         data.get("cat1",""), data.get("comp1",""),
                         data.get("cat2",""), data.get("comp2",""),
                         data.get("cat3",""), data.get("comp3",""),
                         data.get("stats_gols1",""), data.get("stats_assists1",""), data.get("stats_jogos1",""),
                         data.get("stats_gols2",""), data.get("stats_assists2",""), data.get("stats_jogos2",""),
                         data.get("stats_gols3",""), data.get("stats_assists3",""), data.get("stats_jogos3",""),
                         data.get("camisa",""),
                         data.get("video2",""), data.get("video3",""), data.get("video4",""), data.get("video5",""),
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
        return jsonify({"erro": str(e)}), 500

@app.route("/api/admin/usuarios", methods=["GET"])
def admin_listar_usuarios():
    if not session.get("admin"):
        return jsonify({"erro": "Nao autorizado"}), 401
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT email AS id,nome,email,plano,criado_em FROM usuarios ORDER BY criado_em DESC")
                return jsonify([dict(r) for r in c.fetchall()])
    except Exception as e:
        return jsonify([])

@app.route("/api/admin/usuarios/<email>/plano", methods=["PUT"])
def admin_alterar_plano(email):
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json
    plano = data.get("plano", "gratuito")
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("UPDATE usuarios SET plano=%s WHERE email=%s", (plano, email))
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

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
        return jsonify({"ok": True})
    except Exception as e:
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

@app.route("/api/criar_pagamento", methods=["POST"])
def criar_pagamento():
    if "user" not in session or session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    try:
        data = request.json
        plano = data.get("plano", "assinatura")
        email = session["user"]
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT nome FROM usuarios WHERE email=%s", (email,))
                u = c.fetchone()
                nome = u["nome"] if u else "Usuario"
        payload = {
            "items": [{"title": "Assinatura Mensal ANALISE.IO", "quantity": 1, "currency_id": "BRL", "unit_price": 19.90}],
            "payer": {"email": email, "name": nome},
            "back_urls": {"success": BASE_URL+"/pagamento/sucesso", "failure": BASE_URL+"/pagamento/falha", "pending": BASE_URL+"/pagamento/pendente"},
            "auto_return": "approved",
            "external_reference": email+"|"+plano,
            "notification_url": BASE_URL+"/api/webhook_mp"
        }
        req = urllib.request.Request("https://api.mercadopago.com/checkout/preferences",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
        return jsonify({"link": resp.get("init_point", "")})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/api/admin/times", methods=["GET"])
def get_times():
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT valor FROM configuracoes WHERE chave='times'")
                row = c.fetchone()
                if row:
                    return jsonify(json.loads(row["valor"]))
                return jsonify([])
    except Exception as e:
        return jsonify([])

@app.route("/api/admin/times", methods=["POST"])
def save_times():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json
    times = data.get("times", [])
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("""CREATE TABLE IF NOT EXISTS configuracoes 
                    (chave TEXT PRIMARY KEY, valor TEXT)""")
                c.execute("""INSERT INTO configuracoes (chave, valor) 
                    VALUES ('times', %s)
                    ON CONFLICT (chave) DO UPDATE SET valor=EXCLUDED.valor""",
                    (json.dumps(times),))
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/api/admin/agencias", methods=["GET"])
def get_agencias():
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("""CREATE TABLE IF NOT EXISTS configuracoes 
                    (chave TEXT PRIMARY KEY, valor TEXT)""")
                c.execute("SELECT valor FROM configuracoes WHERE chave='agencias'")
                row = c.fetchone()
                if row:
                    return jsonify(json.loads(row["valor"]))
                return jsonify([])
    except Exception as e:
        return jsonify([])

@app.route("/api/admin/agencias", methods=["POST"])
def save_agencias():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json
    agencias = data.get("agencias", [])
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("""CREATE TABLE IF NOT EXISTS configuracoes 
                    (chave TEXT PRIMARY KEY, valor TEXT)""")
                c.execute("""INSERT INTO configuracoes (chave, valor) 
                    VALUES ('agencias', %s)
                    ON CONFLICT (chave) DO UPDATE SET valor=EXCLUDED.valor""",
                    (json.dumps(agencias),))
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
        
@app.route("/api/webhook_mp", methods=["POST"])
def webhook_mp():
    try:
        data = request.json or {}
        topic = data.get("type") or request.args.get("topic", "")
        payment_id = data.get("data", {}).get("id") or request.args.get("id")
        if topic == "payment" and payment_id:
            req = urllib.request.Request(f"https://api.mercadopago.com/v1/payments/{payment_id}",
                headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}"})
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
        return jsonify({"ok": True})

BOT_SECRET = os.environ.get("BOT_SECRET", "scoutbot_secret_2024")

def bot_auth():
    return request.headers.get("X-Bot-Secret") == BOT_SECRET

@app.route("/api/bot/atletas", methods=["GET"])
def bot_buscar_atletas():
    if not bot_auth():
        return jsonify({"erro": "Não autorizado"}), 401
    nome = request.args.get("nome", "").strip()
    clube = request.args.get("clube", "").strip()
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                if nome and clube:
                    c.execute("SELECT id,nome,clube,posicao,pe,foto,stats_gols,stats_assists,stats_jogos,idade FROM atletas WHERE status='aprovado' AND LOWER(nome) LIKE %s AND LOWER(clube) LIKE %s", (f"%{nome.lower()}%", f"%{clube.lower()}%"))
                elif nome:
                    c.execute("SELECT id,nome,clube,posicao,pe,foto,stats_gols,stats_assists,stats_jogos,idade FROM atletas WHERE status='aprovado' AND LOWER(nome) LIKE %s", (f"%{nome.lower()}%",))
                elif clube:
                    c.execute("SELECT id,nome,clube,posicao,pe,foto,stats_gols,stats_assists,stats_jogos,idade FROM atletas WHERE status='aprovado' AND LOWER(clube) LIKE %s", (f"%{clube.lower()}%",))
                else:
                    return jsonify([])
                return jsonify([dict(r) for r in c.fetchall()])
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/api/bot/gol", methods=["POST"])
def bot_registrar_gol():
    if not bot_auth():
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json
    atleta_id = data.get("atleta_id")
    if not atleta_id:
        return jsonify({"erro": "atleta_id obrigatório"}), 400
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT stats_gols, stats_jogos FROM atletas WHERE id=%s", (atleta_id,))
                row = c.fetchone()
                if not row:
                    return jsonify({"erro": "Atleta não encontrado"}), 404
                gols = int(row["stats_gols"] or 0) + 1
                jogos = int(row["stats_jogos"] or 0) + 1
                c.execute("UPDATE atletas SET stats_gols=%s, stats_jogos=%s WHERE id=%s", (str(gols), str(jogos), atleta_id))
            conn.commit()
        return jsonify({"ok": True, "gols": gols, "jogos": jogos})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/api/bot/assistencia", methods=["POST"])
def bot_registrar_assistencia():
    if not bot_auth():
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json
    atleta_id = data.get("atleta_id")
    if not atleta_id:
        return jsonify({"erro": "atleta_id obrigatório"}), 400
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT stats_assists, stats_jogos FROM atletas WHERE id=%s", (atleta_id,))
                row = c.fetchone()
                if not row:
                    return jsonify({"erro": "Atleta não encontrado"}), 404
                assists = int(row["stats_assists"] or 0) + 1
                jogos = int(row["stats_jogos"] or 0) + 1
                c.execute("UPDATE atletas SET stats_assists=%s, stats_jogos=%s WHERE id=%s", (str(assists), str(jogos), atleta_id))
            conn.commit()
        return jsonify({"ok": True, "assists": assists, "jogos": jogos})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/api/bot/jogo", methods=["POST"])
def bot_registrar_jogo():
    if not bot_auth():
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json
    clube = data.get("clube", "").strip()
    if not clube:
        return jsonify({"erro": "clube obrigatório"}), 400
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT id, stats_jogos FROM atletas WHERE status='aprovado' AND LOWER(clube) LIKE %s", (f"%{clube.lower()}%",))
                atletas = c.fetchall()
                for a in atletas:
                    jogos = int(a["stats_jogos"] or 0) + 1
                    c.execute("UPDATE atletas SET stats_jogos=%s WHERE id=%s", (str(jogos), a["id"]))
            conn.commit()
        return jsonify({"ok": True, "atletas_atualizados": len(atletas)})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

# ── SYNC DO SCOUT ─────────────────────────────────────────────

@app.route("/api/sync/atleta", methods=["POST"])
def sync_criar_atleta():
    if request.headers.get("X-Bot-Secret") != BOT_SECRET:
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json

    aid = str(data.get("id", "")).strip()
    if not aid.isdigit() or not (1 <= int(aid) <= 5000000):
        return jsonify({"erro": "ID inválido. Envie um número entre 1 e 5000000."}), 400

    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT id FROM atletas WHERE id=%s", (aid,))
                if c.fetchone():
                    return jsonify({"erro": "ID já existe. Use PUT para atualizar."}), 409

                c.execute('''INSERT INTO atletas (
                    id,nome,idade,posicao,modalidade,clube,
                    pe,disponivel,cat1,comp1,
                    stats_gols,stats_assists,stats_jogos,
                    stats_gols1,stats_assists1,stats_jogos1,
                    status,criado_em)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (aid, data["nome"], 0, "", "Futsal",
                     data.get("clube",""), "Direito", True,
                     data.get("cat1",""), data.get("comp1",""),
                     data.get("stats_gols","0"), data.get("stats_assists","0"), data.get("stats_jogos","0"),
                     data.get("stats_gols1","0"), data.get("stats_assists1","0"), data.get("stats_jogos1","0"),
                     "aprovado", datetime.now().strftime("%d/%m/%Y %H:%M")))
            conn.commit()
        print(f"✅ SYNC CRIAR: id={aid} — {data['nome']} — {data.get('clube','')}")
        return jsonify({"ok": True, "id": aid})
    except Exception as e:
        print(f"❌ SYNC CRIAR ERRO: {e}")
        return jsonify({"erro": str(e)}), 500

@app.route("/api/sync/atleta/<aid>", methods=["PUT"])
def sync_atualizar_atleta(aid):
    if request.headers.get("X-Bot-Secret") != BOT_SECRET:
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("""UPDATE atletas SET
                    clube=%s, cat1=%s, comp1=%s,
                    stats_gols=%s, stats_assists=%s, stats_jogos=%s,
                    stats_gols1=%s, stats_assists1=%s, stats_jogos1=%s
                    WHERE id=%s""",
                    (data.get("clube",""),
                     data.get("cat1",""), data.get("comp1",""),
                     data.get("stats_gols","0"), data.get("stats_assists","0"), data.get("stats_jogos","0"),
                     data.get("stats_gols1","0"), data.get("stats_assists1","0"), data.get("stats_jogos1","0"),
                     aid))
            conn.commit()
        print(f"✅ SYNC ATUALIZAR: id={aid}")
        return jsonify({"ok": True})
    except Exception as e:
        print(f"❌ SYNC ATUALIZAR ERRO: {e}")
        return jsonify({"erro": str(e)}), 500

def _find_comp_index(atleta, competicao):
    for i in range(1, 4):
        if (atleta.get(f"comp{i}") or "").strip() == (competicao or "").strip():
            return i
    return None

@app.route("/api/admin/eventos", methods=["POST"])
def admin_criar_evento():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json
    atleta_id = data.get("atleta_id")
    tipo = data.get("tipo")
    competicao = data.get("competicao", "")
    data_evento = data.get("data", "")
    adversario = data.get("adversario", "")
    try:
        quantidade = int(data.get("quantidade") or 1)
    except (ValueError, TypeError):
        quantidade = 1
    if quantidade < 1:
        quantidade = 1

    if not atleta_id or not tipo:
        return jsonify({"erro": "atleta_id e tipo são obrigatórios"}), 400

    try:
        eid = str(uuid.uuid4())[:8].upper()
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM atletas WHERE id=%s", (atleta_id,))
                atleta = c.fetchone()
                if not atleta:
                    return jsonify({"erro": "Atleta não encontrado"}), 404

                idx = _find_comp_index(atleta, competicao)

                c.execute('''INSERT INTO eventos (id,atleta_id,tipo,competicao,data,adversario,quantidade,criado_em)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
                    (eid, atleta_id, tipo, competicao, data_evento, adversario, quantidade,
                     datetime.now().strftime("%d/%m/%Y %H:%M")))

                if tipo == "gol":
                    campo_total, campo_idx = "stats_gols", (f"stats_gols{idx}" if idx else None)
                elif tipo == "assistencia":
                    campo_total, campo_idx = "stats_assists", (f"stats_assists{idx}" if idx else None)
                else:
                    campo_total, campo_idx = "stats_jogos", (f"stats_jogos{idx}" if idx else None)

                novo_total = int(atleta.get(campo_total) or 0) + quantidade
                c.execute(f"UPDATE atletas SET {campo_total}=%s WHERE id=%s", (str(novo_total), atleta_id))

                if campo_idx:
                    novo_idx = int(atleta.get(campo_idx) or 0) + quantidade
                    c.execute(f"UPDATE atletas SET {campo_idx}=%s WHERE id=%s", (str(novo_idx), atleta_id))
            conn.commit()
        return jsonify({"ok": True, "id": eid})
    except Exception as e:
        print("❌ ERRO CRIAR EVENTO:", e)
        return jsonify({"erro": str(e)}), 500

@app.route("/api/admin/eventos/<atleta_id>", methods=["GET"])
def admin_listar_eventos(atleta_id):
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM eventos WHERE atleta_id=%s ORDER BY criado_em DESC", (atleta_id,))
                return jsonify([dict(r) for r in c.fetchall()])
    except Exception as e:
        return jsonify([])

@app.route("/api/admin/eventos/<eid>", methods=["DELETE"])
def admin_deletar_evento(eid):
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM eventos WHERE id=%s", (eid,))
                evento = c.fetchone()
                if not evento:
                    return jsonify({"erro": "Evento não encontrado"}), 404

                atleta_id = evento["atleta_id"]
                tipo = evento["tipo"]
                quantidade = int(evento.get("quantidade") or 1)
                competicao = evento.get("competicao", "")

                c.execute("SELECT * FROM atletas WHERE id=%s", (atleta_id,))
                atleta = c.fetchone()

                if atleta:
                    idx = _find_comp_index(atleta, competicao)
                    if tipo == "gol":
                        campo_total, campo_idx = "stats_gols", (f"stats_gols{idx}" if idx else None)
                    elif tipo == "assistencia":
                        campo_total, campo_idx = "stats_assists", (f"stats_assists{idx}" if idx else None)
                    else:
                        campo_total, campo_idx = "stats_jogos", (f"stats_jogos{idx}" if idx else None)

                    novo_total = max(0, int(atleta.get(campo_total) or 0) - quantidade)
                    c.execute(f"UPDATE atletas SET {campo_total}=%s WHERE id=%s", (str(novo_total), atleta_id))
                    if campo_idx:
                        novo_idx = max(0, int(atleta.get(campo_idx) or 0) - quantidade)
                        c.execute(f"UPDATE atletas SET {campo_idx}=%s WHERE id=%s", (str(novo_idx), atleta_id))

                c.execute("DELETE FROM eventos WHERE id=%s", (eid,))
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    try:
        conn = get_db()
        conn.close()
        print("✅ PostgreSQL conectado")
    except Exception as e:
        print("❌ ERRO POSTGRES:", e)
    print("ANALISE.IO RODANDO")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
