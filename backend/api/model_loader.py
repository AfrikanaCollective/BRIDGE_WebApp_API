import os
import tensorflow as tf
from django.conf import settings
from celery.signals import worker_process_init

import logging, logging.config
logging.config.dictConfig(settings.LOGGING)


_omr_model = None
_omr_infer_fn = None

_ocr_model = None
_ocr_infer_fn = None

#
# At a later stage, convert the method to Model Server (TF Serving)
#
#
#
#
#

def get_omr_model(signature_name='serving_default'):
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1" # Force CPU use
    global _omr_model, _omr_infer_fn

    if _omr_model is None:
        _omr_model = tf.saved_model.load(settings.OMR_MODEL_PATH) 
        _omr_infer_fn = _omr_model.signatures[signature_name]

    return _omr_infer_fn


def get_ocr_model(signature_name='serving_default'):
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1" # Force CPU use
    global _ocr_model, _ocr_infer_fn

    if _ocr_model is None:
        _ocr_model = tf.saved_model.load(settings.OCR_MODEL_PATH) 
        _ocr_infer_fn = _ocr_model.signatures[signature_name]

    return _ocr_infer_fn


@worker_process_init.connect
def load_models(**kwargs):

    import os
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1" # Force CPU use

    get_omr_model()
    get_ocr_model()
    logging.info("OMR and OCR models loaded in worker process")