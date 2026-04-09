import asyncio
import random
from deploy import app, infer

async def main():
    from torchvision import datasets, transforms

    test_data = datasets.MNIST("/tmp/mnist", train=False, download=True, transform=transforms.ToTensor())
    idx = random.randint(0, len(test_data) - 1)
    image_tensor, true_label = test_data[idx]

    # Convert to 28x28 nested list of floats (raw pixel values, no normalization)
    pixel_values = image_tensor.squeeze(0).tolist()

    result = await infer(pixel_values)
    print(f"True label:  {true_label}")
    print(f"Predicted:   {result['digit']}")
    print(f"Confidence:  {result['probability']:.4f}")

if __name__ == "__main__":
    asyncio.run(main())
