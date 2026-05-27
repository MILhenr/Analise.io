import os
import uuid
import hashlib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, session, send_from_directory, redirect
import psycopg2
from psycopg2.extras import RealDictCursor
import cloudinary
import cloudinary.uploader
import stripe
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "analiseio_super_secret_2024_fixo")
app.permanent_session_lifetime = timedelta(days=7)

DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_USER = "admin"
ADMIN_SENHA = hashlib.sha256("admin123".encode()).hexdigest()
OWNER_EMAIL = "henymc1128@gmail.com"

# ================= STRIPE =================
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
PRECO_ASSINATURA = 1990  # R$19,90 em centavos

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
                    email TEXT PRIMARY KEY, 
                    nome TEXT, 
                    senha TEXT,
                    plano TEXT DEFAULT 'gratuito', 
                    stripe_customer_id TEXT,
                    stripe_subscription_id TEXT,
                    data_assinatura TEXT,
                    criado_em TEXT)''')
                
                c.execute('''CREATE TABLE IF NOT EXISTS atletas (
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
                    usuario_email TEXT,
                    status TEXT DEFAULT 'pendente', 
                    criado_em TEXT)''')
                
                c.execute('''CREATE TABLE IF NOT EXISTS correcoes (
                    id TEXT PRIMARY KEY, 
                    atleta_id TEXT, 
                    atleta_nome TEXT,
                    campo TEXT, 
                    detalhe TEXT, 
                    contato TEXT,
                    status TEXT DEFAULT 'pendente', 
                    criado_em TEXT)''')
                
                c.execute('''CREATE TABLE IF NOT EXISTS clubes (
                    id TEXT PRIMARY KEY, 
                    nome TEXT, 
                    cidade TEXT, 
                    posicao TEXT,
                    idade TEXT, 
                    detalhes TEXT, 
                    contato TEXT,
                    status TEXT DEFAULT 'pendente', 
                    criado_em TEXT)''')
                
                c.execute('''CREATE TABLE IF NOT EXISTS pagamentos (
                    id TEXT PRIMARY KEY,
                    email TEXT,
                    stripe_payment_id TEXT,
                    stripe_session_id TEXT,
                    valor INTEGER,
                    status TEXT DEFAULT 'pendente',
                    tipo TEXT,
                    criado_em TEXT)''')
            
            conn.commit()
        print("✅ Tabelas verificadas/criadas")
    except Exception as e:
        print("❌ ERRO init_db:", e)

init_db()

# ================= DECORATORS =================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session and not session.get("admin"):
            return jsonify({"erro": "Não autenticado"}), 401
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return jsonify({"erro": "Não autorizado"}), 401
        return f(*args, **kwargs)
    return decorated

# ================= HELPERS =================
def hash_senha(s):
    return hashlib.sha256(s.encode()).hexdigest()

def upload_foto(base64_image):
    if not base64_image or base64_image.startswith("http"):
        return base64_image if base64_image else None
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

def criar_stripe_customer(email, nome):
    """Cria cliente no Stripe"""
    try:
        customer = stripe.Customer.create(
            email=email,
            name=nome,
            metadata={"plataforma": "analiseio"}
        )
        return customer.id
    except Exception as e:
        print(f"❌ ERRO criar_stripe_customer: {e}")
        return None

def criar_subscription(customer_id):
    """Cria subscrição mensal de R$19,90"""
    try:
        # Cria ou obtém o produto
        products = stripe.Product.list(limit=1)
        product_id = None
        for p in products.data:
            if p.name == "ANALISE.IO - Assinatura Mensal":
                product_id = p.id
                break
        
        if not product_id:
            product = stripe.Product.create(
                name="ANALISE.IO - Assinatura Mensal",
                description="Acesso completo à plataforma ANALISE.IO"
            )
            product_id = product.id
        
        # Cria o preço
        price = stripe.Price.create(
            product=product_id,
            unit_amount=PRECO_ASSINATURA,
            currency="brl",
            recurring={"interval": "month"}
        )
        
        # Cria a subscrição
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price.id}],
            payment_behavior="default_incomplete",
            payment_settings={"save_default_payment_method": "on_subscription"}
        )
        
        return subscription.id
    except Exception as e:
        print(f"❌ ERRO criar_subscription: {e}")
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
    
    if not email or not nome or not senha:
        return jsonify({"erro": "Preencha todos os campos"}), 400
    
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT email FROM usuarios WHERE email=%s", (email,))
                if c.fetchone():
                    return jsonify({"erro": "Email já cadastrado"}), 400
                
                plano = "assinatura" if email == OWNER_EMAIL else "gratuito"
                c.execute("""INSERT INTO usuarios 
                    (email, nome, senha, plano, criado_em) 
                    VALUES (%s, %s, %s, %s, %s)""",
                    (email, nome, senha, plano, datetime.now().strftime("%d/%m/%Y %H:%M")))
            conn.commit()
        
        print(f"✅ USUÁRIO CADASTRADO: {email}")
        return jsonify({"ok": True})
    except Exception as e:
        print("ERRO CADASTRO:", e)
        return jsonify({"erro": str(e)}), 500

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    user = data.get("user", "").strip()
    senha = hash_senha(data.get("senha", ""))
    
    # Admin login
    if user == ADMIN_USER and senha == ADMIN_SENHA:
        session.permanent = True
        session["user"] = "admin"
        session["admin"] = True
        return jsonify({"ok": True, "admin": True, "nome": "Admin"})
    
    # User login
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
                
                print(f"✅ LOGIN: {email} (plano: {plano})")
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
                return jsonify({
                    "logado": True, 
                    "admin": False, 
                    "nome": u["nome"], 
                    "plano": u["plano"], 
                    "email": email
                })
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
@login_required
def solicitar_atleta():
    data = request.json
    email = session.get("user")
    
    try:
        aid = str(uuid.uuid4())[:8].upper()
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute('''INSERT INTO atletas 
                    (id, nome, idade, posicao, modalidade, clube, pe, altura, peso,
                     instagram, whatsapp, agencia, forte, video, usuario_email, status, criado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                    (aid, data.get("nome", ""), int(data.get("idade") or 0),
                     data.get("posicao", ""), data.get("modalidade", "Futsal"),
                     data.get("clube", ""), data.get("pe", "Direito"),
                     int(data.get("altura") or 0), int(data.get("peso") or 0),
                     data.get("instagram", ""), data.get("whatsapp", ""),
                     data.get("agencia", ""), data.get("forte", ""),
                     data.get("video", ""), email, "pendente",
                     datetime.now().strftime("%d/%m/%Y %H:%M")))
            conn.commit()
        
        print(f"✅ ATLETA SOLICITADO: id={aid} nome={data.get('nome')} user={email}")
        return jsonify({"ok": True, "id": aid})
    except Exception as e:
        print("ERRO SOLICITAR ATLETA:", e)
        return jsonify({"erro": str(e)}), 500

