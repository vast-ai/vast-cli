from .connection import _make_request

class Endpoint:
    name: str
    id: int

    def __repr__(self):
        return f"<Endpoint {self.name} (id={self.id})>"

    def __init__(self, client, name, id, api_key):
        if client is None:
            raise ValueError("Endpoint cannot be created without client reference")
        if not name:
            raise ValueError("Endpoint name cannot be empty")
        if id is None:
            raise ValueError("Endpoint id cannot be empty")
        self.client = client
        self.name = name
        self.id = id
        self.api_key = api_key

    def request(self, route, payload, serverless_request=None, cost: int = 100, retry: bool = True, stream: bool = False):
        """Forward requests to the parent client."""
        return self.client.queue_endpoint_request(
            endpoint=self,
            worker_route=route,
            worker_payload=payload,
            serverless_request=serverless_request,
            cost=cost,
            retry=retry,
            stream=stream
        )

    
    def get_workers(self):
        return self.client.get_endpoint_workers(self)

    async def _route(self, cost: float = 0.0, req_idx: int = 0, timeout: float = 60.0):
            if self.client is None or not self.client.is_open():
                raise ValueError("Client is invalid")
            try:
                response = await _make_request(
                    client=self.client,
                    url=self.client.autoscaler_url,
                    route="/route/",
                    api_key=self.api_key,
                    body={
                        "endpoint": self.name,
                        "api_key": self.api_key,
                        "cost": cost,
                        "request_idx": req_idx,
                        "replay_timeout": timeout,
                    },
                    method="POST",
                    timeout=max(10.0, timeout),
                )
            except Exception as ex:
                raise RuntimeError(f"Failed to route endpoint: {ex}") from ex
            return RouteResponse(response)
    
class RouteResponse:
    status: str
    body: dict
    request_idx: int
    def __repr__(self):
        return f"<RouteResponse status={self.status}>"

    def __init__(self, body: dict):
        if "request_idx" in body.keys():
            self.request_idx = body.get("request_idx")
        else:
            self.request_idx = 0
        if "url" in body.keys():
            self.status = "READY"
            self.body = body
        else:
            self.status = "WAITING"
            self.body = body
            
    def get_url(self):
        return self.body.get("url")
        