const express = require('express');
const cors = require('cors');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { Pool } = require('pg');
const multer = require('multer');
const path = require('path');
const fs = require('fs');

const app = express();

app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));
app.use(express.static('.'));
app.use('/uploads', express.static('uploads'));

// Upload local
if (!fs.existsSync('uploads')) fs.mkdirSync('uploads');
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, 'uploads/'),
  filename:    (req, file, cb) => cb(null, Date.now() + path.extname(file.originalname))
});
const upload = multer({ storage, limits: { fileSize: 5 * 1024 * 1024 } });

// Banco
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false }
});

const JWT_SECRET = process.env.JWT_SECRET || 'analise_io_secret_2024';

// Cria tabelas
async function initDB() {
  const client = await pool.connect();
  try {
    await client.query(`
      CREATE TABLE IF NOT EXISTS usuarios (
        id        SERIAL PRIMARY KEY,
        nome      TEXT NOT NULL,
        email     TEXT UNIQUE NOT NULL,
        senha     TEXT NOT NULL,
        admin     BOOLEAN DEFAULT FALSE,
        plano     TEXT DEFAULT 'gratuito',
        criado_em TIMESTAMP DEFAULT NOW()
      );
      CREATE TABLE IF NOT EXISTS atletas (
        id            SERIAL PRIMARY KEY,
        nome          TEXT NOT NULL,
        idade         INTEGER,
        posicao       TEXT,
        modalidade    TEXT DEFAULT 'Futsal',
        clube         TEXT,
        pe            TEXT,
        altura        INTEGER,
        peso          INTEGER,
        forte         TEXT,
        fraco         TEXT,
        disponivel    BOOLEAN DEFAULT TRUE,
        instagram     TEXT,
        whatsapp      TEXT,
        agencia       TEXT,
        video         TEXT,
        foto          TEXT,
        contrato      TEXT,
        status        TEXT DEFAULT 'pendente',
        stats_gols    TEXT,
        stats_assists TEXT,
        stats_passes  TEXT,
        stats_dribles TEXT,
        stats_nota    TEXT,
        stats_jogos   TEXT,
        criado_em     TIMESTAMP DEFAULT NOW()
      );
      CREATE TABLE IF NOT EXISTS clubes (
        id          SERIAL PRIMARY KEY,
        nome        TEXT NOT NULL,
        cidade      TEXT,
        posicao     TEXT,
        faixa_idade TEXT,
        detalhes    TEXT,
        contato     TEXT,
        status      TEXT DEFAULT 'pendente',
        criado_em   TIMESTAMP DEFAULT NOW()
      );
    `);
    console.log('Tabelas OK');
  } finally {
    client.release();
  }
}

// Middlewares de auth
function auth(req, res, next) {
  const token = (req.headers['authorization'] || '').split(' ')[1];
  if (!token) return res.status(401).json({ erro: 'Nao autenticado' });
  try { req.user = jwt.verify(token, JWT_SECRET); next(); }
  catch { res.status(401).json({ erro: 'Token invalido' }); }
}
function adminOnly(req, res, next) {
  auth(req, res, () => {
    if (!req.user.admin) return res.status(403).json({ erro: 'Acesso negado' });
    next();
  });
}

// ── AUTH ────────────────────────────────────────────────────

app.post('/api/cadastro', async (req, res) => {
  const { nome, email, senha } = req.body;
  if (!nome || !email || !senha) return res.json({ erro: 'Preencha todos os campos' });
  if (senha.length < 6) return res.json({ erro: 'Senha minimo 6 caracteres' });
  try {
    const hash = await bcrypt.hash(senha, 10);
    const r = await pool.query(
      'INSERT INTO usuarios (nome,email,senha) VALUES ($1,$2,$3) RETURNING id,nome,email,plano',
      [nome, email, hash]
    );
    res.json({ ok: true, usuario: r.rows[0] });
  } catch (e) {
    if (e.code === '23505') return res.json({ erro: 'Email ja cadastrado' });
    res.json({ erro: e.message });
  }
});

app.post('/api/login', async (req, res) => {
  const { user: email, senha } = req.body;
  if (email === 'admin' && senha === 'admin123') {
    const token = jwt.sign({ id: 0, nome: 'Admin', admin: true, plano: 'admin' }, JWT_SECRET, { expiresIn: '7d' });
    return res.json({ ok: true, token, nome: 'Admin', admin: true, plano: 'admin' });
  }
  try {
    const r = await pool.query('SELECT * FROM usuarios WHERE email=$1', [email]);
    if (!r.rows.length) return res.json({ erro: 'Usuario nao encontrado' });
    const u = r.rows[0];
    const ok = await bcrypt.compare(senha, u.senha);
    if (!ok) return res.json({ erro: 'Senha incorreta' });
    const token = jwt.sign({ id: u.id, nome: u.nome, admin: u.admin, plano: u.plano }, JWT_SECRET, { expiresIn: '7d' });
    res.json({ ok: true, token, nome: u.nome, admin: u.admin, plano: u.plano });
  } catch (e) {
    res.json({ erro: e.message });
  }
});