# ================= ATLETAS ADMIN =================
@app.route("/api/admin/atletas", methods=["GET"])
@admin_required
def admin_listar_atletas():
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM atletas ORDER BY criado_em DESC")
                return jsonify([dict(r) for r in c.fetchall()])
    except Exception as e:
        print("ERRO ADMIN LISTAR:", e)
        return jsonify([])

@app.route("/api/admin/atletas", methods=["POST"])
@admin_required
def admin_criar_atleta():
    data = request.json
    try:
        aid = str(uuid.uuid4())[:8].upper()
        foto_url = upload_foto(data.get("foto"))
        
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute('''INSERT INTO atletas (
                    id, nome, idade, posicao, modalidade, clube, agencia, contrato,
                    pe, altura, peso, disponivel, instagram, whatsapp, forte, fraco,
                    video, foto, stats_gols, stats_assists, stats_passes, stats_dribles,
                    stats_nota, stats_jogos, status, criado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                    (aid, data.get("nome", ""), int(data.get("idade") or 0),
                     data.get("posicao", ""), data.get("modalidade", "Futsal"),
                     data.get("clube", ""), data.get("agencia", ""),
                     data.get("contrato", ""), data.get("pe", "Direito"),
                     int(data.get("altura") or 0), int(data.get("peso") or 0),
                     bool(data.get("disponivel", True)),
                     data.get("instagram", ""), data.get("whatsapp", ""),
                     data.get("forte", ""), data.get("fraco", ""),
                     data.get("video", ""), foto_url,
                     data.get("stats_gols", ""), data.get("stats_assists", ""),
                     data.get("stats_passes", ""), data.get("stats_dribles", ""),
                     data.get("stats_nota", ""), data.get("stats_jogos", ""),
                     "aprovado", datetime.now().strftime("%d/%m/%Y %H:%M")))
            conn.commit()
        
        print(f"✅ ATLETA CRIADO: id={aid} nome={data.get('nome')} foto={'SIM' if foto_url else 'NAO'}")
        return jsonify({"ok": True, "id": aid, "foto": foto_url})
    except Exception as e:
        print("❌ ERRO CRIAR ATLETA:", e)
        return jsonify({"erro": str(e)}), 500

@app.route("/api/admin/atletas/<aid>", methods=["PUT"])
@admin_required
def admin_editar_atleta(aid):
    data = request.json
    try:
        nova_foto_base64 = data.get("foto")
        nova_foto_url = None
        
        if nova_foto_base64:
            if nova_foto_base64.startswith("http"):
                nova_foto_url = nova_foto_base64
            else:
                nova_foto_url = upload_foto(nova_foto_base64)
        
        with get_db() as conn:
            with conn.cursor() as c:
                if nova_foto_url:
                    c.execute("""UPDATE atletas SET
                        nome=%s, idade=%s, posicao=%s, modalidade=%s, clube=%s,
                        agencia=%s, contrato=%s, pe=%s, altura=%s, peso=%s,
                        disponivel=%s, instagram=%s, whatsapp=%s, forte=%s, fraco=%s,
                        video=%s, foto=%s, stats_gols=%s, stats_assists=%s, stats_passes=%s,
                        stats_dribles=%s, stats_nota=%s, stats_jogos=%s, status=%s
                        WHERE id=%s""",
                        (data.get("nome", ""), int(data.get("idade") or 0),
                         data.get("posicao", ""), data.get("modalidade", "Futsal"),
                         data.get("clube", ""), data.get("agencia", ""),
                         data.get("contrato", ""), data.get("pe", "Direito"),
                         int(data.get("altura") or 0), int(data.get("peso") or 0),
                         bool(data.get("disponivel", True)),
                         data.get("instagram", ""), data.get("whatsapp", ""),
                         data.get("forte", ""), data.get("fraco", ""),
                         data.get("video", ""), nova_foto_url,
                         data.get("stats_gols", ""), data.get("stats_assists", ""),
                         data.get("stats_passes", ""), data.get("stats_dribles", ""),
                         data.get("stats_nota", ""), data.get("stats_jogos", ""),
                         data.get("status", "aprovado"), aid))
                else:
                    c.execute("""UPDATE atletas SET
                        nome=%s, idade=%s, posicao=%s, modalidade=%s, clube=%s,
                        agencia=%s, contrato=%s, pe=%s, altura=%s, peso=%s,
                        disponivel=%s, instagram=%s, whatsapp=%s, forte=%s, fraco=%s,
                        video=%s, stats_gols=%s, stats_assists=%s, stats_passes=%s,
                        stats_dribles=%s, stats_nota=%s, stats_jogos=%s, status=%s
                        WHERE id=%s""",
                        (data.get("nome", ""), int(data.get("idade") or 0),
                         data.get("posicao", ""), data.get("modalidade", "Futsal"),
                         data.get("clube", ""), data.get("agencia", ""),
                         data.get("contrato", ""), data.get("pe", "Direito"),
                         int(data.get("altura") or 0), int(data.get("peso") or 0),
                         bool(data.get("disponivel", True)),
                         data.get("instagram", ""), data.get("whatsapp", ""),
                         data.get("forte", ""), data.get("fraco", ""),
                         data.get("video", ""),
                         data.get("stats_gols", ""), data.get("stats_assists", ""),
                         data.get("stats_passes", ""), data.get("stats_dribles", ""),
                         data.get("stats_nota", ""), data.get("stats_jogos", ""),
                         data.get("status", "aprovado"), aid))
            conn.commit()
        
        print(f"✅ ATLETA EDITADO: id={aid}")
        return jsonify({"ok": True})
    except Exception as e:
        print("❌ ERRO EDITAR ATLETA:", e)
        return jsonify({"erro": str(e)}), 500

@app.route("/api/admin/atletas/<aid>", methods=["DELETE"])
@admin_required
def admin_deletar_atleta(aid):
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("DELETE FROM atletas WHERE id=%s", (aid,))
            conn.commit()
        return jsonify({"ok": True})
    except Exception as e:
        print("❌ ERRO DELETAR ATLETA:", e)
        return jsonify({"erro": str(e)}), 500

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
@admin_required
def admin_criar_clube():
    data = request.json
    try:
        cid = str(uuid.uuid4())[:8].upper()
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute('''INSERT INTO clubes (id, nome, cidade, posicao, idade, detalhes, contato, status, criado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                    (cid, data.get("nome", ""), data.get("cidade", ""),
                     data.get("posicao", ""), data.get("idade", ""),
                     data.get("detalhes", ""), data.get("contato", ""),
                     "aprovado", datetime.now().strftime("%d/%m/%Y %H:%M")))
            conn.commit()
        return jsonify({"ok": True, "id": cid})
    except Exception as e:
        print("ERRO CRIAR CLUBE:", e)
        return jsonify({"erro": str(e)}), 500

@app.route("/api/admin/clubes/<cid>", methods=["DELETE"])
@admin_required
def admin_deletar_clube(cid):
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
@login_required
def solicitar_correcao():
    data = request.json
    try:
        cid = str(uuid.uuid4())[:8].upper()
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute('''INSERT INTO correcoes (id, atleta_id, atleta_nome, campo, detalhe, contato, status, criado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                    (cid, data.get('atleta_id', ''), data.get('atleta_nome', ''),
                     data.get('campo', ''), data.get('detalhe', ''),
                     data.get('contato', ''), 'pendente',
                     datetime.now().strftime("%d/%m/%Y %H:%M")))
            conn.commit()
        print(f"✅ CORRECAO RECEBIDA: atleta={data.get('atleta_nome')} campo={data.get('campo')}")
        return jsonify({"ok": True})
    except Exception as e:
        print("ERRO CORRECAO:", e)
        return jsonify({"erro": str(e)}), 500

@app.route("/api/admin/correcoes", methods=["GET"])
@admin_required
def admin_correcoes():
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT * FROM correcoes ORDER BY criado_em DESC")
                return jsonify([dict(r) for r in c.fetchall()])
    except Exception as e:
        return jsonify([])

# ================= PAGAMENTO - STRIPE =================
@app.route("/api/criar_pagamento", methods=["POST"])
@login_required
def criar_pagamento():
    """Cria sessão de checkout Stripe para pagamento de R$19,90"""
    data = request.json
    email = session.get("user")
    plano = data.get("plano", "assinatura")
    
    if not email:
        return jsonify({"erro": "Não autenticado"}), 401
    
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                # Verifica se usuário já está assinante
                c.execute("SELECT plano, stripe_customer_id FROM usuarios WHERE email=%s", (email,))
                user = c.fetchone()
                
                if user and user["plano"] == "assinatura":
                    return jsonify({"erro": "Você já é assinante"}), 400
                
                # Cria ou obtém customer Stripe
                customer_id = user["stripe_customer_id"] if user else None
                if not customer_id:
                    c.execute("SELECT nome FROM usuarios WHERE email=%s", (email,))
                    user_data = c.fetchone()
                    customer_id = criar_stripe_customer(email, user_data["nome"] if user_data else email)
                    
                    if not customer_id:
                        return jsonify({"erro": "Erro ao criar cliente Stripe"}), 500
                    
                    c.execute("UPDATE usuarios SET stripe_customer_id=%s WHERE email=%s", 
                        (customer_id, email))
                    conn.commit()
        
        # Cria sessão de checkout
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "brl",
                        "product_data": {
                            "name": "ANALISE.IO - Assinatura Mensal",
                            "description": "Acesso completo à plataforma",
                            "images": []
                        },
                        "unit_amount": PRECO_ASSINATURA
                    },
                    "quantity": 1
                }
            ],
            mode="payment",
            success_url="https://seu-dominio.com/pagamento/sucesso?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://seu-dominio.com/pagamento/falha",
            customer_email=email,
            metadata={
                "email": email,
                "plano": plano,
                "plataforma": "analiseio"
            }
        )
        
        # Registra tentativa de pagamento
        with get_db() as conn:
            with conn.cursor() as c:
                pid = str(uuid.uuid4())[:8].upper()
                c.execute('''INSERT INTO pagamentos 
                    (id, email, stripe_session_id, valor, status, tipo, criado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                    (pid, email, checkout_session.id, PRECO_ASSINATURA, 
                     "pendente", plano, datetime.now().strftime("%d/%m/%Y %H:%M")))
            conn.commit()
        
        print(f"✅ SESSAO CHECKOUT CRIADA: email={email} session_id={checkout_session.id}")
        return jsonify({"link": checkout_session.url, "session_id": checkout_session.id})
    
    except Exception as e:
        print(f"❌ ERRO criar_pagamento: {e}")
        return jsonify({"erro": str(e)}), 500

@app.route("/pagamento/sucesso")
def pagamento_sucesso():
    """Página de sucesso após pagamento"""
    session_id = request.args.get("session_id")
    
    if not session_id:
        return redirect("/")
    
    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        if checkout_session.payment_status == "paid":
            email = checkout_session.customer_email
            
            # Atualiza usuário para assinante
            with get_db() as conn:
                with conn.cursor() as c:
                    c.execute("""UPDATE usuarios 
                        SET plano='assinatura', data_assinatura=%s 
                        WHERE email=%s""",
                        (datetime.now().strftime("%d/%m/%Y %H:%M"), email))
                    
                    # Atualiza status de pagamento
                    c.execute("""UPDATE pagamentos 
                        SET status='pago', stripe_payment_id=%s 
                        WHERE stripe_session_id=%s""",
                        (checkout_session.payment_intent, session_id))
                    
                    conn.commit()
            
            print(f"✅ PAGAMENTO CONFIRMADO: email={email}")
            return send_from_directory(".", "analise_site.html")
    
    except Exception as e:
        print(f"❌ ERRO pagamento_sucesso: {e}")
    
    return redirect("/")

@app.route("/api/webhook/stripe", methods=["POST"])
def webhook_stripe():
    """Webhook para confirmar pagamentos via Stripe"""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return jsonify({"erro": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({"erro": "Invalid signature"}), 400
    
    # Handle checkout.session.completed
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session.get("customer_email")
        
        try:
            with get_db() as conn:
                with conn.cursor() as c:
                    c.execute("""UPDATE usuarios 
                        SET plano='assinatura', data_assinatura=%s 
                        WHERE email=%s""",
                        (datetime.now().strftime("%d/%m/%Y %H:%M"), email))
                    conn.commit()
            
            print(f"✅ WEBHOOK: Pagamento confirmado para {email}")
        except Exception as e:
            print(f"❌ ERRO webhook: {e}")
    
    return jsonify({"ok": True})

@app.route("/api/cancelar_assinatura", methods=["POST"])
@login_required
def cancelar_assinatura():
    """Cancela assinatura do usuário"""
    email = session.get("user")
    
    try:
        with get_db() as conn:
            with conn.cursor() as c:
                c.execute("SELECT stripe_subscription_id FROM usuarios WHERE email=%s", (email,))
                user = c.fetchone()
                
                if user and user["stripe_subscription_id"]:
                    stripe.Subscription.delete(user["stripe_subscription_id"])
                
                c.execute("UPDATE usuarios SET plano='gratuito' WHERE email=%s", (email,))
                conn.commit()
        
        print(f"✅ ASSINATURA CANCELADA: {email}")
        return jsonify({"ok": True})
    except Exception as e:
        print(f"❌ ERRO cancelar_assinatura: {e}")
        return jsonify({"erro": str(e)}), 500

# ================= HEALTH CHECK =================
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "preco": f"R${PRECO_ASSINATURA/100:.2f}"})

# ================= START =================
if __name__ == "__main__":
    try:
        conn = get_db()
        conn.close()
        print("✅ PostgreSQL conectado")
    except Exception as e:
        print("❌ ERRO POSTGRES:", e)
    
    print("="*50)
    print("ANALISE.IO BACKEND")
    print(f"Preço Assinatura: R${PRECO_ASSINATURA/100:.2f}")
    print("="*50)
    
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
