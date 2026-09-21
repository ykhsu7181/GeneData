import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('files', '0020_assembly_detail_metadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='assembly',
            name='at_content',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)]),
        ),
        migrations.AddField(
            model_name='assembly',
            name='gap_count',
            field=models.BigIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AddField(
            model_name='assembly',
            name='n_count',
            field=models.BigIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AddField(
            model_name='assembly',
            name='n_percentage',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)]),
        ),
        migrations.AddField(
            model_name='assembly',
            name='sequence_count',
            field=models.IntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AddField(
            model_name='assembly',
            name='sequence_md5',
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
    ]
