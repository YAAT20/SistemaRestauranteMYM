"""
Middleware personalizado para requerir autenticación en todas las rutas
excepto la de login y admin.
"""
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings

class LoginRequiredMiddleware:
    """
    Middleware que redirige a login cualquier request a URLs protegidas
    si el usuario no está autenticado.
    """
    
    # URLs que NO requieren autenticación
    URLS_PERMITIDAS = [
        '/usuarios/login/',
        '/usuarios/logout/',
        '/admin/login/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Verificar si la URL está en la lista de permitidas
        ruta_permitida = any(
            request.path.startswith(url) for url in self.URLS_PERMITIDAS
        )
        
        # Si no está permitida y el usuario no está autenticado, redirigir a login
        if not ruta_permitida and not request.user.is_authenticated:
            return redirect(settings.LOGIN_URL)
        
        response = self.get_response(request)
        return response
