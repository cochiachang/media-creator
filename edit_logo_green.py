import os
import base64
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

prompt = (
    "A professional corporate logo for 'PAUL WRIGHT' consulting firm. "
    "The logo has a dark forest green square icon on the left side containing geometric shapes that form the letters 'PW' or abstract professional mark. "
    "To the right of the icon is the company name 'PAUL WRIGHT' in large bold dark green text. "
    "Below the company name is the tagline 'Expertise | Integrity | Credibility' in smaller green text. "
    "The entire color scheme uses shades of green: dark forest green (#1a4d2e or #2d5a27), medium green, and white background. "
    "Clean, minimalist, professional corporate style. White background. High quality vector-style logo."
)

print("Generating green version of Paul Wright logo...")

response = client.images.generate(
    model="gpt-image-1",
    prompt=prompt,
    size="1024x1024",
    quality="high",
    n=1,
)

image_b64 = response.data[0].b64_json
image_bytes = base64.b64decode(image_b64)

output_path = "output_green.png"
with open(output_path, "wb") as f:
    f.write(image_bytes)

print(f"Green logo saved to: {output_path}")
