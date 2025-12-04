from django_minio_backend import MinioBackend

# ✅ Custom backend that actually overwrites existing objects in MinIO
class OverwritingMinioBackend(MinioBackend):
    def save(self, name, content, max_length=None):
        # Delete existing file if replace_existing=True
        if self.replace_existing and self.exists(name):
            self.delete(name)
        return super().save(name, content, max_length=max_length)

class PdfsStorage(OverwritingMinioBackend):
    bucket_name = "pdfs"
    auto_create_bucket = True # create if not exists
    replace_existing = True # don’t overwrite existing files

class RawImageStorage(OverwritingMinioBackend):
    bucket_name = "raw_pdf_page_images"
    auto_create_bucket = True  # create if not exists
    replace_existing = True   # don’t overwrite existing files

    def get_object_parameters(self, name):
        params = super().get_object_parameters(name)
        if name.lower().endswith(".png"):
            params["ContentType"] = "image/png"
        elif name.lower().endswith(".jpg") or name.lower().endswith(".jpeg"):
            params["ContentType"] = "image/jpeg"
        return params

class ProcessedImageStorage(OverwritingMinioBackend):
    bucket_name = "processed_pdf_page_images"
    auto_create_bucket = True  # create if not exists
    replace_existing = True   # don’t overwrite existing files

    def get_object_parameters(self, name):
        params = super().get_object_parameters(name)
        if name.lower().endswith(".png"):
            params["ContentType"] = "image/png"
        elif name.lower().endswith(".jpg") or name.lower().endswith(".jpeg"):
            params["ContentType"] = "image/jpeg"
        return params

class AlignedImageStorage(OverwritingMinioBackend):
    bucket_name = "registered_pdf_page_images"
    auto_create_bucket = True  # create if not exists
    replace_existing = True   # don’t overwrite existing files

    def get_object_parameters(self, name):
        params = super().get_object_parameters(name)
        if name.lower().endswith(".png"):
            params["ContentType"] = "image/png"
        elif name.lower().endswith(".jpg") or name.lower().endswith(".jpeg"):
            params["ContentType"] = "image/jpeg"
        return params



