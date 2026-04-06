import logging
import os
import requests
import time


debug = os.getenv("VAST_DEBUG", "") == "1"
log = logging.getLogger("WorkerGroup")

if debug and not any(isinstance(h, logging.StreamHandler) for h in log.handlers):
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(asctime)s] %(name)s - %(levelname)s - %(message)s'))
    handler.setLevel(logging.DEBUG)
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)
    log.propagate = False


class WorkerGroup:
    WEBSERVER_URL = "https://console.vast.ai"
    AUTOSCALER_URL = "https://run.vast.ai/"

    def __init__(
        self,
        api_key: str,
        cold_mult: int,
        endpoint_id: int,
        endpoint_name: str,
        min_load: int,
        search_params: str,
        target_util: float,
        template_id: int,
        autoscaler_instance: str = "",
    ):
        self.api_key = api_key
        self.cold_mult = cold_mult
        self.endpoint_id = endpoint_id
        self.endpoint_name = endpoint_name
        self.min_load = min_load
        self.search_params = search_params
        self.target_util = target_util
        self.template_id = template_id
        self.autoscaler_instance = autoscaler_instance

    def create_worker_group(self):
        try:
            request_body = {
                "cold_mult": self.cold_mult,
                "endpoint_id": self.endpoint_id,
                "endpoint_name": self.endpoint_name,
                "min_load": self.min_load,
                "search_params": self.search_params,
                "target_util": self.target_util,
                "template_id": self.template_id,
                "autoscaler_instance": self.autoscaler_instance,
            }
            headers = {"Authorization": f"Bearer {self.api_key}"}

            log.debug(f"POST {self.WEBSERVER_URL}/api/v0/autojobs/")
            log.debug(f"Request body: {request_body}")

            response = requests.post(
                url=f"{self.WEBSERVER_URL}/api/v0/autojobs/",
                json=request_body,
                headers=headers,
            )
            log.debug(f"Response status: {response.status_code}")
            log.debug(f"Response body: {response.text}")

            result = response.json()["id"]
            log.debug(f"Worker group created with ID: {result}")
            return result
        except Exception as ex:
            log.error(f"Failed to create worker group: {ex}")
            raise RuntimeError(f"Failed to create worker group: {ex}")

    def check_worker_group_status(self, max_attempts: int = 60) -> bool:
        try:
            request_body = {"id": self.endpoint_id, "api_key": self.api_key}
            max_attempts = 60
            log.debug(f"Waiting for workers to become ready (max {max_attempts} attempts)...")
            time.sleep(5)  # INFO: ensures autoscaler has the info to be parsed
            for attempt in range(max_attempts):
                try:
                    log.debug(f"Polling worker status (attempt {attempt + 1}/{max_attempts})...")
                    response = requests.post(url=f"{self.AUTOSCALER_URL}/get_endpoint_workers/", json=request_body)
                    response.raise_for_status()

                    workers = response.json()
                    log.debug(f"Found {len(workers)} workers: {workers}")

                    for worker in workers:
                        # Handle both dict and string responses
                        if isinstance(worker, dict):
                            status = worker.get("status", "unknown")
                        else:
                            status = str(worker)
                        log.debug(f"Worker status: {status}")
                        if status == "idle":
                            log.debug("Worker is idle and ready")
                            return True
                except Exception as ex:
                    log.debug(f"Poll attempt failed: {ex}")

                time.sleep(5)

            log.warning(f"Workers did not become ready after {max_attempts} attempts")
            return False
        except Exception as ex:
            log.error(f"Failed to check worker group status: {ex}")
            raise RuntimeError(f"Failed to check workergroup group status: {ex}")
