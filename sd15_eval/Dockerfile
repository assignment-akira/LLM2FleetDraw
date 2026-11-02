FROM pytorch/pytorch:2.6.0-cuda12.6-cudnn9-runtime
RUN pip install --no-cache-dir 'diffusers==0.35.1' 'transformers==4.53.3' 'accelerate==1.9.0' 'safetensors>=0.5,<1' 'pillow==11.3.0'
WORKDIR /workspace

# LoRA adapter loader for diffusers 0.35.1; keep separate from unrelated environments.
RUN pip install --no-cache-dir "peft==0.17.1" \
 && python -c 'import peft, diffusers, transformers; from diffusers import StableDiffusionPipeline; print("LORA DEPENDENCIES READY", peft.__version__, diffusers.__version__, transformers.__version__)'
