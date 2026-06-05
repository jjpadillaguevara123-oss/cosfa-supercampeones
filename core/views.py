import random, json
from itertools import combinations
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.utils import timezone

from .models import (Grado, Equipo, Jugador, InscripcionJugador, Partido, EventoPartido,
                     SetVoleibol, GrupoTorneo, ReglaDeporte, ConfiguracionSistema,
                     ImagenCarrusel, TorneoHistorico, PaisParticipante,
                     PAIS_LIST, CICLO_CHOICES, DEPORTE_CHOICES, GENERO_CHOICES,
                     DEPORTES_POR_CICLO, GENEROS_POR_DEPORTE, CICLO_POR_GRADO, get_ciclo)
from .forms import (GradoForm, EquipoForm, JugadorForm, InscripcionForm, PartidoForm,
                    GolForm, ReglaDeporteForm, ImagenCarruselForm, BusquedaForm, ConfigForm)

def is_admin(u): return u.is_authenticated and u.is_staff

def get_config():
    cfg, _ = ConfiguracionSistema.objects.get_or_create(pk=1)
    return cfg

# ── Helpers ───────────────────────────────────────────────────────────────────
def _tabla_grupo(gt):
    pos = []
    for eq in gt.equipos.all():
        qs = Partido.objects.filter(
            Q(equipo_local=eq)|Q(equipo_visitante=eq),
            grupo_torneo=gt, jugado=True)
        pj=pg=pe=pp=gf=gc=0
        for p in qs:
            pj += 1
            if p.equipo_local == eq:
                gf += p.puntos_local; gc += p.puntos_visitante
                if p.puntos_local > p.puntos_visitante: pg += 1
                elif p.puntos_local == p.puntos_visitante: pe += 1
                else: pp += 1
            else:
                gf += p.puntos_visitante; gc += p.puntos_local
                if p.puntos_visitante > p.puntos_local: pg += 1
                elif p.puntos_visitante == p.puntos_local: pe += 1
                else: pp += 1
        pts = pg*3+pe
        pos.append({'equipo':eq,'pj':pj,'pg':pg,'pe':pe,'pp':pp,
                    'gf':gf,'gc':gc,'dg':gf-gc,'pts':pts})
    pos.sort(key=lambda x:(-x['pts'],-x['dg'],-x['gf']))
    return pos

def _tabla_completa(ciclo, deporte, genero):
    """Tabla incluyendo fase de grupos Y partidos finales."""
    gts = GrupoTorneo.objects.filter(ciclo=ciclo,deporte=deporte,genero=genero)
    tablas = [{'grupo':gt,'posiciones':_tabla_grupo(gt)} for gt in gts]
    finales = Partido.objects.filter(
        ciclo=ciclo,deporte=deporte,genero=genero,
        fase__in=['final','tercer_puesto']
    ).select_related('equipo_local__grado','equipo_visitante__grado').prefetch_related('sets')
    # Determinar podio si hay final jugada
    podio = None
    final = finales.filter(fase='final', jugado=True).first()
    tercero = finales.filter(fase='tercer_puesto', jugado=True).first()
    if final:
        campe = final.ganador()
        subcampe = final.equipo_visitante if campe == final.equipo_local else final.equipo_local
        bronze = tercero.ganador() if tercero else None
        podio = {'primero': campe, 'segundo': subcampe, 'tercero': bronze}
    return tablas, finales, podio

def _top_goles(deporte=None, ciclo=None, genero=None, limit=10):
    qs = EventoPartido.objects.filter(tipo='gol', partido__jugado=True)
    if deporte: qs = qs.filter(partido__deporte=deporte)
    if ciclo:   qs = qs.filter(partido__ciclo=ciclo)
    if genero and genero!='X': qs = qs.filter(partido__genero=genero)
    return (qs.values('jugador__id','jugador__nombre','jugador__apellido',
                      'jugador__grado__pais','jugador__grado__bandera','jugador__foto')
              .annotate(total=Count('id')).order_by('-total')[:limit])

def _top_asist(deporte=None, ciclo=None, genero=None, limit=10):
    qs = EventoPartido.objects.filter(tipo='gol', asistente__isnull=False, partido__jugado=True)
    if deporte: qs = qs.filter(partido__deporte=deporte)
    if ciclo:   qs = qs.filter(partido__ciclo=ciclo)
    if genero and genero!='X': qs = qs.filter(partido__genero=genero)
    return (qs.values('asistente__id','asistente__nombre','asistente__apellido',
                      'asistente__grado__pais','asistente__grado__bandera','asistente__foto')
              .annotate(total=Count('id')).order_by('-total')[:limit])

def _stats_colectivos(deporte, ciclo=None, genero=None):
    qs = Partido.objects.filter(jugado=True, deporte=deporte)
    if ciclo:  qs = qs.filter(ciclo=ciclo)
    if genero and genero!='X': qs = qs.filter(genero=genero)
    stats = {}
    for p in qs.select_related('equipo_local__grado','equipo_visitante__grado'):
        for eq, pf, pc in [(p.equipo_local,p.puntos_local,p.puntos_visitante),
                           (p.equipo_visitante,p.puntos_visitante,p.puntos_local)]:
            if eq.pk not in stats:
                stats[eq.pk] = {'equipo':eq,'pj':0,'pg':0,'pp':0,'pf':0,'pc':0}
            s = stats[eq.pk]
            s['pj']+=1; s['pf']+=pf; s['pc']+=pc
            if pf>pc: s['pg']+=1
            else: s['pp']+=1
    return sorted(stats.values(), key=lambda x:(-x['pg'],-(x['pf']-x['pc']),-x['pf']))

# ── AUTH ──────────────────────────────────────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        return redirect('admin_dashboard' if request.user.is_staff else 'home')
    error = None
    if request.method == 'POST':
        u = authenticate(request, username=request.POST.get('username'),
                         password=request.POST.get('password'))
        if u:
            login(request, u)
            return redirect('admin_dashboard' if u.is_staff else 'home')
        error = 'Usuario o contraseña incorrectos'
    return render(request,'core/login.html',{'error':error,'config':get_config()})

def logout_view(request):
    logout(request); return redirect('home')

# ── HOME ──────────────────────────────────────────────────────────────────────
def home(request):
    # Admin va al dashboard EXCEPTO si viene con ?user_view=1
    if request.user.is_staff and not request.GET.get('user_view'):
        return redirect('admin_dashboard')
    cfg = get_config()
    # Últimos partidos jugados (con fecha puesta por admin)
    partidos_recientes = Partido.objects.filter(jugado=True).select_related(
        'equipo_local__grado','equipo_visitante__grado'
    ).prefetch_related('sets','eventos__jugador','eventos__equipo'
    ).order_by('-fecha','-pk')[:10]
    imagenes = ImagenCarrusel.objects.filter(activo=True)
    grados   = Grado.objects.all().order_by('grado','grupo')
    ctx = {
        'cfg':cfg,'partidos_recientes':partidos_recientes,
        'imagenes':imagenes,'grados':grados,'ciclos':CICLO_CHOICES,
        'top_goles': _top_goles(deporte='futbol', limit=5),
        'top_asist': _top_asist(deporte='futbol', limit=5),
        'top_goles_ciclos': {c: _top_goles(deporte='futbol', ciclo=c, limit=5) for c,n in CICLO_CHOICES},
        'top_asist_ciclos': {c: _top_asist(deporte='futbol', ciclo=c, limit=5) for c,n in CICLO_CHOICES},
        'stats_basket': _stats_colectivos('baloncesto')[:5],
        'stats_voley':  _stats_colectivos('voleibol')[:5],
        'stats_basket_ciclos': {c: _stats_colectivos('baloncesto', ciclo=c)[:5] for c,n in CICLO_CHOICES},
        'stats_voley_ciclos':  {c: _stats_colectivos('voleibol',  ciclo=c)[:5] for c,n in CICLO_CHOICES},
        'deportes': DEPORTE_CHOICES,
        'historial': TorneoHistorico.objects.all()[:3],
    }
    return render(request,'core/home.html',ctx)

