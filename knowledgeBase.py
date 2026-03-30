import os
import time
import requests
from bs4 import BeautifulSoup
from langchain_openai import OpenAIEmbeddings
import chromadb
import praw  # Reddit API

embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("company_interview_intel")

# Real public sources per company
SOURCES = {
    "Anthropic": {
        "blogs": [
            "https://www.anthropic.com/research",
            "https://www.anthropic.com/careers",
        ],
        "reddit_queries": [
            "Anthropic interview experience software engineer",
            "Anthropic ML engineer interview",
            "Anthropic new grad interview process",
        ]
    },
    "Microsoft": {
        "blogs": [
            "https://careers.microsoft.com/us/en/culture",
            "https://engineering.microsoft.com/",
        ],
        "reddit_queries": [
            "Microsoft AI engineer interview experience",
            "Microsoft new grad ML interview",
        ]
    },
    "Google": {
        "blogs": [
            "https://careers.google.com/how-we-hire/",
            "https://blog.research.google/",
        ],
        "reddit_queries": [
            "Google ML engineer interview experience 2024 2025",
            "Google new grad software engineer interview",
        ]
    },
    "Meta": {
        "blogs": [
            "https://engineering.fb.com/",
            "https://ai.meta.com/blog/",
        ],
        "reddit_queries": [
            "Meta AI engineer interview experience",
            "Meta new grad ML interview 2024 2025",
        ]
    }
}

def scrape_page(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove nav, footer, scripts
        for tag in soup(["nav", "footer", "script", "style", "header"]):
            tag.decompose()
        
        text = soup.get_text(separator=" ", strip=True)
        
        # Limit to first 3000 chars per page — enough for context
        return text[:3000]
    except Exception as e:
        print(f"  Failed to scrape {url}: {e}")
        return ""

def scrape_reddit(queries: list, limit: int = 5) -> list:
    # Uses Reddit's public JSON API — no auth needed
    results = []
    
    for query in queries:
        try:
            url = f"https://www.reddit.com/r/cscareerquestions/search.json"
            params = {
                "q": query,
                "limit": limit,
                "sort": "relevance",
                "t": "year"  # last year only — keep it fresh
            }
            headers = {"User-Agent": "interview-coach-app/1.0"}
            response = requests.get(url, params=params, 
                                    headers=headers, timeout=10)
            
            data = response.json()
            posts = data["data"]["children"]
            
            for post in posts:
                post_data = post["data"]
                title = post_data.get("title", "")
                selftext = post_data.get("selftext", "")
                
                if selftext and len(selftext) > 100:
                    # Only keep posts with real content
                    combined = f"Title: {title}\n\n{selftext[:2000]}"
                    results.append(combined)
            
            time.sleep(1)  # Be polite to Reddit
            
        except Exception as e:
            print(f"  Reddit scrape failed for '{query}': {e}")
    
    return results

def chunk_text(text: str, chunk_size: int = 500) -> list:
    # Split into overlapping chunks for better retrieval
    words = text.split()
    chunks = []
    overlap = 50
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if len(chunk) > 100:  # Skip tiny chunks
            chunks.append(chunk)
    
    return chunks

def build_knowledge_base():
    print("Building knowledge base from real sources...\n")
    
    all_documents = []
    all_metadatas = []
    all_ids = []
    idx = 0
    
    for company, sources in SOURCES.items():
        print(f"Scraping {company}...")
        
        # Scrape engineering blogs and careers pages
        for url in sources["blogs"]:
            print(f"  Blog: {url}")
            text = scrape_page(url)
            
            if text:
                chunks = chunk_text(text)
                for chunk in chunks:
                    all_documents.append(chunk)
                    all_metadatas.append({
                        "company": company,
                        "source": "blog",
                        "url": url
                    })
                    all_ids.append(f"{company}_blog_{idx}")
                    idx += 1
        
        # Scrape Reddit interview experiences
        print(f"  Reddit: fetching interview experiences...")
        reddit_posts = scrape_reddit(sources["reddit_queries"])
        
        for post in reddit_posts:
            chunks = chunk_text(post, chunk_size=300)
            for chunk in chunks:
                all_documents.append(chunk)
                all_metadatas.append({
                    "company": company,
                    "source": "reddit",
                    "url": "r/cscareerquestions"
                })
                all_ids.append(f"{company}_reddit_{idx}")
                idx += 1
        
        print(f"  Done — {idx} total chunks so far\n")
    
    # Embed everything in one batch — much faster than one by one
    print(f"Embedding {len(all_documents)} chunks...")
    
    # Batch in groups of 100 to avoid API limits
    batch_size = 100
    all_embeddings = []
    
    for i in range(0, len(all_documents), batch_size):
        batch = all_documents[i:i + batch_size]
        batch_embeddings = embeddings.embed_documents(batch)
        all_embeddings.extend(batch_embeddings)
        print(f"  Embedded {min(i + batch_size, len(all_documents))}/{len(all_documents)}")
    
    # Store in ChromaDB
    collection.upsert(
        documents=all_documents,
        embeddings=all_embeddings,
        metadatas=all_metadatas,
        ids=all_ids
    )
    
    print(f"\nKnowledge base complete — {len(all_documents)} chunks stored.")

def get_company_context(company: str, question: str) -> str:
    query = f"{company} interview {question} AI ML engineer"
    query_embedding = embeddings.embed_query(query)
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=4,
        where={"company": company}
    )
    
    if not results["documents"][0]:
        return f"No intel found for {company}."
    
    # Show where each piece came from
    chunks = results["documents"][0]
    metas = results["metadatas"][0]
    
    context_parts = []
    for chunk, meta in zip(chunks, metas):
        source = meta.get("source", "unknown")
        context_parts.append(f"[Source: {source}]\n{chunk}")
    
    return "\n\n---\n\n".join(context_parts)

if __name__ == "__main__":
    build_knowledge_base()
    
    # Test retrieval
    print("\n=== TEST: What does Anthropic look for? ===")
    print(get_company_context("Anthropic", "tell me about yourself"))