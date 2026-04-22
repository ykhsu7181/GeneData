# Generated manually for stage-one hierarchy support.

from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('files', '0008_genomefile_accession'),
    ]

    operations = [
        migrations.CreateModel(
            name='Assembly',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='default', max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_default', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('accession', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assemblies', to='files.accession', verbose_name='Accession')),
            ],
            options={
                'db_table': 'assembly',
                'ordering': ['accession__accession', '-is_default', 'name', 'id'],
            },
        ),
        migrations.CreateModel(
            name='Annotation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='default-annotation', max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('is_default', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assembly', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='annotations', to='files.assembly', verbose_name='Assembly')),
            ],
            options={
                'db_table': 'annotation',
                'ordering': ['assembly__accession__accession', 'assembly__name', '-is_default', 'name', 'id'],
            },
        ),
        migrations.AddField(
            model_name='genomefile',
            name='assembly',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='files', to='files.assembly', verbose_name='Assembly'),
        ),
        migrations.AddField(
            model_name='genomefile',
            name='annotation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='files', to='files.annotation', verbose_name='Annotation'),
        ),
        migrations.AddConstraint(
            model_name='assembly',
            constraint=models.UniqueConstraint(fields=('accession', 'name'), name='uniq_assembly_name_per_accession'),
        ),
        migrations.AddConstraint(
            model_name='assembly',
            constraint=models.UniqueConstraint(condition=Q(('is_default', True)), fields=('accession',), name='uniq_default_assembly_per_accession'),
        ),
        migrations.AddConstraint(
            model_name='annotation',
            constraint=models.UniqueConstraint(fields=('assembly', 'name'), name='uniq_annotation_name_per_assembly'),
        ),
        migrations.AddConstraint(
            model_name='annotation',
            constraint=models.UniqueConstraint(condition=Q(('is_default', True)), fields=('assembly',), name='uniq_default_annotation_per_assembly'),
        ),
    ]
