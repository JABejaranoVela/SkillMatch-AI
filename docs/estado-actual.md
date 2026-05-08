# Estado Actual

## Implementado

- Proyecto creado en carpeta `SkillMatch-AI`.
- Backend FastAPI con Docker, SQLAlchemy, Alembic y PostgreSQL/pgvector.
- Autenticacion con registro, login JWT y usuario actual.
- Subida de CV PDF/DOCX.
- Solo un CV activo por usuario: al subir uno nuevo, los anteriores quedan inactivos.
- Extraccion de texto con PyMuPDF y python-docx.
- Normalizacion basica y deteccion de skills por diccionario.
- Perfil profesional estructurado con tipo de perfil inferido, tecnologias, idiomas, experiencia y formacion detectada.
- Extraccion actual de conocimientos: PyMuPDF/python-docx para texto + normalizacion + diccionario ampliado de skills + reglas heuristicas para tipo de perfil.
- Sincronizacion externa real con Tecnoempleo desde la pantalla Ofertas para priorizar portales espanoles.
- La importacion CSV/JSON queda solo como endpoint tecnico, no aparece en la UI del MVP.
- La pantalla Ofertas permite buscar por el perfil activo: genera terminos desde `profile_type` y skills detectadas, consulta Tecnoempleo y muestra fuente, modalidad, ubicacion, resumen, requisitos, coincidencias y enlace original.
- La pantalla Matching no busca ofertas nuevas: ordena las ofertas ya disponibles por compatibilidad con el CV activo, explica coincidencias/faltantes y recoge feedback.
- Matching hibrido con reglas de skills y embeddings semanticos.
- Embeddings generados con `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` y guardados en pgvector.
- Score actual: 65% coincidencia de skills detectadas + 35% similitud semantica entre CV y oferta.
- Feedback de usuario: guardado, descartado y postulado.
- Frontend Angular con login, registro, CVs, ofertas, matching y feedback.
- Navegacion condicionada por sesion: Login/Registro solo aparecen sin token; con sesion aparecen CV, Ofertas, Matching y Salir.
- Pantalla CV muestra siempre el bloque de perfil: pendiente antes de procesar, y tipo de perfil + skills despues de procesar.
- Docker Compose para frontend, backend y base de datos.

## URLs Locales

- Frontend: http://localhost:4200
- Backend: http://localhost:8000
- Swagger/OpenAPI: http://localhost:8000/docs
- Healthcheck: http://localhost:8000/api/v1/health

## Prueba Realizada

- Usuario demo creado en la base local actual:
  - Email: `demo.skillmatch@example.com`
  - Password: `Password123`
- CV temporal subido desde `storage/tmp_cv_demo.docx`.
- Perfil detectado:
  - Angular
  - FastAPI
  - Machine Learning
  - Python
  - SQL
- Ofertas:
  - 1 oferta manual.
  - 3 ofertas importadas desde Remotive.
- Matching:
  - Se calcula siempre contra el CV activo del usuario.
  - 4 resultados generados en la base local actual.
- Perfil detectado tras reprocesar el CV actual: `Backend Developer`.
- Tras ampliar el diccionario, el CV de prueba detecta `Full Stack Developer` y skills como Java, Spring Boot, Vue, TypeScript, Docker, GitHub Actions, JWT, Swagger/OpenAPI, MySQL, SQLite, Maven, npm y Schemathesis.
- Feedback:
  - 1 interaccion `saved` registrada.

## Pendiente Prioritario

- Mejorar UI para seleccionar CV sin escribir ID manualmente.
- Mostrar detalle completo de oferta y enlace externo.
- Ampliar diccionario de skills en espanol/ingles tecnico.
- Recalcular embeddings cuando se reprocesa un CV o cuando cambie una oferta existente.
- Anadir opcionalmente Adzuna/InfoJobs/Jooble cuando se disponga de claves API.
- Anadir tests automatizados con pytest y pruebas frontend.
- Decidir politica de datos personales y borrado de CVs.

## Fuente Externa De Ofertas

Fuente principal actual:
- Portal: `https://www.tecnoempleo.com`
- La aplicacion conserva la URL original y muestra `tecnoempleo` como fuente de la oferta.
- Remotive queda disponible como endpoint tecnico, pero no se usa en la busqueda por perfil del MVP.
