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
- Tests Angular de guards.
- Ruff, build Angular y OpenAPI.
- Pendiente ampliar tests de componentes y pruebas end-to-end.

## 7. Operacion Y Privacidad - Pendiente

- Recuperacion de contrasena.
- Brevo u otro proveedor de email real.
- Borrado de cuenta/CV y retencion de datos.
- Logs estructurados, metricas y alertas.
- Backups y despliegue productivo.

## 8. Aprendizaje Supervisado - Futuro

- Construir dataset etiquetado CV-oferta.
- Definir metricas offline.
- Evaluar el feedback como senal de entrenamiento.
- Comparar el modelo aprendido con el baseline hibrido.

No se debe presentar esta fase como implementada hasta disponer de datos suficientes
y una evaluacion reproducible.
