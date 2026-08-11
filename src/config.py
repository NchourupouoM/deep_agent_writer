import os
from typing import Optional, Literal
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
# from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

# Charge les variables d'environnement depuis .env
load_dotenv()

ProviderType = Literal["openai", "anthropic", "google", "deepseek", "openrouter"]

class LLMFactory:
    """
    Factory pour instancier des ChatModels de façon agnostique.
    Supporte les API directes et la passerelle OpenRouter.
    """

    @staticmethod
    def get_model(
        provider: ProviderType = "openrouter",
        temperature: float = 0.2,
        max_tokens: Optional[int] = 4096,
    ) -> BaseChatModel:
        """
        Retourne une instance de BaseChatModel configurée selon le provider.
        """
        
        # 1. OPTION OPENROUTER (Passerelle Agnostique)
        if provider == "openrouter":

            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY manquante dans le fichier .env")
            
            return ChatOpenAI(
                model=os.getenv("MODEL", "anthropic/claude-3.5-sonnet"),  # Modèle par défaut
                openai_api_key=api_key,
                openai_api_base="https://openrouter.ai/api/v1",
                temperature=temperature,
                max_tokens=max_tokens,
                default_headers={
                    "HTTP-Referer": "https://github.com/NchourupouoM",
                    "X-Title": "DeepAgent Medium Writer"
                }
            )

        # 2. OPTION OPENAI DIRECT
        elif provider == "openai":
            return ChatOpenAI(
                model=os.getenv("MODEL", "gpt-4o"),  # Modèle par défaut
                temperature=temperature,
                max_tokens=max_tokens
            )

        # # 3. OPTION ANTHROPIC DIRECT
        # elif provider == "anthropic":
        #     return ChatAnthropic(
        #         model=os.getenv("MODEL", "anthropic/claude-3.5-sonnet"),
        #         temperature=temperature,
        #         max_tokens=max_tokens
        #     )

        # 4. OPTION GOOGLE GEMINI DIRECT
        elif provider == "google":
            return ChatGoogleGenerativeAI(
                model=os.getenv("MODEL", "google/gemini-3.5-flash-lite"),
                temperature=temperature,
                max_output_tokens=max_tokens
            )

        # 5. OPTION DEEPSEEK DIRECT
        elif provider == "deepseek":
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                raise ValueError("DEEPSEEK_API_KEY manquante dans le fichier .env")
                
            return ChatOpenAI(
                model=os.getenv("MODEL"), # ex: "deepseek-chat" ou "deepseek-coder"
                openai_api_key=api_key,
                openai_api_base="https://api.deepseek.com/v1",
                temperature=temperature,
                max_tokens=max_tokens
            )

        else:
            raise ValueError(f"Provider non supporté : {provider}")


# --- TEST RAPIDE DE LA FACTORY ---
if __name__ == "__main__":
    print("🧪 Test d'instanciation de la Factory LLM...")
    
    try:
        # Exemple via OpenRouter avec Claude 3.5 Sonnet
        llm = LLMFactory.get_model(
            provider="openrouter",
            model_name="google/gemini-3.5-flash-lite",
            temperature=0.3
        )
        print(f"✅ Modèle instancié avec succès : {type(llm).__name__} via OpenRouter")
        
        # Test d'invocation simple
        response = llm.invoke("Dis 'Système prêt !' en une phrase.")
        print(f"🤖 Réponse du modèle : {response.content}")
        
    except Exception as e:
        print(f"❌ Erreur lors du test : {e}")