# ── DETALLE PARTIDO (usuario) ─────────────────────────────────────────────────
def partido_detalle(request, pk):
    p = get_object_or_404(Partido, pk=pk)
    eventos_local = EventoPartido.objects.filter(
        partido=p, equipo=p.equipo_local).select_related('jugador','asistente')
    eventos_visita = EventoPartido.objects.filter(
        partido=p, equipo=p.equipo_visitante).select_related('jugador','asistente')
    sets = SetVoleibol.objects.filter(partido=p)
    _, finales, podio = _tabla_completa(p.ciclo, p.deporte, p.genero)
    return render(request,'core/partido_detalle.html',{
        'p':p,'eventos_local':eventos_local,'eventos_visita':eventos_visita,
        'sets':sets,'cfg':get_config(),'podio':podio,
    })

# ── VISTA GRADO ───────────────────────────────────────────────────────────────
def vista_grado(request, pk):
    grado = get_object_or_404(Grado, pk=pk)
    cfg   = get_config()
    equipos_data = []
    for dep in grado.deportes():
        generos = GENEROS_POR_DEPORTE.get(dep,['X'])
        for gen in generos:
            eq = Equipo.objects.filter(grado=grado,deporte=dep,genero=gen).first()
            if not eq: continue
            inscs = InscripcionJugador.objects.filter(equipo=eq).select_related('jugador')
            # Tabla con TODOS los partidos (grupos + finales)
            pj=pg=pe=pp=gf=gc=0
            all_partidos = Partido.objects.filter(
                Q(equipo_local=eq)|Q(equipo_visitante=eq), jugado=True
            )
            for p in all_partidos:
                pj+=1
                if p.equipo_local==eq:
                    gf+=p.puntos_local; gc+=p.puntos_visitante
                    if p.puntos_local>p.puntos_visitante: pg+=1
                    elif p.puntos_local==p.puntos_visitante: pe+=1
                    else: pp+=1
                else:
                    gf+=p.puntos_visitante; gc+=p.puntos_local
                    if p.puntos_visitante>p.puntos_local: pg+=1
                    elif p.puntos_visitante==p.puntos_local: pe+=1
                    else: pp+=1
            tabla_pos = {'pj':pj,'pg':pg,'pe':pe,'pp':pp,
                         'gf':gf,'gc':gc,'dg':gf-gc,'pts':pg*3+pe}
            partidos_eq = Partido.objects.filter(
                Q(equipo_local=eq)|Q(equipo_visitante=eq)
            ).select_related('equipo_local__grado','equipo_visitante__grado'
            ).prefetch_related('sets').order_by('-fecha')[:6]
            equipos_data.append({
                'equipo':eq,'deporte':dep,'genero':gen,
                'genero_label':'Mixto' if gen=='X' else dict(GENERO_CHOICES).get(gen,''),
                'deporte_label':dict(DEPORTE_CHOICES).get(dep,''),
                'inscs':inscs,'tabla_pos':tabla_pos,'partidos':partidos_eq,
            })
    return render(request,'core/vista_grado.html',
                  {'cfg':cfg,'grado':grado,'equipos_data':equipos_data})

# ── PARTIDOS USUARIO ──────────────────────────────────────────────────────────
def partidos_view(request):
    cfg     = get_config()
    ciclo   = request.GET.get('ciclo','I')
    deporte = request.GET.get('deporte','futbol')
    genero  = request.GET.get('genero','M')
    partidos = Partido.objects.filter(
        ciclo=ciclo,deporte=deporte,genero=genero
    ).select_related('equipo_local__grado','equipo_visitante__grado'
    ).prefetch_related('sets').order_by('-fecha','-pk')
    ctx = {'cfg':cfg,'partidos':partidos,
           'ciclo_sel':ciclo,'deporte_sel':deporte,'genero_sel':genero,
           'ciclos':CICLO_CHOICES,'deportes':DEPORTE_CHOICES,'generos':GENERO_CHOICES}
    return render(request,'core/partidos_view.html',ctx)

# ── BUSCAR ────────────────────────────────────────────────────────────────────
def buscar_jugadores(request):
    cfg=get_config(); form=BusquedaForm(request.GET or None)
    resultados=[]; query=''
    if form.is_valid():
        query=form.cleaned_data['q']
        resultados=Jugador.objects.filter(
            Q(nombre__icontains=query)|Q(apellido__icontains=query)|Q(ti__icontains=query)
        ).select_related('grado')
    return render(request,'core/buscar.html',
                  {'form':form,'resultados':resultados,'query':query,'cfg':cfg})

# ── PERFIL JUGADOR ────────────────────────────────────────────────────────────
def perfil_jugador(request, pk):
    jugador = get_object_or_404(Jugador, pk=pk)
    inscs   = InscripcionJugador.objects.filter(jugador=jugador).select_related('equipo__grado')
    # Goles
    eventos_gol = EventoPartido.objects.filter(
        jugador=jugador, tipo='gol'
    ).select_related('partido','equipo__grado','asistente').order_by('-partido__fecha')
    # Asistencias dadas
    eventos_asist = EventoPartido.objects.filter(
        asistente=jugador, tipo='gol'
    ).select_related('partido','jugador','equipo__grado').order_by('-partido__fecha')
    # Stats reales contadas desde BD (solo jugado=True)
    total_goles     = eventos_gol.filter(partido__jugado=True).count()
    total_asist     = eventos_asist.filter(partido__jugado=True).count()
    total_amarillas = EventoPartido.objects.filter(jugador=jugador, tipo='amarilla', partido__jugado=True).count()
    total_rojas     = EventoPartido.objects.filter(jugador=jugador, tipo='roja',     partido__jugado=True).count()
    total_pj        = Partido.objects.filter(
        jugado=True
    ).filter(
        Q(equipo_local__inscripciones__jugador=jugador) |
        Q(equipo_visitante__inscripciones__jugador=jugador)
    ).distinct().count()

    return render(request,'core/perfil_jugador.html',{
        'jugador':jugador,'inscs':inscs,
        'eventos_gol':eventos_gol,'eventos_asist':eventos_asist,
        'total_goles':total_goles,'total_asist':total_asist,
        'total_pj':total_pj,
        'total_amarillas':total_amarillas,'total_rojas':total_rojas,
        'cfg':get_config(),
    })

# ── ESTADÍSTICAS ──────────────────────────────────────────────────────────────
def estadisticas(request):
    cfg     = get_config()
    dep     = request.GET.get('deporte','futbol')
    ciclo   = request.GET.get('ciclo','')
    genero  = request.GET.get('genero','')
    if dep == 'futbol':
        ctx_extra = {
            'top_goles': _top_goles('futbol', ciclo or None, genero or None),
            'top_asist': _top_asist('futbol', ciclo or None, genero or None),
        }
    else:
        sc = _stats_colectivos(dep, ciclo or None, genero or None)
        ctx_extra = {
            'stats_col': sc,
            'mas_ofensivo':  max(sc, key=lambda x: x['pf']) if sc else None,
            'mas_defensivo': min(sc, key=lambda x: x['pc']) if sc else None,
        }
    total_p = Partido.objects.filter(jugado=True, deporte=dep)
    if ciclo: total_p = total_p.filter(ciclo=ciclo)
    if genero and genero!='X': total_p = total_p.filter(genero=genero)
    ctx = {
        'cfg':cfg,'deporte_sel':dep,'ciclo_sel':ciclo,'genero_sel':genero,
        'total_partidos':total_p.count(),
        'total_goles': (EventoPartido.objects.filter(
            tipo='gol', partido__jugado=True,
            **({'partido__ciclo':ciclo} if ciclo else {}),
            **({'partido__genero':genero} if genero and genero!='X' else {})
        ).count()) if dep=='futbol' else 0,
        'total_amarillas': (EventoPartido.objects.filter(
            tipo='amarilla', partido__jugado=True,
            **({'partido__ciclo':ciclo} if ciclo else {}),
        ).count()) if dep=='futbol' else 0,
        'total_rojas': (EventoPartido.objects.filter(
            tipo='roja', partido__jugado=True,
            **({'partido__ciclo':ciclo} if ciclo else {}),
        ).count()) if dep=='futbol' else 0,
        'deportes':DEPORTE_CHOICES,'ciclos':CICLO_CHOICES,'generos':GENERO_CHOICES,
        **ctx_extra
    }
    return render(request,'core/estadisticas.html',ctx)

