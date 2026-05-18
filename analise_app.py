import urllib.request
from flask import Flask, request, jsonify, session, send_from_directory
import json
import os
import uuid
import hashlib
from datetime import datetime

app = Flask(__name__)
app.secret_key = "imperio_analise_2024"

DB_PATH = "db.json"

# ================= DB =================

def load_db():
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "r") as f:
            return json.load(f)
    return {"usuarios": {}, "analises": {}, "admin": {"email": "henry@imperio.com", "senha": hash_senha("admin123")}}

def save_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def hash_senha(s):
    return hashlib.sha256(s.encode()).hexdigest()

# ================= ROTAS =================

@app.route("/")
def index():
    return send_from_directory(".", "analise_site.html")

@app.route("/api/cadastro", methods=["POST"])
def cadastro():
    data = request.json
    db = load_db()
    email = data.get("email", "").lower().strip()
    if email in db["usuarios"]:
        return jsonify({"erro": "Email já cadastrado"}), 400
    db["usuarios"][email] = {
        "nome": data.get("nome", ""),
        "email": email,
        "senha": hash_senha(data.get("senha", "")),
        "plano": "gratuito",
        "analises_mes": 0,
        "criado_em": datetime.now().strftime("%d/%m/%Y %H:%M")
    }
    save_db(db)
    return jsonify({"ok": True})

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    db = load_db()
    email = data.get("email", "").lower().strip()
    senha = hash_senha(data.get("senha", ""))

    # admin
    if email == db["admin"]["email"] and senha == db["admin"]["senha"]:
        session["user"] = "admin"
        session["admin"] = True
        return jsonify({"ok": True, "admin": True})

    if email not in db["usuarios"]:
        return jsonify({"erro": "Email não encontrado"}), 401
    if db["usuarios"][email]["senha"] != senha:
        return jsonify({"erro": "Senha incorreta"}), 401

    session["user"] = email
    session["admin"] = False
    return jsonify({"ok": True, "admin": False, "nome": db["usuarios"][email]["nome"], "plano": db["usuarios"][email]["plano"]})

@app.route("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/me")
def me():
    if "user" not in session:
        return jsonify({"logado": False})
    db = load_db()
    if session.get("admin"):
        return jsonify({"logado": True, "admin": True})
    email = session["user"]
    u = db["usuarios"].get(email, {})
    return jsonify({"logado": True, "admin": False, "nome": u.get("nome"), "plano": u.get("plano"), "email": email})

@app.route("/api/solicitar", methods=["POST"])
def solicitar():
    if "user" not in session or session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json
    db = load_db()
    email = session["user"]
    u = db["usuarios"][email]

    # Verifica limite
    if u["plano"] == "gratuito":
        return jsonify({"erro": "plano_necessario"}), 403

    aid = str(uuid.uuid4())[:8].upper()
    db["analises"][aid] = {
        "id": aid,
        "usuario": email,
        "nome_usuario": u["nome"],
        "link": data.get("link", ""),
        "numero": data.get("numero", ""),
        "posicao": data.get("posicao", ""),
        "observacoes": data.get("observacoes", ""),
        "status": "aguardando",
        "resultado": "",
        "criado_em": datetime.now().strftime("%d/%m/%Y %H:%M")
    }
    save_db(db)
    return jsonify({"ok": True, "id": aid})

@app.route("/api/minhas_analises")
def minhas_analises():
    if "user" not in session:
        return jsonify({"erro": "Não autorizado"}), 401
    db = load_db()
    email = session["user"]
    resultado = [a for a in db["analises"].values() if a["usuario"] == email]
    resultado.sort(key=lambda x: x["criado_em"], reverse=True)
    return jsonify(resultado)

@app.route("/api/admin/analises")
def admin_analises():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    db = load_db()
    lista = list(db["analises"].values())
    lista.sort(key=lambda x: x["criado_em"], reverse=True)
    return jsonify(lista)

@app.route("/api/admin/entregar", methods=["POST"])
def admin_entregar():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json
    db = load_db()
    aid = data.get("id")
    if aid not in db["analises"]:
        return jsonify({"erro": "Análise não encontrada"}), 404
    db["analises"][aid]["resultado"] = data.get("resultado", "")
    db["analises"][aid]["status"] = "entregue"
    save_db(db)
    return jsonify({"ok": True})

@app.route("/api/admin/usuarios")
def admin_usuarios():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    db = load_db()
    return jsonify(list(db["usuarios"].values()))

@app.route("/api/admin/upgrade", methods=["POST"])
def admin_upgrade():
    if not session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    data = request.json
    db = load_db()
    email = data.get("email")
    plano = data.get("plano")
    if email in db["usuarios"]:
        db["usuarios"][email]["plano"] = plano
        save_db(db)
    return jsonify({"ok": True})


MP_ACCESS_TOKEN = "APP_USR-6719425973860470-051719-0dba2eadcd461aa80a64231ff92c09ba-2112056378"
MP_PUBLIC_KEY = "APP_USR-90e13660-4204-4f29-9435-55399dfaa19f"

@app.route("/api/criar_pagamento", methods=["POST"])
def criar_pagamento():
    if "user" not in session or session.get("admin"):
        return jsonify({"erro": "Não autorizado"}), 401
    
    data = request.json
    plano = data.get("plano", "avulso")
    email = session["user"]
    db = load_db()
    nome = db["usuarios"][email]["nome"]
    
    valor = 10.00 if plano == "avulso" else 60.00
    titulo = "Análise Avulsa" if plano == "avulso" else "Assinatura Mensal Ilimitada"
    
    try:
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
            headers={
                "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
                "Content-Type": "application/json"
            }
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
                    db = load_db()
                    if email in db["usuarios"]:
                        db["usuarios"][email]["plano"] = plano
                        save_db(db)
        
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
    db = load_db()
    save_db(db)
    print("")
    print("  ANALISE.IO RODANDO")
    print("  http://localhost:5000")
    print("")
    print("  Admin: henry@imperio.com / admin123")
    print("")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
