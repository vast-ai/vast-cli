import asyncio
from vastai import Serverless, ServerlessRequest

MAX_TOKENS = 128

async def main():
    async with Serverless() as client:
        endpoint = await client.get_endpoint(name="my-vllm-endpoint")

        payload = {
            "input" : {
                "model": "Qwen/Qwen3-8B",
                "prompt" : "Who are you?",
                "max_tokens" : MAX_TOKENS,
                "temperature" : 0.7
            }
        }
        
        # Create a ServerlessRequest object to attach callbacks before submitting the request
        req = ServerlessRequest()

        # Attach a callback to run when the machine finished work on the request
        def work_finished_callback(response):
            if response.get("ok"):
                print(f"Request finished. Got response of length {len(response['response']['choices'][0]['text'])}")
            else:
                print(f"Request failed in callback. Status={response.get('status')}")

        req.then(work_finished_callback)

        try:
            result = await endpoint.request(route="/v1/completions", payload=payload, serverless_request=req, cost=MAX_TOKENS)
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