# ── TABLA POSICIONES ──────────────────────────────────────────────────────────
def tabla_posiciones(request):
    cfg    = get_config()
    ciclo  = request.GET.get('ciclo','I')
    dep    = request.GET.get('deporte','futbol')
    genero = request.GET.get('genero','M')
    tablas, finales, podio = _tabla_completa(ciclo, dep, genero)
    ctx = {'cfg':cfg,'tablas':tablas,'partidos_finales':finales,'podio':podio,
           'ciclo_sel':ciclo,'deporte_sel':dep,'genero_sel':genero,
           'ciclos':CICLO_CHOICES,'deportes':DEPORTE_CHOICES,'generos':GENERO_CHOICES,
           'deporte_label':dict(DEPORTE_CHOICES).get(dep,'')}
    return render(request,'core/tabla_posiciones.html',ctx)

# ── HISTORIAL TORNEOS ─────────────────────────────────────────────────────────
def historial_torneos(request):
    torneos = TorneoHistorico.objects.all()
    return render(request,'core/historial_torneos.html',
                  {'torneos':torneos,'cfg':get_config()})

# ── REGLAS ────────────────────────────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def admin_horario_semanal(request):
    from datetime import date, timedelta
    from collections import defaultdict
    ciclo  = request.GET.get('ciclo', '')
    dep    = request.GET.get('deporte', '')
    genero = request.GET.get('genero', '')
    semana = request.GET.get('semana', '')

    hoy = date.today()
    if semana:
        try:
            year, week = semana.split('-W')
            lunes = date.fromisocalendar(int(year), int(week), 1)
        except Exception:
            lunes = hoy - timedelta(days=hoy.weekday())
    else:
        lunes = hoy - timedelta(days=hoy.weekday())
    domingo = lunes + timedelta(days=6)

    qs = Partido.objects.filter(
        fecha__gte=lunes, fecha__lte=domingo
    ).select_related(
        'equipo_local__grado', 'equipo_visitante__grado', 'grupo_torneo'
    ).order_by('fecha', 'hora')

    if ciclo:  qs = qs.filter(ciclo=ciclo)
    if dep:    qs = qs.filter(deporte=dep)
    if genero: qs = qs.filter(genero=genero)

    dias = defaultdict(list)
    for p in qs:
        dias[p.fecha].append(p)
    dias_ordenados = sorted(dias.items())

    return render(request, 'core/admin_horario_semanal.html', {
        'cfg': get_config(),
        'dias': dias_ordenados,
        'lunes': lunes,
        'domingo': domingo,
        'ciclo_sel': ciclo,
        'deporte_sel': dep,
        'genero_sel': genero,
        'semana_sel': semana or lunes.strftime('%Y-W%V'),
        'ciclos': CICLO_CHOICES,
        'deportes': DEPORTE_CHOICES,
        'generos': GENERO_CHOICES,
        'total_partidos': qs.count(),
    })


def reglas(request):
    return render(request,'core/reglas.html',
                  {'cfg':get_config(),'reglas':ReglaDeporte.objects.all()})

# ── COSFABOT (sin IA, basado en BD) ──────────────────────────────────────────
def chatbot_view(request):
    return render(request,'core/chatbot.html',{'cfg':get_config(),'ciclos':CICLO_CHOICES,'deportes':DEPORTE_CHOICES})

def chatbot_api(request):
    if request.method != 'POST':
        return JsonResponse({'error':'Método no permitido'},status=405)
    try: body = json.loads(request.body)
    except: return JsonResponse({'error':'JSON inválido'},status=400)
    pregunta_id = body.get('pregunta_id','')
    ciclo       = body.get('ciclo','')
    deporte     = body.get('deporte','futbol')
    genero      = body.get('genero','M')
    reply = _responder_pregunta(pregunta_id, ciclo, deporte, genero)
    return JsonResponse({'reply': reply})

def _responder_pregunta(pid, ciclo, deporte, genero):
    dep_name = dict(DEPORTE_CHOICES).get(deporte, deporte)
    cic_name = dict(CICLO_CHOICES).get(ciclo, ciclo) if ciclo else 'todos los ciclos'
    gen_name = 'Masculino' if genero=='M' else ('Femenino' if genero=='F' else 'Mixto')
    ctx = f"{dep_name} · {cic_name} · {gen_name}"

    qs_p = Partido.objects.filter(jugado=True, deporte=deporte)
    if ciclo:  qs_p = qs_p.filter(ciclo=ciclo)
    if genero and genero!='X': qs_p = qs_p.filter(genero=genero)

    if pid == 'campeon':
        final = qs_p.filter(fase='final').order_by('-fecha').first()
        if final and final.ganador():
            g = final.ganador()
            return f"🏆 El campeón de {ctx} es **{g.nombre_corto()}**{' (' + g.pais + ')' if g.pais else ''}. ¡Felicitaciones!"
        return f"⏳ El torneo de {ctx} aún no tiene campeón. La final no se ha jugado."

    elif pid == 'mas_anotador':
        if deporte == 'futbol':
            top = _top_goles(deporte=deporte, ciclo=ciclo if ciclo else None,
                             genero=genero if genero!='X' else None, limit=1)
            if top:
                g = top[0]
                return (f"⚽ El máximo goleador de {ctx} es "
                        f"**{g['jugador__nombre']} {g['jugador__apellido']}** "
                        f"({g['jugador__grado__pais'] or 'sin selección'}) "
                        f"con **{g['total']} goles**. ¡Un crack!")
            return f"😕 Aún no hay goles registrados en {ctx}."
        else:
            stats = _stats_colectivos(deporte, ciclo or None, genero or None)
            if stats:
                s = stats[0]
                return (f"🏆 El equipo más anotador de {ctx} es "
                        f"**{s['equipo'].nombre_corto()}** "
                        f"({s['equipo'].pais or 'sin selección'}) "
                        f"con **{s['pf']} puntos** a favor en {s['pj']} partidos.")
            return f"😕 No hay datos de {ctx} aún."

    elif pid == 'menos_anotado':
        stats = _stats_colectivos(deporte, ciclo or None, genero or None)
        if stats:
            mejor_def = min(stats, key=lambda x: x['pc'])
            return (f"🛡️ El equipo menos anotado (mejor defensa) de {ctx} es "
                    f"**{mejor_def['equipo'].nombre_corto()}** "
                    f"({mejor_def['equipo'].pais or '–'}) "
                    f"con solo **{mejor_def['pc']} puntos en contra** en {mejor_def['pj']} partidos.")
        return f"😕 No hay datos de {ctx} aún."

    elif pid == 'mas_victorias':
        stats = _stats_colectivos(deporte, ciclo or None, genero or None)
        if stats:
            lider = max(stats, key=lambda x: x['pg'])
            return (f"🥇 El equipo con más victorias en {ctx} es "
                    f"**{lider['equipo'].nombre_corto()}** "
                    f"({lider['equipo'].pais or '–'}) "
                    f"con **{lider['pg']} victorias** de {lider['pj']} partidos disputados.")
        return f"😕 No hay datos de {ctx} aún."

    elif pid == 'max_asistidor':
        top = _top_asist(deporte=deporte, ciclo=ciclo if ciclo else None,
                         genero=genero if genero!='X' else None, limit=1)
        if top:
            a = top[0]
            return (f"🎯 El máximo asistidor de {ctx} es "
                    f"**{a['asistente__nombre']} {a['asistente__apellido']}** "
                    f"({a['asistente__grado__pais'] or '–'}) "
                    f"con **{a['total']} asistencias**. ¡Qué visión de juego!")
        return f"😕 No hay asistencias registradas en {ctx}."

    elif pid == 'tabla':
        stats = _stats_colectivos(deporte, ciclo or None, genero or None)
        if not stats:
            return f"📊 No hay partidos jugados en {ctx} aún."
        lines = [f"📊 **Tabla de {ctx}:**\n"]
        medals = ['🥇','🥈','🥉']
        for i, s in enumerate(stats[:5]):
            med = medals[i] if i < 3 else f"{i+1}°"
            lines.append(f"{med} {s['equipo'].nombre_corto()} — {s['pg']}G {s['pp']}P | {s['pf']}-{s['pc']}")
        return "\n".join(lines)

    elif pid == 'proximos':
        proximos = Partido.objects.filter(jugado=False, deporte=deporte)
        if ciclo: proximos = proximos.filter(ciclo=ciclo)
        if genero and genero!='X': proximos = proximos.filter(genero=genero)
        proximos = proximos.select_related('equipo_local__grado','equipo_visitante__grado'
                   ).order_by('fecha','pk')[:5]
        if not proximos:
            return f"📅 No hay partidos pendientes en {ctx}."
        lines = [f"📅 **Próximos partidos de {ctx}:**\n"]
        for p in proximos:
            fecha = p.fecha.strftime('%d/%m/%Y') if p.fecha else 'Sin fecha'
            lines.append(f"• {p.equipo_local.nombre_corto()} vs {p.equipo_visitante.nombre_corto()} — {fecha}")
        return "\n".join(lines)

    elif pid == 'resumen_torneo':
        stats = _stats_colectivos(deporte, ciclo or None, genero or None)
        total_p = qs_p.count()
        total_g = EventoPartido.objects.filter(tipo='gol', partido__deporte=deporte,
                    **({'partido__ciclo':ciclo} if ciclo else {})).count() if deporte=='futbol' else 0
        final = qs_p.filter(fase='final').first()
        campen = final.ganador() if final and final.jugado else None
        lines = [f"🏟️ **Resumen del torneo — {ctx}**\n",
                 f"• Partidos jugados: {total_p}"]
        if deporte == 'futbol': lines.append(f"• Goles anotados: {total_g}")
        if campen: lines.append(f"• 🏆 Campeón: {campen.nombre_corto()} ({campen.pais or '–'})")
        if stats:
            lines.append(f"• Equipo más anotador: {stats[0]['equipo'].nombre_corto()} ({stats[0]['pf']} pts)")
        return "\n".join(lines)

    return "🤔 No entendí la pregunta. Selecciona una de las opciones disponibles."