// ── ATLETAS ─────────────────────────────────────────────────

// GET publico — lista aprovados com filtros
app.get('/api/atletas', async (req, res) => {
  try {
    const { posicao, modalidade, disponivel, q } = req.query;
    let sql = "SELECT * FROM atletas WHERE status='aprovado'";
    const params = [];
    let i = 1;
    if (posicao)    { sql += ` AND posicao=$${i++}`;    params.push(posicao); }
    if (modalidade) { sql += ` AND modalidade=$${i++}`; params.push(modalidade); }
    if (disponivel === 'sim') sql += ' AND disponivel=TRUE';
    if (disponivel === 'nao') sql += ' AND disponivel=FALSE';
    if (q) {
      sql += ` AND (LOWER(nome) LIKE $${i} OR LOWER(posicao) LIKE $${i} OR LOWER(clube) LIKE $${i})`;
      params.push('%' + q.toLowerCase() + '%'); i++;
    }
    sql += ' ORDER BY criado_em DESC';
    const r = await pool.query(sql, params);
    res.json(r.rows);
  } catch (e) { res.status(500).json({ erro: e.message }); }
});

// GET admin — lista todos
app.get('/api/admin/atletas', adminOnly, async (req, res) => {
  try {
    const r = await pool.query('SELECT * FROM atletas ORDER BY criado_em DESC');
    res.json(r.rows);
  } catch (e) { res.status(500).json({ erro: e.message }); }
});

// POST admin — adiciona atleta direto (aprovado), suporta multipart/form-data para foto
app.post('/api/atletas', adminOnly, upload.single('foto'), async (req, res) => {
  try {
    const b = req.body;
    const foto = req.file ? '/uploads/' + req.file.filename : (b.foto_url || null);
    const r = await pool.query(`
      INSERT INTO atletas
        (nome,idade,posicao,modalidade,clube,pe,altura,peso,forte,fraco,
         disponivel,instagram,whatsapp,agencia,video,foto,contrato,status,
         stats_gols,stats_assists,stats_passes,stats_dribles,stats_nota,stats_jogos)
      VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,'aprovado',
              $18,$19,$20,$21,$22,$23) RETURNING *`,
      [
        b.nome, b.idade||null, b.posicao, b.modalidade||'Futsal',
        b.clube||'', b.pe||'Direito',
        b.altura||null, b.peso||null,
        b.forte||'', b.fraco||'',
        b.disponivel === 'true' || b.disponivel === true,
        b.instagram||'', b.whatsapp||'',
        b.agencia||'', b.video||'',
        foto, b.contrato||'',
        b.stats_gols||'', b.stats_assists||'',
        b.stats_passes||'', b.stats_dribles||'',
        b.stats_nota||'', b.stats_jogos||''
      ]
    );
    res.json({ ok: true, atleta: r.rows[0] });
  } catch (e) { res.status(500).json({ erro: e.message }); }
});

// POST solicitar — usuario logado envia pedido (fica pendente)
app.post('/api/atletas/solicitar', auth, async (req, res) => {
  try {
    const b = req.body;
    if (!b.nome || !b.posicao) return res.json({ erro: 'Nome e posicao obrigatorios' });
    await pool.query(`
      INSERT INTO atletas
        (nome,idade,posicao,modalidade,clube,pe,altura,peso,
         instagram,whatsapp,agencia,forte,video,status)
      VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,'pendente')`,
      [b.nome, b.idade||null, b.posicao, b.modalidade||'Futsal',
       b.clube||'', b.pe||'Direito', b.altura||null, b.peso||null,
       b.instagram||'', b.whatsapp||'', b.agencia||'', b.forte||'', b.video||'']
    );
    res.json({ ok: true });
  } catch (e) { res.status(500).json({ erro: e.message }); }
});

// PUT status — aprova ou recusa
app.put('/api/atletas/:id/status', adminOnly, async (req, res) => {
  try {
    const { status } = req.body;
    await pool.query('UPDATE atletas SET status=$1 WHERE id=$2', [status, req.params.id]);
    res.json({ ok: true });
  } catch (e) { res.status(500).json({ erro: e.message }); }
});

