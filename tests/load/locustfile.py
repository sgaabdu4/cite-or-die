from locust import HttpUser, between, task


class CiteOrDieUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        response = self.client.post("/dev/token", data={"tenant_id": "load", "subject": "locust"})
        self.token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {self.token}"}
        self.client.post(
            "/upload",
            files={
                "file": ("load.txt", b"Load testing source text for cite-or-die.", "text/plain")
            },
            headers=headers,
        )

    @task
    def chat(self) -> None:
        self.client.post(
            "/chat",
            json={"question": "What is this source for?"},
            headers={"Authorization": f"Bearer {self.token}"},
        )
