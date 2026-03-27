import os
import json
import time
import requests
import re
from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, RateLimitError, APITimeoutError
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.theme import Theme
from rich.prompt import Prompt

# Темы оформления
custom_theme = Theme({
    "info": "dim cyan",
    "success": "bold green",
    "warning": "bold yellow",
    "error": "bold red",
    "user_label": "bold green",
    "assistant_label": "bold blue",
    "thinking_style": "italic dim white",
    "balance": "bold magenta"
})

console = Console(theme=custom_theme)

class ProxyAssistant:
    def __init__(self):
        console.clear()
        console.print("[info]🚀 Инициализация систем...[/info]")
        load_dotenv()
        
        self.api_key = os.getenv("PROXY_API_KEY")
        self.base_url = os.getenv("BASE_URL")
        self.history_file = "chat_history.json"
        
        if not self.api_key:
            console.print("[error]❌ КРИТИЧЕСКАЯ ОШИБКА: Ключ не найден в .env[/error]")
            exit(1)

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.history = self._load_history()
        
        self.mode = "standard"
        self.models = {
            "standard": os.getenv("DEFAULT_MODEL", "gpt-4o-mini"),
            "thinking": os.getenv("THINKING_MODEL", "o3-mini")
        }

        # Получаем баланс
        self.balance = self._get_balance()
        
        console.print("[success]✅ Система готова к работе.[/success]")
        time.sleep(0.5)

    def _get_balance(self):
        """Запрос баланса согласно документации ProxyAPI"""
        try:
            # Официальный эндпоинт для проверки баланса
            url = "https://api.proxyapi.ru/proxyapi/balance"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # Для ключей с лимитом возвращается остаток (limit - used)
                bal = data.get('balance', 0)
                return f"{bal:.2f} руб."
            elif response.status_code == 403:
                return "Доступ к балансу выключен в ЛК"
            return f"Ошибка {response.status_code}"
        except Exception:
            return "Сбой сети"

    def _load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except: return []
        return []

    def _save_history(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            console.print(f"[error]❌ Ошибка сохранения истории: {e}[/error]")

    def print_welcome_banner(self):
        console.print(Panel.fit(
            f"[bold blue]TERMINAL AI ASSISTANT[/bold blue]\n"
            f"[dim]ProxyAPI Edition | Reasoning Support[/dim]\n\n"
            f"[balance]💰 Текущий баланс: {self.balance}[/balance]",
            border_style="blue", padding=(1, 2)
        ))
        console.print(f"[info]Режим: [bold]{self.mode.upper()}[/bold] ({self.models[self.mode]})[/info]")
        console.print("[info]Команды: [bold]/mode[/bold], [bold]/clear[/bold], [bold]/exit[/bold][/info]\n")

    def get_ai_response(self, user_input):
        self.history.append({"role": "user", "content": user_input})
        model_id = self.models[self.mode]
        
        try:
            with console.status(f"[bold green]Запрос к {model_id}...", spinner="dots"):
                response = self.client.chat.completions.create(
                    model=model_id,
                    messages=self.history,
                    timeout=150
                )

            message = response.choices[0].message # Используем индекс для надежности
            content = message.content or ""
            reasoning = getattr(message, 'reasoning_content', None)

            return content, reasoning

        except APITimeoutError:
            console.print("[error]⏳ ОШИБКА: Превышено время ожидания.[/error]")
        except RateLimitError:
            console.print("[error]🛑 ОШИБКА: Лимиты или баланс.[/error]")
        except Exception as e:
            if "402" in str(e):
                console.print("[error]💰 ОШИБКА: Недостаточно средств.[/error]")
            else:
                console.print(f"[error]❌ Ошибка API: {str(e)}[/error]")
        
        return None, None

    def run(self):
        self.print_welcome_banner()
        
        while True:
            user_input = Prompt.ask(f"[user_label]👤 ({self.mode})[/user_label]").strip()

            if not user_input: continue

            if user_input.lower() in ["/exit", "exit", "quit"]:
                self._save_history()
                console.print("[warning]👋 История сохранена. Выход.[/warning]")
                break

            if user_input.lower() == "/mode":
                self.mode = "thinking" if self.mode == "standard" else "standard"
                console.print(f"[warning]🔄 Модель: {self.models[self.mode].upper()}[/warning]\n")
                continue

            if user_input.lower() == "/clear":
                self.history = []
                self._save_history()
                console.print("[warning]🧹 Контекст очищен.[/warning]\n")
                continue

            ans_text, ans_reasoning = self.get_ai_response(user_input)

            if ans_text:
                if ans_reasoning:
                    console.print(Panel(ans_reasoning, title="🧠 Thoughts", style="thinking_style", border_style="dim"))
                
                console.print(Panel(Markdown(ans_text), title=f"🤖 {self.models[self.mode]}", border_style="blue"))
                
                self.history.append({"role": "assistant", "content": ans_text})
                self._save_history()

if __name__ == "__main__":
    try:
        ProxyAssistant().run()
    except KeyboardInterrupt:
        console.print("\n[warning]⚠️ Прервано пользователем.[/warning]")
