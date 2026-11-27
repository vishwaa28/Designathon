from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()
endpoint = "https://2000163829-0823-resource.services.ai.azure.com/openai/v1"
deployment_name = "gpt-5.4"
api_key = os.getenv("azure_api_key")

client = OpenAI(
    base_url=endpoint,
    api_key=api_key
)

response = client.responses.create(
    model=deployment_name,
    input="What is the capital of France?",
)

print(f"answer: {response.output_text}")
