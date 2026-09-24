from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('files', '0022_accession_view_statistics')]

    operations = [
        migrations.CreateModel(
            name='AnnotationFeatureIndex',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('building', 'Building'), ('ready', 'Ready'), ('failed', 'Failed')], default='building', max_length=20)),
                ('source_file_size', models.BigIntegerField()),
                ('source_file_mtime_ns', models.BigIntegerField()),
                ('source_file_md5', models.CharField(blank=True, default='', max_length=64)),
                ('feature_count', models.BigIntegerField(default=0)),
                ('chromosomes', models.JSONField(default=list)),
                ('feature_types', models.JSONField(default=list)),
                ('error_message', models.TextField(blank=True, default='')),
                ('indexed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('annotation', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='feature_index', to='files.annotation')),
                ('source_file', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='annotation_feature_indexes', to='files.datafile')),
            ],
            options={'db_table': 'annotation_feature_index'},
        ),
        migrations.CreateModel(
            name='AnnotationFeature',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_line', models.BigIntegerField()),
                ('seqid', models.CharField(max_length=255)),
                ('source', models.CharField(blank=True, max_length=255, null=True)),
                ('feature', models.CharField(blank=True, max_length=100, null=True)),
                ('start', models.BigIntegerField()),
                ('end', models.BigIntegerField()),
                ('length', models.BigIntegerField()),
                ('score', models.CharField(blank=True, max_length=100, null=True)),
                ('strand', models.CharField(blank=True, max_length=10, null=True)),
                ('phase', models.CharField(blank=True, max_length=20, null=True)),
                ('attributes', models.JSONField(default=dict)),
                ('sequence_ontology', models.CharField(blank=True, max_length=100, null=True)),
                ('name', models.TextField(blank=True, null=True)),
                ('feature_index', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='features', to='files.annotationfeatureindex')),
            ],
            options={'db_table': 'annotation_feature', 'ordering': ['source_line', 'id']},
        ),
        migrations.AddIndex(model_name='annotationfeature', index=models.Index(fields=['feature_index', 'seqid', 'feature', 'start'], name='idx_af_seq_type_start')),
        migrations.AddIndex(model_name='annotationfeature', index=models.Index(fields=['feature_index', 'feature'], name='idx_af_feature_type')),
        migrations.AddIndex(model_name='annotationfeature', index=models.Index(fields=['feature_index', 'seqid', 'start', 'end'], name='idx_af_seq_interval')),
    ]
