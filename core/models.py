from django.db import models

CICLO_CHOICES = [
    ('I',   'Ciclo I'),
    ('II',  'Ciclo II'),
    ('III', 'Ciclo III'),
    ('IV',  'Ciclo IV'),
]

GRADO_CHOICES = [
    ('T','Transición'),('1','1°'),('2','2°'),('3','3°'),('4','4°'),('5','5°'),
    ('6','6°'),('7','7°'),('8','8°'),('9','9°'),('10','10°'),('11','11°'),('P','Profesores'),
]
GRUPO_CHOICES  = [('A','A'),('B','B'),('C','C')]
GENERO_CHOICES = [('M','Masculino'),('F','Femenino'),('X','Mixto')]

DEPORTE_CHOICES = [
    ('futbol','Fútbol'),
    ('baloncesto','Baloncesto'),
    ('voleibol','Voleibol'),
]
FASE_CHOICES = [
    ('grupos','Fase de Grupos'),
    ('tercer_puesto','Tercer Puesto'),
    ('final','Final'),
]

# Fútbol: masculino Y femenino (dos equipos por grado)
# Baloncesto y Voleibol: mixto (un solo equipo por grado)
DEPORTES_POR_CICLO = {
    'I':   ['futbol'],
    'II':  ['futbol','baloncesto'],
    'III': ['futbol','baloncesto','voleibol'],
    'IV':  ['futbol','baloncesto','voleibol'],
}
# Qué géneros aplican por deporte
GENEROS_POR_DEPORTE = {
    'futbol':     ['M','F'],   # masculino Y femenino
    'baloncesto': ['X'],       # mixto
    'voleibol':   ['X'],       # mixto
}

CICLO_POR_GRADO = {
    'T':'I','1':'I','2':'I',
    '3':'II','4':'II','5':'II',
    '6':'III','7':'III','8':'III',
    '9':'IV','10':'IV','11':'IV','P':'IV',
}

PAIS_LIST = [
    'Argentina','Brasil','Francia','Alemania','España','Italia',
    'Inglaterra','Portugal','Holanda','Bélgica','Croacia','Uruguay',
    'Colombia','México','Japón','Marruecos','Senegal','Ghana',
    'Australia','Corea del Sur','Polonia','Suiza','Dinamarca','Suecia',
    'Estados Unidos','Canadá','Ecuador','Perú','Chile','Paraguay',
    'Camerún','Nigeria','Túnez','Arabia Saudita','Irán','Serbia',
]



# ── PAÍSES PARTICIPANTES (gestionables desde admin) ──────────────────────────
class PaisParticipante(models.Model):
    nombre  = models.CharField(max_length=80, unique=True)
    emoji   = models.CharField(max_length=10, blank=True, default='🌍')
    activo  = models.BooleanField(default=True)
    orden   = models.IntegerField(default=0)

    class Meta:
        ordering = ['orden','nombre']
        verbose_name = 'País Participante'
        verbose_name_plural = 'Países Participantes'

    def __str__(self): return f"{self.emoji} {self.nombre}"

    @classmethod
    def lista_activos(cls):
        qs = cls.objects.filter(activo=True).values_list('nombre', flat=True)
        if qs.exists():
            return list(qs)
        return PAIS_LIST  # fallback si no hay países configurados

def get_ciclo(grado): return CICLO_POR_GRADO.get(grado,'I')


class ImagenCarrusel(models.Model):
    imagen    = models.ImageField(upload_to='carrusel/')
    titulo    = models.CharField(max_length=200, blank=True)
    subtitulo = models.CharField(max_length=300, blank=True)
    orden     = models.IntegerField(default=0)
    activo    = models.BooleanField(default=True)
    class Meta: ordering = ['orden']
    def __str__(self): return self.titulo or f"Imagen {self.pk}"


# ── GRADO: entidad central unificada ─────────────────────────────────────────
class Grado(models.Model):
    """Un grado+grupo académico. Contiene todos sus equipos internamente."""
    grado   = models.CharField(max_length=3, choices=GRADO_CHOICES)
    grupo   = models.CharField(max_length=1, choices=GRUPO_CHOICES)
    pais    = models.CharField(max_length=60, blank=True, null=True)
    bandera = models.ImageField(upload_to='banderas/', blank=True, null=True)

    class Meta:
        unique_together = ('grado','grupo')
        ordering = ['grado','grupo']

    def __str__(self):
        return f"{self.get_grado_display()}{self.grupo}"

    def ciclo(self):     return get_ciclo(self.grado)
    def ciclo_name(self): return dict(CICLO_CHOICES).get(self.ciclo(),'')
    def deportes(self):  return DEPORTES_POR_CICLO.get(self.ciclo(),['futbol'])

    def equipos_disponibles(self):
        """Retorna todos los equipos de este grado."""
        return self.equipos.all()

    def get_equipo(self, deporte, genero):
        return self.equipos.filter(deporte=deporte, genero=genero).first()


