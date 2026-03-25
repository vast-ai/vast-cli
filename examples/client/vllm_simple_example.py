import asyncio
from vastai import Serverless

MAX_TOKENS = 128

async def main():
    async with Serverless() as client:
        endpoint = await client.get_endpoint(name="my-vllm-endpoint")

        payload = {
            "model": "Qwen/Qwen3-8B",
            "prompt" : "Who are you?",
            "max_tokens" : MAX_TOKENS,
            "temperature" : 0.7
        }
        
        try:
            result = await endpoint.request("/v1/completions", payload, cost=MAX_TOKENS)
            if result["ok"]:
                # Success path
                print(result["response"]["choices"][0]["text"])
            else:
                # Request failed (HTTP error)
                print(f"Request failed. Status={result.get('status')}, Msg={result.get('text')}")
        except Exception as ex:
            # Exception raised (transport error, invalid JSON, etc.)
            print(f"Request failed with exception: {ex}")

if __name__ == "__main__":
    asyncio.run(main())