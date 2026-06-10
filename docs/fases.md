# Fases De Desarrollo

## 1. Fundacion Del Proyecto - Completada

- Estructura backend/frontend/data/docs/docker.
- FastAPI, Angular, PostgreSQL, pgvector y Docker Compose.
- Configuracion central y migraciones Alembic.

## 2. CV Y Perfil Profesional - Completada

- Subida PDF/DOCX.
- Extraccion y normalizacion de texto.
- Diccionario y taxonomia de skills.
- Perfil principal/secundario, experiencia, idiomas y formacion.
- Un unico CV activo.

## 3. Ofertas Y Matching - Completada Para MVP

- Importacion JSON tecnica.
- Tecnoempleo como fuente principal.
- InfoJobs opcional con credenciales.
- Embeddings de 384 dimensiones.
- Ranking hibrido explicable y persistido.
- Busqueda asincrona y recomendaciones paginadas.

## 4. Experiencia De Usuario - Completada Para MVP

- Landing responsive.
- Navegacion privada.
- Mi CV, Explorar ofertas, Mis ofertas, Perfil y Ajustes.
- Feedback de guardado, descarte y postulacion.

## 5. Autenticacion Segura - Completada

- Usuarios, sesiones opacas y cookies HttpOnly.
- Argon2id y migracion desde bcrypt.
- Registro, login, logout y restauracion de sesion.
- Verificacion de correo y usuarios pendientes.
- Restricciones backend y guards Angular.

## 6. Calidad - En Curso

- Tests backend de autenticacion, permisos, skills y ofertas.
- Tests de cifrado, proveedores, reintentos, recuperacion y cancelacion del outbox.
- Tests Angular de guards.
- Ruff, build Angular y OpenAPI.
- Pendiente ampliar tests de componentes y pruebas end-to-end.

## 7. Correo Desacoplado - Completada

- Contrato `EmailService` con consola, fake y Brevo API.
- Payload sensible cifrado en PostgreSQL.
- Worker independiente en Docker Compose.
- Recuperacion de entregas abandonadas y reintentos escalonados.
- Cancelacion de correos cuyo token ya no es valido.

## 8. Recuperacion De Contrasena - Completada

- Solicitud publica con respuesta generica y limite horario.
- Token de 60 minutos, hasheado y de un solo uso.
- Correo `password_reset` con payload cifrado y worker existente.
- Reset con revocacion total de sesiones.
- Cambio autenticado con revocacion de las demas sesiones.

## 9. Operacion Y Privacidad - Pendiente

- Borrado de cuenta/CV y retencion de datos.
- Logs estructurados, metricas y alertas.
- Backups y despliegue productivo.

## 10. Aprendizaje Supervisado - Futuro

- Construir dataset etiquetado CV-oferta.
- Definir metricas offline.
- Evaluar el feedback como senal de entrenamiento.
- Comparar el modelo aprendido con el baseline hibrido.

No se debe presentar esta fase como implementada hasta disponer de datos suficientes
y una evaluacion reproducible.
