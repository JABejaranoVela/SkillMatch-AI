# SkillMatch AI - Guia De Trabajo

## Objetivo

SkillMatch AI es una aplicacion web que transforma un CV en un perfil profesional
estructurado y lo compara con ofertas tecnologicas de Espana. El resultado debe ser
util para la persona candidata y explicable: porcentaje de compatibilidad, skills
coincidentes, skills ausentes y enlace a la oferta original.

## Estado Funcional

El MVP implementa:

- registro, login, logout y restauracion de sesion;
- sesiones opacas almacenadas como hash y cookie HttpOnly;
- verificacion de correo con token de 24 horas y reenvio con cooldown;
- recuperacion de contrasena con token de 60 minutos y respuesta no enumeradora;
- cambio de contrasena con revocacion selectiva de sesiones;
- cola persistente de correo con payload cifrado, worker y proveedor Brevo;
- usuarios `pending`, `active` y `disabled`;
- subida y procesamiento de CV PDF;
- un unico CV activo por usuario;
- deteccion de skills, tipo de perfil, experiencia, idiomas y formacion;
- busqueda de ofertas basada en el perfil;
- importacion desde Tecnoempleo y, con credenciales, InfoJobs;
- ranking hibrido por reglas y embeddings;
- explicacion del score y feedback `saved`, `discarded` y `applied`;
- frontend Angular responsive;
- tests backend y tests Angular de guards.

No estan implementados todavia:

- entrenamiento supervisado con el feedback;
- borrado completo de cuenta y politica completa de retencion;
- despliegue productivo automatizado.

## Stack

- Frontend: Angular 20, TypeScript, SCSS y Lucide.
- Backend: Python 3.12, FastAPI, SQLAlchemy, Alembic y Pydantic.
- Base de datos: PostgreSQL 16 con pgvector.
- CV: PyMuPDF para PDF con validacion defensiva.
- NLP: diccionario local, taxonomia, regex y GLiNER opcional.
- Embeddings: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Seguridad: Argon2id, compatibilidad de migracion bcrypt, sesiones opacas,
  cookies HttpOnly y tokens de cuenta hasheados.
- Infraestructura: Docker Compose y Nginx.

## Estructura

- `backend/`: API, modelos, migraciones y servicios.
- `frontend/`: aplicacion Angular.
- `data/skills/`: diccionario y taxonomia de skills.
- `data/sample_jobs/`: oferta semilla para pruebas/importacion.
- `docs/`: arquitectura, API, modelo de datos, fases y estado.
- `docker/`: PostgreSQL y configuracion Nginx.
- `storage/`: CVs y artefactos locales; nunca se versiona.
- `tests/`: pruebas backend.

## Datos

- El diccionario versionado contiene 90 skills con nombre, categoria y aliases.
- La taxonomia local contiene 13 categorias y aliases canonicos.
- Los CV son aportados por cada usuario y se consideran datos personales.
- Tecnoempleo es la fuente activa por defecto. Se consulta su portal y se conserva
  la URL original.
- InfoJobs usa su API oficial y solo se activa con `INFOJOBS_CLIENT_ID` y
  `INFOJOBS_CLIENT_SECRET`.
- El repositorio no debe contener CV reales, credenciales, bases locales ni logs
  con enlaces de verificacion.

## Reglas De Negocio

- Solo puede existir un CV activo por usuario.
- Las recomendaciones se calculan contra el CV activo y procesado.
- Solo se recomiendan ofertas activas de `tecnoempleo` o `infojobs`.
- El ranking usa como maximo 50 ofertas candidatas y pagina de 20 en 20.
- El algoritmo actual es `hybrid-rules-semantic-v1`.
- Score: 65% coincidencia de skills y 35% similitud semantica.
- Cada resultado persiste usuario, CV, oferta, scores, explicacion y version.
- El feedback no modifica aun el algoritmo; se almacena para trabajo futuro.

## Autenticacion Y Autorizacion

