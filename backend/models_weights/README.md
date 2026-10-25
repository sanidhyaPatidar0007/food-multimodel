# Model weights

Nothing is bundled here: **no trained model ships with FoodVerse AI.** Without weights the app says so and
falls back to manual selection / labelled baselines. To enable real inference, drop ONNX files here.

## Food classifier (Food Scanner)
- `food_classifier.onnx` - input `(1,3,H,W)` float32, ImageNet mean/std normalisation, output logits or probabilities `(1,N)`.
- `food_labels.txt` - one class name per line, same order as the outputs (e.g. Food-101 class names such as `apple_pie`).
- Set `FOOD_MODEL_INPUT_SIZE` if your model is not 224x224. Labels are matched to the nutrition table by name
  (underscores become spaces); labels with no table entry are reported as "recognised but not in the nutrition table".
- Different normalisation? Edit `preprocess_for_classifier` in `app/utils/imaging.py`.

## Freshness classifier (optional)
- `freshness_classifier.onnx` + `freshness_labels.txt`. Label names containing `fresh`/`good` => visually fresh,
  `rot`/`spoil`/`stale`/`bad`/`mold` => deterioration, anything else => uncertain.
  Datasets to train on: e.g. public "fresh vs rotten fruits and vegetables" image sets (check each licence).
- Confidence shown is the model's softmax probability and is labelled **uncalibrated**.

## Exporting a model
```python
# PyTorch example
torch.onnx.export(model.eval(), torch.randn(1, 3, 224, 224), "food_classifier.onnx", input_names=["input"], output_names=["logits"])
```