def vista_usuario(request):
    """Vista home forzada — nunca redirige al admin dashboard."""
    cfg = get_config()
    partidos_recientes = Partido.objects.filter(jugado=True).select_related(
        'equipo_local__grado','equipo_visitante__grado'
    ).prefetch_related('sets','eventos__jugador','eventos__equipo'
    ).order_by('-fecha','-pk')[:10]
    imagenes = ImagenCarrusel.objects.filter(activo=True)
    grados   = Grado.objects.all().order_by('grado','grupo')
    ctx = {
        'cfg':cfg,'partidos_recientes':partidos_recientes,
        'imagenes':imagenes,'grados':grados,'ciclos':CICLO_CHOICES,
        'top_goles': _top_goles(deporte='futbol', limit=5),
        'top_asist': _top_asist(deporte='futbol', limit=5),
        'stats_basket': _stats_colectivos('baloncesto')[:5],
        'stats_voley':  _stats_colectivos('voleibol')[:5],
        'deportes': DEPORTE_CHOICES,
        'historial': TorneoHistorico.objects.all()[:3],
    }
    return render(request,'core/home.html',ctx)

# ════════════════════════════════════════════════════════════════════════
#  ADMIN
# ════════════════════════════════════════════════════════════════════════
@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    cfg = get_config()
    ctx = {
        'cfg':cfg,
        'total_jugadores':  Jugador.objects.count(),
        'total_partidos':   Partido.objects.count(),
        'partidos_jugados': Partido.objects.filter(jugado=True).count(),
        'total_grados':     Grado.objects.count(),
        'total_goles':      EventoPartido.objects.filter(tipo='gol').count(),
        'partidos_hoy':     Partido.objects.filter(fecha=timezone.now().date()).select_related(
                            'equipo_local__grado','equipo_visitante__grado'),
        'top_goles':        _top_goles(limit=5),
        'grados':           Grado.objects.all().order_by('grado','grupo'),
        'ciclos':           CICLO_CHOICES,
    }
    return render(request,'core/admin_dashboard.html',ctx)

# ── Grados CRUD ───────────────────────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def admin_grados(request):
    ciclo_sel = request.GET.get('ciclo','')
    grados = Grado.objects.prefetch_related('jugadores','equipos').all()
    if ciclo_sel:
        ids = [g for g,c in CICLO_POR_GRADO.items() if c==ciclo_sel]
        grados = grados.filter(grado__in=ids)
    return render(request,'core/admin_grados.html',
                  {'grados':grados,'cfg':get_config(),
                   'ciclos':CICLO_CHOICES,'ciclo_sel':ciclo_sel})

@login_required
@user_passes_test(is_admin)
def admin_grado_crear(request):
    form = GradoForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        g = form.save()
        for dep in g.deportes():
            for gen in GENEROS_POR_DEPORTE.get(dep,['X']):
                Equipo.objects.get_or_create(grado=g,deporte=dep,genero=gen)
        messages.success(request,'✅ Grado creado.')
        return redirect('admin_grados')
    return render(request,'core/admin_grado_form.html',
                  {'form':form,'titulo':'Crear Grado','cfg':get_config()})

@login_required
@user_passes_test(is_admin)
def admin_grado_editar(request, pk):
    g = get_object_or_404(Grado,pk=pk)
    form = GradoForm(request.POST or None, request.FILES or None, instance=g)
    if form.is_valid():
        form.save(); messages.success(request,'✅ Grado actualizado.')
        return redirect('admin_grados')
    return render(request,'core/admin_grado_form.html',
                  {'form':form,'titulo':'Editar Grado','grado':g,'cfg':get_config()})

@login_required
@user_passes_test(is_admin)
def admin_grado_eliminar(request, pk):
    g = get_object_or_404(Grado,pk=pk)
    if request.method == 'POST':
        g.delete(); messages.success(request,'🗑️ Grado eliminado.')
        return redirect('admin_grados')
    return render(request,'core/confirmar_eliminar.html',
                  {'objeto':g,'volver':'admin_grados','cfg':get_config()})

@login_required
@user_passes_test(is_admin)
def admin_grado_detalle(request, pk):
    grado  = get_object_or_404(Grado,pk=pk)
    equipos = Equipo.objects.filter(grado=grado).prefetch_related('inscripciones__jugador')
    return render(request,'core/admin_grado_detalle.html',
                  {'grado':grado,'equipos':equipos,'cfg':get_config()})

# ── Sorteo países ─────────────────────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def sorteo_paises(request):
    grados = Grado.objects.all().order_by('grado','grupo')
    if request.method == 'POST':
        if 'asignar_todos' in request.POST:
            prim = list(grados.filter(grado__in=['T','1','2','3','4','5']))
            secu = list(grados.filter(grado__in=['6','7','8','9','10','11','P']))
            paises = PaisParticipante.lista_activos(); random.shuffle(paises)
            def asignar(lista):
                usados = []
                for ga in lista:
                    disp = [p for p in paises if p not in usados] or paises[:]
                    pais = random.choice(disp); ga.pais=pais; ga.save(); usados.append(pais)
            asignar(prim); asignar(secu)
            messages.success(request,'🌍 Países asignados.')
            return redirect('sorteo_paises')
        if 'grado_id' in request.POST and 'pais' in request.POST:
            g = get_object_or_404(Grado,pk=request.POST['grado_id'])
            g.pais = request.POST['pais']; g.save()
            return JsonResponse({'ok':True})
    grados_json = json.dumps([{
        'id':g.pk,'nombre':str(g),'pais':g.pais or '',
        'ciclo':g.ciclo(),'grado_code':g.grado
    } for g in grados])
    cfg = get_config()
    paises_activos = PaisParticipante.lista_activos()
    # Fallback: if no active PaisParticipante, use config text list
    if not paises_activos:
        paises_activos = cfg.get_paises_sorteo() if hasattr(cfg, 'get_paises_sorteo') else []
    return render(request,'core/sorteo_paises.html',{
        'grados': grados,
        'grados_json': grados_json,
        'paises_json': json.dumps(paises_activos),
        'paises_default_json': json.dumps(PAIS_LIST),
        'cfg': cfg,
    })

