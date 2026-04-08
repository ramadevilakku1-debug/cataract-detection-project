import torch
import timm

print("Loading PyTorch model...")
device = torch.device("cpu")
model = timm.create_model(
    'vit_base_patch16_224',
    pretrained=False,
    num_classes=3
)
model.load_state_dict(torch.load('cataract_vit_model.pth', map_location=device))
model.eval()

print("Creating dummy input...")
dummy_input = torch.randn(1, 3, 224, 224, device=device)

print("Exporting to ONNX format...")
torch.onnx.export(
    model,
    dummy_input,
    "cataract_vit_model.onnx",
    export_params=True,
    opset_version=14,
    do_constant_folding=True,
    input_names=['input'],
    output_names=['output'],
    dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
)
print("Conversion complete!")
