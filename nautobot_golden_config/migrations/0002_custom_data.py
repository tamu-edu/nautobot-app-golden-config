# Generated by Django 3.1.3 on 2021-02-22 01:27

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("nautobot_golden_config", "0001_initial"),
    ]

    def insertData(apps, schema_editor):
        GoldenConfigSetting = apps.get_model("nautobot_golden_config", "GoldenConfigSetting")
        global_settings = GoldenConfigSetting.objects.create()
        global_settings.save()

    operations = [
        migrations.RunPython(insertData),
    ]