- El registro responde de forma generica para no revelar si un email existe.
- Un usuario nuevo se crea como `pending` y sin `email_verified_at`.
- El token de verificacion se genera aleatoriamente, dura 24 horas, se guarda solo
  como SHA-256 y es de un solo uso.
- El reenvio requiere sesion `pending`, aplica 60 segundos de cooldown e invalida
  tokens anteriores sin usar.
- Registro y reenvio escriben en `email_outbox` y no esperan al proveedor.
- El payload sensible se cifra con Fernet usando
  `EMAIL_PAYLOAD_ENCRYPTION_KEY`; las variables JSON nunca incluyen el token.
- `email-worker` entrega por `ConsoleEmailService` en desarrollo y Brevo API en
  produccion. Los tests usan `FakeEmailService`.
- Los reintentos se programan a 1, 5, 15, 60 y 240 minutos. Las filas `sending`
  abandonadas se recuperan y los correos con tokens usados, caducados o invalidados
  se cancelan.
- En produccion no se registran enlaces completos ni tokens.
- La recuperacion admite cinco solicitudes por usuario y hora. El reset revoca
  todas las sesiones; el cambio autenticado conserva solo la sesion actual.
- Las escrituras que reciben cookie de sesion deben validar `Origin` contra
  `FRONTEND_URL`/CORS. No desactivar este middleware para resolver problemas de
  clientes externos.
- El rate limiting usa `auth_rate_limit_buckets` y claves HMAC-SHA256. No persistir
  identificadores, emails ni IPs en claro.
- Los usuarios `pending` pueden iniciar sesion, consultar la sesion, reenviar la
  verificacion y cerrar sesion.
- CV, ofertas y feedback requieren `status=active` y `email_verified_at`.
- Las contrasenas nuevas usan Argon2id; hashes bcrypt existentes se actualizan al
  iniciar sesion correctamente.

## Rutas Frontend

- Publicas: `/`, `/login`, `/register`, `/verify-email`, `/forgot-password` y
  `/reset-password`.
- Estado de verificacion: `/verify-email-sent`.
- Verificadas: `/dashboard`, `/resumes`, `/cv`, `/jobs`, `/my-jobs`,
  `/saved-jobs`, `/profile` y `/settings`.
- `verifiedGuard` bloquea rutas privadas para usuarios no verificados.
- `pendingGuard` controla la pantalla de correo enviado.

## Sistema Visual

- Los tokens globales viven en `frontend/src/styles.scss`.
- No introducir colores, radios, sombras o fuentes locales si existe un token.
- Fuente base: Inter con fallbacks del sistema.
- Navegacion privada: sidebar en escritorio y panel superpuesto en movil.
- Landing y autenticacion usan layout publico.
- Nombres visibles principales: `Mi CV`, `Explorar ofertas` y `Mis ofertas`.

## Desarrollo

- Mantener cambios acotados al comportamiento solicitado.
- No introducir servicios externos obligatorios sin fallback.
- No versionar `.env`, CVs, logs, caches, builds o bases de datos locales.
- No cambiar `EMAIL_PAYLOAD_ENCRYPTION_KEY` mientras existan correos pendientes.
- Mantener `TRUST_PROXY_HEADERS=false` salvo que un proxy controlado sea el unico
  acceso al backend y sobrescriba `X-Forwarded-For`.
- Crear migraciones Alembic para cualquier cambio de esquema.
- Mantener OpenAPI alineado con la implementacion.
- Anadir tests para autenticacion, permisos, parsing, matching y cambios de rutas.
- No reintroducir JWT/localStorage ni el antiguo router `/matching`.

## Verificacion

```bash
docker compose exec backend pytest -q
docker compose exec backend ruff check app tests
docker compose exec backend python -m app.commands.cleanup --dry-run
cd frontend
npm run test:ci
npm run build
```

## Referencias

- Estado: `docs/estado-actual.md`
- Arquitectura: `docs/arquitectura.md`
- API: `docs/api.md`
- Modelo de datos: `docs/modelo-datos.md`
- Fases: `docs/fases.md`
