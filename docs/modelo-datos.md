# Modelo De Datos Inicial

## Entidades

- `users`: usuarios de la plataforma.
- `resumes`: archivos CV y texto extraido.
- `professional_profiles`: perfil estructurado derivado de un CV.
- `skills`: catalogo normalizado de habilidades.
- `profile_skills`: relacion entre perfil y skills detectadas.
- `jobs`: ofertas de empleo.
- `job_skills`: skills requeridas por una oferta.
- `match_results`: resultados de compatibilidad.
- `user_job_interactions`: feedback e interacciones.
- `job_imports`: auditoria de importaciones.

## Principios

- Separar texto bruto, texto limpio y perfil estructurado.
- Versionar resultados de matching.
- Guardar explicaciones como JSON estructurado.
- Preparar feedback para entrenamiento supervisado futuro.
- Crear el esquema con Alembic y activar la extension `vector` para pgvector.
