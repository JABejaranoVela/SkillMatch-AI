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

## Sistema Visual

Toda modificacion visual del frontend debe partir de los tokens definidos en `frontend/src/styles.scss`. No usar colores hexadecimales, sombras, radios ni fuentes nuevas directamente en componentes salvo que antes se registren como token global y se documenten aqui.

### Fuente

- Fuente unica de la aplicacion: `Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`.
- Usar `var(--font-family-base)` indirectamente desde `:root`; no declarar `font-family` en componentes salvo caso excepcional.

### Colores Base

- Fondo de pagina: `--color-bg` (`#f5f7fa`).
- Superficie principal: `--color-surface` (`#ffffff`).
- Superficie suave: `--color-surface-soft` (`#f8fafc`).
- Bordes: `--color-border` (`#e2e8f0`) y `--color-border-strong` (`#d0d5dd`).
- Texto principal: `--color-text` (`#18202f`).
- Titulos: `--color-heading` (`#101828`).
- Texto secundario: `--color-muted` (`#667085`).
- Texto de cuerpo/menus: `--color-body` (`#344054`).

### Colores De Marca Y Estados

- Primario/brand: `--color-primary` (`#047857`).
- Primario fuerte para botones/iconos: `--color-primary-strong` (`#0f766e`).
- Primario suave para fondos activos: `--color-primary-soft` (`#ecfdf5`).
- Chips verdes: `--color-primary-chip` (`#dff5ee`).
- Bordes verdes: `--color-primary-border` (`#b7e4cf`).
- Acento naranja para perfil detectado: `--color-accent` (`#f97316`).
- Fondo acento: `--color-accent-soft` (`#fff7ed`).
- Borde acento: `--color-accent-border` (`#fed7aa`).
- Informacion azul: `--color-info` (`#2563eb`) y `--color-info-soft` (`#eff6ff`).
- Exito: `--color-success` (`#15803d`) y `--color-success-soft` (`#dcfce7`).
- Error: `--color-danger` (`#b42318`) y `--color-danger-soft` (`#fff1f2`).
- Documento PDF: `--color-document-pdf` (`#ef4444`).

### Radios, Sombras Y Espaciado

- Radio pequeno: `--radius-sm` (`8px`).
- Radio medio: `--radius-md` (`10px`).
- Radio grande de tarjetas/paneles: `--radius-lg` (`14px`).
- Pastillas/chips: `--radius-pill` (`999px`).
- Sombra header: `--shadow-sm`.
- Sombra tarjetas: `--shadow-md`.
- Sombra panel desplegable: `--shadow-lg`.
- Padding horizontal de pagina: `--page-padding`.

### Reglas De Uso

- Botones primarios: fondo con `--color-primary-strong` o gradiente registrado basado en primarios.
- Estados activos de navegacion: `--color-primary` y `--color-primary-soft`.
- Tarjetas: `--color-surface`, `--color-border`, `--radius-lg`, `--shadow-md`.
- Texto informativo: `--color-muted`.
- No introducir paletas nuevas por pantalla; si hace falta un color nuevo, justificarlo y registrarlo aqui.

## Estado

Consultar `docs/estado-actual.md` antes de continuar. El stack Docker queda preparado con frontend en `http://localhost:4200` y backend en `http://localhost:8000`.