// DELETE atleta
app.delete('/api/atletas/:id', adminOnly, async (req, res) => {
  try {
    await pool.query('DELETE FROM atletas WHERE id=$1', [req.params.id]);
    res.json({ ok: true });
  } catch (e) { res.status(500).json({ erro: e.message }); }
});

// POST importar CSV — recebe array de objetos ja parseados
app.post('/api/atletas/importar-csv', adminOnly, async (req, res) => {
  try {
    const { atletas } = req.body;
    if (!atletas?.length) return res.json({ erro: 'Nenhum atleta no payload' });
    let count = 0;
    for (const b of atletas) {
      if (!b.nome || !b.posicao) continue;
      await pool.query(`
        INSERT INTO atletas
          (nome,idade,posicao,modalidade,clube,pe,altura,peso,agencia,contrato,
           instagram,whatsapp,forte,fraco,video,
           stats_gols,stats_assists,stats_passes,stats_dribles,stats_nota,stats_jogos,
           disponivel,status)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,
                $16,$17,$18,$19,$20,$21,$22,'aprovado')`,
        [b.nome, parseInt(b.idade)||null, b.posicao, 'Futsal',
         b.clube||'', b.pe||'Direito', parseInt(b.altura)||null, parseInt(b.peso)||null,
         b.agencia||'', b.contrato||'', b.instagram||'', b.whatsapp||'',
         b.forte||'', b.fraco||'', b.video||'',
         b.gols||'', b.assists||'', b.passes||'',
         b.dribles||'', b.nota||'', b.jogos||'',
         b.disponivel !== 'false']
      );
      count++;
    }
    res.json({ ok: true, importados: count });
  } catch (e) { res.status(500).json({ erro: e.message }); }
});

// ── CLUBES ──────────────────────────────────────────────────

app.get('/api/clubes', async (req, res) => {
  try {
    const r = await pool.query("SELECT * FROM clubes WHERE status='aprovado' ORDER BY criado_em DESC");
    res.json(r.rows);
  } catch (e) { res.status(500).json({ erro: e.message }); }
});

app.get('/api/admin/clubes', adminOnly, async (req, res) => {
  try {
    const r = await pool.query('SELECT * FROM clubes ORDER BY criado_em DESC');
    res.json(r.rows);
  } catch (e) { res.status(500).json({ erro: e.message }); }
});

// Clube envia vaga — fica pendente
app.post('/api/clubes', async (req, res) => {
  try {
    const { nome, cidade, posicao, faixa_idade, detalhes, contato } = req.body;
    if (!nome || !posicao || !contato) return res.json({ erro: 'Preencha nome, posicao e contato' });
    await pool.query(
      'INSERT INTO clubes (nome,cidade,posicao,faixa_idade,detalhes,contato) VALUES ($1,$2,$3,$4,$5,$6)',
      [nome, cidade||'Brasil', posicao, faixa_idade||'', detalhes||'', contato]
    );
    res.json({ ok: true });
  } catch (e) { res.status(500).json({ erro: e.message }); }
});

// Admin adiciona clube direto (aprovado)
app.post('/api/admin/clubes', adminOnly, async (req, res) => {
  try {
    const { nome, cidade, posicao, faixa_idade, detalhes, contato } = req.body;
    if (!nome || !posicao) return res.json({ erro: 'Nome e posicao obrigatorios' });
    const r = await pool.query(
      "INSERT INTO clubes (nome,cidade,posicao,faixa_idade,detalhes,contato,status) VALUES ($1,$2,$3,$4,$5,$6,'aprovado') RETURNING *",
      [nome, cidade||'Brasil', posicao, faixa_idade||'', detalhes||'', contato||'']
    );
    res.json({ ok: true, clube: r.rows[0] });
  } catch (e) { res.status(500).json({ erro: e.message }); }
});

app.put('/api/admin/clubes/:id/status', adminOnly, async (req, res) => {
  try {
    const { status } = req.body;
    await pool.query('UPDATE clubes SET status=$1 WHERE id=$2', [status, req.params.id]);
    res.json({ ok: true });
  } catch (e) { res.status(500).json({ erro: e.message }); }
});

app.delete('/api/admin/clubes/:id', adminOnly, async (req, res) => {
  try {
    await pool.query('DELETE FROM clubes WHERE id=$1', [req.params.id]);
    res.json({ ok: true });
  } catch (e) { res.status(500).json({ erro: e.message }); }
});

// ── START ────────────────────────────────────────────────────
initDB().then(() => {
  const PORT = process.env.PORT || 3000;
  app.listen(PORT, () => console.log('Servidor rodando na porta ' + PORT));
}).catch(e => {
  console.error('Erro ao conectar no banco:', e.message);
  process.exit(1);
});
