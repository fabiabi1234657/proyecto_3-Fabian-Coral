-- Script de base de datos MySQL para proyecto_3
-- Base de datos: mercancia

DROP SCHEMA IF EXISTS mercancia;
CREATE SCHEMA mercancia CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mercancia;

-- Creación de la tabla producto con soporte para MEDIUMBLOB e índices de optimización
CREATE TABLE producto (
    idproducto INT PRIMARY KEY AUTO_INCREMENT,
    producto VARCHAR(255) NOT NULL,
    marca VARCHAR(100) NOT NULL,
    precio DECIMAL(10, 2) NOT NULL,
    imagen MEDIUMBLOB NULL,
    imagen_mime VARCHAR(100) NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_producto_nombre (producto),
    INDEX idx_producto_marca (marca)
);

-- Inserción de datos iniciales de prueba
INSERT INTO producto (producto, marca, precio, imagen, imagen_mime) 
VALUES 
('Teclado mecánico', 'Redragon', 150.00, NULL, NULL),
('Monitor 24 pulgadas', 'Samsung', 900.00, NULL, NULL);

-- ====================================================================
-- SCRIPT DE MIGRACIÓN SEGURA PARA BASES DE DATOS EXISTENTES
-- ====================================================================
-- ALTER TABLE producto ADD COLUMN IF NOT EXISTS imagen MEDIUMBLOB NULL;
-- ALTER TABLE producto ADD COLUMN IF NOT EXISTS imagen_mime VARCHAR(100) NULL;
-- CREATE INDEX idx_producto_nombre ON producto (producto);
-- CREATE INDEX idx_producto_marca ON producto (marca);