# ── Guardar países config ──────────────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def guardar_paises_config(request):
    if request.method == 'POST':
        paises_txt = request.POST.get('paises_lista', '').strip()
        cfg = get_config()
        cfg.paises_sorteo = paises_txt
        cfg.save()
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False}, status=405)


@login_required
@user_passes_test(is_admin)
def admin_equipo_editar(request, pk):
    eq = get_object_or_404(Equipo,pk=pk)
    form = EquipoForm(request.POST or None, request.FILES or None, instance=eq)
    # Filtrar capitán: solo jugadores inscritos en ESTE equipo
    jugadores_equipo = Jugador.objects.filter(
        inscripciones__equipo=eq
    ).distinct().order_by('apellido','nombre')
    form.fields['capitan'].queryset = jugadores_equipo
    if form.is_valid():
        form.save(); messages.success(request,'✅ Equipo actualizado.')
        return redirect('admin_grado_detalle',pk=eq.grado.pk)
    return render(request,'core/admin_equipo_form.html',
                  {'form':form,'equipo':eq,'cfg':get_config()})

# ── Jugadores CRUD ────────────────────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def admin_jugadores(request):
    ciclo    = request.GET.get('ciclo','')
    grado_id = request.GET.get('grado','')
    genero   = request.GET.get('genero','')
    q        = request.GET.get('q','').strip()
    qs = Jugador.objects.select_related('grado').prefetch_related('inscripciones').all()
    if ciclo:
        gs = [g for g,c in CICLO_POR_GRADO.items() if c==ciclo]
        qs = qs.filter(grado__grado__in=gs)
    if grado_id:
        qs = qs.filter(grado__pk=grado_id)
    if genero:
        qs = qs.filter(genero=genero)
    if q:
        qs = qs.filter(
            Q(ti__icontains=q) |
            Q(nombre__icontains=q) |
            Q(apellido__icontains=q)
        )
    return render(request,'core/admin_jugadores.html',{
        'jugadores': qs,
        'cfg':       get_config(),
        'ciclos':    CICLO_CHOICES,
        'ciclo_sel': ciclo,
        'grado_sel': grado_id,
        'genero_sel': genero,
        'q':         q,
        'grados':    Grado.objects.all().order_by('grado','grupo'),
    })

@login_required
@user_passes_test(is_admin)
def admin_jugador_crear(request, grado_pk=None):
    grado_obj = None
    if grado_pk:
        grado_obj = get_object_or_404(Grado, pk=grado_pk)

    form = JugadorForm(request.POST or None, request.FILES or None,
                       initial={'grado': grado_obj} if grado_obj else None)
    insc_form = InscripcionForm(request.POST or None)

    if grado_obj:
        insc_form.fields['equipo'].queryset = Equipo.objects.filter(
            grado=grado_obj).order_by('deporte', 'genero')
    else:
        insc_form.fields['equipo'].queryset = Equipo.objects.none()

    if request.method == 'POST' and 'crear_jugador' in request.POST:
        if form.is_valid():
            j = form.save(commit=False)
            if grado_obj:
                j.grado = grado_obj
            j.save()
            if insc_form.is_valid() and insc_form.cleaned_data.get('equipo'):
                equipo_sel = insc_form.cleaned_data['equipo']
                numero = insc_form.cleaned_data.get('numero_camiseta', 0)
                InscripcionJugador.objects.get_or_create(
                    jugador=j, equipo=equipo_sel,
                    defaults={'numero_camiseta': numero})
                messages.success(request, f'✅ Jugador {j} inscrito en {equipo_sel}.')
            else:
                messages.success(request, f'✅ Jugador {j} registrado.')
            if grado_obj:
                return redirect('admin_grado_detalle', pk=grado_obj.pk)
            return redirect('admin_grados')
        else:
            messages.error(request, '❌ Revisa los campos del formulario.')

    return render(request, 'core/admin_jugador_form.html',
                  {'form': form, 'insc_form': insc_form,
                   'titulo': 'Inscribir Jugador',
                   'cfg': get_config(), 'grado_obj': grado_obj})

@login_required
@user_passes_test(is_admin)
def admin_jugador_editar(request, pk):
    j = get_object_or_404(Jugador,pk=pk)
    form = JugadorForm(request.POST or None, request.FILES or None, instance=j)
    # Filtrar inscripcion: solo equipos del grado del jugador
    insc_form = InscripcionForm(request.POST or None)
    if j.grado:
        insc_form.fields['equipo'].queryset = Equipo.objects.filter(
            grado=j.grado).select_related('grado')
    inscs = InscripcionJugador.objects.filter(jugador=j).select_related('equipo__grado')
    if request.method == 'POST':
        if 'save_jugador' in request.POST and form.is_valid():
            form.save(); messages.success(request,'✅ Jugador actualizado.')
            if j.grado:
                return redirect('admin_grado_detalle', pk=j.grado.pk)
            return redirect('admin_grados')
        if 'add_insc' in request.POST and insc_form.is_valid():
            equipo = insc_form.cleaned_data['equipo']
            numero = insc_form.cleaned_data['numero_camiseta']
            obj, created = InscripcionJugador.objects.get_or_create(
                jugador=j, equipo=equipo,
                defaults={'numero_camiseta':numero})
            if not created:
                obj.numero_camiseta=numero; obj.save()
                messages.warning(request,'⚠️ Ya inscrito, camiseta actualizada.')
            else:
                messages.success(request,'✅ Inscripción agregada.')
            return redirect('admin_jugador_editar',pk=pk)
    return render(request,'core/admin_jugador_form.html',{
        'form':form,'insc_form':insc_form,'titulo':'Editar Jugador',
        'jugador':j,'inscripciones':inscs,'cfg':get_config()})

@login_required
@user_passes_test(is_admin)
def admin_jugador_eliminar(request, pk):
    j = get_object_or_404(Jugador, pk=pk)
    grado_pk = j.grado.pk if j.grado else None
    if request.method == 'POST':
        j.delete()
        messages.success(request, '🗑️ Jugador eliminado.')
        if grado_pk:
            return redirect('admin_grado_detalle', pk=grado_pk)
        return redirect('admin_grados')
    return render(request, 'core/confirmar_eliminar.html',
                  {'objeto': j, 'volver': 'admin_grados', 'cfg': get_config()})

@login_required
@user_passes_test(is_admin)
def equipos_por_grado(request):
    """Retorna JSON con los equipos de un grado dado (para AJAX en formulario jugador)."""
    grado_id = request.GET.get('grado_id')
    if not grado_id:
        return JsonResponse({'equipos': []})
    equipos = Equipo.objects.filter(grado_id=grado_id).select_related('grado').order_by('deporte','genero')
    data = [{'id': e.pk, 'nombre': str(e)} for e in equipos]
    return JsonResponse({'equipos': data})

@login_required
@user_passes_test(is_admin)
def admin_insc_eliminar(request, pk):
    i = get_object_or_404(InscripcionJugador,pk=pk); jid=i.jugador.pk; i.delete()
    messages.success(request,'🗑️ Eliminada.')
    return redirect('admin_jugador_editar',pk=jid)

# ── Partidos CRUD ─────────────────────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def admin_partidos(request):
    ciclo=request.GET.get('ciclo',''); dep=request.GET.get('deporte',''); gen=request.GET.get('genero','')
    qs = Partido.objects.select_related('equipo_local__grado','equipo_visitante__grado').all()
    if ciclo: qs=qs.filter(ciclo=ciclo)
    if dep:   qs=qs.filter(deporte=dep)
    if gen:   qs=qs.filter(genero=gen)
    return render(request,'core/admin_partidos.html',{
        'partidos':qs,'cfg':get_config(),'ciclos':CICLO_CHOICES,
        'deportes':DEPORTE_CHOICES,'generos':GENERO_CHOICES,
        'ciclo_sel':ciclo,'deporte_sel':dep,'genero_sel':gen})

