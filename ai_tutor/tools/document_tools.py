from openai import OpenAI
import requests
from io import BytesIO

client = OpenAI()

async def create_vector_store(name):
    """Create a new vector store"""
    vector_store = client.vector_stores.create(name=name)
    print(f"Created vector store: {vector_store.id}")
    return vector_store.id

async def upload_file_to_store(vector_store_id, file_path):
    """Upload a file to OpenAI and add it to the vector store"""
    # Upload file to OpenAI
    file_id = await create_file(file_path)
    
    # Add file to vector store
    client.vector_stores.files.create(
        vector_store_id=vector_store_id,
        file_id=file_id
    )
    
    print(f"Added file {file_id} to vector store {vector_store_id}")
    return file_id

async def create_file(file_path):
    """Upload a file to OpenAI"""
    if file_path.startswith("http://") or file_path.startswith("https://"):
        # Download file from URL
        response = requests.get(file_path)
        file_content = BytesIO(response.content)
        file_name = file_path.split("/")[-1]
        file_tuple = (file_name, file_content)
        result = client.files.create(
            file=file_tuple,
            purpose="assistants"
        )
    else:
        # Upload local file
        with open(file_path, "rb") as file_content:
            result = client.files.create(
                file=file_content,
                purpose="assistants"
            )
    
    print(f"Created file: {result.id}")
    return result.id

async def check_file_status(vector_store_id, file_id=None):
    """Check if files in vector store are ready to be used"""
    result = client.vector_stores.files.list(
        vector_store_id=vector_store_id
    )
    
    # If a specific file_id is provided, check only that file
    if file_id:
        for file in result.data:
            if file.id == file_id:
                return file.status == "completed", file
    
    # Otherwise check all files
    all_completed = all(file.status == "completed" for file in result.data)
    return all_completed, result.data 