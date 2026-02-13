import asyncio
from vastai import Serverless, ServerlessRequest
import random

COST_PER_REQUEST = 100

async def main():
    async with Serverless() as client:
        endpoint = await client.get_endpoint(name="my-comfy-endpoint")

        payload = {
            "input": {
                "modifier": "Text2Image",
                "modifications": {
                    "prompt": "Generate a page from a peanuts comic strip.",
                    "width": 512,
                    "height": 512,
                    "steps": 10,
                    "seed": random.randint(1, 1000)
                }
            }
        }
        
        responses = []

        CUR_LOAD = 300
        while True:
            # Create a ServerlessRequest object to attach callbacks before submitting the request
            req = ServerlessRequest()
            # Attach a callback to run when the machine finished work on the request
            def work_finished_callback(response):
                print(f"{len([x for x in responses if x.status != "Complete"])} in flight")    
            req.then(work_finished_callback)
            responses.append(endpoint.request(route="/generate/sync", payload=payload, serverless_request=req, cost=COST_PER_REQUEST))
            await asyncio.sleep(COST_PER_REQUEST / CUR_LOAD)

if __name__ == "__main__":
    asyncio.run(main())