from uuid import uuid4

from locust import HttpUser, between, task
from typing_extensions import override


class CiteOrDieUser(HttpUser):
    wait_time = between(1, 3)

    @override
    def on_start(self) -> None:
        response = self.client.post(
            "/dev/token", data={"tenant_id": f"load-{uuid4().hex}", "subject": "locust"}
        )
        response.raise_for_status()
        self.token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {self.token}"}
        upload = self.client.post(
            "/upload",
            files={
                "file": ("load.txt", b"Load testing source text for cite-or-die.", "text/plain")
            },
            headers=headers,
        )
        upload.raise_for_status()

    @task
    def chat(self) -> None:
        with self.client.post(
            "/chat",
            json={"question": "What is this source for?"},
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
        ) as response:
            if response.status_code != 200 or not response.json().get("citations"):
                response.failure("Chat did not return a successful cited answer")
