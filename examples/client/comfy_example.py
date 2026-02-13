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
        
        response = await endpoint.request("/generate/sync", payload)

        # Get the file from the path on the local machine using SCP or SFTP
        # or configure S3 to upload to cloud storage.
        print(response["response"]["output"][0]["local_path"])

if __name__ == "__main__":
    asyncio.run(main())