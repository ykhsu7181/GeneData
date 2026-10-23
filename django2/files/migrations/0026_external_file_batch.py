from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('files', '0025_alter_datafile_file_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExternalFileBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('batch_id', models.CharField(db_index=True, max_length=64, unique=True)),
                ('name', models.CharField(blank=True, max_length=255)),
                ('token_prefix_snapshot', models.CharField(max_length=16)),
                ('status', models.CharField(choices=[('ready', 'Ready'), ('partial', 'Partial')], max_length=20)),
                ('strict', models.BooleanField(default=True)),
                ('request_fingerprint', models.CharField(db_index=True, max_length=64)),
                ('idempotency_hash', models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ('file_count', models.PositiveIntegerField(default=0)),
                ('total_size', models.BigIntegerField(default=0)),
                ('snapshot_sha256', models.CharField(max_length=64)),
                ('resolution_summary', models.JSONField(default=dict)),
                ('expires_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by_token', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='external_file_batches', to='files.dataaccesstoken')),
            ],
            options={
                'db_table': 'external_file_batch',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.CreateModel(
            name='ExternalFileBatchItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.PositiveIntegerField()),
                ('file_code', models.CharField(max_length=100)),
                ('file_name', models.CharField(max_length=255)),
                ('content_version', models.CharField(max_length=80)),
                ('size', models.BigIntegerField()),
                ('sha256', models.CharField(max_length=64)),
                ('file_format', models.CharField(blank=True, max_length=50)),
                ('role', models.CharField(blank=True, max_length=100)),
                ('accession', models.CharField(blank=True, max_length=100)),
                ('assembly', models.CharField(blank=True, max_length=100)),
                ('dataset', models.CharField(blank=True, max_length=100)),
                ('roles', models.JSONField(default=list)),
                ('accessions', models.JSONField(default=list)),
                ('assemblies', models.JSONField(default=list)),
                ('datasets', models.JSONField(default=list)),
                ('content_url', models.CharField(max_length=500)),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='files.externalfilebatch')),
                ('data_file', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='external_batch_items', to='files.datafile')),
            ],
            options={
                'db_table': 'external_file_batch_item',
                'ordering': ['position', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='externalfilebatchitem',
            constraint=models.UniqueConstraint(fields=('batch', 'position'), name='uniq_external_batch_position'),
        ),
        migrations.AddConstraint(
            model_name='externalfilebatchitem',
            constraint=models.UniqueConstraint(fields=('batch', 'file_code'), name='uniq_external_batch_file_code'),
        ),
    ]
