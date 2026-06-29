"""
train_model.py
Trains a tiny ONNX model for N.I.W.O.E.C.
Run this script once to generate:
    models/model.onnx
    models/tokenizer.json   (plus a few extra tokenizer files)
"""

import os
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModel

# Suppress HuggingFace symlink warnings on Windows (harmless but noisy)
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# -------------------------------------------------------------------
# 1. Dummy training data – replace with your own real data later
# -------------------------------------------------------------------
texts = [
    "App needs 60 FPS, real-time physics, 4K textures",
    "Simple 2D puzzle, lightweight",
    "AAA open world, ray tracing, 32 GB RAM recommended",
    "VR training simulator, high GPU memory, 90 FPS",
    "Minimalist text editor, low resource usage",
]
# Each row: [cpu_cores, ram_mb, gpu_vram_mb]
hardware = [
    [4, 8192, 4096],
    [2, 4096, 2048],
    [8, 16384, 8192],
    [6, 16384, 12288],
    [2, 2048, 512],
]
# 1 = works, 0 = doesn't work
labels = [0, 1, 0, 0, 1]

# -------------------------------------------------------------------
# 2. Load and save tokenizer
# -------------------------------------------------------------------
tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
os.makedirs("models", exist_ok=True)
tokenizer.save_pretrained("models")
print("Tokenizer saved to models/")

# -------------------------------------------------------------------
# 3. Define the model
# -------------------------------------------------------------------
class HardwarePredictor(nn.Module):
    def __init__(self):
        super().__init__()
        self.text_encoder = AutoModel.from_pretrained(
            "sentence-transformers/all-MiniLM-L6-v2"
        )
        # Freeze the transformer to speed up training (optional)
        for param in self.text_encoder.parameters():
            param.requires_grad = False

        self.fc = nn.Sequential(
            nn.Linear(384 + 3, 128),   # 384 = MiniLM embedding size, +3 hw features
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Sigmoid()
        )

    def forward(self, input_ids, attention_mask, hw_features):
        with torch.no_grad():
            text_out = self.text_encoder(
                input_ids=input_ids, attention_mask=attention_mask
            )
        # Mean pooling over the sequence dimension
        text_emb = text_out.last_hidden_state.mean(dim=1)   # [batch, 384]
        combined = torch.cat([text_emb, hw_features], dim=1)
        return self.fc(combined)

model = HardwarePredictor()

# -------------------------------------------------------------------
# 4. Prepare training tensors
# -------------------------------------------------------------------
max_len = 128   # must match the Rust code (self.max_len)
encodings = tokenizer(
    texts,
    padding="max_length",
    truncation=True,
    max_length=max_len,
    return_tensors="pt"
)
input_ids = encodings["input_ids"]
attention_mask = encodings["attention_mask"]

hw_tensor = torch.tensor(hardware, dtype=torch.float32)
# Normalise hardware features (same normalisation as in Rust)
hw_tensor[:, 0] /= 64.0      # cpu cores
hw_tensor[:, 1] /= 65536.0   # ram MB
hw_tensor[:, 2] /= 24576.0   # gpu vram MB

labels_tensor = torch.tensor(labels, dtype=torch.float32).unsqueeze(1)

# -------------------------------------------------------------------
# 5. Train (quick, just to have a working model)
# -------------------------------------------------------------------
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
loss_fn = nn.BCELoss()

model.train()
for epoch in range(50):
    optimizer.zero_grad()
    outputs = model(input_ids, attention_mask, hw_tensor)
    loss = loss_fn(outputs, labels_tensor)
    loss.backward()
    optimizer.step()
print(f"Training finished. Final loss: {loss.item():.4f}")

# -------------------------------------------------------------------
# 6. Export to ONNX
# -------------------------------------------------------------------
model.eval()
dummy_input_ids = torch.zeros(1, max_len, dtype=torch.long)
dummy_attention_mask = torch.zeros(1, max_len, dtype=torch.long)
dummy_hw = torch.zeros(1, 3, dtype=torch.float32)

torch.onnx.export(
    model,
    (dummy_input_ids, dummy_attention_mask, dummy_hw),
    "models/model.onnx",
    input_names=["input_ids", "attention_mask", "hw_features"],
    output_names=["output"],
    dynamic_axes={
        "input_ids": {0: "batch_size"},
        "attention_mask": {0: "batch_size"},
        "hw_features": {0: "batch_size"},
        "output": {0: "batch_size"},
    },
    opset_version=14,
)
print("ONNX model saved to models/model.onnx")
print("All done. You can now build the Rust application.")