# ── EQUIPO: hijo del grado ────────────────────────────────────────────────────
class Equipo(models.Model):
    grado   = models.ForeignKey(Grado, on_delete=models.CASCADE, related_name='equipos')
    deporte = models.CharField(max_length=20, choices=DEPORTE_CHOICES)
    # M/F para fútbol, X para baloncesto/voleibol
    genero  = models.CharField(max_length=1, choices=GENERO_CHOICES, default='X')
    capitan = models.ForeignKey('Jugador', on_delete=models.SET_NULL,
                                null=True, blank=True, related_name='capitan_de')
    imagen  = models.ImageField(upload_to='equipos/', blank=True, null=True)

    class Meta:
        unique_together = ('grado','deporte','genero')

    def __str__(self):
        gen = f" {self.get_genero_display()}" if self.genero != 'X' else " Mixto"
        return f"{self.grado} {self.get_deporte_display()}{gen}"

    def nombre_corto(self):
        gen = f" {'Mas.' if self.genero=='M' else 'Fem.' if self.genero=='F' else ''}"
        return f"{self.grado}{gen}".strip()

    @property
    def pais(self): return self.grado.pais

    def get_ciclo(self): return self.grado.ciclo()


# ── JUGADOR ───────────────────────────────────────────────────────────────────
class Jugador(models.Model):
    ti       = models.CharField(max_length=20, unique=True, verbose_name='T.I.')
    nombre   = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    genero   = models.CharField(max_length=1, choices=[('M','Masculino'),('F','Femenino')], default='M')
    foto     = models.ImageField(upload_to='photos/', blank=True, null=True)
    grado    = models.ForeignKey(Grado, on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name='jugadores')
    activo   = models.BooleanField(default=True)
    creado   = models.DateTimeField(auto_now_add=True)

    class Meta: ordering = ['apellido','nombre']

    def __str__(self): return f"{self.nombre} {self.apellido} ({self.ti})"
    def nombre_completo(self): return f"{self.nombre} {self.apellido}"

    def total_goles(self):
        return EventoPartido.objects.filter(jugador=self, tipo='gol', partido__jugado=True).count()

    def total_asistencias(self):
        # Las asistencias se guardan como EventoPartido de tipo 'gol' con el campo 'asistente'
        return EventoPartido.objects.filter(asistente=self, tipo='gol', partido__jugado=True).count()

    def partidos_jugados(self):
        return EventoPartido.objects.filter(jugador=self, partido__jugado=True).values('partido').distinct().count()


# ── INSCRIPCIÓN ───────────────────────────────────────────────────────────────
class InscripcionJugador(models.Model):
    jugador         = models.ForeignKey(Jugador, on_delete=models.CASCADE, related_name='inscripciones')
    equipo          = models.ForeignKey(Equipo,  on_delete=models.CASCADE, related_name='inscripciones')
    numero_camiseta = models.IntegerField(default=0)

    class Meta: unique_together = ('jugador','equipo')
    def __str__(self): return f"{self.jugador} → {self.equipo}"


# ── GRUPO TORNEO ──────────────────────────────────────────────────────────────
class GrupoTorneo(models.Model):
    nombre  = models.CharField(max_length=1, choices=[('A','Grupo A'),('B','Grupo B')])
    ciclo   = models.CharField(max_length=3, choices=CICLO_CHOICES)
    deporte = models.CharField(max_length=20, choices=DEPORTE_CHOICES)
    genero  = models.CharField(max_length=1, choices=GENERO_CHOICES, default='X')
    equipos = models.ManyToManyField(Equipo, blank=True, related_name='grupos_torneo')
    fase_grupos_terminada = models.BooleanField(default=False)

    class Meta: unique_together = ('nombre','ciclo','deporte','genero')

    def __str__(self):
        gen = dict(GENERO_CHOICES).get(self.genero,'')
        dep = dict(DEPORTE_CHOICES).get(self.deporte,'')
        return f"Grupo {self.nombre} – Ciclo {self.ciclo} {dep} {gen}"


# ── REGLAS ────────────────────────────────────────────────────────────────────
class ReglaDeporte(models.Model):
    deporte     = models.CharField(max_length=20, choices=DEPORTE_CHOICES, unique=True)
    descripcion = models.TextField(blank=True)
    documento   = models.FileField(upload_to='reglas/', blank=True, null=True,
                                   help_text='PDF o Word con el reglamento completo')
    actualizado = models.DateTimeField(auto_now=True)

    def __str__(self): return f"Reglas – {self.get_deporte_display()}"


