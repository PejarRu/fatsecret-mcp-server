# Plan de nuevas funciones FatSecret MCP

Fecha: 2026-10-05

## Objetivo

Ampliar MCP actual para consultar historial y estadísticas, recetas, perfil, peso, favoritos y comidas guardadas. Mantener acceso a cuenta personal existente, catálogo `ES/es`, confirmación antes de escrituras y verificación posterior de cualquier cambio.

## Estado actual

Producción ya permite:

- Consultar diario por rango de fechas.
- Buscar alimentos.
- Consultar porciones.
- Añadir, editar y eliminar entradas.
- Validar `food_id` y `serving_id` antes de escribir.
- Verificar cambios y revertir automáticamente creaciones inconsistentes.

Código local iniciado pero aún no registrado ni desplegado:

- `src/fatsecret_mcp/tools/account.py`
- `src/fatsecret_mcp/tools/recipes.py`

## Herramientas propuestas

### Perfil

#### `get_user_profile`

Devuelve únicamente datos disponibles mediante `GET /rest/profile/v1`:

- Unidad de peso.
- Unidad de altura.
- Altura.
- Último peso y fecha.
- Peso objetivo.

No mostrar tokens, email ni datos que FatSecret no proporcione.

#### `check_fatsecret_connection`

Comprueba mediante una llamada real que token sigue válido. Devuelve estado, región/idioma configurados y resumen no sensible del perfil.

### Peso

#### `get_weight_history`

Consulta `GET /rest/weight/month/v2` para uno o varios meses. Convierte `date_int` a `YYYY-MM-DD`, ordena fechas y calcula opcionalmente:

- Peso inicial y final.
- Cambio absoluto.
- Media.
- Mínimo y máximo.

No inventar días sin medición.

### Recetas

#### `search_recipes`

Usa `GET /rest/recipes/search/v3`. Soporta:

- Texto.
- Tipo de receta.
- Imágenes obligatorias.
- Calorías y distribución de macros.
- Tiempo de preparación.
- Paginación.

Valores por defecto: `region=ES`, `language=es` cuando endpoint/edición lo permita.

#### `get_recipe`

Usa `GET /rest/recipe/v2`. Devuelve ingredientes, instrucciones, tiempos, porciones y nutrición.

#### `get_favorite_recipes`

Usa `GET /rest/recipe/favorites/v2`.

#### `set_recipe_favorite`

Añade o elimina favorito mediante `POST/DELETE /rest/recipe/favorites/v1`. Requiere confirmación del usuario y comprobación posterior.

### Alimentos favoritos

#### `get_favorite_foods`

Usa `GET /rest/food/favorites/v2`.

#### `set_food_favorite`

Añade o elimina favorito mediante `POST/DELETE /rest/food/favorite/v1`. Puede conservar `serving_id` y `number_of_units`. Validar alimento y porción antes de escribir y verificar después.

### Comidas guardadas

#### `get_saved_meals`

Usa `GET /rest/saved-meals/v2`. Permite filtrar por `breakfast`, `lunch`, `dinner` u `other`.

#### `get_saved_meal_items`

Usa `GET /rest/saved-meals/item/v2` con `saved_meal_id`.

#### `add_saved_meal_to_diary`

Herramienta compuesta:

1. Consulta elementos de comida guardada.
2. Muestra resumen y solicita confirmación.
3. Valida cada alimento y porción.
4. Añade elementos uno a uno.
5. Verifica cada entrada.
6. Si alguna falla, revierte entradas creadas durante esa operación.

### Historial y estadísticas

#### `get_food_history_stats`

Obtiene diario en rango limitado y calcula localmente:

- Alimentos más repetidos.
- Número de veces y días distintos.
- Porciones habituales.
- Distribución por comida.
- Calorías y macros acumulados/medios.
- Primer y último consumo.

Debe agrupar preferentemente por `food_id`; nombre solo como etiqueta. Rango por defecto: últimos 30 días. Límite recomendado: 93 días por llamada.

#### `get_daily_nutrition_summary`

Resume calorías, proteínas, carbohidratos, grasas, fibra y otros nutrientes disponibles para una fecha.

#### `get_monthly_nutrition_summary`

Usa `GET /rest/food-entries/month/v2` para calorías y macros diarios del mes. Puede comparar meses sin descargar cada entrada individual.

### Ejercicio

#### `get_monthly_exercise_summary`

Usa `GET /rest/exercise-entries/month/v2` para calorías de actividad por día. Lectura opcional posterior a funciones prioritarias.

## Seguridad y consistencia

- Nunca exponer credenciales ni tokens en respuestas MCP o logs.
- Mantener `ES/es` como localización predeterminada, configurable por usuario.
- `region/language` localizan catálogo; no deben describirse como servidor de cuenta.
- Detectar `payload.error` aunque HTTP sea 200.
- Normalizar objeto único y lista.
- Confirmar explícitamente altas, cambios y eliminaciones.
- Validar IDs antes de escribir.
- Releer y verificar después de escribir.
- Revertir operaciones compuestas incompletas.
- Evitar almacenamiento permanente de contenido API no permitido; respetar límite de caché de 24 horas.
- IDs y tokens solo se conservan cuando términos FatSecret lo permiten.

## Pruebas necesarias

1. Pruebas unitarias de normalización, fechas y estadísticas.
2. Respuestas simuladas con objeto único, listas vacías y `error` HTTP 200.
3. Validación de región/idioma.
4. Lecturas reales: perfil, peso, recetas, favoritos y comidas guardadas.
5. Escrituras reales solo con confirmación y datos de prueba reversibles.
6. Verificar desde API, web y móvil.
7. Confirmar lista de herramientas mediante flujo OAuth MCP completo.
8. Ejecutar compilación, lint y typecheck disponibles antes de desplegar.

## Orden recomendado

1. Perfil y estado de conexión.
2. Historial de peso.
3. Historial y estadísticas de alimentos.
4. Recetas.
5. Lectura de favoritos y comidas guardadas.
6. Escritura de favoritos.
7. Añadir comida guardada al diario con rollback.
8. Resúmenes mensuales y ejercicio.

## Fuera de alcance inmediato

- Multiusuario y facturación SaaS.
- Recomendaciones médicas.
- Datos no expuestos por FatSecret, como hora exacta de entrada.
- Exportación o conservación permanente incompatible con términos de FatSecret.
- Tratar MCP como proxy genérico para descargar base de datos FatSecret.