@login_required
@user_passes_test(is_admin)
def admin_partido_crear(request):
    ciclo   = request.GET.get('ciclo','') or request.POST.get('ciclo','')
    deporte = request.GET.get('deporte','') or request.POST.get('deporte','')
    genero  = request.GET.get('genero','') or request.POST.get('genero','')
    if not ciclo or not deporte:
        return render(request,'core/admin_partido_selector.html',{
            'cfg':get_config(),'ciclos':CICLO_CHOICES,
            'deportes':DEPORTE_CHOICES,'generos':GENERO_CHOICES})
    grados_ciclo = [g for g,c in CICLO_POR_GRADO.items() if c==ciclo]
    equipos_qs   = Equipo.objects.filter(
        grado__grado__in=grados_ciclo,deporte=deporte,genero=genero
    ).select_related('grado')
    form = PartidoForm(request.POST or None)
    form.fields['equipo_local'].queryset    = equipos_qs
    form.fields['equipo_visitante'].queryset = equipos_qs
    form.fields['ciclo'].initial    = ciclo
    form.fields['deporte'].initial  = deporte
    form.fields['genero'].initial   = genero
    form.fields['grupo_torneo'].queryset = GrupoTorneo.objects.filter(
        ciclo=ciclo,deporte=deporte,genero=genero)
    if request.method == 'POST' and form.is_valid():
        form.save(); messages.success(request,'✅ Partido creado.')
        return redirect('admin_partidos')
    return render(request,'core/admin_partido_form.html',{
        'form':form,'titulo':'Crear Partido','cfg':get_config(),
        'ciclo':ciclo,'deporte':deporte,'genero':genero})

@login_required
@user_passes_test(is_admin)
def admin_partido_editar(request, pk):
    partido  = get_object_or_404(Partido,pk=pk)
    form     = PartidoForm(request.POST or None, instance=partido)
    grados_ciclo = [g for g,c in CICLO_POR_GRADO.items() if c==partido.ciclo]
    equipos_qs   = Equipo.objects.filter(
        grado__grado__in=grados_ciclo,deporte=partido.deporte,genero=partido.genero
    ).select_related('grado')
    form.fields['equipo_local'].queryset    = equipos_qs
    form.fields['equipo_visitante'].queryset = equipos_qs
    form.fields['grupo_torneo'].queryset    = GrupoTorneo.objects.filter(
        ciclo=partido.ciclo,deporte=partido.deporte,genero=partido.genero)
    # Jugadores POR equipo para goles
    jug_local   = Jugador.objects.filter(
        inscripciones__equipo=partido.equipo_local).distinct()
    jug_visita  = Jugador.objects.filter(
        inscripciones__equipo=partido.equipo_visitante).distinct()
    gol_form_local  = GolForm(equipo_local=partido.equipo_local,
                               equipo_visitante=partido.equipo_local,
                               prefix='local')
    gol_form_visita = GolForm(equipo_local=partido.equipo_visitante,
                               equipo_visitante=partido.equipo_visitante,
                               prefix='visita')
    gol_form_local.fields['goleador'].queryset  = jug_local
    gol_form_local.fields['goleador']._equipo   = partido.equipo_local
    gol_form_local.fields['asistente'].queryset = jug_local
    gol_form_local.fields['asistente']._equipo  = partido.equipo_local
    gol_form_local.fields['equipo_gol'].queryset = equipos_qs.filter(pk=partido.equipo_local.pk)
    gol_form_visita.fields['goleador'].queryset  = jug_visita
    gol_form_visita.fields['goleador']._equipo   = partido.equipo_visitante
    gol_form_visita.fields['asistente'].queryset = jug_visita
    gol_form_visita.fields['asistente']._equipo  = partido.equipo_visitante
    gol_form_visita.fields['equipo_gol'].queryset = equipos_qs.filter(pk=partido.equipo_visitante.pk)

    eventos_local  = EventoPartido.objects.filter(
        partido=partido,equipo=partido.equipo_local).select_related('jugador','asistente')
    eventos_visita = EventoPartido.objects.filter(
        partido=partido,equipo=partido.equipo_visitante).select_related('jugador','asistente')
    sets_vb = SetVoleibol.objects.filter(partido=partido) if partido.deporte=='voleibol' else []

    # Límite de goles (solo contar tipo='gol', no tarjetas)
    goles_local_max  = partido.puntos_local
    goles_visita_max = partido.puntos_visitante
    goles_local_act  = eventos_local.filter(tipo='gol').count()
    goles_visita_act = eventos_visita.filter(tipo='gol').count()
    puede_gol_local  = partido.deporte=='futbol' and partido.jugado and (goles_local_max == 0 or goles_local_act < goles_local_max)
    puede_gol_visita = partido.deporte=='futbol' and partido.jugado and (goles_visita_max == 0 or goles_visita_act < goles_visita_max)
    puede_tarjeta    = partido.jugado and partido.deporte == 'futbol'

    if request.method == 'POST':
        if 'save_partido' in request.POST and form.is_valid():
            form.save(); messages.success(request,'✅ Partido actualizado.')
            return redirect('admin_partidos')
        if 'add_gol_local' in request.POST and puede_gol_local:
            goleador_id = request.POST.get('local-goleador', '').strip()
            asistente_id = request.POST.get('local-asistente', '').strip()
            if goleador_id:
                try:
                    goleador_obj = Jugador.objects.get(pk=int(goleador_id), inscripciones__equipo=partido.equipo_local)
                    asistente_obj = None
                    if asistente_id:
                        asistente_obj = Jugador.objects.filter(pk=int(asistente_id), inscripciones__equipo=partido.equipo_local).first()
                    EventoPartido.objects.create(
                        partido=partido, equipo=partido.equipo_local,
                        jugador=goleador_obj, tipo='gol',
                        asistente=asistente_obj)
                    messages.success(request,'⚽ Gol local registrado.')
                    return redirect('admin_partido_editar', pk=pk)
                except (ValueError, Jugador.DoesNotExist):
                    messages.error(request, '❌ Jugador inválido.')
        if 'add_gol_visita' in request.POST and puede_gol_visita:
            goleador_id = request.POST.get('visita-goleador', '').strip()
            asistente_id = request.POST.get('visita-asistente', '').strip()
            if goleador_id:
                try:
                    goleador_obj = Jugador.objects.get(pk=int(goleador_id), inscripciones__equipo=partido.equipo_visitante)
                    asistente_obj = None
                    if asistente_id:
                        asistente_obj = Jugador.objects.filter(pk=int(asistente_id), inscripciones__equipo=partido.equipo_visitante).first()
                    EventoPartido.objects.create(
                        partido=partido, equipo=partido.equipo_visitante,
                        jugador=goleador_obj, tipo='gol',
                        asistente=asistente_obj)
                    messages.success(request,'⚽ Gol visitante registrado.')
                    return redirect('admin_partido_editar', pk=pk)
                except (ValueError, Jugador.DoesNotExist):
                    messages.error(request, '❌ Jugador inválido.')
        if 'del_evento' in request.POST:
            EventoPartido.objects.filter(pk=request.POST.get('evento_id'),partido=partido).delete()
            messages.success(request,'🗑️ Evento eliminado.')
            return redirect('admin_partido_editar',pk=pk)
        if 'add_tarjeta' in request.POST and puede_tarjeta:
            jug_id  = request.POST.get('tarjeta_jugador','').strip()
            eq_id   = request.POST.get('tarjeta_equipo','').strip()
            tipo_t  = request.POST.get('tarjeta_tipo','amarilla')
            minuto  = request.POST.get('tarjeta_minuto','').strip()
            if jug_id and eq_id:
                try:
                    eq_pk = int(eq_id)
                    jug_pk = int(jug_id)
                    # Validar que el equipo sea local o visitante
                    if eq_pk not in [partido.equipo_local.pk, partido.equipo_visitante.pk]:
                        messages.error(request, '❌ Equipo inválido.')
                    else:
                        # Validar que el jugador pertenezca al equipo seleccionado
                        jugador_valido = Jugador.objects.filter(
                            pk=jug_pk, inscripciones__equipo_id=eq_pk
                        ).exists()
                        if not jugador_valido:
                            messages.error(request, '❌ El jugador no pertenece al equipo seleccionado.')
                        else:
                            EventoPartido.objects.create(
                                partido=partido,
                                jugador_id=jug_pk,
                                equipo_id=eq_pk,
                                tipo=tipo_t,
                                minuto=int(minuto) if minuto.isdigit() else None
                            )
                            messages.success(request, '🟨 Tarjeta registrada.')
                except (ValueError, TypeError):
                    messages.error(request, '❌ Datos inválidos.')
            return redirect('admin_partido_editar', pk=pk)
        if 'save_set' in request.POST and partido.deporte=='voleibol':
            num_set = int(request.POST.get('num_set',1))
            SetVoleibol.objects.update_or_create(
                partido=partido, numero_set=num_set,
                defaults={'puntos_local':int(request.POST.get('set_local',0)),
                          'puntos_visita':int(request.POST.get('set_visita',0))})
            messages.success(request,f'✅ Set {num_set} guardado.')
            return redirect('admin_partido_editar',pk=pk)
        if 'del_set' in request.POST:
            SetVoleibol.objects.filter(pk=request.POST.get('set_id'),partido=partido).delete()
            messages.success(request,'🗑️ Set eliminado.')
            return redirect('admin_partido_editar',pk=pk)

    # Split events by type for template
    goles_local_qs     = eventos_local.filter(tipo='gol')
    goles_visita_qs    = eventos_visita.filter(tipo='gol')
    tarjetas_local_qs  = eventos_local.filter(tipo__in=['amarilla','roja'])
    tarjetas_visita_qs = eventos_visita.filter(tipo__in=['amarilla','roja'])

    return render(request,'core/admin_partido_form.html',{
        'form':form,'titulo':'Editar Partido','partido':partido,
        'gol_form_local':gol_form_local,'gol_form_visita':gol_form_visita,
        'eventos_local':eventos_local,'eventos_visita':eventos_visita,
        'goles_local':goles_local_qs,'goles_visita':goles_visita_qs,
        'tarjetas_local':tarjetas_local_qs,'tarjetas_visita':tarjetas_visita_qs,
        'jug_local':jug_local,'jug_visita':jug_visita,
        'sets_vb':sets_vb,'cfg':get_config(),
        'puede_gol_local':puede_gol_local,'puede_gol_visita':puede_gol_visita,
        'puede_tarjeta':puede_tarjeta,
        'goles_local_act':goles_local_act,'goles_visita_act':goles_visita_act,
        'goles_local_max':goles_local_max,'goles_visita_max':goles_visita_max,
    })

