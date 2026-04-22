from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('files', '0013_accession_genetic_stock_id_assembly_metadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='assembly',
            name='display_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='assembly',
            name='standard_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='annotation',
            name='display_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='annotation',
            name='release_version',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='annotation',
            name='source_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='annotation',
            name='standard_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
