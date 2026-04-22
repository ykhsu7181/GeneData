from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('files', '0012_alter_genomefile_category_variableblocks'),
    ]

    operations = [
        migrations.AddField(
            model_name='accession',
            name='genetic_stock_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='assembly',
            name='bio_project',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='assembly',
            name='reference',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
