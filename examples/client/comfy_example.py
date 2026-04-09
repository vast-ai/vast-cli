import asyncio
from vastai import Serverless
import random

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
        try:
            result = await endpoint.request("/generate/sync", payload)
            if result["ok"]:
                print(result["response"]["output"][0]["local_path"])
            else:
                print(f"Request failed. Status={result.get("status")}, Msg={result.get("text")}")
        except Exception as ex:
            print(f"Request failed with exception: {ex}")

if __name__ == "__main__":
    asyncio.run(main())