from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_eventos_config_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='imagencarrusel',
            name='posicion',
            field=models.CharField(
                choices=[
                    ('center center', 'Centro (por defecto)'),
                    ('center top',    'Arriba'),
                    ('center bottom', 'Abajo'),
                    ('left center',   'Izquierda'),
                    ('right center',  'Derecha'),
                    ('center 25%',    'Cuarto superior'),
                    ('center 75%',    'Cuarto inferior'),
                ],
                default='center center',
                help_text='Parte de la imagen que queda visible',
                max_length=30,
            ),
        ),
    ]
