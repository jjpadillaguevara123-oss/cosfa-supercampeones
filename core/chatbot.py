"""CosfaBot – contexto mínimo para reducir uso de tokens y evitar límite de cuota."""
from django.db.models import Count

def build_context():
    from .models import Grado, Jugador, Partido, EventoPartido
    lines = ["=== TORNEO COSFA SUPERCAMPEONES ==="]
    # Solo grados con país
    lines.append("\n## GRADOS Y PAÍSES")
    for g in Grado.objects.filter(pais__isnull=False).exclude(pais='').order_by('grado','grupo')[:20]:
        lines.append(f"{g}: {g.pais} (Ciclo {g.ciclo()})")
    # Stats básicas
    total_j = Jugador.objects.count()
    total_p = Partido.objects.filter(jugado=True).count()
    total_g = EventoPartido.objects.filter(tipo='gol').count()
    lines.append(f"\n## RESUMEN\nJugadores: {total_j} | Partidos jugados: {total_p} | Goles: {total_g}")
    # Top 5 goleadores
    lines.append("\n## TOP GOLEADORES")
    for ev in (EventoPartido.objects.filter(tipo='gol')
               .values('jugador__nombre','jugador__apellido','jugador__grado__pais')
               .annotate(t=Count('id')).order_by('-t')[:5]):
        lines.append(f"- {ev['jugador__nombre']} {ev['jugador__apellido']} ({ev['jugador__grado__pais'] or '?'}): {ev['t']} goles")
    # Próximos partidos
    from django.utils import timezone
    lines.append("\n## PRÓXIMOS PARTIDOS")
    for p in Partido.objects.filter(jugado=False, fecha__gte=timezone.now().date()).order_by('fecha')[:6]:
        lines.append(f"- {p.fecha}: {p.equipo_local.nombre_corto()} vs {p.equipo_visitante.nombre_corto()} [{p.get_deporte_display()}]")
    # Resultados recientes
    lines.append("\n## RESULTADOS RECIENTES")
    for p in Partido.objects.filter(jugado=True).order_by('-fecha')[:6]:
        lines.append(f"- {p.equipo_local.nombre_corto()} {p.puntos_local}-{p.puntos_visitante} {p.equipo_visitante.nombre_corto()} [{p.get_deporte_display()}]")
    return "\n".join(lines)

def ask_gemini(user_message: str, history: list, api_key: str) -> str:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        context = build_context()
        system = f"""Eres CosfaBot 🏆, asistente del torneo COSFA SUPERCAMPEONES.
Responde en español, amigable y conciso. Usa los datos del torneo.
No inventes estadísticas. Si no tienes el dato, dilo.

DATOS:
{context}"""
        contents = []
        for msg in history[-6:]:
            role = "user" if msg['role'] == 'user' else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg['text'])]))
        contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
        response = client.models.generate_content(
            model="gemini-1.5-flash-8b",  # modelo más pequeño = más cuota disponible
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=400,
                temperature=0.6,
            )
        )
        return response.text
    except Exception as e:
        err = str(e)
        if '429' in err or 'quota' in err.lower() or 'rate' in err.lower():
            return "⏳ Gemini está ocupado. Espera 15 segundos e intenta de nuevo."
        if 'api_key' in err.lower() or 'invalid' in err.lower():
            return "❌ API Key inválida. Ve a Panel → Configuración."
        return f"❌ Error: {err[:80]}"
