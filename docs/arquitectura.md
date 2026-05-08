# Arquitectura

## Vision General

SkillMatch AI se organiza como una aplicacion web separada en frontend, backend y base de datos.

- Angular consume una API REST.
- FastAPI concentra la logica de negocio, IA, matching y persistencia.
- PostgreSQL guarda usuarios, CVs, perfiles, ofertas, resultados y feedback.
- pgvector permite similitud semantica entre perfiles y ofertas.

## Componentes

### Frontend

Responsable de la experiencia de usuario:
- autenticacion;
- subida de CV;
- visualizacion del perfil extraido;
- ranking de ofertas;
- explicacion de compatibilidad;
- feedback.

### Backend

Responsable de:
- seguridad y sesiones;
- validacion de archivos;
- extraccion de texto;
- normalizacion NLP;
- gestion de ofertas;
- calculo de matching;
- persistencia de feedback.

### Base De Datos

PostgreSQL sera la fuente de verdad. Los documentos se almacenaran inicialmente en filesystem y la base guardara metadatos y rutas internas.

### IA Y Matching

El MVP usara un enfoque hibrido:
- reglas ponderadas para skills, experiencia, formacion e idiomas;
- embeddings para similitud semantica con `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`;
- explicaciones derivadas de coincidencias y penalizaciones.

El porcentaje mostrado al usuario se calcula como:

```text
score final = 65% score por skills detectadas + 35% score semantico por embeddings
```

Los embeddings se guardan en las columnas vectoriales de `professional_profiles.embedding` y `jobs.embedding`.
