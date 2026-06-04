from django import forms
from .models import (Grado, Equipo, Jugador, InscripcionJugador, Partido,
                     EventoPartido, GrupoTorneo, ReglaDeporte, ConfiguracionSistema,
                     ImagenCarrusel, DEPORTE_CHOICES, GENERO_CHOICES, CICLO_CHOICES,
                     GRADO_CHOICES, GRUPO_CHOICES, GENEROS_POR_DEPORTE)

W  = {'class':'form-control'}
WS = {'class':'form-select'}
WC = {'class':'form-check-input'}

class GradoForm(forms.ModelForm):
    class Meta:
        model  = Grado
        fields = ['grado','grupo','pais','bandera']
        widgets = {
            'grado':   forms.Select(attrs=WS),
            'grupo':   forms.Select(attrs=WS),
            'pais':    forms.TextInput(attrs=W),
            'bandera': forms.ClearableFileInput(attrs={'class':'form-control'}),
        }

class EquipoForm(forms.ModelForm):
    class Meta:
        model  = Equipo
        fields = ['grado','deporte','genero','capitan','imagen']
        widgets = {
            'grado':   forms.Select(attrs=WS),
            'deporte': forms.Select(attrs=WS),
            'genero':  forms.Select(attrs=WS),
            'capitan': forms.Select(attrs=WS),
            'imagen':  forms.ClearableFileInput(attrs={'class':'form-control'}),
        }

class JugadorForm(forms.ModelForm):
    class Meta:
        model  = Jugador
        fields = ['ti','nombre','apellido','genero','grado','foto']
        widgets = {
            'ti':      forms.TextInput(attrs={**W,'placeholder':'T.I.'}),
            'nombre':  forms.TextInput(attrs={**W,'placeholder':'Nombre'}),
            'apellido':forms.TextInput(attrs={**W,'placeholder':'Apellido'}),
            'genero':  forms.Select(attrs=WS),
            'grado':   forms.Select(attrs=WS),
            'foto':    forms.ClearableFileInput(attrs={'class':'form-control'}),
        }

class InscripcionForm(forms.ModelForm):
    class Meta:
        model  = InscripcionJugador
        fields = ['equipo','numero_camiseta']
        widgets = {
            'equipo':          forms.Select(attrs=WS),
            'numero_camiseta': forms.NumberInput(attrs={**W,'min':0,'max':99}),
        }

class PartidoForm(forms.ModelForm):
    class Meta:
        model  = Partido
        fields = ['equipo_local','equipo_visitante','fecha','hora','fase',
                  'grupo_torneo','deporte','ciclo','genero',
                  'jugado','puntos_local','puntos_visitante','link_facebook']
        widgets = {
            'equipo_local':     forms.Select(attrs=WS),
            'equipo_visitante': forms.Select(attrs=WS),
            'fecha':            forms.DateInput(attrs={**W,'type':'date'}),
            'hora':             forms.TimeInput(attrs={**W,'type':'time'}),
            'fase':             forms.Select(attrs=WS),
            'grupo_torneo':     forms.Select(attrs=WS),
            'deporte':          forms.Select(attrs=WS),
            'ciclo':            forms.Select(attrs=WS),
            'genero':           forms.Select(attrs=WS),
            'jugado':           forms.CheckboxInput(attrs=WC),
            'puntos_local':     forms.NumberInput(attrs={**W,'min':0}),
            'puntos_visitante': forms.NumberInput(attrs={**W,'min':0}),
            'link_facebook':    forms.URLInput(attrs={**W,'placeholder':'https://facebook.com/...'}),
        }

class JugadorConCamisetaChoiceField(forms.ModelChoiceField):
    """ModelChoiceField que muestra 'Nombre Apellido (#N)' usando InscripcionJugador."""
    def __init__(self, *args, equipo=None, **kwargs):
        self._equipo = equipo
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        if self._equipo:
            from .models import InscripcionJugador
            insc = InscripcionJugador.objects.filter(jugador=obj, equipo=self._equipo).first()
            if insc:
                return f"{obj.nombre} {obj.apellido} (#{insc.numero_camiseta})"
        return f"{obj.nombre} {obj.apellido}"


