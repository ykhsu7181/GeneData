from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("files", "0021_assembly_fasta_statistics"),
    ]

    operations = [
        migrations.AddField(
            model_name="accession",
            name="view_count",
            field=models.PositiveBigIntegerField(db_index=True, default=0),
        ),
        migrations.AddField(
            model_name="accession",
            name="last_viewed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
