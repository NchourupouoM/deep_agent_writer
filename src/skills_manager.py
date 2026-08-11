import os
import re
import yaml
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from prompts import SKILL_INDEX_HEADER


class SkillMetadata(BaseModel):
    """Pydantic model compliant with AgentSkills.io specification."""
    name: str
    description: str
    version: str = "1.0.0"
    authors: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    filepath: str


class Skill(BaseModel):
    """Complete Skill representation (YAML Metadata + Markdown Body)."""
    metadata: SkillMetadata
    content: str


class SkillsManager:
    """
    AgentSkills.io compliant Skills Manager.
    Scans, parses, indexes, and dynamically loads skill files for LLM Agents.
    """

    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = skills_dir
        self.skills_registry: Dict[str, Skill] = {}
        self.load_all_skills()

    def _parse_skill_file(self, filepath: str) -> Optional[Skill]:
        """Extracts YAML frontmatter and Markdown body from a SKILL.md file."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw_content = f.read()

            # Match YAML block between --- and ---
            pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
            match = re.match(pattern, raw_content, re.DOTALL)

            if not match:
                print(f"⚠️ Warning: File {filepath} does not follow AgentSkills.io YAML frontmatter format.")
                return None

            yaml_str, markdown_body = match.groups()
            frontmatter = yaml.safe_load(yaml_str)

            metadata = SkillMetadata(
                name=frontmatter.get("name"),
                description=frontmatter.get("description"),
                version=str(frontmatter.get("version", "1.0.0")),
                authors=frontmatter.get("authors", []),
                tags=frontmatter.get("tags", []),
                filepath=filepath
            )

            return Skill(metadata=metadata, content=markdown_body.strip())

        except Exception as e:
            print(f"❌ Error parsing skill file {filepath}: {e}")
            return None

    def load_all_skills(self):
        """Scans skills/ directory and registers all valid .md skill files."""
        self.skills_registry.clear()
        if not os.path.exists(self.skills_dir):
            os.makedirs(self.skills_dir)
            return

        for root, _, files in os.walk(self.skills_dir):
            for file in files:
                if file.endswith(".md"):
                    full_path = os.path.join(root, file)
                    skill = self._parse_skill_file(full_path)
                    if skill:
                        self.skills_registry[skill.metadata.name] = skill

        print(f"✅ Loaded {len(self.skills_registry)} Skills adhering to AgentSkills.io standard.")

    def get_skills_index_for_prompt(self) -> str:
        """
        Generates a lightweight skills index formatted for system prompts.
        Allows the agent to select the correct skill dynamically.
        """
        lines = [SKILL_INDEX_HEADER]

        redaction_skills = []
        excalidraw_skills = []

        for skill in self.skills_registry.values():
            meta = skill.metadata
            item = f"- **{meta.name}**: {meta.description} (Tags: {', '.join(meta.tags)})"
            if "redaction" in meta.tags:
                redaction_skills.append(item)
            elif "excalidraw" in meta.tags:
                excalidraw_skills.append(item)

        lines.append("\n📌 **Pedagogical Redaction Skills:**")
        lines.extend(redaction_skills)

        lines.append("\n📌 **Excalidraw Visual Diagram Skills:**")
        lines.extend(excalidraw_skills)

        return "\n".join(lines)

    def get_skill_content(self, skill_name: str) -> Optional[str]:
        """Retrieves full markdown content of a specified skill."""
        skill = self.skills_registry.get(skill_name)
        return skill.content if skill else None


# if __name__ == "__main__":
#     print("🧪 Testing SkillsManager with isolated prompts...")
#     manager = SkillsManager(skills_dir="skills")
#     print(manager.get_skills_index_for_prompt())