import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv

from src.graph import create_deep_agent_graph
from src.tools import read_workspace_file, list_workspace_files

load_dotenv()


def print_banner():
    print("""
    ===============================================================
    🚀 DEEP AGENT MEDIUM WRITER (LangChain + LangGraph + Postgres)
    ===============================================================
    Powered by AgentSkills.io | Model-Agnostic | Visual Pedagogical AI
    """)


def display_workspace_summary():
    print("\n---------------------------------------------------------------")
    print("📁 GENERATED WORKSPACE ARTIFACTS SUMMARY:")
    print("---------------------------------------------------------------")
    print(list_workspace_files.invoke({}))
    print("---------------------------------------------------------------\n")


def main():
    print_banner()

    # 1. Ask User for Article Topic
    topic = input("\n📝 Enter the AI Article Topic to generate: ").strip()
    if not topic:
        topic = "LoRA and QLoRA Fine-Tuning Explained Visually from First Principles"
        print(f"ℹ️ No topic entered. Using default: '{topic}'")

    # 2. Thread Configuration for State Persistence
    thread_id = f"article_thread_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    print(f"🆔 Session Thread ID: {thread_id}")

    # 3. Compile Graph with Postgres Checkpointer
    app = create_deep_agent_graph(use_postgres=True)

    # 4. Initial Execution Run
    initial_state = {
        "messages": [],
        "topic": topic,
        "selected_redaction_skill": None,
        "selected_excalidraw_skill": None,
        "skill_selection_rationale": None,
        "research_notes_path": None,
        "draft_path": None,
        "diagrams_path": None,
        "next_node": "skill_router",
        "revision_feedback": None,
        "is_approved": False
    }

    print("\n⏳ Starting Deep Agent Autonomous Execution Pipeline...")
    
    # Stream events until Interrupt (HITL before human_review)
    for event in app.stream(initial_state, config=config):
        for node_name, output in event.items():
            print(f"✔️ Node Completed: [{node_name}]")

    # 5. HUMAN-IN-THE-LOOP INTERRUPT LOOP
    while True:
        display_workspace_summary()

        print("🔎 Human Review Options:")
        print("  1. Inspect Draft Article (workspace/draft.md)")
        print("  2. Inspect Excalidraw Specs (workspace/diagrams_spec.md)")
        print("  3. Approve and Finish Article ✅")
        print("  4. Request Revision with Feedback 🔄")

        choice = input("\nChoose an option (1-4): ").strip()

        if choice == "1":
            content = read_workspace_file.invoke({"filename": "draft.md"})
            print(f"\n--- DRAFT ARTICLE PREVIEW ---\n{content[:2000]}...\n[Truncated for CLI]\n")

        elif choice == "2":
            content = read_workspace_file.invoke({"filename": "diagrams_spec.md"})
            print(f"\n--- EXCALIDRAW DIAGRAM SPECS ---\n{content}\n")

        elif choice == "3":
            print("\n🎉 Article Approved by Human Editor! Saved to workspace/.")
            print(f"📂 Final files ready in 'workspace/' directory for Medium publication.")
            print("===============================================================\n")
            break

        elif choice == "4":
            feedback = input("\n✍️ Enter your revision feedback for the agents: ").strip()
            if feedback:
                print(f"\n🔄 Resuming graph execution with feedback: '{feedback}'...")
                
                # Update graph state with human feedback and resume
                app.update_state(config, {"revision_feedback": feedback, "draft_path": None})
                
                for event in app.stream(None, config=config):
                    for node_name, output in event.items():
                        print(f"✔️ Node Completed: [{node_name}]")
            else:
                print("⚠️ Feedback cannot be empty.")


if __name__ == "__main__":
    main()