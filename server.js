const express = require('express');
const cors = require('cors');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { Pool } = require('pg');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const helmet = require('helmet');

const app = express();

// =========================
// CONFIG
// =========================

const PORT = process.env.PORT || 3000;

const JWT_SECRET =
  process.env.JWT_SECRET ||
  'analise_io_secret_2024';

// =========================
// MIDDLEWARES
// =========================

app.use(helmet());

app.use(cors({
  origin: '*'
}));

app.use(express.json({
  limit: '10mb'
}));

app.use(express.urlencoded({
  extended: true,
  limit: '10mb'
}));

app.use(express.static('.'));

app.use(
  '/uploads',
  express.static(path.join(__dirname, 'uploads'))
);

// =========================
// UPLOADS
// =========================

const uploadsDir = path.join(__dirname, 'uploads');

if (!fs.existsSync(uploadsDir)) {
  fs.mkdirSync(uploadsDir);
}

const storage = multer.diskStorage({

  destination: (req, file, cb) => {
    cb(null, uploadsDir);
  },

  filename: (req, file, cb) => {

    const uniqueName =
      Date.now() +
      '-' +
      Math.round(Math.random() * 1e9) +
      path.extname(file.originalname);

    cb(null, uniqueName);
  }

});

const upload = multer({

  storage,

  limits: {
    fileSize: 5 * 1024 * 1024
  },

  fileFilter: (req, file, cb) => {

    const allowed = [
      'image/png',
      'image/jpeg',
      'image/jpg'
    ];

    if (!allowed.includes(file.mimetype)) {
      return cb(new Error('Formato inválido'));
    }

    cb(null, true);
  }

});

// =========================
// DATABASE
// =========================

const pool = new Pool({

  connectionString: process.env.DATABASE_URL,

  ssl:
    process.env.NODE_ENV === 'production'
      ? { rejectUnauthorized: false }
      : false

});

// =========================
// INIT DATABASE
// =========================

async function initDB() {

  const client = await pool.connect();

  try {

    await client.query(`
      CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        nome TEXT,
        email TEXT UNIQUE,
        senha_hash TEXT,
        admin BOOLEAN DEFAULT FALSE,
        plano TEXT DEFAULT 'gratuito',
        created_at TIMESTAMP DEFAULT NOW()
      );
    `);

    await client.query(`
      CREATE TABLE IF NOT EXISTS atletas (
        id SERIAL PRIMARY KEY,
        nome TEXT,
        idade INT,
        posicao TEXT,
        modalidade TEXT,
        clube TEXT,
        pe TEXT,
        altura INT,
        peso INT,
        forte TEXT,
        fraco TEXT,
        disponivel BOOLEAN DEFAULT true,
        instagram TEXT,
        whatsapp TEXT,
        agencia TEXT,
        video TEXT,
        foto TEXT,
        contrato TEXT,
        status TEXT DEFAULT 'pendente',
        stats_gols TEXT,
        stats_assists TEXT,
        stats_passes TEXT,
        stats_dribles TEXT,
        stats_nota TEXT,
        stats_jogos TEXT,
        created_at TIMESTAMP DEFAULT NOW()
      );
    `);

    await client.query(`
      CREATE TABLE IF NOT EXISTS clubes (
        id SERIAL PRIMARY KEY,
        nome TEXT,
        cidade TEXT,
        posicao TEXT,
        idade TEXT,
        detalhes TEXT,
        contato TEXT,
        status TEXT DEFAULT 'pendente',
        created_at TIMESTAMP DEFAULT NOW()
      );
    `);

    console.log('✅ Banco conectado');

  } catch (err) {

    console.error('❌ Erro init DB:', err);

  } finally {

    client.release();

  }

}

initDB();

// =========================
// TEST ROUTE
// =========================

app.get('/api/test', async (req, res) => {

  try {

    const result = await pool.query(
      'SELECT NOW()'
    );

    res.json({
      ok: true,
      time: result.rows[0]
    });

  } catch (err) {

    res.status(500).json({
      ok: false,
      erro: err.message
    });

  }

});

// =========================
// CADASTRO
// =========================

