"""
Image -> 3D Model Converter
----------------------------
یک اسکریپت تکی که با گرادیو رابط کاربری می‌سازد، کاربر یک عکس (مثلاً چهره)
بارگذاری می‌کند و با استفاده از مدل رایگان و متن‌باز Shap-E (ساخته OpenAI،
در دسترس از طریق کتابخانه diffusers) آن را به یک مدل سه‌بعدی (.glb) تبدیل
می‌کند. کاملاً رایگان، بدون نیاز به کلید API یا سرویس پولی.

اجرا روی Hugging Face Spaces با Docker SDK.
"""

import os
import tempfile

import gradio as gr
import numpy as np
import torch

# در برخی محیط‌های Docker/Spaces، Gradio هنگام launch() یک درخواست HTTP به
# خودش (http://0.0.0.0:PORT) می‌زند تا مطمئن شود سرور بالا آمده؛ اگر آن
# درخواست به هر دلیلی (شبکه/پراکسی محدودشده) شکست بخورد، Gradio با خطای
# "localhost is not accessible" کرش می‌کند. چون سرور واقعاً بالا می‌آید
# (فقط این self-check است که مشکل دارد)، این بررسی را غیرفعال می‌کنیم.
try:
    import gradio.networking as _gr_networking
    _gr_networking.url_ok = lambda url: True
except Exception as _e:
    print(f"[WARN] Could not patch gradio.networking.url_ok: {_e}")
from PIL import Image
from diffusers import ShapEImg2ImgPipeline
from diffusers.utils import export_to_gif

# -----------------------------------------------------------------------
# تنظیمات
# -----------------------------------------------------------------------
MODEL_ID = "openai/shap-e-img2img"          # مدل رایگان و متن‌باز
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32

print(f"[INFO] Loading {MODEL_ID} on {DEVICE} ...")
pipe = ShapEImg2ImgPipeline.from_pretrained(MODEL_ID, torch_dtype=DTYPE)
pipe = pipe.to(DEVICE)
print("[INFO] Model loaded.")


def _preprocess(image: Image.Image, size: int = 256) -> Image.Image:
    """تصویر ورودی را برای مدل آماده می‌کند (اندازه استاندارد + پس‌زمینه سفید)."""
    image = image.convert("RGBA")
    background = Image.new("RGBA", image.size, (255, 255, 255, 255))
    image = Image.alpha_composite(background, image).convert("RGB")
    image.thumbnail((size, size))
    canvas = Image.new("RGB", (size, size), (255, 255, 255))
    offset = ((size - image.width) // 2, (size - image.height) // 2)
    canvas.paste(image, offset)
    return canvas


def image_to_3d(image: Image.Image, guidance_scale: float, steps: int):
    if image is None:
        raise gr.Error("لطفاً ابتدا یک تصویر بارگذاری کنید.")

    processed = _preprocess(image)

    with torch.no_grad():
        result = pipe(
            image=processed,
            guidance_scale=guidance_scale,
            num_inference_steps=int(steps),
            frame_size=256,
            output_type="mesh",
        )

    mesh = result.images[0]

    out_dir = tempfile.mkdtemp()
    glb_path = os.path.join(out_dir, "model.glb")

    # ذخیره خروجی به فرمت glb برای نمایش سه‌بعدی و دانلود
    from diffusers.utils import export_to_glb  # optional helper
    try:
        export_to_glb(mesh, glb_path)
    except Exception:
        # نسخه‌های قدیمی‌تر diffusers ممکن است export_to_glb نداشته باشند
        mesh.export(glb_path)

    return glb_path, glb_path


demo = gr.Blocks(title="تبدیل تصویر به مدل سه‌بعدی (رایگان)")
demo.show_api = False

with demo:
    gr.Markdown(
        """
        # 🧊 تبدیل تصویر به مدل سه‌بعدی
        یک عکس (مثلاً پرتره یا هر شیء دیگر) بارگذاری کنید تا با مدل رایگان و
        متن‌باز **Shap-E** به یک فایل سه‌بعدی `.glb` تبدیل شود.
        همه‌چیز رایگان است — بدون نیاز به کلید API.
        """
    )

    with gr.Row():
        with gr.Column():
            input_image = gr.Image(type="pil", label="تصویر ورودی")
            guidance = gr.Slider(1.0, 20.0, value=15.0, step=0.5, label="Guidance Scale")
            steps = gr.Slider(16, 128, value=64, step=1, label="تعداد مراحل استنتاج")
            run_btn = gr.Button("تولید مدل سه‌بعدی 🚀", variant="primary")

        with gr.Column():
            model_out = gr.Model3D(label="نتیجه سه‌بعدی")
            file_out = gr.File(label="دانلود فایل .glb")

    run_btn.click(
        fn=image_to_3d,
        inputs=[input_image, guidance, steps],
        outputs=[model_out, file_out],
    )

    gr.Markdown(
        """
        ---
        ساخته‌شده با [diffusers](https://github.com/huggingface/diffusers) و مدل
        رایگان [Shap-E](https://huggingface.co/openai/shap-e-img2img).
        روی CPU کار می‌کند اما با GPU سریع‌تر است.
        """
    )

if __name__ == "__main__":
    demo.queue(max_size=10).launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_api=False,
        share=False,
    )
