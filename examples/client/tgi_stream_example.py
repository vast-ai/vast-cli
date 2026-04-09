import asyncio
from vastai import Serverless

MAX_TOKENS = 1024

def build_prompt(system_prompt: str, user_prompt: str) -> str:
    return (
        f"<<SYS>>\n{system_prompt.strip()}\n<</SYS>>\n\n"
        f"User: {user_prompt.strip()}\n"
        f"Assistant:"
    )

async def main():
    async with Serverless() as client:
        endpoint = await client.get_endpoint(name="my-tgi-endpoint")

        system_prompt = (
            "You are Qwen.\n"
            "You are to only speak in English.\n"
        )
        user_prompt = """
        Critically analyze the extent to which hotdogs are sandwiches.
        """

        prompt = build_prompt(system_prompt, user_prompt)

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": MAX_TOKENS,
                "temperature": 0.7,
                "do_sample": True,
                "return_full_text": False,
            }
        }

        try:
            result = await endpoint.request(
                "/generate_stream",
                payload,
                cost=MAX_TOKENS,
                stream=True,
            )
            if result["ok"]:
                # Success path - process the stream
                stream = result["response"]

                printed_answer = False
                async for event in stream:
                    tok = (event.get("token") or {}).get("text")
                    if tok:
                        if not printed_answer:
                            printed_answer = True
                            print("Answer:\n", end="", flush=True)
                        print(tok, end="", flush=True)
            else:
                # Request failed (HTTP error)
                print(f"Request failed. Status={result.get('status')}, Msg={result.get('text')}")
        except Exception as ex:
            # Exception raised (transport error, invalid JSON, etc.)
            print(f"Request failed with exception: {ex}")

if __name__ == "__main__":
    asyncio.run(main())