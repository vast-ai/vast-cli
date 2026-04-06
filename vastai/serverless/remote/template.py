from typing import Optional
import logging
import requests
import os
import json
import urllib.parse


debug = os.getenv("VAST_DEBUG", "") == "1"
log = logging.getLogger("Template")

if debug and not any(isinstance(h, logging.StreamHandler) for h in log.handlers):
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(asctime)s] %(name)s - %(levelname)s - %(message)s'))
    handler.setLevel(logging.DEBUG)
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)
    log.propagate = False


class Template:
    WEBSERVER_URL = "https://console.vast.ai"

    def __init__(
        self,
        api_key: str,
        image_name: Optional[str] = None,
        env_vars: Optional[dict] = None,
        disk_space: Optional[int] = None,
        template_name: Optional[str] = None,
        onstart_cmd: str = "",
        port : int = 3000,
    ):
        self.api_key = api_key
        self.name = template_name + "-endpoint" if template_name else f"template-{os.urandom(15)}-endpoint"
        self.image_name = image_name
        self.env_vars = env_vars
        self.disk_space = disk_space
        self.onstart_cmd = onstart_cmd

    def create_template(self):
        try:
            request_body = {
                "name": self.name,
                "image": self.image_name,
                "onstart": self.onstart_cmd,
                "recommended_disk_space": self.disk_space,
                "runtype": "ssh",
            }
            headers = {"Authorization": f"Bearer {self.api_key}"}
            env_vars_string = "-p 3000:3000"
            for name, val in self.env_vars.items():
                env_vars_string += f" -e {name}={val}"

            request_body["env"] = env_vars_string

            log.debug(f"POST {self.WEBSERVER_URL}/api/v0/template/")
            log.debug(f"Request body: {request_body}")

            response = requests.post(
                url=f"{self.WEBSERVER_URL}/api/v0/template/",
                json=request_body,
                headers=headers,
            )
            log.debug(f"Response status: {response.status_code}")
            log.debug(f"Response body: {response.text}")

            result = response.json()["template"]["id"]
            log.debug(f"Template created with ID: {result}")
            return result
        except Exception as ex:
            log.error(f"Failed to create template: {ex}")
            raise RuntimeError(f"Failed to create template: {ex}")

    def teardown_template(self):
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}

            order_by = [{"col": "created_at", "dir": "desc"}]
            limit = 60
            params = {
                "order_by": json.dumps(order_by),
                "limit": limit,
            }
            encoded_params = urllib.parse.urlencode(params)
            url = f"{self.WEBSERVER_URL}/api/v0/template/?{encoded_params}"

            log.debug(f"GET {url}")
            response = requests.get(url=url, headers=headers)
            log.debug(f"Response status: {response.status_code}")
            response.raise_for_status()

            template_id_to_delete = None
            for template in response.json()["templates"]:
                if "-endpoint" in template["name"]:
                    template_id_to_delete = template["id"]
                    log.debug(f"Found template to delete: {template['name']} (ID: {template_id_to_delete})")
                    break

            if template_id_to_delete is None:
                log.warning("No template with '-endpoint' suffix found to delete")
                return

            log.debug(f"DELETE {self.WEBSERVER_URL}/api/v0/template/ with template_id={template_id_to_delete}")
            response = requests.delete(url=f"{self.WEBSERVER_URL}/api/v0/template/", headers=headers, json={"template_id": template_id_to_delete})
            log.debug(f"Response status: {response.status_code}")
            response.raise_for_status()
            log.debug(f"Template {template_id_to_delete} deleted successfully")
        except Exception as ex:
            log.error(f"Failed to teardown template: {ex}")
            raise RuntimeError(f"Failed to teardown template: {ex}")
