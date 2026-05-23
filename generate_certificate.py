import os
import base64
from openai import OpenAI

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

prompt = (
    "A professional coffee competition certificate of recognition, elegant and clean design. "
    "White background with decorative red and orange tropical leaf illustrations on the right side. "
    "Top of certificate has official logos: Alliance for Coffee Excellence, SCACR, Costa Rica Taza de la Excelencia, and Cup of Excellence logos in a row. "
    "Bold heading text 'CERTIFICADO DE RECONOCIMIENTO'. "
    "Large bold farm name 'FINCA LOS PINOS' in the center. "
    "Smaller text with owner name, company name, competition year 2025. "
    "Text lines: 'GANADOR Categoría EXPERIMENTALES', 'POSICIÓN: 07', 'NOTA: 88.13'. "
    "Three signature lines at the bottom. "
    "Professional, formal certificate layout, portrait orientation, white paper texture, high quality print design."
)

print("Generating certificate image...")

response = client.images.generate(
    model="gpt-image-1",
    prompt=prompt,
    size="1024x1536",
    quality="high",
    n=1,
)

image_b64 = response.data[0].b64_json
image_bytes = base64.b64decode(image_b64)

os.makedirs(OUTPUT_DIR, exist_ok=True)
output_path = os.path.join(OUTPUT_DIR, "certificate.png")
with open(output_path, "wb") as f:
    f.write(image_bytes)

print(f"Certificate saved to: {output_path}")
