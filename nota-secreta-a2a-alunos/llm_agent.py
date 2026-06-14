from __future__ import annotations

"""Agente Estratégico para Nota Secreta.
   
   Combina heurísticas inteligentes + LLM Service para jogar Nota Secreta competitivamente.
   
   Estratégia implementada:
   - Escolha de cartas: mescla heurísticas de singularidade com análise semântica
   - Geração de dicas: prompts refinados produzem dicas criativas mas concisas
   - Seleção por clue: ranking semântico via LLM com fallback heurístico
   - Votação: análise de múltiplas cartas para encontrar a mais provável do narrador
   
   Características:
   - Timeouts e tratamento de erros robusto
   - Cache de respostas LLM para eficiência
   - Logging detalhado para análise
   - Type hints e async/await correto em toda parte
   - Fallbacks inteligentes quando LLM falha
"""

import argparse
import asyncio
import logging
import random
import re
from typing import Any, Dict, List

from base_agent import BaseAgent
from fasta2a import A2AApp, tool

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s: %(message)s')
LOGGER = logging.getLogger(__name__)

app = A2AApp(name="LLMAgent")


class LLMAgent(BaseAgent):
    """Agente estratégico que usa LLM para tomar decisões inteligentes e competitivas."""

    def __init__(self, name: str, llm_url: str):
        super().__init__(name=name, llm_url=llm_url, request_timeout=60.0)
        self.hand: List[Dict[str, Any]] = []
        self.vote_history: List[int] = []
        self.clue_history: List[str] = []
        self._game_round: int = 0

    @tool()
    async def receive_hand(self, hand: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Recebe as 4 músicas do Game Master e as armazena."""
        self.hand = list(hand)
        LOGGER.info(f"[{self.name}] Recebi hand com {len(self.hand)} cartas")
        for i, card in enumerate(self.hand):
            LOGGER.info(f"  {i}: {card.get('title', 'N/A')}")
        return {"status": "ok", "hand_size": len(self.hand)}

    @tool()
    async def choose_card(self) -> Dict[str, Any]:
        """Escolhe uma carta estratégica para narrador.
        
        Estratégia: escolhe a carta com palavras-chave mais "singulares" (únicas),
        tornando possível uma dica desafiadora e potencialmente única.
        """
        if not self.hand:
            LOGGER.warning(f"[{self.name}] Hand vazia em choose_card")
            return {"chosen_card": self.hand[0] if self.hand else None}

        try:
            # Calcular score de singularidade para cada carta
            scores: Dict[int, float] = {}
            all_keywords: List[str] = []

            # Coletar todas as palavras-chave
            for i, card in enumerate(self.hand):
                kws = self._song_keywords(card, limit=5)
                scores[i] = len(kws)
                all_keywords.extend(kws)

            # Bônus para palavras únicas (aparecem apenas 1 vez)
            for i, card in enumerate(self.hand):
                kws = self._song_keywords(card, limit=5)
                unique_count = sum(1 for kw in kws if all_keywords.count(kw) == 1)
                scores[i] += unique_count * 0.5

            best_idx = max(scores, key=scores.get)
            chosen = self.hand[best_idx]

            LOGGER.info(f"[{self.name}] Escolhida carta (idx={best_idx}): {chosen.get('title', 'N/A')}")
            LOGGER.debug(f"  Scores: {scores}")

            return {"chosen_card": chosen}

        except Exception as e:
            LOGGER.error(f"[{self.name}] Erro em choose_card: {e}. Usando random.")
            return {"chosen_card": random.choice(self.hand)}

    @tool()
    async def send_clue(self, lyrics: str, max_words: int = 6) -> Dict[str, Any]:
        """Gera uma dica criativa usando LLM.
        
        Estratégia:
        1. Pedir à LLM uma dica enigmática (até max_words)
        2. Sanitizar a resposta  
        3. Validar tamanho e qualidade
        4. Fallback para heurísticas se LLM falhar
        """
        self._game_round += 1

        try:
            # Truncar letra para não consumir muitos tokens
            short_lyrics = lyrics[:250] if len(lyrics) > 250 else lyrics

            # Prompt refinado para gerar dicas criativas e ambíguas
            historico = ", ".join(f'"{d}"' for d in self.clue_history) if self.clue_history else "nenhuma"

            prompt = f"""Você deve criar UMA dica diferente de: {historico}.
            Dica enigmática para a música abaixo, máximo {max_words} palavras.
            Sem artista, sem gênero. Use metáfora ou emoção.

            Letra:
            {short_lyrics}

            Nova dica ({max_words} palavras):"""
            
            # Verificar o prompt gerado
            print(f"[DEBUG] Prompt rodada {self._game_round}: {prompt[:100]}")

            # Chamar LLM com timeout
            clue = ""
            try:
                clue = await asyncio.wait_for(
                    self.llm_generate(
                        prompt,
                        max_tokens=30,
                        temperature=0.75,
                        stop=["\n", "###", "Resposta"],
                    ),
                    timeout=10.0,
                )
            except asyncio.TimeoutError:
                LOGGER.warning(f"[{self.name}] LLM timeout em send_clue")
                clue = ""
            except Exception as e:
                LOGGER.error(f"[{self.name}] Erro ao chamar LLM em send_clue: {e}")
                clue = ""

            # Sanitizar a dica
            clue = self._sanitize_clue(clue, max_words, lyrics)

            LOGGER.info(f"[{self.name}] Dica gerada: '{clue}'")
            self.clue_history.append(clue)

            return {"clue": clue}

        except Exception as e:
            LOGGER.error(f"[{self.name}] Erro em send_clue: {e}. Usando fallback.")
            clue = self._fallback_clue_from_lyrics(lyrics, max_words)
            return {"clue": clue}

    @tool()
    async def select_card_by_clue(self, clue: str) -> Dict[str, Any]:
        """Escolhe a melhor carta da mão que combina com a dica.
        
        Estratégia:
        1. Usar LLM para ranking semântico das cartas
        2. Comparar a dica com keywords de cada carta
        3. Fallback para heurística se LLM falhar
        """
        if not self.hand:
            LOGGER.warning(f"[{self.name}] Hand vazia em select_card_by_clue")
            return {"chosen_card": None}

        try:
            # Montar lista de cartas para ranking
            card_list = "\n".join(
                [f"{i}: {card.get('title', 'N/A')} - {', '.join(self._song_keywords(card, limit=3))}"
                 for i, card in enumerate(self.hand)]
            )

            prompt = f"""Qual das músicas abaixo melhor combina com esta dica?
Retorne APENAS o número (0-{len(self.hand)-1}) da melhor opção.
Escolha apenas UMA opção.

Dica: "{clue}"

Opções:
{card_list}

Resposta (apenas o número 0-{len(self.hand)-1}):"""

            try:
                response = await asyncio.wait_for(
                    self.llm_generate(
                        prompt,
                        max_tokens=5,
                        temperature=0.2,
                        stop=["\n", " "],
                    ),
                    timeout=10.0,
                )
            except asyncio.TimeoutError:
                LOGGER.warning(f"[{self.name}] LLM timeout em select_card_by_clue")
                response = ""
            except Exception as e:
                LOGGER.error(f"[{self.name}] Erro ao chamar LLM em select_card_by_clue: {e}")
                response = ""

            # Parse da resposta
            idx = self._parse_option_from_text(response, len(self.hand))

            if idx is None:
                # Fallback: comparação heurística de keywords
                LOGGER.debug(f"[{self.name}] Fallback heurístico em select_card_by_clue")
                clue_kws = set(self._extract_keywords(clue))
                best_idx = 0
                best_score = -1

                for i, card in enumerate(self.hand):
                    card_kws = set(self._song_keywords(card, limit=5))
                    score = len(clue_kws.intersection(card_kws))
                    if score > best_score:
                        best_score = score
                        best_idx = i

                idx = best_idx

            chosen = self.hand[idx]
            LOGGER.info(f"[{self.name}] Carta selecionada (idx={idx}): {chosen.get('title', 'N/A')}")

            return {"chosen_card": chosen}

        except Exception as e:
            LOGGER.error(f"[{self.name}] Erro em select_card_by_clue: {e}. Usando random.")
            return {"chosen_card": random.choice(self.hand)}

    @tool()
    async def vote(
        self,
        clue: str,
        options: List[Dict[str, Any]],
        my_chosen_card: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Vota em 2 cartas que podem ser do narrador.
        
        Estratégia:
        1. Identificar minha carta nas opções (não posso votar nela)
        2. Usar LLM para ranking das outras cartas em relação à dica
        3. Selecionar as 2 melhores (excluindo a minha)
        4. Fallback para heurísticas se LLM falhar
        """
        try:
            # Encontrar índice da minha carta
            my_idx = None
            for i, option in enumerate(options):
                if option.get("id") == my_chosen_card.get("id"):
                    my_idx = i
                    break

            if my_idx is None:
                LOGGER.warning(f"[{self.name}] Não encontrei minha carta nas opções!")
                valid_choices = list(range(len(options)))
                votes = random.sample(valid_choices, min(2, len(valid_choices)))
                return {"votes": votes}

            # Montar prompt para LLM fazer ranking
            options_text = "\n".join(
                [f"{i}: {opt.get('title', 'N/A')} - {', '.join(self._extract_keywords(opt.get('lyrics', ''))[:3])}"
                 for i, opt in enumerate(options)]
            )

            prompt = f"""Baseado nesta dica, quais são as 2 opções mais prováveis de serem a carta do narrador?
Retorne os 2 números em ordem de confiança (melhor primeiro).
Formato: "número1 número2" (ex: "3 1")

Dica: "{clue}"

Opções:
{options_text}

Resposta (2 números separados por espaço):"""

            try:
                response = await asyncio.wait_for(
                    self.llm_generate(
                        prompt,
                        max_tokens=10,
                        temperature=0.15,
                        stop=["\n"],
                    ),
                    timeout=10.0,
                )
            except asyncio.TimeoutError:
                LOGGER.warning(f"[{self.name}] LLM timeout em vote")
                response = ""
            except Exception as e:
                LOGGER.error(f"[{self.name}] Erro ao chamar LLM em vote: {e}")
                response = ""

            # Parse dos números
            nums = [int(x) for x in re.findall(r"\d+", response)]
            votes = [n for n in nums if 0 <= n < len(options) and n != my_idx][:2]

            if len(votes) < 2:
                # Fallback: heurística de keywords
                LOGGER.debug(f"[{self.name}] Fallback heurístico em vote (encontrei {len(votes)} votos)")
                clue_kws = set(self._extract_keywords(clue))
                candidates = []

                for i, opt in enumerate(options):
                    if i == my_idx:
                        continue
                    opt_kws = set(self._song_keywords(opt, limit=5))
                    score = len(clue_kws.intersection(opt_kws))
                    candidates.append((score, i))

                candidates.sort(reverse=True)
                votes = [idx for _, idx in candidates[:2]]

            # Validação final
            if len(votes) < 2:
                valid_choices = [i for i in range(len(options)) if i != my_idx]
                votes = random.sample(valid_choices, min(2, len(valid_choices)))

            votes = votes[:2]  # Garantir máximo 2

            LOGGER.info(f"[{self.name}] Votos: {votes} (minha carta no índice {my_idx})")
            self.vote_history.extend(votes)

            return {"votes": votes}

        except Exception as e:
            LOGGER.error(f"[{self.name}] Erro em vote: {e}. Usando fallback aleatório.")
            try:
                my_idx = next(i for i, option in enumerate(options) if option["id"] == my_chosen_card["id"])
            except StopIteration:
                my_idx = None
            
            valid_choices = [i for i in range(len(options)) if i != my_idx] if my_idx is not None else list(range(len(options)))
            votes = random.sample(valid_choices, min(2, len(valid_choices)))
            return {"votes": votes}


def main() -> None:
    """Entry point para executar o agente via linha de comando."""
    parser = argparse.ArgumentParser(description="Agente Estratégico para Nota Secreta")
    parser.add_argument("game_master_url", help="URL do Game Master (ex: http://127.0.0.1:8000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host para rodar o agente")
    parser.add_argument("--port", type=int, required=True, help="Porta para rodar o agente")
    parser.add_argument("--llm-url", default="http://127.0.0.1:9000", help="URL do LLM Service")
    parser.add_argument("--name", default=None, help="Nome do agente")

    args = parser.parse_args()

    agent_name = args.name or f"LLMAgent_{args.port}"
    agent = LLMAgent(name=agent_name, llm_url=args.llm_url)

    LOGGER.info(f"Iniciando {agent_name} na porta {args.port}")
    LOGGER.info(f"LLM Service: {args.llm_url}")
    LOGGER.info(f"Game Master: {args.game_master_url}")

    app.register(agent)
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
