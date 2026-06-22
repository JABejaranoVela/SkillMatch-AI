# Privacidad y datos personales

**Borrador técnico pendiente de revisión legal.**

Este documento describe el tratamiento técnico actual de datos personales en SkillMatch AI. No es una política legal definitiva y debe revisarse antes de una puesta en producción real.

## Datos tratados

SkillMatch AI puede almacenar los siguientes datos cuando un usuario sube un CV:

- Archivo físico del CV en el almacenamiento configurado.
- Metadatos del CV: nombre de archivo, ruta interna, tipo, estado y fechas.
- Texto bruto extraído del CV (`raw_text`).
- Texto normalizado (`clean_text`).
- Perfil profesional detectado.
- Resumen, experiencia, formación, idiomas, tecnologías y análisis técnico.
- Habilidades asociadas al perfil.
- Embeddings/vector semántico del perfil si están habilitados.
- Resultados de compatibilidad entre CV y ofertas.
- Feedback del usuario sobre ofertas: guardada, descartada o postulada.

Las ofertas de empleo, skills globales y datos de importación de ofertas no pertenecen a un CV concreto y pueden ser compartidos por varios usuarios.

## Finalidad

Los datos del CV se usan para:

- Analizar el perfil profesional del usuario.
- Extraer habilidades, formación, idiomas y experiencia.
- Calcular recomendaciones de ofertas compatibles.
- Explicar la compatibilidad entre CV y ofertas.

La base legal, textos informativos finales y consentimiento legal definitivo están pendientes de validación.

## Eliminación de CV implementada

La aplicación permite eliminar un CV propio desde la pantalla de CV.

Al eliminar un CV se elimina de forma explícita:

- Registro `Resume`.
- Archivo físico si existe.
- `raw_text` y `clean_text` al eliminar el registro.
- `ProfessionalProfile`.
- `ProfileSkill` asociado al perfil.
- Embedding del perfil al eliminar `ProfessionalProfile`.
- `MatchResult` asociado al CV.

No se eliminan:

- `Job`, porque las ofertas son globales.
- `JobSkill`, porque pertenece a ofertas globales.
- `Skill`, porque el catálogo de habilidades es global.
- `UserJobInteraction` cuando puede conservarse sin datos derivados del CV.

## Interacciones conservadas

Las interacciones del usuario sobre ofertas se conservan cuando no contienen datos derivados del CV.

Antes de eliminar los resultados de matching del CV, la aplicación desvincula:

- `UserJobInteraction.match_result_id = null`

Se conserva:

- `job_id`.
- Tipo de interacción: guardada, descartada o postulada.
- Fecha de creación.

No se conservan puntuaciones, explicaciones, habilidades coincidentes ni requisitos faltantes asociados al `MatchResult` eliminado.

## Limitaciones actuales

- La eliminación completa de cuenta está pendiente.
- La retención automática de CVs antiguos está pendiente.
- La política de backups y eliminación en copias de seguridad está pendiente.
- El contacto/responsable de privacidad está pendiente de definición.
- `JobSearchTask` no tiene `resume_id`, por lo que no se puede asociar técnicamente una tarea histórica a un CV concreto sin migración. Por ahora no se eliminan tareas de búsqueda al eliminar un CV.
- No existe todavía una política legal completa de RGPD.

## Notas operativas

- Los endpoints no deben exponer rutas internas de archivos.
- Los logs no deben incluir texto bruto del CV, texto normalizado, emails junto al contenido del CV ni datos extraídos sensibles.
- La demo pública de análisis de CV no debe persistir CVs ni perfiles profesionales.
