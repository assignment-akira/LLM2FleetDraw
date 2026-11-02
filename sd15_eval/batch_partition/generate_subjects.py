import argparse,json,time
from pathlib import Path
import torch
from diffusers import StableDiffusionPipeline
MODEL='stable-diffusion-v1-5/stable-diffusion-v1-5'
REPO='artificialguybr/logo-redmond-1-5v-logo-lora-for-liberteredmond-sd-1-5'
WEIGHT='LogoRedmond15V-LogoRedmAF-Logo.safetensors'
def main():
 p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=101);p.add_argument('--steps',type=int,default=22);a=p.parse_args()
 assert torch.cuda.is_available(),'CUDA missing, stop instead of CPU fallback'
 dtype=torch.float16
 pipe=StableDiffusionPipeline.from_pretrained(MODEL,torch_dtype=dtype,use_safetensors=True,safety_checker=None)
 pipe.enable_model_cpu_offload();pipe.enable_attention_slicing()
 assert pipe.unet.dtype==dtype and pipe.text_encoder.dtype==dtype
 pipe.load_lora_weights(REPO,weight_name=WEIGHT,adapter_name='logo');pipe.set_adapters(['logo'],adapter_weights=[.8])
 out=Path('/outputs/batch_partition/materials');out.mkdir(parents=True,exist_ok=True)
 neg='photograph, dark background, extra objects, text, shading, complex pattern, watermark, cropped'
 for name,subject in [('turtle','cute turtle, full body, side view'),('flower','simple single flower with petals stem and two leaves')]:
  prompt=subject+', minimalist black line drawing, full body, single object, white background, flat 2D icon, simple outline'
  assert len(pipe.tokenizer(prompt,add_special_tokens=True,truncation=False).input_ids)<=77
  gen=torch.Generator(device='cpu').manual_seed(a.seed)
  print('GENERATING',name,flush=True);t=time.monotonic()
  im=pipe(prompt=prompt,negative_prompt=neg,width=512,height=512,num_inference_steps=a.steps,guidance_scale=7.0,generator=gen).images[0]
  im.save(out/(name+'.png'))
  (out/(name+'.json')).write_text(json.dumps({'prompt':prompt,'negative_prompt':neg,'seed':a.seed,'steps':a.steps,'lora':REPO,'weight':.8,'elapsed':round(time.monotonic()-t,2)},indent=2))
  print('SAVED',name,flush=True)
 print('IMAGE GENERATION PASS',flush=True)
if __name__=='__main__':main()
