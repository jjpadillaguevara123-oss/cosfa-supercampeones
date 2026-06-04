from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_add_pais_participante'),
    ]

    operations = [
        # EventoPartido: add minuto field + update tipo choices
        migrations.AddField(
            model_name='eventopartido',
            name='minuto',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Minuto'),
        ),
        migrations.AlterField(
            model_name='eventopartido',
            name='tipo',
            field=models.CharField(
                choices=[('gol','Gol'),('amarilla','Tarjeta Amarilla'),('roja','Tarjeta Roja')],
                default='gol', max_length=20
            ),
        ),
        # ConfiguracionSistema: add modo_oscuro + paises_sorteo
        migrations.AddField(
            model_name='configuracionsistema',
            name='modo_oscuro',
            field=models.BooleanField(default=False, verbose_name='Modo Oscuro por Defecto'),
        ),
        migrations.AddField(
            model_name='configuracionsistema',
            name='paises_sorteo',
            field=models.TextField(blank=True, default='', verbose_name='Países para Sorteo (uno por línea)'),
        ),
    ]
