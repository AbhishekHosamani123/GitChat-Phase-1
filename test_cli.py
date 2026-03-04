import os
import sys

sys.path.append(r'd:\GitChat Phase 1')

try:
    from chat import retrieve_context
    repo_id = '59f828ed3d490a539f0d4f45a408311a481b28d6eba483d28306e2d8bce069f5'
    query = 'Explain how Context is created and passed to subcommands.'
    
    context, top_results, confidence, retrieved_ids, boosted_scores = retrieve_context(query, repo_id)
    
    print("\n[Simulated GitChat Response]")
    answer = "Context is created by..."
    
    if top_results and top_results[0]['sim'] < 0.35:
        answer += "\n\n⚠ Low retrieval confidence. Answer may be incomplete."
                
    sources = []
    for row in top_results:
         sources.append(f"- {row['file_path']}: {row['start_line']}–{row['end_line']}")
            
    answer += "\n\nSources:\n" + "\n".join(sources)
    answer += f"\n\nConfidence: {confidence}"
    
    print(answer)
except Exception as e:
    import traceback
    traceback.print_exc()
