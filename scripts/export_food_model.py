"""Export the FREE, Apache-2.0 `nateraw/food` model (ViT fine-tuned on Food-101) to ONNX for the Food Scanner.

Run once, in any Python env with network access (not needed at runtime):
    pip install torch transformers onnx
    python scripts/export_food_model.py            # writes backend/models_weights/food_classifier.onnx + food_labels.txt

Then set in backend/.env:
    FOOD_MODEL_MEAN=0.5,0.5,0.5
    FOOD_MODEL_STD=0.5,0.5,0.5
Check the model card on Hugging Face for current licence/terms before shipping. Accuracy on your own photos is NOT guaranteed:
Food-101 has 101 dishes; anything outside them will be mislabelled, so keep the confidence badge visible.
"""
from pathlib import Path

import torch
from transformers import AutoModelForImageClassification

MODEL_ID = "nateraw/food"
OUT = Path(__file__).resolve().parents[1] / "backend" / "models_weights"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    model = AutoModelForImageClassification.from_pretrained(MODEL_ID).eval()
    labels = [model.config.id2label[i] for i in range(len(model.config.id2label))]
    (OUT / "food_labels.txt").write_text("\n".join(labels) + "\n", encoding="utf-8")

    class Wrapper(torch.nn.Module):          # return plain logits tensor
        def __init__(self, m): super().__init__(); self.m = m
        def forward(self, x): return self.m(pixel_values=x).logits

    torch.onnx.export(Wrapper(model), torch.randn(1, 3, 224, 224), str(OUT / "food_classifier.onnx"),
                      input_names=["pixel_values"], output_names=["logits"], opset_version=14,
                      dynamic_axes={"pixel_values": {0: "batch"}, "logits": {0: "batch"}})
    print(f"Wrote {len(labels)} labels and food_classifier.onnx to {OUT}")


if __name__ == "__main__":
    main()