@login_required
@user_passes_test(is_admin)
def admin_partido_eliminar(request, pk):
    p = get_object_or_404(Partido,pk=pk)
    if request.method == 'POST':
        p.delete(); messages.success(request,'🗑️ Partido eliminado.')
        return redirect('admin_partidos')
    return render(request,'core/confirmar_eliminar.html',
                  {'objeto':p,'volver':'admin_partidos','cfg':get_config()})

# ── Sorteo grupos ─────────────────────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def admin_sorteo_grupos(request):
    cfg    = get_config()
    ciclo  = request.GET.get('ciclo','I')
    dep    = request.GET.get('deporte','futbol')
    genero = request.GET.get('genero','M')
    grados_ciclo = [g for g,c in CICLO_POR_GRADO.items() if c==ciclo]
    equipos_disp = list(Equipo.objects.filter(
        grado__grado__in=grados_ciclo,deporte=dep,genero=genero
    ).select_related('grado'))
    grupos_exist = GrupoTorneo.objects.filter(
        ciclo=ciclo,deporte=dep,genero=genero).prefetch_related('equipos')

    if request.method == 'POST':
        if 'ejecutar_sorteo' in request.POST:
            ids = request.POST.getlist('equipos_sel')
            sel = [e for e in equipos_disp if str(e.pk) in ids] if ids else equipos_disp[:]
            random.shuffle(sel)
            mitad = len(sel)//2 + len(sel)%2
            ga_eq=sel[:mitad]; gb_eq=sel[mitad:]
            GrupoTorneo.objects.filter(ciclo=ciclo,deporte=dep,genero=genero).delete()
            Partido.objects.filter(ciclo=ciclo,deporte=dep,genero=genero,fase='grupos').delete()
            ga,_=GrupoTorneo.objects.get_or_create(nombre='A',ciclo=ciclo,deporte=dep,genero=genero)
            gb,_=GrupoTorneo.objects.get_or_create(nombre='B',ciclo=ciclo,deporte=dep,genero=genero)
            ga.equipos.set(ga_eq); gb.equipos.set(gb_eq)
            d=date.today(); dia=0
            for gt,miembros in [(ga,ga_eq),(gb,gb_eq)]:
                for e1,e2 in combinations(miembros,2):
                    Partido.objects.create(
                        equipo_local=e1,equipo_visitante=e2,
                        fecha=d+timedelta(days=dia),
                        fase='grupos',grupo_torneo=gt,
                        deporte=dep,ciclo=ciclo,genero=genero)
                    dia+=1
            messages.success(request,f'✅ Grupos creados.')
            return redirect(f"{request.path}?ciclo={ciclo}&deporte={dep}&genero={genero}")

        if 'terminar_fase_grupos' in request.POST:
            gts = GrupoTorneo.objects.filter(ciclo=ciclo,deporte=dep,genero=genero)
            for gt in gts: gt.fase_grupos_terminada=True; gt.save()
            tablas = {gt.nombre:_tabla_grupo(gt) for gt in gts}
            eq1a=tablas.get('A',[{}])[0].get('equipo') if tablas.get('A') else None
            eq1b=tablas.get('B',[{}])[0].get('equipo') if tablas.get('B') else None
            eq2a=tablas.get('A',[{},{}])[1].get('equipo') if len(tablas.get('A',[]))>1 else None
            eq2b=tablas.get('B',[{},{}])[1].get('equipo') if len(tablas.get('B',[]))>1 else None
            fd=date.today()+timedelta(days=7)
            if eq1a and eq1b:
                Partido.objects.get_or_create(equipo_local=eq1a,equipo_visitante=eq1b,
                    fase='final',ciclo=ciclo,deporte=dep,genero=genero,defaults={'fecha':fd})
            if eq2a and eq2b:
                Partido.objects.get_or_create(equipo_local=eq2a,equipo_visitante=eq2b,
                    fase='tercer_puesto',ciclo=ciclo,deporte=dep,genero=genero,defaults={'fecha':fd})
            messages.success(request,'🏆 Finales generadas.')
            return redirect(f"{request.path}?ciclo={ciclo}&deporte={dep}&genero={genero}")

    equipos_json = json.dumps([
        {'id':e.pk,'nombre':e.nombre_corto(),'pais':e.pais or ''} for e in equipos_disp])
    ctx = {'cfg':cfg,'ciclo':ciclo,'deporte':dep,'genero':genero,
           'equipos_disp':equipos_disp,'grupos_exist':grupos_exist,'equipos_json':equipos_json,
           'ciclos':CICLO_CHOICES,'deportes':DEPORTE_CHOICES,'generos':GENERO_CHOICES}
    return render(request,'core/admin_sorteo_grupos.html',ctx)

# ── Torneo: cerrar y guardar historial ────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def admin_cerrar_torneo(request):
    cfg = get_config()
    if request.method == 'POST':
        año  = request.POST.get('año', timezone.now().year)
        nombre = request.POST.get('nombre','Torneo')
        # Construir resumen
        resumen = {'deportes': []}
        for dep_code, dep_name in DEPORTE_CHOICES:
            for ciclo_code, ciclo_name in CICLO_CHOICES:
                generos_dep = GENEROS_POR_DEPORTE.get(dep_code,['X'])
                for gen in generos_dep:
                    tablas, finales, podio = _tabla_completa(ciclo_code, dep_code, gen)
                    if not tablas and not finales: continue
                    top_g = list(_top_goles(dep_code, ciclo_code, gen if gen!='X' else None, 3))
                    resumen['deportes'].append({
                        'deporte': dep_name, 'ciclo': ciclo_name, 'genero': gen,
                        'campeon': podio['primero'].nombre_corto() if podio and podio.get('primero') else None,
                        'campeon_pais': podio['primero'].pais if podio and podio.get('primero') else None,
                        'segundo': podio['segundo'].nombre_corto() if podio and podio.get('segundo') else None,
                        'tercero': podio['tercero'].nombre_corto() if podio and podio.get('tercero') else None,
                        'max_goleador': f"{top_g[0]['jugador__nombre']} {top_g[0]['jugador__apellido']} ({top_g[0]['total']} goles)" if top_g else None,
                    })
        TorneoHistorico.objects.create(
            nombre=nombre, año=int(año), resumen_json=json.dumps(resumen))

        if 'reset_completo' in request.POST:
            # Borrar todo excepto jugadores y grados
            EventoPartido.objects.all().delete()
            SetVoleibol.objects.all().delete()
            Partido.objects.all().delete()
            GrupoTorneo.objects.all().delete()
            InscripcionJugador.objects.all().delete()
            messages.success(request,'✅ Torneo cerrado y reseteado. Jugadores conservados.')
        else:
            messages.success(request,'✅ Resumen del torneo guardado.')
        return redirect('admin_dashboard')

    from django.utils import timezone as tz
    return render(request,'core/admin_cerrar_torneo.html',{'cfg':cfg,'now':tz.now()})

