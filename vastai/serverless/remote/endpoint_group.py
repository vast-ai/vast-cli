import logging
import os
import requests


debug = os.getenv("VAST_DEBUG", "") == "1"
log = logging.getLogger("EndpointGroup")

if debug and not any(isinstance(h, logging.StreamHandler) for h in log.handlers):
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(asctime)s] %(name)s - %(levelname)s - %(message)s'))
    handler.setLevel(logging.DEBUG)
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)
    log.propagate = False


class EndpointGroup:
    WEBSERVER_URL = "https://console.vast.ai"

    def __init__(
        self,
        api_key: str,
        endpoint_name: str,
        cold_mult: int = 3,
        min_workers: int = 5,
        max_workers: int = 16,
        min_load: int = 1,
        min_cold_load: int = 0,
        target_util: float = 0.9,
        autoscaler_instance: str = "",
    ):
        self.api_key = api_key
        self.endpoint_name = endpoint_name
        self.cold_mult = cold_mult
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.min_load = min_load
        self.min_cold_load = min_cold_load
        self.target_util = target_util
        self.autoscaler_instance = autoscaler_instance

    def create_endpoint_group(self):
        try:
            request_body = {
                "endpoint_name": self.endpoint_name,
                "cold_mult": self.cold_mult,
                "cold_workers": self.min_workers,
                "max_workers": self.max_workers,
                "min_load": self.min_load,
                "min_cold_load": self.min_cold_load,
                "target_util": self.target_util,
                "autoscaler_instance": self.autoscaler_instance,
            }
            headers = {"Authorization": f"Bearer {self.api_key}"}

            log.debug(f"POST {self.WEBSERVER_URL}/api/v0/endptjobs/")
            log.debug(f"Request body: {request_body}")

            response = requests.post(
                url=f"{self.WEBSERVER_URL}/api/v0/endptjobs/",
                json=request_body,
                headers=headers,
            )
            log.debug(f"Response status: {response.status_code}")
            log.debug(f"Response body: {response.text}")
            response.raise_for_status()

            result = response.json()["result"]
            log.debug(f"Endpoint group created with ID: {result}")
            return result
        except Exception as ex:
            log.error(f"Failed to create endpoint group: {ex}")
            raise RuntimeError(f"Failed to create endpoint group: {ex}")

    def teardown_endpoint_group(self):
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}

            log.debug(f"GET {self.WEBSERVER_URL}/api/v0/endptjobs/")
            endpoint_jobs_response = requests.get(url=f"{self.WEBSERVER_URL}/api/v0/endptjobs/", headers=headers)
            log.debug(f"Response status: {endpoint_jobs_response.status_code}")
            endpoint_jobs_response.raise_for_status()

            endpoint_job_id = None
            for result in endpoint_jobs_response.json()["results"]:
                if result["endpoint_name"] == self.endpoint_name:
                    endpoint_job_id = result["id"]
                    log.debug(f"Found endpoint job ID: {endpoint_job_id} for endpoint '{self.endpoint_name}'")
                    break

            if endpoint_job_id is None:
                log.warning(f"No endpoint job found for endpoint '{self.endpoint_name}'")
                return

            log.debug(f"DELETE {self.WEBSERVER_URL}/api/v0/endptjobs/{endpoint_job_id}/")
            response = requests.delete(
                url=f"{self.WEBSERVER_URL}/api/v0/endptjobs/{endpoint_job_id}/",
                headers=headers,
            )
            log.debug(f"Response status: {response.status_code}")
            response.raise_for_status()
            log.debug(f"Endpoint group {endpoint_job_id} deleted successfully")

        except Exception as ex:
            log.error(f"Failed to teardown endpoint group: {ex}")
            raise RuntimeError(f"Failed to teardown endpoint group: {ex}")
