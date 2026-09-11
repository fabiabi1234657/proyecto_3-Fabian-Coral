drop schema if exists mercancia;
create schema mercancia;
use mercancia;


create table producto(
idproducto int primary key auto_increment,
producto text,
marca text,
precio decimal
);

INSERT INTO producto (producto, marca, precio) 
VALUES 
('Teclado mecánico', 'Redragon', 150.00),
('Monitor 24 pulgadas', 'Samsung', 900.00);