# ── Registro jugadores finalizado ─────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def admin_finalizar_registro(request):
    if request.method == 'POST':
        # Borrar jugadores que no están inscritos en ningún equipo
        sin_inscripcion = Jugador.objects.filter(inscripciones__isnull=True)
        n = sin_inscripcion.count()
        sin_inscripcion.delete()
        messages.success(request, f'✅ Registro finalizado. {n} jugadores sin inscripción eliminados.')
        return redirect('admin_jugadores')
    jugadores_sin = Jugador.objects.filter(inscripciones__isnull=True).count()
    return render(request,'core/admin_finalizar_registro.html',
                  {'cfg':get_config(),'jugadores_sin':jugadores_sin})

# ── Reglas CRUD ───────────────────────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def admin_reglas(request):
    return render(request,'core/admin_reglas.html',
                  {'reglas':ReglaDeporte.objects.all(),'cfg':get_config()})

@login_required
@user_passes_test(is_admin)
def admin_regla_form(request, pk=None):
    obj  = get_object_or_404(ReglaDeporte,pk=pk) if pk else None
    form = ReglaDeporteForm(request.POST or None, request.FILES or None, instance=obj)
    if form.is_valid():
        form.save(); messages.success(request,'✅ Regla guardada.')
        return redirect('admin_reglas')
    return render(request,'core/admin_regla_form.html',{'form':form,'obj':obj,'cfg':get_config()})

@login_required
@user_passes_test(is_admin)
def admin_regla_eliminar(request, pk):
    obj = get_object_or_404(ReglaDeporte,pk=pk)
    if request.method == 'POST':
        obj.delete(); messages.success(request,'🗑️ Eliminada.')
        return redirect('admin_reglas')
    return render(request,'core/confirmar_eliminar.html',
                  {'objeto':obj,'volver':'admin_reglas','cfg':get_config()})

# ── Carrusel CRUD ─────────────────────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def admin_carrusel(request):
    return render(request,'core/admin_carrusel.html',
                  {'imgs':ImagenCarrusel.objects.all(),'cfg':get_config()})

@login_required
@user_passes_test(is_admin)
def admin_carrusel_crear(request):
    form = ImagenCarruselForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save(); messages.success(request,'✅ Imagen agregada.')
        return redirect('admin_carrusel')
    return render(request,'core/admin_carrusel_form.html',
                  {'form':form,'titulo':'Agregar Imagen','cfg':get_config()})

@login_required
@user_passes_test(is_admin)
def admin_carrusel_editar(request, pk):
    img  = get_object_or_404(ImagenCarrusel,pk=pk)
    form = ImagenCarruselForm(request.POST or None, request.FILES or None, instance=img)
    if form.is_valid():
        form.save(); messages.success(request,'✅ Actualizada.')
        return redirect('admin_carrusel')
    return render(request,'core/admin_carrusel_form.html',
                  {'form':form,'titulo':'Editar Imagen','cfg':get_config()})

@login_required
@user_passes_test(is_admin)
def admin_carrusel_eliminar(request, pk):
    img = get_object_or_404(ImagenCarrusel,pk=pk)
    if request.method == 'POST':
        img.delete(); messages.success(request,'🗑️ Eliminada.')
        return redirect('admin_carrusel')
    return render(request,'core/confirmar_eliminar.html',
                  {'objeto':img,'volver':'admin_carrusel','cfg':get_config()})

# ── Configuración ─────────────────────────────────────────────────────────────
@login_required
@user_passes_test(is_admin)
def admin_configuracion(request):
    cfg  = get_config()
    form = ConfigForm(request.POST or None, instance=cfg)
    if form.is_valid():
        form.save(); messages.success(request,'✅ Configuración guardada.')
        return redirect('admin_configuracion')
    return render(request,'core/admin_configuracion.html',{'cfg':cfg,'form':form})



@login_required
@user_passes_test(is_admin)
def admin_paises(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'crear':
            nombre = request.POST.get('nombre','').strip()
            emoji  = request.POST.get('emoji','🌍').strip()
            if nombre:
                PaisParticipante.objects.get_or_create(nombre=nombre, defaults={'emoji':emoji,'activo':True})
                messages.success(request, f'✅ País "{nombre}" agregado.')
        elif action == 'toggle':
            pk = request.POST.get('pk')
            p  = get_object_or_404(PaisParticipante, pk=pk)
            p.activo = not p.activo; p.save()
            return JsonResponse({'ok':True,'activo':p.activo})
        elif action == 'eliminar':
            pk = request.POST.get('pk')
            get_object_or_404(PaisParticipante, pk=pk).delete()
            messages.success(request, '🗑️ País eliminado.')
        elif action == 'editar':
            pk     = request.POST.get('pk')
            nombre = request.POST.get('nombre','').strip()
            emoji  = request.POST.get('emoji','🌍').strip()
            p = get_object_or_404(PaisParticipante, pk=pk)
            p.nombre = nombre; p.emoji = emoji; p.save()
            return JsonResponse({'ok':True})
        elif action == 'seed':
            # Poblar desde PAIS_LIST si la tabla está vacía
            if not PaisParticipante.objects.exists():
                EMOJIS = {
                    'Argentina':'🇦🇷','Brasil':'🇧🇷','Francia':'🇫🇷','Alemania':'🇩🇪',
                    'España':'🇪🇸','Italia':'🇮🇹','Inglaterra':'🏴󠁧󠁢󠁥󠁮󠁧󠁿','Portugal':'🇵🇹',
                    'Holanda':'🇳🇱','Bélgica':'🇧🇪','Croacia':'🇭🇷','Uruguay':'🇺🇾',
                    'Colombia':'🇨🇴','México':'🇲🇽','Japón':'🇯🇵','Marruecos':'🇲🇦',
                    'Senegal':'🇸🇳','Ghana':'🇬🇭','Australia':'🇦🇺','Corea del Sur':'🇰🇷',
                    'Polonia':'🇵🇱','Suiza':'🇨🇭','Dinamarca':'🇩🇰','Suecia':'🇸🇪',
                    'Estados Unidos':'🇺🇸','Canadá':'🇨🇦','Ecuador':'🇪🇨','Perú':'🇵🇪',
                    'Chile':'🇨🇱','Paraguay':'🇵🇾','Camerún':'🇨🇲','Nigeria':'🇳🇬',
                    'Túnez':'🇹🇳','Arabia Saudita':'🇸🇦','Irán':'🇮🇷','Serbia':'🇷🇸',
                }
                for i,nombre in enumerate(PAIS_LIST):
                    PaisParticipante.objects.create(nombre=nombre,emoji=EMOJIS.get(nombre,'🌍'),orden=i)
                messages.success(request,'✅ Lista inicial cargada.')
            else:
                messages.info(request,'ℹ️ Ya existen países configurados.')
        return redirect('admin_paises')

    paises = PaisParticipante.objects.all()
    return render(request,'core/admin_paises.html',{
        'paises':paises,'cfg':get_config()
    })

# ══════════════════════════════════════
# Context processor global
# ══════════════════════════════════════
def global_context(request):
    """Inyecta variables disponibles en todos los templates."""
    from .models import CICLO_CHOICES, DEPORTE_CHOICES
    return {
        'ciclos': CICLO_CHOICES,
        'deportes': DEPORTE_CHOICES,
    }
