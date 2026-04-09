import asyncio
from deploy import app, square

async def main():
    for x in range(1, 10):
        result = await square(x)
        print(f"square({x}) = {result}")

if __name__ == "__main__":
    asyncio.run(main())
