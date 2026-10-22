from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('files', '0026_external_file_batch'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExternalFileArchive',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('archive_id', models.CharField(db_index=True, max_length=64, unique=True)),
                ('token_prefix_snapshot', models.CharField(max_length=16)),
                ('archive_format', models.CharField(choices=[('zip', 'ZIP'), ('tar.gz', 'TAR.GZ')], max_length=10)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('running', 'Running'), ('ready', 'Ready'), ('failed', 'Failed'), ('expired', 'Expired')], db_index=True, default='queued', max_length=20)),
                ('request_fingerprint', models.CharField(db_index=True, max_length=64)),
                ('idempotency_hash', models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ('archive_name', models.CharField(max_length=255)),
                ('output_relative_path', models.CharField(blank=True, max_length=500)),
                ('file_count', models.PositiveIntegerField(default=0)),
                ('total_input_size', models.BigIntegerField(default=0)),
                ('archive_size', models.BigIntegerField(blank=True, null=True)),
                ('archive_sha256', models.CharField(blank=True, max_length=64)),
                ('attempt_count', models.PositiveIntegerField(default=0)),
                ('error_code', models.CharField(blank=True, max_length=100)),
                ('error_detail', models.CharField(blank=True, max_length=500)),
                ('expires_at', models.DateTimeField()),
                ('queued_at', models.DateTimeField(auto_now_add=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='archives', to='files.externalfilebatch')),
                ('created_by_token', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='external_file_archives', to='files.dataaccesstoken')),
            ],
            options={
                'db_table': 'external_file_archive',
                'ordering': ['-queued_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='externalfilearchive',
            index=models.Index(fields=['status', 'queued_at'], name='ext_archive_status_queue'),
        ),
    ]
