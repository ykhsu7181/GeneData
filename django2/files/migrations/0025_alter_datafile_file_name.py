from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("files", "0024_datafile_access_policy_and_token"),
    ]

    operations = [
        migrations.AlterField(
            model_name="datafile",
            name="file_name",
            field=models.CharField(db_index=True, max_length=255),
        ),
    ]
