# Estado Actual

Actualizado: 23 de junio de 2026.

## Producto Implementado

- Landing publica con demo real de analisis de CV.
- Aplicacion Angular 20 responsive.
- Registro con respuesta generica, login, logout y restauracion de sesion.
- Sesiones opacas con cookie HttpOnly y hash almacenado en PostgreSQL.
- Usuarios `pending`, `active` y `disabled`.
- Verificacion de correo con token hasheado, validez de 24 horas y un solo uso.
- Reenvio autenticado para usuarios pendientes con cooldown de 60 segundos.
- Recuperacion de contrasena con token hasheado de 60 minutos y correo encolado.
- Cambio autenticado de contrasena conservando solo la sesion actual.
- `EmailService` desacoplado con consola, fake de tests y Brevo API.
- `email_outbox` con payload Fernet, token asociado, intentos y ultimo error.
- Worker separado con recuperacion de filas abandonadas y reintentos escalonados.
- Rate limiting persistente en PostgreSQL para flujos sensibles.
- Limpieza operativa de sesiones, tokens, outbox, buckets y estados abandonados.
- Subida de CV solo PDF con limite de 10 MB.
- Validacion defensiva de PDF: extension, MIME, cabecera, parseo, paginas y texto minimo.
- Consentimiento minimo antes de subir CV.
- Eliminacion de CV propio con borrado de archivo y datos derivados.
- Un unico CV activo por usuario.
- Extraccion, normalizacion y perfil profesional estructurado.
- Deteccion de skills por diccionario, patrones y NER opcional.
- Deteccion de tipo de perfil principal/secundario, experiencia, idiomas y formacion.
- Embeddings de perfil y oferta almacenados en pgvector.
- Busqueda asincrona por perfil en Tecnoempleo e InfoJobs opcional.
- Ranking hibrido 65% skills y 35% similitud semantica.
- Recomendaciones persistidas, explicadas y paginadas.
- Interacciones `viewed`, `saved`, `discarded` y `applied`.
- Pantallas de Dashboard, Mi CV, Explorar ofertas, Mis ofertas, Perfil y Ajustes.
- Docker de desarrollo y produccion separados con tags de imagen diferentes.
- Nginx productivo sirve Angular y proxifica `/api` hacia FastAPI.
- OpenAPI/Swagger disponible en desarrollo y deshabilitado en produccion.
- Runbook de staging en `docs/staging-runbook.md`.

## Seguridad Y Permisos

- Los usuarios pendientes pueden iniciar sesion, consultar su sesion, reenviar el
  correo y cerrar sesion.
- Los usuarios pendientes reciben `403` al acceder a CV, ofertas o feedback.
- El frontend replica esa restriccion mediante `verifiedGuard`.
- Las contrasenas usan Argon2id y mantienen compatibilidad de migracion con bcrypt.
- Los tokens de sesion, verificacion y recuperacion no se almacenan en texto plano.
- El token incluido en un correo pendiente solo existe cifrado en `email_outbox`.
- Los correos se cancelan si su token fue usado, caduco o se invalido por reenvio.
- El reset revoca todas las sesiones y limita solicitudes a cinco por usuario/hora.
- En produccion no se registran enlaces de verificacion ni tokens.
- Tampoco se registran emails, IPs ni payloads descifrados en produccion.
- Las escrituras autenticadas con cookie validan su cabecera `Origin`.
- CORS productivo exige HTTPS, incluye `FRONTEND_URL` y no admite comodines o
  localhost.
- Produccion exige Brevo como proveedor de correo.
- Los CV, backups, secretos, dumps y el directorio `storage/` estan excluidos de Git.

## Datos Y Fuentes

- Diccionario local: 90 skills.
- Taxonomia: 13 categorias tecnicas y 15 aliases canonicos.
- Oferta semilla: 1 registro JSON para pruebas.
- Tecnoempleo: fuente activa por defecto, consultada desde su portal.
- InfoJobs: integracion por API oficial, desactivada si faltan credenciales.
- El feedback se conserva como interacciones, pero aun no entrena modelos.

## Matching

- Version: `hybrid-rules-semantic-v1`.
- Modelo: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Vector: 384 dimensiones.
- Formula: `0.65 * rules_score + 0.35 * semantic_score`.
- Candidatas: hasta 50 ofertas activas de Tecnoempleo/InfoJobs.
- Paginacion: 20 resultados por solicitud.
- Explicacion: skills coincidentes, skills ausentes y desglose del score.

## Calidad Verificada

- 178 pruebas backend superadas.
- 52 pruebas Angular superadas.
- Ruff sin errores.
- `pip check` sin conflictos.
- `npm audit --omit=dev` sin vulnerabilidades de produccion.
- Build Angular correcto.
- Alembic alineado: `alembic check` sin nuevas operaciones.
- Docker Compose de desarrollo y produccion validan correctamente.

## URLs Locales

- Frontend: http://localhost:4200
- Backend: http://localhost:8000
- Swagger/OpenAPI desarrollo: http://localhost:8000/docs
- Healthcheck: http://localhost:8000/api/v1/health

## Estado De Despliegue

El repositorio esta listo para un primer despliegue controlado/staging, no para
apertura amplia a usuarios reales.

Pendientes operativos antes de usuarios reales:

- Dominio o subdominio real.
- HTTPS real validado.
- Brevo con API key real fuera del repositorio.
- SPF, DKIM y DMARC.
- Backups generados y restauracion probada.
- Monitorizacion y alertas.
- Revision legal/RGPD.
- Politica final de retencion y eliminacion completa de cuenta.
