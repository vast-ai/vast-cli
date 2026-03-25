import asyncio
from vastai import Serverless
import random

async def main():
    async with Serverless(instance="alpha", debug=True) as client:
        endpoint = await client.get_endpoint(name="my-comfy-endpoint")
        session = await endpoint.session(cost=100, lifetime=30)
        payload = lambda : {
            "input": {
                "modifier": "Text2Image",
                "modifications": {
                    "prompt": "Generate a page from a peanuts comic strip.",
                    "width": 512,
                    "height": 512,
                    "steps": 10,
                    "seed": random.randint(1, 1000)
                },
                "webhook": {
                    "url": "http://localhost:3001/session/end",
                    "extra_params": {
                        "session_id": session.session_id,
                        "session_auth" : session.auth_data
                    }
                }
            }
        }
        # This test allows us to test:
        # - Session creation
        # - Session async request handlign
        # - Closing sessions with webhooks
        # - Error handling for requests on closed sessions
        # The expected result is to see the first request succeed,
        # and the second request fail due to the closed session.
        try:
            response = await session.request("/generate", payload())
            if not response.get("ok"):
                print(f"Request failed: {response.get('text')}")
            else:
                print("Request succeeded")
        except Exception as ex:
            print(f"Request failed: {ex}")

        await asyncio.sleep(5)
        try:
            response = await session.request("/generate", payload())
            if not response.get("ok"):
                print(f"Request failed: {response.get('text')}")
            else:
                print("Request succeeded")
        except Exception as ex:
            print(f"Request failed: {ex}")
            

if __name__ == "__main__":
    asyncio.run(main())