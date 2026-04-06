from vastai import Deployment
from vastai.data.query import gpu_name, RTX_4090, RTX_5090

app = Deployment(name="train-mnist")


@app.context()
class MNISTModel:
    async def __aenter__(self):
        import torch
        import torch.nn as nn
        import torch.optim as optim
        from torchvision import datasets, transforms

        class CNN(nn.Module):
            def __init__(self):
                super().__init__()
                self.conv1 = nn.Conv2d(1, 32, 3, padding=1)
                self.conv2 = nn.Conv2d(32, 64, 3, padding=1)
                self.pool = nn.MaxPool2d(2)
                self.fc1 = nn.Linear(64 * 7 * 7, 128)
                self.fc2 = nn.Linear(128, 10)
                self.relu = nn.ReLU()

            def forward(self, x):
                x = self.pool(self.relu(self.conv1(x)))
                x = self.pool(self.relu(self.conv2(x)))
                x = x.view(-1, 64 * 7 * 7)
                x = self.relu(self.fc1(x))
                return self.fc2(x)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = CNN().to(device)
        optimizer = optim.Adam(model.parameters(), lr=1e-3)
        loss_fn = nn.CrossEntropyLoss()

        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.1307,), (0.3081,)),
        ])
        train_data = datasets.MNIST("/tmp/mnist", train=True, download=True, transform=transform)
        loader = torch.utils.data.DataLoader(train_data, batch_size=64, shuffle=True)

        print("Training MNIST classifier...")
        model.train()
        for epoch in range(3):
            total_loss = 0.0
            for images, labels in loader:
                images, labels = images.to(device), labels.to(device)
                optimizer.zero_grad()
                loss = loss_fn(model(images), labels)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            print(f"  Epoch {epoch + 1}/3  loss={total_loss / len(loader):.4f}")

        model.eval()
        self.model = model
        self.device = device
        print("Training complete. Model ready for inference.")
        return self

    async def __aexit__(self, *exc):
        pass


@app.remote(benchmark_dataset=[{"pixel_values": [[0.0] * 28] * 28}])
async def infer(pixel_values: list[list[float]]) -> dict:
    """Classify a 28x28 grayscale MNIST image.

    Args:
        pixel_values: 28x28 nested list of floats (0.0=black, 1.0=white),
                      raw pixel intensities before normalization.

    Returns:
        dict with "digit" (predicted class) and "probability" (confidence).
    """
    import torch

    ctx = app.get_context(MNISTModel)

    tensor = torch.tensor(pixel_values, dtype=torch.float32)
    # Normalize the same way training data was normalized
    tensor = (tensor - 0.1307) / 0.3081
    tensor = tensor.unsqueeze(0).unsqueeze(0).to(ctx.device)  # (1, 1, 28, 28)
    tensor = torch.flip(tensor, dims=[2])  # flip vertically

    with torch.no_grad():
        logits = ctx.model(tensor)
        probs = torch.softmax(logits, dim=1)
        prob, digit = probs.max(dim=1)

    return {"digit": digit.item(), "probability": prob.item()}


image = app.image("vastai/pytorch:@vastai-automatic-tag", 16)
image.venv("/venv/main")
image.require(gpu_name.in_([RTX_4090, RTX_5090]))
app.configure_autoscaling(min_load=100, max_workers=3) #!VAST_IGNORE_CHANGES
app.ensure_ready()
