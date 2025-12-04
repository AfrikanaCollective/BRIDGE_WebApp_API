from django.db import migrations
from django.contrib.auth.hashers import make_password

def create_default_user(apps, schema_editor):
    User = apps.get_model("api", "CustomUser")  # <-- use your app + model name
    UserType = apps.get_model("api", "UserType")

    # Ensure a default user type exists (create or fetch)
    user_type, _ = UserType.objects.get_or_create(
        code="DM",
        defaults={"description": "Program Data Manager"}
    )

    if not User.objects.filter(username="bridge").exists():
        User.objects.create(
            username="bridge",
            email="tuti.collaborate@gmail.com",
            first_name="Timothy",
            last_name="Tuti",
            phone="+254736262966",
            is_staff=True,
            is_superuser=True,
            user_type=user_type,
            password=make_password("@Dmin2o13!"),  # securely hash password
        )

def delete_default_user(apps, schema_editor):
    User = apps.get_model("api", "CustomUser")
    User.objects.filter(username="bridge").delete()

class Migration(migrations.Migration):

    dependencies = [
        ("api", "0002_auto_populate_data"),  # adjust accordingly
    ]

    operations = [
        migrations.RunPython(create_default_user, delete_default_user),
    ]