app.post('/api/cadastro', async (req, res) => {

  try {

    const {
      nome,
      email,
      senha
    } = req.body;

    if (!nome || !email || !senha) {

      return res.status(400).json({
        erro: 'Campos obrigatórios'
      });

    }

    const existe = await pool.query(
      'SELECT * FROM users WHERE email = $1',
      [email]
    );

    if (existe.rows.length > 0) {

      return res.status(400).json({
        erro: 'Email já cadastrado'
      });

    }

    const senha_hash =
      await bcrypt.hash(senha, 10);

    await pool.query(`
      INSERT INTO users (
        nome,
        email,
        senha_hash
      )
      VALUES ($1,$2,$3)
    `, [
      nome,
      email,
      senha_hash
    ]);

    res.json({
      ok: true
    });

  } catch (err) {

    console.error(err);

    res.status(500).json({
      erro: err.message
    });

  }

});

// =========================
// LOGIN
// =========================

app.post('/api/login', async (req, res) => {

  try {

    const {
      user,
      senha
    } = req.body;

    const result = await pool.query(
      'SELECT * FROM users WHERE email = $1',
      [user]
    );

    if (result.rows.length === 0) {

      return res.status(400).json({
        erro: 'Usuário não encontrado'
      });

    }

    const usuario = result.rows[0];

    const senhaOk =
      await bcrypt.compare(
        senha,
        usuario.senha_hash
      );

    if (!senhaOk) {

      return res.status(400).json({
        erro: 'Senha incorreta'
      });

    }

    const token = jwt.sign({

      id: usuario.id,
      email: usuario.email,
      admin: usuario.admin

    }, JWT_SECRET, {
      expiresIn: '7d'
    });

    res.json({
      ok: true,
      token,
      nome: usuario.nome,
      admin: usuario.admin,
      plano: usuario.plano
    });

  } catch (err) {

    console.error(err);

    res.status(500).json({
      erro: err.message
    });

  }

});

// =========================
// GET ATLETAS
// =========================

app.get('/api/atletas', async (req, res) => {

  try {

    const result = await pool.query(`
      SELECT *
      FROM atletas
      ORDER BY id DESC
    `);

    res.json(result.rows);

  } catch (err) {

    console.error(err);

    res.status(500).json({
      erro: err.message
    });

  }

});

// =========================
// ADD ATLETA
// =========================

app.post('/api/atletas', async (req, res) => {

  try {

    const {

      nome,
      idade,
      posicao,
      modalidade,
      clube,
      pe,
      altura,
      peso,
      forte,
      fraco,
      disponivel,
      instagram,
      whatsapp,
      agencia,
      video,
      foto,
      contrato,
      status,
      stats_gols,
      stats_assists,
      stats_passes,
      stats_dribles,
      stats_nota,
      stats_jogos

    } = req.body;

    await pool.query(`

      INSERT INTO atletas (

        nome,
        idade,
        posicao,
        modalidade,
        clube,
        pe,
        altura,
        peso,
        forte,
        fraco,
        disponivel,
        instagram,
        whatsapp,
        agencia,
        video,
        foto,
        contrato,
        status,
        stats_gols,
        stats_assists,
        stats_passes,
        stats_dribles,
        stats_nota,
        stats_jogos

      )

      VALUES (

        $1,$2,$3,$4,$5,$6,
        $7,$8,$9,$10,$11,$12,
        $13,$14,$15,$16,$17,$18,
        $19,$20,$21,$22,$23,$24

      )

    `, [

      nome,
      idade,
      posicao,
      modalidade,
      clube,
      pe,
      altura,
      peso,
      forte,
      fraco,
      disponivel,
      instagram,
      whatsapp,
      agencia,
      video,
      foto,
      contrato,
      status,
      stats_gols,
      stats_assists,
      stats_passes,
      stats_dribles,
      stats_nota,
      stats_jogos

    ]);

    res.json({
      ok: true
    });

  } catch (err) {

    console.error(err);

    res.status(500).json({
      ok: false,
      erro: err.message
    });

  }

});

// =========================
// DELETE ATLETA
// =========================

app.delete('/api/atletas/:id', async (req, res) => {

  try {

    const id = req.params.id;

    await pool.query(`
      DELETE FROM atletas
      WHERE id = $1
    `, [id]);

    res.json({
      ok: true
    });

  } catch (err) {

    console.error(err);

    res.status(500).json({
      erro: err.message
    });

  }

});

// =========================
// START
// =========================

app.listen(PORT, () => {

  console.log(`
🚀 ANALISE.IO ONLINE
PORTA: ${PORT}
`);

});