class GolForm(forms.Form):
    equipo_gol = forms.ModelChoiceField(
        queryset=Equipo.objects.none(), widget=forms.Select(attrs=WS),
        label='Equipo que anota')
    goleador   = JugadorConCamisetaChoiceField(
        queryset=Jugador.objects.none(), widget=forms.Select(attrs=WS),
        label='Goleador')
    asistente  = JugadorConCamisetaChoiceField(
        queryset=Jugador.objects.none(), required=False,
        widget=forms.Select(attrs=WS), label='Asistente (opcional)')

    def __init__(self, *args, equipo_local=None, equipo_visitante=None, **kwargs):
        super().__init__(*args, **kwargs)
        equipos = Equipo.objects.none()
        jug_qs  = Jugador.objects.none()
        if equipo_local and equipo_visitante:
            from django.db.models import Q
            equipos = Equipo.objects.filter(pk__in=[equipo_local.pk, equipo_visitante.pk])
            jug_qs  = Jugador.objects.filter(
                inscripciones__equipo__in=[equipo_local, equipo_visitante]
            ).distinct()
        self.fields['equipo_gol'].queryset = equipos
        # Asignamos equipo para que los labels incluyan número de camiseta
        self.fields['goleador'].queryset   = jug_qs
        self.fields['goleador']._equipo    = equipo_local
        self.fields['asistente'].queryset  = jug_qs
        self.fields['asistente']._equipo   = equipo_local

class GrupoTorneoForm(forms.ModelForm):
    class Meta:
        model  = GrupoTorneo
        fields = ['nombre','ciclo','deporte','genero','equipos']
        widgets = {
            'nombre':  forms.Select(attrs=WS),
            'ciclo':   forms.Select(attrs=WS),
            'deporte': forms.Select(attrs=WS),
            'genero':  forms.Select(attrs=WS),
            'equipos': forms.CheckboxSelectMultiple(),
        }

class ReglaDeporteForm(forms.ModelForm):
    class Meta:
        model  = ReglaDeporte
        fields = ['deporte','descripcion','documento']
        widgets = {
            'deporte':     forms.Select(attrs=WS),
            'descripcion': forms.Textarea(attrs={**W,'rows':8}),
            'documento':   forms.ClearableFileInput(attrs={'class':'form-control'}),
        }

class ImagenCarruselForm(forms.ModelForm):
    class Meta:
        model  = ImagenCarrusel
        fields = ['imagen','titulo','subtitulo','orden','activo']
        widgets = {
            'imagen':    forms.ClearableFileInput(attrs={'class':'form-control'}),
            'titulo':    forms.TextInput(attrs=W),
            'subtitulo': forms.TextInput(attrs=W),
            'orden':     forms.NumberInput(attrs=W),
            'activo':    forms.CheckboxInput(attrs=WC),
        }

class BusquedaForm(forms.Form):
    q = forms.CharField(max_length=100, label='', widget=forms.TextInput(attrs={
        'class':'form-control search-input',
        'placeholder':'🔍 Buscar jugador por nombre o T.I...',
        'autocomplete':'off',
    }))

class ConfigForm(forms.ModelForm):
    class Meta:
        model  = ConfiguracionSistema
        fields = ['banner_titulo','banner_subtitulo','mensaje_bienvenida',
                  'mostrar_estadisticas','mostrar_tabla','gemini_api_key',
                  'modo_oscuro','paises_sorteo']
        widgets = {
            'banner_titulo':      forms.TextInput(attrs=W),
            'banner_subtitulo':   forms.TextInput(attrs=W),
            'mensaje_bienvenida': forms.Textarea(attrs={**W,'rows':3}),
            'mostrar_estadisticas': forms.CheckboxInput(attrs=WC),
            'mostrar_tabla':        forms.CheckboxInput(attrs=WC),
            'gemini_api_key':       forms.TextInput(attrs={**W,
                'placeholder':'AIza...','autocomplete':'off'}),
            'modo_oscuro':          forms.CheckboxInput(attrs=WC),
            'paises_sorteo':        forms.Textarea(attrs={**W,'rows':8,
                'placeholder':'Argentina\nBrasil\nFrancia\n...'}),
        }
