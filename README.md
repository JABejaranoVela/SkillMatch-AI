# SkillMatch AI

Plataforma web inteligente para analizar curriculums y recomendar ofertas de empleo compatibles con explicaciones claras del resultado.

## Estado Actual

Proyecto en fase inicial. Se esta creando la arquitectura base para:
- backend FastAPI;
- frontend Angular;
- PostgreSQL con pgvector;
- procesamiento de CV;
- matching por reglas y embeddings;
- feedback para aprendizaje futuro.

## Estructura

```text
backend/   API FastAPI y servicios de IA/matching
frontend/  Aplicacion Angular
docs/      Documentacion tecnica y academica
data/      Diccionarios y datos semilla
docker/    Configuracion de infraestructura
scripts/   Utilidades de proyecto
```

## Desarrollo Previsto

El desarrollo se realiza por fases. La referencia principal del proyecto esta en `CODEx.md`.

## Arranque Local Con Docker

```bash
docker compose up --build -d
```

- Frontend: http://localhost:4200
- Backend: http://localhost:8000
- Swagger/OpenAPI: http://localhost:8000/docs

El frontend usa `frontend/proxy.conf.json` para redirigir `/api` al backend durante desarrollo.
