from django.contrib import admin
from .models import (Grado, Equipo, Jugador, InscripcionJugador, Partido,
                     EventoPartido, GrupoTorneo, ReglaDeporte,
                     ConfiguracionSistema, ImagenCarrusel)
admin.site.register(Grado)
admin.site.register(Equipo)
admin.site.register(Jugador)
admin.site.register(InscripcionJugador)
admin.site.register(Partido)
admin.site.register(EventoPartido)
admin.site.register(GrupoTorneo)
admin.site.register(ReglaDeporte)
admin.site.register(ConfiguracionSistema)
admin.site.register(ImagenCarrusel)
from .models import SetVoleibol
admin.site.register(SetVoleibol)
from .models import TorneoHistorico
admin.site.register(TorneoHistorico)
