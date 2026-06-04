"""
Script de configuración inicial para COSFA Supercampeones.
Ejecuta: python setup.py
"""
import os, sys, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cosfa_supercampeones.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth.models import User
from core.models import ConfiguracionSistema, Equipo

print("\n🏆 COSFA SUPERCAMPEONES – Configuración Inicial\n" + "="*50)

# Admin
admin_user = input("\n👤 Nombre de usuario ADMINISTRADOR [admin]: ").strip() or "admin"
admin_pass = input(f"🔑 Contraseña para '{admin_user}' [admin123]: ").strip() or "admin123"
if not User.objects.filter(username=admin_user).exists():
    User.objects.create_superuser(admin_user, f'{admin_user}@cosfa.edu.co', admin_pass)
    print(f"✅ Admin creado: {admin_user}")
else:
    print(f"⚠️  Usuario '{admin_user}' ya existe.")

# User
user_name = input("\n👤 Usuario NORMAL [usuario]: ").strip() or "usuario"
user_pass = input(f"🔑 Contraseña para '{user_name}' [usuario123]: ").strip() or "usuario123"
if not User.objects.filter(username=user_name).exists():
    User.objects.create_user(user_name, password=user_pass)
    print(f"✅ Usuario creado: {user_name}")
else:
    print(f"⚠️  Usuario '{user_name}' ya existe.")

# Config
cfg, _ = ConfiguracionSistema.objects.get_or_create(pk=1)
cfg.save()
print("\n✅ Configuración del sistema lista.")

# Equipos base
crear = input("\n¿Crear equipos base para todos los grados? [S/n]: ").strip().lower()
if crear != 'n':
    grados = ['1','2','3','4','5','6','7','8','9','10','11','P']
    grupos_por_grado = {
        '7': ['A','B','C'], '8': ['A','B','C'], '9': ['A','B','C']
    }
    created = 0
    for grado in grados:
        grupos = grupos_por_grado.get(grado, ['A','B'])
        for gr in grupos:
            for gen in ['M','F']:
                _, c = Equipo.objects.get_or_create(
                    grado=grado, grupo=gr, genero=gen, deporte='futbol'
                )
                if c: created += 1
    print(f"✅ {created} equipos creados ({Equipo.objects.count()} total).")

print(f"\n🚀 ¡Listo! Ejecuta: python manage.py runserver")
print(f"   Accede a: http://127.0.0.1:8000/")
print(f"   Admin: {admin_user} / {admin_pass}\n")
