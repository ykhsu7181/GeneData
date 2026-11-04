from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("files", "0024_datafile_access_policy_and_token"),
    ]

    operations = [
        migrations.DeleteModel(
            name="GenomeFile",
        ),
    ]
