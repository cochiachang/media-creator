import os
import sys
from google import genai
from google.genai import types

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def generate_image(prompt: str, output_filename: str = "output.png") -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    client = genai.Client(api_key=api_key)

    response = client.models.generate_images(
        model="imagen-4.0-generate-001",
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio="1:1",
        ),
    )

    if not response.generated_images:
        raise RuntimeError("No images were generated")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    image_data = response.generated_images[0].image
    with open(output_path, "wb") as f:
        f.write(image_data.image_bytes)

    return output_path


if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else (
        "A portrait of a beautiful young woman with elegant features, "
        "soft lighting, professional photography style, high quality"
    )
    filename = sys.argv[2] if len(sys.argv) > 2 else "output.png"

    print(f"Generating image with prompt: {prompt}")
    result = generate_image(prompt, filename)
    print(f"Image saved to: {result}")
