import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bridge.settings')
os.environ["CUDA_VISIBLE_DEVICES"] = "-1" # Force CPU use

app = Celery('bridge')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')