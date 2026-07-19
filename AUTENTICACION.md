# Autenticación y Protección de Rutas

## Cambios Realizados

Se ha implementado un sistema completo de autenticación para proteger todas las rutas del sistema. Los cambios incluyen:

### 1. Middleware de Autenticación
- **Archivo**: `restaurantemym/middleware.py`
- **Función**: Redirige automáticamente cualquier usuario NO autenticado a la página de login
- **Rutas Permitidas sin Autenticación**:
  - `/usuarios/login/` - Página de login
  - `/usuarios/logout/` - Logout
  - `/admin/login/` - Login del admin

### 2. Protección en Vistas
- Todas las vistas de las apps (menu, pedidos, cocina, inventario, caja, administracion, usuarios) usan `LoginRequiredMixin` o `@login_required`
- La función `home()` en `pedidos/views.py` ahora está protegida con `@login_required`

### 3. Configuración de Django
- `LOGIN_URL = '/usuarios/login/'` - URL de redirección para usuarios no autenticados
- `LOGIN_REDIRECT_URL = '/'` - URL a la que redirige después del login (depende del rol del usuario)
- `LOGOUT_REDIRECT_URL = '/usuarios/login/'` - Redirección después de logout

## Comportamiento

1. **Usuario no autenticado accede a cualquier URL**:
   - Es redirigido automáticamente a `/usuarios/login/`
   - No puede acceder a NADA del sistema hasta que inicie sesión

2. **Usuario inicia sesión correctamente**:
   - Es redirigido según su rol:
     - ADMIN → Dashboard de administración (`/administracion/reporte_dashboard/`)
     - MOZO → Lista de platos (`/menu/plato_list/`)
     - Otros → Home (`/`)

3. **Usuario accede a cualquier vista protegida**:
   - Tiene acceso completo a esa vista
   - Si intenta acceder sin estar autenticado, es redirigido a login

## Seguridad Adicional

- El middleware verifica autenticación ANTES de que llegue a la vista
- Combinado con `LoginRequiredMixin` en vistas, proporciona doble protección
- Incluso si se olvida un decorador/mixin en una vista, el middleware la protege

## URLs Permitidas

Para modificar qué URLs NO requieren autenticación, edita la lista `URLS_PERMITIDAS` en `restaurantemym/middleware.py`.

Ejemplo para añadir una nueva URL pública:
```python
URLS_PERMITIDAS = [
    '/usuarios/login/',
    '/usuarios/logout/',
    '/admin/login/',
]
```
