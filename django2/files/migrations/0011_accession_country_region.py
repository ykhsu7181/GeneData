from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("files", "0010_backfill_default_assembly_annotation"),
    ]

    operations = [
        migrations.AddField(
            model_name="accession",
            name="country",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="accession",
            name="region",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
