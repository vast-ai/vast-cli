import asyncio
from vastai import Serverless

MAX_TOKENS = 128

async def main():
    async with Serverless() as client:
        endpoint = await client.get_endpoint(name="my-tgi-endpoint")

        prompt = "Who are you?"

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": MAX_TOKENS,
                "temperature": 0.7,
                "return_full_text": False
            }
        }

        resp = await endpoint.request("/generate", payload, cost=MAX_TOKENS)

        print(resp["response"]["generated_text"])

if __name__ == "__main__":
    asyncio.run(main())
