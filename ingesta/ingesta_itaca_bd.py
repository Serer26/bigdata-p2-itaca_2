import os
import sys
import json
import hashlib
import logging
from datetime import date

import psycopg2
import psycopg2.extras
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"logs/ingesta_{date.today()}.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("ingesta_itaca_bd")

TABLAS = ["alumnos", "cursos", "calificaciones", "contenidos"]
CAMPOS = {
    "alumnos": ["Anyo", "NIA", "sexo", "nacionalidad", "provincia", "municipio",
                "ensenanza", "curso", "grupo", "turno", "linea", "modalidad", "repite",
                "estado_matricula", "tipo_matricula", "fecha_matricula",
                "fecha_ingreso_centro"],
    "cursos": ["Anyo", "codigo", "nombre_cas", "nombre_val", "abreviatura",
               "ensenanza", "padre"],
    "calificaciones": ["Anyo", "evaluacion", "alumno", "ensenanza", "curso", "contenido",
                       "bloque_contenido", "nota_numerica", "tipo_nota"],
    "contenidos": ["Anyo", "codigo", "nombre_cas", "nombre_val", "ensenanza", "curso"],
}

# Hash generado una única vez por NIA original y reutilizado en todas las tablas
nias_anonimizados = {}


def anonimizar_nia(nia: str) -> str:
    if nia not in nias_anonimizados:
        nias_anonimizados[nia] = hashlib.sha256(str(nia).encode()).hexdigest()[:10]
    return nias_anonimizados[nia]


def conectar():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def extraer_tabla(conexion, tabla: str) -> list[dict]:
    # Solo los campos del modelo (no SELECT *): los datos personales de alumnos
    # (nombre, documento, teléfonos, emails...) no salen de la base de datos.
    # En la BD las columnas están en minúscula: "Anyo" es anyo y "NIA" es nia.
    columnas = sql.SQL(", ").join(
        sql.SQL("{} AS {}").format(sql.Identifier(campo.lower()), sql.Identifier(campo))
        for campo in CAMPOS[tabla]
    )
    consulta = sql.SQL("SELECT {} FROM {}").format(columnas, sql.Identifier(tabla))

    with conexion.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(consulta)
        datos = [dict(fila) for fila in cur.fetchall()]

    for registro in datos:
        if tabla == "alumnos":
            registro["NIA"] = anonimizar_nia(registro["NIA"])
        if tabla == "calificaciones":
            registro["alumno"] = anonimizar_nia(registro["alumno"])
    return datos


def guardar(datos: list[dict], nombre: str) -> None:
    fecha = date.today().isoformat()
    ruta = f"data/raw/{nombre}_{fecha}.json"
    os.makedirs("data/raw", exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Guardados %d registros en %s", len(datos), ruta)


def main() -> int:
    logger.info("Inicio de la ingesta ITACA (BD relacional)")
    try:
        conexion = conectar()
    except psycopg2.OperationalError:
        logger.exception("No se puede conectar a la base de datos")
        return 1

    try:
        for tabla in TABLAS:
            guardar(extraer_tabla(conexion, tabla), tabla)
        logger.info("Ingesta completada")
        return 0
    except Exception:
        logger.exception("Error durante la ingesta")
        return 1
    finally:
        conexion.close()


if __name__ == "__main__":
    sys.exit(main())
