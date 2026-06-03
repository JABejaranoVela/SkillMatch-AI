# SkillMatch AI - Guia De Trabajo

## Objetivo

SkillMatch AI es una plataforma web inteligente para analizar curriculums y recomendar ofertas de empleo compatibles mediante IA explicable.

El MVP debe permitir:
- registro e inicio de sesion;
- subida de CV en PDF o DOCX;
- extraccion y normalizacion de texto;
- deteccion de habilidades, experiencia, formacion, idiomas y tecnologias;
- carga/sincronizacion de ofertas desde una API publica con fallback CSV/JSON;
- ranking de ofertas mediante reglas y embeddings;
- explicacion del resultado;
- feedback del usuario para aprendizaje supervisado futuro.

## Stack

- Frontend: Angular, TypeScript, HTML5 y SCSS.
- Backend: Python, FastAPI, SQLAlchemy, Alembic y Pydantic.
- Base de datos: PostgreSQL con pgvector.
- CV: PyMuPDF para PDF y python-docx para DOCX.
- NLP: spaCy, regex y diccionario propio de skills.
- Embeddings: sentence-transformers.
- ML futuro: pandas, numpy y scikit-learn.
- Seguridad: JWT, passlib/bcrypt, validacion de archivos y HTTPS en produccion.
- Despliegue: Docker Compose, Nginx y VPS.

## Arquitectura

- `backend/`: API REST, autenticacion, persistencia, procesamiento de CV, matching y feedback.
- `frontend/`: aplicacion Angular para usuario final y administracion basica.
- `data/`: diccionario de skills y datasets semilla.
- `docs/`: documentacion tecnica y academica.
- `docker/`: configuracion de infraestructura.
- `scripts/`: utilidades de importacion, seeds y mantenimiento.

## Fases

1. Preparacion del proyecto y arquitectura.
2. Backend base y base de datos.
3. Frontend base.
4. Subida y procesamiento de CV.
5. Gestion de ofertas.
6. Matching por reglas.
7. Embeddings y similitud semantica.
8. Ranking hibrido y explicabilidad.
9. Feedback del usuario.
10. Pruebas y despliegue.

## Decisiones Cerradas

- Alcance: MVP demostrable.
- Idioma inicial: espanol.
- Ofertas MVP: Tecnoempleo como fuente principal para Espana. Remotive queda como endpoint tecnico externo, pero la busqueda por perfil y recomendaciones normales deben priorizar Espana.
- PDF: PyMuPDF como primera opcion.
- IA: reglas + embeddings preentrenados; sin entrenamiento deep learning desde cero.
- ML supervisado: preparado mediante feedback, no obligatorio para el MVP.

## Reglas De Desarrollo

- Mantener cambios pequenos, explicables y por fases.
- No introducir servicios externos obligatorios sin documentar fallback.
- Versionar el algoritmo de matching en cada resultado.
- Tratar CVs como datos personales: validar archivos, limitar acceso por usuario y no exponer rutas internas.
- Mantener un unico CV activo por usuario en el MVP; las recomendaciones se calculan solo con ese CV activo.
- Inferir un `profile_type` principal y un perfil secundario desde el CV para orientar la busqueda y explicar el tipo de perfil detectado.
- La extraccion no entrena modelos propios: usa texto extraido, diccionario ampliado de skills, regex, deteccion conservadora de terminos tecnicos no registrados, taxonomia local y NER opcional con GLiNER si la dependencia `ner` esta instalada.
- Pipeline de skills: diccionario fiable (`source=dictionary`) -> patrones tecnicos (`source=pattern`) -> NER opcional (`source=ner`) -> normalizacion canonica -> clasificacion por taxonomia -> guardado con confianza.
- Guardar en `professional_profiles.analysis` las puntuaciones por perfil, evidencias usadas, skills agrupadas por categoria y origen de deteccion (`dictionary` o `pattern`).
- El matching actual usa ML preentrenado mediante embeddings `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` y pgvector.
- Score actual: 65% reglas de skills + 35% similitud semantica CV-oferta.
- No mostrar ofertas de Arbeitnow en el flujo principal porque trae demasiadas ofertas de Alemania. Para el MVP, `/jobs/recommended` y `/matching/active` filtran por `source = tecnoempleo`.
- Documentar endpoints relevantes mediante OpenAPI/FastAPI.
- Anadir tests al cerrar cada comportamiento critico.

## Estado

Consultar `docs/estado-actual.md` antes de continuar. El stack Docker queda preparado con frontend en `http://localhost:4200` y backend en `http://localhost:8000`.