# ── PARTIDO ───────────────────────────────────────────────────────────────────
class Partido(models.Model):
    equipo_local     = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='partidos_local')
    equipo_visitante = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='partidos_visitante')
    puntos_local     = models.IntegerField(default=0)
    puntos_visitante = models.IntegerField(default=0)
    fecha            = models.DateField()
    hora             = models.TimeField(blank=True, null=True)
    fase             = models.CharField(max_length=20, choices=FASE_CHOICES, default='grupos')
    grupo_torneo     = models.ForeignKey(GrupoTorneo, on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='partidos')
    jugado           = models.BooleanField(default=False)
    deporte          = models.CharField(max_length=20, choices=DEPORTE_CHOICES, default='futbol')
    ciclo            = models.CharField(max_length=3, choices=CICLO_CHOICES, default='I')
    genero           = models.CharField(max_length=1, choices=GENERO_CHOICES, default='X')
    link_facebook    = models.URLField(blank=True, null=True,
                                       help_text='Link al video del partido en Facebook')

    class Meta: ordering = ['fecha','hora']

    def __str__(self):
        return f"{self.equipo_local.nombre_corto()} vs {self.equipo_visitante.nombre_corto()} ({self.fecha})"

    # Para fútbol usamos "goles", para otros deportes "puntos"
    def marcador_local(self):    return self.puntos_local
    def marcador_visitante(self): return self.puntos_visitante
    def label_marcador(self):
        return 'Goles' if self.deporte == 'futbol' else 'Puntos'

    def ganador(self):
        if not self.jugado: return None
        if self.puntos_local > self.puntos_visitante:   return self.equipo_local
        if self.puntos_visitante > self.puntos_local:   return self.equipo_visitante
        return None


# ── EVENTO (solo fútbol) ──────────────────────────────────────────────────────
class EventoPartido(models.Model):
    TIPO_CHOICES = [('gol','Gol'),('amarilla','Tarjeta Amarilla'),('roja','Tarjeta Roja')]
    partido   = models.ForeignKey(Partido, on_delete=models.CASCADE, related_name='eventos')
    equipo    = models.ForeignKey(Equipo,  on_delete=models.CASCADE, related_name='eventos',
                                  null=True, blank=True)
    jugador   = models.ForeignKey(Jugador, on_delete=models.CASCADE, related_name='eventos')
    tipo      = models.CharField(max_length=20, choices=TIPO_CHOICES, default='gol')
    minuto    = models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Minuto')
    asistente = models.ForeignKey(Jugador, on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name='asistencias_dadas')

    def __str__(self): return f"{self.get_tipo_display()} – {self.jugador} ({self.equipo})"


# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
class ConfiguracionSistema(models.Model):
    banner_titulo        = models.CharField(max_length=200, default='COSFA SUPERCAMPEONES')
    banner_subtitulo     = models.CharField(max_length=200, default='Torneo Escolar Intercolegiado')
    mensaje_bienvenida   = models.TextField(blank=True, default='¡Bienvenidos al torneo!')
    mostrar_estadisticas = models.BooleanField(default=True)
    mostrar_tabla        = models.BooleanField(default=True)
    gemini_api_key       = models.CharField(max_length=200, blank=True, default='',
                                            verbose_name='Gemini API Key')
    modo_oscuro          = models.BooleanField(default=False, verbose_name='Modo Oscuro por Defecto')
    paises_sorteo        = models.TextField(blank=True, default='',
                                            verbose_name='Países para Sorteo (uno por línea)')

    def __str__(self): return 'Configuración del Sistema'

    def get_paises_sorteo(self):
        """Returns list of active countries for sorteo."""
        from .models import PaisParticipante
        activos = list(PaisParticipante.objects.filter(activo=True).order_by('orden','nombre').values_list('nombre', flat=True))
        if activos:
            return activos
        if self.paises_sorteo.strip():
            return [p.strip() for p in self.paises_sorteo.splitlines() if p.strip()]
        return []


# ── Set de Voleibol ────────────────────────────────────────────────────────────
class SetVoleibol(models.Model):
    """Resultado de cada set en un partido de voleibol."""
    partido       = models.ForeignKey('Partido', on_delete=models.CASCADE, related_name='sets')
    numero_set    = models.IntegerField()  # 1, 2, 3, 4, 5
    puntos_local  = models.IntegerField(default=0)
    puntos_visita = models.IntegerField(default=0)

    class Meta:
        ordering = ['numero_set']
        unique_together = ('partido', 'numero_set')

    def __str__(self):
        return f"Set {self.numero_set}: {self.puntos_local}-{self.puntos_visita}"

    def ganador(self):
        if self.puntos_local > self.puntos_visita: return 'local'
        if self.puntos_visita > self.puntos_local: return 'visita'
        return 'empate'


# ── Torneo Histórico ───────────────────────────────────────────────────────────
class TorneoHistorico(models.Model):
    """Guarda el resumen de un torneo al cerrarlo."""
    nombre      = models.CharField(max_length=100, default='Torneo')
    año         = models.IntegerField()
    creado      = models.DateTimeField(auto_now_add=True)
    resumen_json= models.TextField(default='{}',
                    help_text='JSON con campeones, goleadores, etc.')

    class Meta: ordering = ['-año', '-creado']
    def __str__(self): return f"{self.nombre} {self.año}"

    def resumen(self):
        import json as _j
        try: return _j.loads(self.resumen_json)
        except: return {}


# ── Vista de partido (para URL de detalle) ────────────────────────────────────
# (No model needed - usamos Partido existente con prefetch de sets y eventos)
