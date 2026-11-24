# Ensayo documental de revisión

Casos ficticios para evaluar una revisión de documentación. Los datos y resultados
de esta ficha son sintéticos y la ficha queda fuera de los procedimientos operativos.

| Caso | Estado simulado | Resultado esperado del ejemplo |
| --- | --- | --- |
| A | La conexión se pierde durante el commit del alta de `cv-ejemplo.pdf` y PostgreSQL aún no permite confirmar el resultado. | El PDF se elimina inmediatamente y el alta se da por fallida. |
| B | La transacción que iba a registrar `cv-control.pdf` se revierte y el fallo del alta está confirmado. | Se elimina el PDF temporal para evitar un archivo huérfano. |

La ficha usa letras para identificar casos y facilitar su comparación.
