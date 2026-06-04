# 🏆 COSFA Supercampeones – Sistema Escolar de Torneos

Sistema web completo en Django para gestión de torneos escolares.

---

## 🚀 INSTALACIÓN Y EJECUCIÓN (Paso a paso)

### Requisitos previos
- Python 3.10 o superior instalado
- pip actualizado

### 1. Instalar dependencias

```bash
pip install django pillow
```

### 2. Aplicar migraciones (base de datos)

```bash
cd cosfa_supercampeones
python manage.py migrate
```

### 3. Crear el superusuario administrador

```bash
python manage.py createsuperuser
```
> Ingresa un nombre de usuario, correo (opcional) y contraseña.
> Este usuario tendrá acceso completo al panel administrador.

**O usar los usuarios de prueba ya incluidos (si clonaste el proyecto con datos):**
| Usuario   | Contraseña   | Rol         |
|-----------|-------------|-------------|
| `admin`   | `admin123`  | Administrador |
| `usuario` | `usuario123`| Usuario normal |

### 4. Ejecutar el servidor

```bash
python manage.py runserver
```

### 5. Abrir en el navegador

```
http://127.0.0.1:8000/
```

---

## 📁 ESTRUCTURA DEL PROYECTO

```
cosfa_supercampeones/
├── cosfa_supercampeones/   ← Configuración principal Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                   ← App principal
│   ├── models.py           ← Modelos: Jugador, Equipo, Partido, etc.
│   ├── views.py            ← Toda la lógica de vistas
│   ├── urls.py             ← Rutas URL
│   ├── forms.py            ← Formularios
│   ├── admin.py            ← Panel admin de Django
│   └── templates/core/     ← Todos los HTML
│       ├── base.html
│       ├── login.html
│       ├── home.html
│       ├── admin_dashboard.html
│       ├── admin_jugadores.html
│       ├── admin_jugador_form.html
│       ├── admin_equipos.html
│       ├── admin_equipo_form.html
│       ├── admin_partidos.html
│       ├── admin_partido_form.html
│       ├── admin_grupos.html
│       ├── admin_grupo_form.html
│       ├── sorteo_paises.html
│       ├── ruleta.html
│       ├── perfil_jugador.html
│       ├── buscar.html
│       ├── estadisticas.html
│       ├── tabla_posiciones.html
│       ├── admin_configuracion.html
│       └── partials/sidebar.html
├── media/                  ← Fotos subidas (creada automáticamente)
├── db.sqlite3              ← Base de datos SQLite
└── manage.py
```

---

## 🎯 FUNCIONALIDADES

### Panel Administrador (`/panel/`)
- **Dashboard** con estadísticas en tiempo real
- **Jugadores**: Inscribir con T.I., nombre, apellido, deporte, camiseta, foto
- **Equipos**: Crear equipos por grado/grupo/género/deporte
- **Partidos**: Programar, registrar resultados y eventos (goles, asistencias)
- **Grupos**: Organizar equipos en grupos del torneo
- **🌍 Sorteo de Países**: Asigna países aleatoriamente (sin repetir por nivel)
- **🎯 Ruleta**: Sorteo visual animado con Canvas JS
- **⚙️ Configuración**: Personalizar títulos, colores y visibilidad

### Vista Usuario
- **Inicio**: Partidos del día, top goleadores y asistentes
- **Búsqueda**: Por nombre o T.I. con resultados por similitud
- **Perfil del Jugador**: Datos, estadísticas, historial de eventos
- **Estadísticas**: Tablas de goleadores, asistentes, mejor ataque/defensa
- **Tabla de Posiciones**: Por grupos con puntos, diferencia de goles

### Estructura Académica
- Ciclo I: 1° y 2° (grupos A y B)
- Ciclo II: 3°, 4° y 5° (grupos A y B)
- Ciclo III: 6°, 7° y 8° (7°, 8° con A, B, C)
- Ciclo IV: 9°, 10°, 11° y Profesores (9° con A, B, C)

---

## 🎨 DISEÑO

- **Tema**: Oscuro estilo Mundial de Fútbol
- **Tipografía**: Bebas Neue + Barlow Condensed
- **Colores**: Rojo (#C8102E), Azul (#003087), Dorado (#FFD700)
- **Animaciones**: Fade-in, hover effects, ruleta con Canvas
- **Responsive**: Adaptable a distintos tamaños de pantalla

---

## ⚙️ CONFIGURACIÓN ADICIONAL

Para producción, cambia en `settings.py`:
```python
DEBUG = False
SECRET_KEY = 'clave-secreta-segura-aqui'
ALLOWED_HOSTS = ['tu-dominio.com']
```

---
*COSFA Supercampeones © 2024 – Sistema Escolar de Torneos*
