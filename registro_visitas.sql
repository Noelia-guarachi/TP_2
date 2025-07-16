CREATE DATABASE IF NOT EXISTS registro_visitas;
USE registro_visitas;

CREATE TABLE IF NOT EXISTS visitas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre_apellido VARCHAR(100) NOT NULL,
    dni VARCHAR(20) NOT NULL,
    motivo VARCHAR(255),
    persona_visitada VARCHAR(100),
    hora_ingreso DATETIME DEFAULT CURRENT_TIMESTAMP,
    hora_egreso DATETIME
);
INSERT INTO visitas (nombre_apellido, dni, motivo, persona_visitada)
VALUES
