# Estado del desarrollo

Fecha: 2026-10-05

## Producción actual

- MCP activo: `https://fatsecret.mcp.development.antonberzins.com/mcp`
- Docker con reinicio automático, HTTPS, OAuth 2.1 para ChatGPT y OAuth 1.0 para FatSecret.
- Herramientas desplegadas: consultar diario, buscar alimentos, obtener porciones, añadir, editar y eliminar entradas.

## Problema investigado

Una operación de escritura puede aparecer como correcta en ChatGPT aunque FatSecret devuelva un objeto JSON `error` con HTTP 200. La implementación desplegada valida el estado HTTP, pero las operaciones de crear, editar y eliminar todavía no validan `payload.error` ni releen la entrada creada mediante `food_entry_id`.

FatSecret no documenta servidores de diario seleccionables por `region` o `language`. Esos parámetros localizan y filtran el catálogo; no seleccionan la cuenta ni el diario. OAuth usa un host central y puede haber autorizado otra cuenta que permanecía iniciada en el navegador. La cuenta vinculada tampoco queda identificada por email o username en los tokens guardados.

Próxima corrección prioritaria:

1. Detectar errores FatSecret aunque HTTP sea 200.
2. Exigir `food_entry_id` al crear.
3. Verificar cada creación mediante lectura inmediata por ID y fecha.
4. Exponer perfil y diagnóstico de cuenta vinculada sin mostrar tokens.
5. Permitir `region` y `language` en búsquedas, sin presentarlos como selector de servidor.
6. Facilitar reautorización explícita en ventana privada para vincular la cuenta móvil correcta.

## Trabajo local no desplegado

Se iniciaron módulos nuevos:

- `src/fatsecret_mcp/tools/recipes.py`: búsqueda y detalle de recetas.
- `src/fatsecret_mcp/tools/account.py`: perfil, peso, comidas guardadas y favoritos.

Estos módulos no están registrados todavía en `server.py`, no tienen pruebas completas y no fueron desplegados. Deben conservarse, terminarse y verificarse después de resolver el diagnóstico de identidad/escritura.

## SaaS pendiente

Servidor actual representa una sola cuenta personal. No está preparado para múltiples usuarios ni cobros. Antes de comercializarlo hace falta autorización escrita de FatSecret para el uso MCP, arquitectura multiusuario con tokens aislados, facturación, límites, términos, privacidad y cumplimiento de la retención máxima de 24 horas para datos no declarados como almacenables.
