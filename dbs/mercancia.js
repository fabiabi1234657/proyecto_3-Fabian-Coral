// Script de inicialización y migración para MongoDB (Base de datos: mercancia, Colección: producto)

// 1. Creación de Índices para optimización de consultas
db.producto.createIndex({ idproducto: 1 }, { unique: true, sparse: true });
db.producto.createIndex({ producto: 1 });
db.producto.createIndex({ marca: 1 });
db.producto.createIndex({ producto: "text", descripcion: "text", marca: "text" });

// 2. Inserción de documentos de ejemplo con la estructura híbrida
db.producto.insertMany([
  // Nivel 1: <= 1 MB (Binario en MySQL) -> ruta=null, tamano_real=null, tamano_comprimido=null, almacenamiento="mysql", cifrada=false
  {
    idproducto: 1,
    producto: 'Teclado mecánico',
    marca: 'Redragon',
    precio: 150.00,
    descripcion: 'Teclado mecánico switches azules con retroiluminación RGB',
    url: '',
    ruta: null,
    tamano_real: null,
    tamano_comprimido: null,
    mime_type: 'image/jpeg',
    almacenamiento: 'mysql',
    cifrada: false
  },

  // Nivel 2: > 1 MB y <= 3 MB (Cifrado en disco) -> tamano_comprimido=null, almacenamiento="filesystem", cifrada=true
  {
    idproducto: 2,
    producto: 'Monitor 24 pulgadas',
    marca: 'Samsung',
    precio: 900.00,
    descripcion: 'Monitor gamer Full HD 144Hz panel IPS',
    url: '',
    ruta: 'storage/images/sample_monitor.enc',
    tamano_real: 2450000,
    tamano_comprimido: null,
    mime_type: 'image/jpeg',
    almacenamiento: 'filesystem',
    cifrada: true
  }
]);

// 3. Migración segura para documentos existentes en MongoDB
db.producto.updateMany(
  { almacenamiento: { $exists: false } },
  {
    $set: {
      ruta: null,
      tamano_real: null,
      tamano_comprimido: null,
      mime_type: null,
      almacenamiento: "mysql",
      cifrada: false
    }
  }
);