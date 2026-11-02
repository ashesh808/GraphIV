"""In-memory Azure SDK-shaped transport for persistence contract tests."""

from types import SimpleNamespace

import pytest


class FakeService:
    def __init__(self):
        self.objects = {}
        self.downloads = []
        self.uploads = []
        self.fail_upload = None
        self.fail_download = None

    def get_blob_client(self, container, blob):
        service = self
        key = (container, blob)

        class Blob:
            def download_blob(self):
                service.downloads.append(key)
                if key not in service.objects:
                    raise FileNotFoundError(blob)
                value = service.objects[key]

                class Download:
                    def chunks(self):
                        middle = max(1, len(value) // 2)
                        yield value[:middle]
                        if service.fail_download and service.fail_download(key):
                            raise OSError("transport interrupted")
                        yield value[middle:]

                return Download()

            def upload_blob(self, data, overwrite=False, metadata=None):
                service.uploads.append(key)
                if service.fail_upload and service.fail_upload(key):
                    raise OSError("transport interrupted")
                if not overwrite and key in service.objects:
                    raise OSError("object exists")
                service.objects[key] = data if isinstance(data, bytes) else data.read()

        return Blob()

    def get_container_client(self, container):
        service = self

        class Container:
            def list_blobs(self, name_starts_with=""):
                return [
                    SimpleNamespace(name=name)
                    for held_container, name in service.objects
                    if held_container == container and name.startswith(name_starts_with)
                ]

        return Container()


@pytest.fixture
def fake_blobs():
    return FakeService()
