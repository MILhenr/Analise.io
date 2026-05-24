const express = require('express');
const cors = require('cors');
const { Pool } = require('pg');

const app = express();

app.use(cors());
app.use(express.json());
app.use(express.static('.'));

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: {
    rejectUnauthorized: false
  }
});

app.get('/', async(req,res)=>{

  try{

    const r = await pool.query('SELECT * FROM atletas');

    res.json(r.rows);

  }catch(err){

    res.json({
      erro: err.message
    });

  }

});

app.listen(process.env.PORT || 3000, ()=>{
  console.log('Servidor rodando');
});
