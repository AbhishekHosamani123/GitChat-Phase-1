import os
import time
from supabase import create_client
from google import genai
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

load_dotenv()

# CONFIG
EMBEDDING_MODEL = "models/gemini-embedding-001"
# Set to 3072 for Gemini models
PINECONE_DIMENSION = 3072
BATCH_SIZE = 25

def init_pinecone():
    """Initializes the Pinecone index, creating it if it doesn't exist."""
    pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
    index_name = "gitchat"
    
    if index_name not in [i.name for i in pc.list_indexes()]:
        print(f"Creating Pinecone index '{index_name}' with dimension {PINECONE_DIMENSION}...")
        pc.create_index(
            name=index_name,
            dimension=PINECONE_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        print("Waiting for index to be ready...")
        time.sleep(10) # Give it a moment to initialize
    
    return pc.Index(index_name)

def get_gemini_embeddings(texts: list[str]) -> list[list[float]]:
    """Retrieve embeddings for a list of text strings using the Gemini API."""
    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
        )
        return [e.values for e in response.embeddings]
    except Exception as e:
        print(f"Error fetching embeddings from Gemini: {e}")
        return []

def fetch_pending_chunks(batch_size):
    """Fetches a batch of pending chunks from the database."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    supabase = create_client(url, key)
    
    try:
        response = supabase.table("chunks") \
            .select("chunk_id, repo_id, chunk_text, file_path, function_name, embedding_status") \
            .eq("embedding_status", "pending") \
            .limit(batch_size) \
            .execute()
        return response.data
    except Exception as e:
        print(f"Failed to fetch pending chunks: {e}")
        return []

def mark_chunks_as_indexed(chunk_ids):
    """Updates the database status for successfully embedded chunks."""
    if not chunk_ids:
        return
        
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY")
    supabase = create_client(url, key)
    
    try:
        # Supabase allows updating multiple rows matching an IN clause
        supabase.table("chunks") \
            .update({"embedding_status": "indexed"}) \
            .in_("chunk_id", chunk_ids) \
            .execute()
    except Exception as e:
        print(f"Failed to update chunk status: {e}")

def run_worker():
    print("--- Starting Embedding Worker ---")
    pinecone_index = init_pinecone()
    
    while True:
        # Fetch a batch of pending chunks
        batch = fetch_pending_chunks(BATCH_SIZE)
        
        if not batch:
            print("No more pending chunks. Worker sleeping for 60 seconds...")
            time.sleep(60)
            continue
            
        print(f"Processing batch of {len(batch)} chunks...")
        
        # Prepare data for embedding
        texts_to_embed = []
        vectors_to_upsert = []
        
        for row in batch:
            chunk_id = row['chunk_id']
            repo_id = row['repo_id']
            code = row['chunk_text']
            file_path = row['file_path']
            symbol_name = row['function_name']
            
            # Reconstruct content logic
            context = f"File: {file_path}\n"
            if symbol_name:
                context += f"Component: {symbol_name}\n"
            context += f"Code:\n{code}"
            
            texts_to_embed.append(context)
            
            # Prepare the Pinecone upsert tuple (without the vector yet)
            vectors_to_upsert.append({
                "id": chunk_id,
                "values": None, # Will fill this next
                "metadata": {
                    "repo_id": repo_id,
                    "file_path": file_path,
                    "function_name": symbol_name if symbol_name else ""
                },
                "namespace": repo_id # Clean isolation
            })
            
        # Call the Gemini API
        embeddings = get_gemini_embeddings(texts_to_embed)
        
        if not embeddings or len(embeddings) != len(batch):
            print("Failed to generate embeddings. Retrying in 30 seconds...")
            time.sleep(30)
            continue
            
        # Group vectors by namespace (repo_id) for upserting
        namespaces = {}
        for i, vec_dict in enumerate(vectors_to_upsert):
            vec_dict["values"] = embeddings[i]
            ns = vec_dict.pop("namespace") # Extract namespace
            if ns not in namespaces:
                namespaces[ns] = []
            namespaces[ns].append(vec_dict)
            
        # Upsert to Pinecone per namespace
        success = True
        for ns, vectors in namespaces.items():
            try:
                pinecone_index.upsert(vectors=vectors, namespace=ns)
            except Exception as e:
                print(f"Failed to upsert namespace {ns} to Pinecone: {e}")
                success = False
                break
                
        if not success:
            print("Skipping database update due to Pinecone upsert failure.")
            time.sleep(10)
            continue
            
        # Mark chunks as indexed in local DB
        chunk_ids_to_mark = [row['chunk_id'] for row in batch]
        mark_chunks_as_indexed(chunk_ids_to_mark)
        
        print(f"Successfully embedded and indexed {len(batch)} chunks.")
        
        # Free tier rate limit protection
        print("Sleeping for 40 seconds to respect rate limits...")
        time.sleep(40)

if __name__ == "__main__":
    run_worker()
