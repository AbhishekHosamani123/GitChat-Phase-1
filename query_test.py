import os
import sys

# Change dir explicitly in the script just in case
sys.path.append(r'd:\GitChat Phase 1')

try:
    from chat import retrieve_context
except ImportError:
    print("Could not import chat module")
    sys.exit(1)

# we can use the sha256 of click for demo
repo_id = '02d5ffc8bb7994addbf277b0c3ff4a9a08eb23ca51909f1969df656dd3d65ee1'
query = 'How is the click parser implemented?'

try:
    context, top_results, confidence, retrieved_ids, boosted_scores = retrieve_context(query, repo_id)
    
    print("\n[Simulated GitChat Response]")
    answer = "The click parser is implemented using ..."
    
    if top_results and top_results[0]['sim'] < 0.35:
        answer += "\n\n⚠ Low retrieval confidence. Answer may be incomplete."
                
    sources = []
    for row in top_results:
         sources.append(f"- {row['file_path']}: {row['start_line']}–{row['end_line']}")
            
    answer += "\n\nSources:\n" + "\n".join(sources)
    answer += f"\n\nConfidence: {confidence}"
    
    print(answer)
    print("\n[Debug Log Entry]")
    print(f"retrieved_ids: {retrieved_ids}")
    print(f"boosted_scores: {boosted_scores}")
    
except Exception as e:
    import traceback
    traceback.print_exc()
