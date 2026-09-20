import pytest
from botocore.exceptions import ClientError

from backend.app.store import RustFSStorage


def client_error(code: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": "test error"}},
        "HeadBucket",
    )


class FakeS3Client:
    def __init__(self, head_error: ClientError | None = None):
        self.head_error = head_error
        self.head_calls = 0
        self.created_buckets = []
        self.list_responses = []
        self.list_requests = []
        self.deleted_keys = []

    def head_bucket(self, **kwargs):
        self.head_calls += 1
        if self.head_error:
            raise self.head_error

    def create_bucket(self, **kwargs):
        self.created_buckets.append(kwargs["Bucket"])

    def list_objects_v2(self, **kwargs):
        self.list_requests.append(kwargs)
        return self.list_responses.pop(0)

    def delete_object(self, **kwargs):
        self.deleted_keys.append(kwargs["Key"])


def storage_with(client: FakeS3Client) -> RustFSStorage:
    storage = object.__new__(RustFSStorage)
    storage.bucket = "meeting-files"
    storage.client = client
    storage._ready = False
    return storage


@pytest.mark.parametrize("code", ["404", "NoSuchBucket", "NotFound"])
def test_ensure_bucket_creates_missing_bucket_once(code):
    client = FakeS3Client(client_error(code))
    storage = storage_with(client)

    storage._ensure_bucket()
    storage._ensure_bucket()

    assert client.head_calls == 1
    assert client.created_buckets == ["meeting-files"]
    assert storage._ready is True


def test_ensure_bucket_reuses_existing_bucket():
    client = FakeS3Client()
    storage = storage_with(client)

    storage._ensure_bucket()

    assert client.head_calls == 1
    assert client.created_buckets == []
    assert storage._ready is True


def test_ensure_bucket_does_not_hide_permission_errors():
    client = FakeS3Client(client_error("AccessDenied"))
    storage = storage_with(client)

    with pytest.raises(ClientError):
        storage._ensure_bucket()

    assert client.created_buckets == []
    assert storage._ready is False


def test_list_keys_reads_all_pages():
    client = FakeS3Client()
    client.list_responses = [
        {
            "Contents": [{"Key": "meetings/1.json"}],
            "IsTruncated": True,
            "NextContinuationToken": "next-page",
        },
        {"Contents": [{"Key": "meetings/2.json"}], "IsTruncated": False},
    ]
    storage = storage_with(client)

    keys = storage.list_keys("meetings/")

    assert keys == ["meetings/1.json", "meetings/2.json"]
    assert client.list_requests[1]["ContinuationToken"] == "next-page"


def test_delete_removes_object():
    client = FakeS3Client()
    storage = storage_with(client)

    storage.delete("meetings/1.json")

    assert client.deleted_keys == ["meetings/1.json"]
