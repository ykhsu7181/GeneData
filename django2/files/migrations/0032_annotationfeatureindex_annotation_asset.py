from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("files", "0031_dataasset_core_constraints")]

    operations = [
        migrations.AlterField(
            model_name="annotationfeatureindex",
            name="annotation",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="feature_index",
                to="files.annotation",
            ),
        ),
        migrations.AddField(
            model_name="annotationfeatureindex",
            name="annotation_asset",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="annotation_feature_index",
                to="files.dataasset",
            ),
        ),
        migrations.AddConstraint(
            model_name="annotationfeatureindex",
            constraint=models.CheckConstraint(
                check=(
                    Q(annotation__isnull=False, annotation_asset__isnull=True)
                    | Q(annotation__isnull=True, annotation_asset__isnull=False)
                ),
                name="annotation_index_single_target",
            ),
        ),
    ]
