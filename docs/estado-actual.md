# Estado Actual

Actualizado: 11 de junio de 2026.

## Producto Implementado

- Landing publica y aplicacion Angular responsive.
- Registro con respuesta generica, login, logout y restauracion de sesion.
- Sesiones opacas con cookie HttpOnly y hash almacenado en PostgreSQL.
- Usuarios `pending`, `active` y `disabled`.
- Verificacion de correo con token hasheado, validez de 24 horas y un solo uso.
- Reenvio autenticado para usuarios pendientes con cooldown de 60 segundos.
- `EmailService` desacoplado con consola, fake de tests y Brevo API.
- `email_outbox` con payload Fernet, token asociado, intentos y ultimo error.
- Worker separado con recuperacion de filas abandonadas y reintentos escalonados.
- Recuperacion de contrasena con token hasheado de 60 minutos y correo encolado.
- Cambio autenticado de contrasena conservando solo la sesion actual.
- Subida de CV PDF/DOCX con limite de 10 MB.
- Un unico CV activo por usuario.
- Extraccion, normalizacion y perfil profesional estructurado.
- Deteccion de skills por diccionario, patrones y NER opcional.
- Deteccion de tipo de perfil principal/secundario, experiencia, idiomas y formacion.
- Embeddings de perfil y oferta almacenados en pgvector.
- Busqueda asincrona por perfil en Tecnoempleo e InfoJobs opcional.
- Ranking hibrido 65% skills y 35% similitud semantica.
- Recomendaciones persistidas, explicadas y paginadas.
- Interacciones `viewed`, `saved`, `discarded` y `applied`.
- Pantallas de Mi CV, Explorar ofertas, Mis ofertas, Perfil y Ajustes.

## Seguridad Y Permisos

- Los usuarios pendientes pueden iniciar sesion, consultar su sesion, reenviar el
  correo y cerrar sesion.
- Los usuarios pendientes reciben `403` al acceder a CV, ofertas o feedback.
- El frontend replica esa restriccion mediante `verifiedGuard`.
- Las contrasenas usan Argon2id y mantienen compatibilidad de migracion con bcrypt.
- Los tokens de sesion y verificacion no se almacenan en texto plano.
- El token incluido en un correo pendiente solo existe cifrado en `email_outbox`.
- Los correos se cancelan si su token fue usado, caduco o se invalido por reenvio.
- El reset revoca todas las sesiones y limita solicitudes a cinco por usuario/hora.
- En produccion no se registran enlaces de verificacion ni tokens.
- Los CV y el directorio `storage/` estan excluidos de Git.

## Datos Y Fuentes

- Diccionario local: 90 skills.
- Taxonomia: 13 categorias tecnicas y 15 aliases canonicos.
- Oferta semilla: 1 registro JSON para pruebas.
- Tecnoempleo: fuente activa por defecto, consultada desde su portal.
- InfoJobs: integracion por API oficial, desactivada si faltan credenciales.
- Las integraciones legacy fuera del mercado objetivo se retiraron del flujo actual.

## Matching

- Version: `hybrid-rules-semantic-v1`.
- Modelo: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- Vector: 384 dimensiones.
- Formula: `0.65 * rules_score + 0.35 * semantic_score`.
- Candidatas: hasta 50 ofertas activas de Tecnoempleo/InfoJobs.
- Paginacion: 20 resultados por solicitud.
- Explicacion: skills coincidentes, skills ausentes y desglose del score.

## Calidad Verificada

- 92 pruebas backend superadas.
- 11 pruebas Angular superadas.
- Ruff sin errores.
- Build Angular correcto.
- Migracion Alembic actual: `20260611_0009`.
- OpenAPI expone los endpoints de autenticacion y verificacion actuales.

## URLs Locales

- Frontend: http://localhost:4200
- Backend: http://localhost:8000
- Swagger/OpenAPI: http://localhost:8000/docs
- Healthcheck: http://localhost:8000/api/v1/health

## Pendiente

- Politica de borrado y retencion de datos personales.
- Eliminacion de cuenta y CV desde la interfaz.
- Evaluacion cuantitativa con pares CV-oferta etiquetados.
- Uso supervisado del feedback.
- Pipeline de despliegue productivo y observabilidad.
