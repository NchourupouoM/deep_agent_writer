import json
import redis
import os
from typing import List, Tuple, Dict, Any
from dotenv import load_dotenv

from src.celery_app import celery_app
from src.graph import create_deep_agent_graph

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.Redis.from_url(REDIS_URL)

_graph_app = None

def get_graph():
    """
    Lazy instanciation du graphe propre au worker enfant.
    """
    global _graph_app
    if _graph_app is None:
        print("🔌 [Worker Process] Opening fresh PostgreSQL connection pool...")
        _graph_app = create_deep_agent_graph(use_postgres=True)
    return _graph_app


def parse_stream_event(event: Any) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Parse de manière 100% sécurisée n'importe quel événement retourné par graph.stream()
    qu'il s'agisse d'un dictionnaire, d'un tuple ou d'une liste.
    """
    parsed_results = []
    
    if isinstance(event, dict):
        for node_name, output in event.items():
            if isinstance(output, dict):
                clean_out = {k: str(v) for k, v in output.items() if k != "messages"}
            elif isinstance(output, (list, tuple)):
                clean_out = {"data": [str(x) for x in output]}
            else:
                clean_out = {"data": str(output)}
            parsed_results.append((str(node_name), clean_out))
            
    elif isinstance(event, (tuple, list)) and len(event) >= 2:
        node_name = str(event[0])
        output = event[1]
        if isinstance(output, dict):
            clean_out = {k: str(v) for k, v in output.items() if k != "messages"}
        elif isinstance(output, (list, tuple)):
            clean_out = {"data": [str(x) for x in output]}
        else:
            clean_out = {"data": str(output)}
        parsed_results.append((node_name, clean_out))
        
    return parsed_results


@celery_app.task(bind=True, name="tasks.generate_article_task")
def generate_article_task(self, thread_id: str, topic: str):
    channel_name = f"channel:{thread_id}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [],
        "topic": topic,
        "selected_redaction_skill": None,
        "selected_excalidraw_skill": None,
        "research_notes_path": None,
        "draft_path": None,
        "diagrams_path": None,
        "next_node": "skill_router",
        "revision_feedback": None,
        "is_approved": False
    }

    try:
        print(f"🚀 [Celery Worker] Starting task for thread: {thread_id}")
        graph = get_graph()

        # Stream LangGraph events
        for event in graph.stream(initial_state, config=config):
            # Utilisation du parser sécurisé
            parsed_items = parse_stream_event(event)
            for node_name, output_dict in parsed_items:
                payload = {
                    "node": node_name,
                    "thread_id": thread_id,
                    "output": output_dict
                }
                redis_client.publish(channel_name, json.dumps(payload))

        state_snapshot = graph.get_state(config)
        if "human_review" in state_snapshot.next:
            payload = {"event": "HITL_INTERRUPT", "status": "waiting_human_review"}
            redis_client.publish(channel_name, json.dumps(payload))
            redis_client.set(f"status:{thread_id}", "waiting_human_review")
        else:
            payload = {"event": "COMPLETED", "status": "completed"}
            redis_client.publish(channel_name, json.dumps(payload))
            redis_client.set(f"status:{thread_id}", "completed")

        return {"status": "success", "thread_id": thread_id}

    except Exception as e:
        error_payload = {"event": "ERROR", "error": str(e)}
        redis_client.publish(channel_name, json.dumps(error_payload))
        redis_client.set(f"status:{thread_id}", "failed")
        raise e


@celery_app.task(bind=True, name="tasks.resume_article_task")
def resume_article_task(self, thread_id: str, feedback: str):
    channel_name = f"channel:{thread_id}"
    config = {"configurable": {"thread_id": thread_id}}

    try:
        print(f"🔄 [Celery Worker] Resuming task for thread: {thread_id} with feedback")
        
        graph = get_graph()
        graph.update_state(config, {"revision_feedback": feedback, "draft_path": None})

        for event in graph.stream(None, config=config):
            parsed_items = parse_stream_event(event)
            for node_name, output_dict in parsed_items:
                payload = {
                    "node": node_name,
                    "thread_id": thread_id,
                    "output": output_dict
                }
                redis_client.publish(channel_name, json.dumps(payload))

        state_snapshot = graph.get_state(config)
        if "human_review" in state_snapshot.next:
            redis_client.publish(channel_name, json.dumps({"event": "HITL_INTERRUPT"}))
            redis_client.set(f"status:{thread_id}", "waiting_human_review")
        else:
            redis_client.publish(channel_name, json.dumps({"event": "COMPLETED"}))
            redis_client.set(f"status:{thread_id}", "completed")

        return {"status": "resumed_success", "thread_id": thread_id}

    except Exception as e:
        redis_client.publish(channel_name, json.dumps({"event": "ERROR", "error": str(e)}))
        raise e