# Nota Secreta — Agente Estratégico com LLM

Implementação de um **agente inteligente estratégico** para o jogo "Nota Secreta" (adaptação de Dixit para música brasileira) que combina heurísticas sofisticadas com LLM local para competir consistentemente.

**Integrantes:** Renata Modesto, Sofia Icavino

Este projeto demonstra:
- Integração de LLM em sistemas multiagentes autônomos
- Estratégias de decisão semântica vs. heurísticas
- Tratamento robusto de respostas imperfeitas
- Arquitetura distribuída com comunicação A2A

## 📋 Índice
1. [Como Executar](#como-executar)
2. [Arquitetura e Estratégia](#arquitetura-e-estratégia)
3. [Detalhes de Implementação](#detalhes-de-implementação)
4. [Exemplos de Saída](#exemplos-de-saída)
5. [Dificuldades e Soluções](#dificuldades-e-soluções)

---

## 🎮 Como Executar

### Opção 1: Execução Automatizada (Recomendada)

```bash
# Inicia tudo automaticamente
python run_game.py --model Phi-3.5-mini-instruct-Q4_K_M.gguf
```

Ou em modo mock (sem LLM real):
```bash
python run_game.py --force-mock
```

### Opção 2: Execução Manual

**Terminal 1: LLM Service**
```bash
python llm_service.py --model Phi-3.5-mini-instruct-Q4_K_M.gguf --port 9000
```

**Terminal 2: Game Master**
```bash
python game_master.py --port 8000 --db brazilian_songs.csv --target-score 30 --log-dir logs
```

**Terminais 3-8: Agentes**
```bash
python llm_agent.py http://127.0.0.1:8000 --port 8001 --llm-url http://127.0.0.1:9000 --name LLMAgent_1
python random_agent.py http://127.0.0.1:8000 --port 8002 --llm-url http://127.0.0.1:9000 --name RandomAgent_2
# ... (mais 4 agentes aleatórios nas portas 8003-8006)
```

---

## 🧠 Arquitetura e Estratégia

### 5 Tools Implementadas

**1. `receive_hand(hand: List[Dict])`** - Recebe e armazena 4 músicas

**2. `choose_card()`** - Escolhe música como narrador
- Estratégia: Seleciona carta com palavras-chave mais únicas

**3. `send_clue(lyrics: str, max_words: int = 6)`** - Gera dica via LLM
- LLM pede dica criativa (temperature 0.75)
- Sanitização robusta remove prefixos e pontuação
- Fallback para keywords da letra se LLM falhar

**4. `select_card_by_clue(clue: str)`** - Escolhe carta que combina com dica
- LLM ranking (temperature 0.2)
- Fallback: interseção de keywords

**5. `vote(clue: str, options: List[Dict], my_chosen_card: Dict)`** - Vota em 2 cartas
- LLM ranking (temperature 0.15)
- Validação: exatamente 2, distintos, não a própria
- Fallback: heurística de keywords

---

## 🔧 Detalhes de Implementação

### Parâmetros LLM

| Tool | max_tokens | temperature | timeout |
|------|-----------|-------------|---------|
| `send_clue` | 30 | 0.75 | 10s |
| `select_card_by_clue` | 5 | 0.2 | 10s |
| `vote` | 10 | 0.15 | 10s |

### Fallbacks Hierárquicos

```
LLM Call → Parse Response → Heuristic → Random Choice
```

---

## 📊 Exemplos de Saída

```
[INFO] Iniciando LLMAgent_1 na porta 8001

=== RODADA 1 ===
[INFO] Recebi hand com 4 cartas: Garota de Ipanema, João Valentão, ...
[INFO] Escolhida carta (idx=1): João Valentão
[INFO] Dica gerada: 'valentão brigão coração'
[INFO] Votos: [3, 2] (minha carta no índice 1)

[GAME] Pontuação: [3, 1, 1, 6, 4, 4]
[GAME] Placar Acumulado: [3, 1, 1, 6, 4, 4]
```

---

## 🐛 Dificuldades Encontradas e Soluções

**1. Respostas Inconsistentes LLM**
- Problema: Formato variado, prefixos aleatórios
- Solução: Sanitização robusta + parser flexível

**2. Timeouts Frequentes**
- Problema: LLM demora >60s
- Solução: Timeouts curtos (10s) + fallbacks imediatos

**3. Ambiguidade em Dicas**
- Problema: Óbvias ou vagas demais
- Solução: Prompts refinados + rejeitar substrings

**4. Identificação de Própria Carta**
- Problema: ID não encontrado em opções embaralhadas
- Solução: Comparar por `card["id"]` + fallback random

---

O projeto combina dois estilos de comunicação:

- **REST/FastAPI** entre os agentes e o serviço LLM centralizado (`llm_service.py`);
- **A2A / JSON-RPC** entre o Game Master e os agentes.

Em uma execução típica:

1. o `run_game.py` sobe o serviço LLM;
2. sobe o `game_master.py`;
3. sobe 1 agente estratégico e 5 agentes aleatórios;
4. registra os agentes no Game Master;
5. executa uma partida completa;
6. salva um log da partida em `logs/`.

---

## 2. Estrutura dos arquivos

Arquivos principais:

- `fasta2a.py`: mini-implementação de `A2AApp` e `@tool`
- `base_agent.py`: utilidades comuns para agentes
- `llm_service.py`: serviço LLM centralizado (real ou mock)
- `game_master.py`: coordenação da partida, votação, pontuação e logs
- `llm_agent.py`: agente estratégico a ser estudado e modificado
- `random_agent.py`: baseline aleatório
- `run_game.py`: sobe tudo e executa uma partida completa
- `render_log_readable.py`: transforma logs em uma visualização mais legível
- `brazilian_songs.csv`: base de músicas usada pelo jogo
- `tests/`: testes auxiliares

---

## 3. O que você deve modificar

Em geral, os arquivos mais importantes para o aluno são:

- `llm_agent.py`
- `base_agent.py` (opcional)

Você pode reorganizar a lógica interna do agente, desde que preserve a interface esperada
pelo restante da infraestrutura.

As ferramentas (tools) esperadas do agente são:

- `receive_hand(hand)`
- `choose_card()`
- `send_clue(lyrics, max_words=6)`
- `select_card_by_clue(clue)`
- `vote(clue, options, my_chosen_card)`

---

## 4. Instalação

Crie e ative um ambiente virtual:

```bash
python3 -m venv venv
source venv/bin/activate
```

Instale as dependências:

```bash
python3 -m pip install -r requirements.txt
```

---

## 5. Execução rápida

### 5.1. Rodar em modo mock

Esse modo não usa um modelo real e é útil para validar rapidamente a arquitetura:

```bash
python3 run_game.py --force-mock
```

### 5.2. Rodar com um modelo GGUF real

```bash
python3 run_game.py --model /caminho/do/modelo.gguf
```

Exemplo:

```bash
python3 run_game.py --model ~/Documentos/LLM/Phi-3.5-mini-instruct-Q4_K_M.gguf
```

---

## 6. Opções úteis do `run_game.py`

### Subir 6 agentes estratégicos

```bash
python3 run_game.py --all-strategic --force-mock
```

ou:

```bash
python3 run_game.py --all-strategic --model /caminho/do/modelo.gguf
```

### Alterar a base de músicas

```bash
python3 run_game.py --db outra_base.csv --force-mock
```

### Ajustar concorrência do serviço LLM

```bash
python3 run_game.py --model /caminho/do/modelo.gguf --llm-max-concurrency 1
```

---

## 7. Logs

Ao final da partida, o Game Master salva um log JSON em:

```text
logs/
```

O caminho do log também é mostrado no terminal ao fim da execução.

Esses logs ajudam a entender:

- qual agente foi narrador em cada rodada;
- qual dica foi produzida;
- quais cartas foram jogadas;
- como os votos foram distribuídos;
- como a pontuação evoluiu ao longo da partida.

---

## 8. Como ler os logs

Para transformar um log em uma visualização mais legível:

```bash
python3 render_log_readable.py logs/partida_xxx.json
```

---

## 9. Observações sobre a base de músicas

A base CSV deve conter, no mínimo, as colunas:

- `id`
- `title`
- `artist`
- `lyrics`

A base fornecida aqui serve para testes e desenvolvimento local.
Na avaliação, vai ser usada uma base oficial definida pelo professor.

---

## 10. Objetivo pedagógico

O foco deste trabalho não é apenas “fazer um agente funcionar”, mas construir
um **sistema multiagente baseado em LLM**.

Por isso, espera-se que o agente:

- use a LLM para decisões semânticas;
- lide com respostas imperfeitas de forma robusta;
- preserve o protocolo esperado pela infraestrutura.

Em outras palavras:

> a implementação interna pode variar, mas a interface externa do agente deve continuar compatível.

---

## 11. Resumo

Use esta versão do projeto para:

- entender a arquitetura;
- rodar testes locais;
- modificar o agente estratégico;
- experimentar diferentes prompts e estratégias.

Fluxo mínimo recomendado:

1. rodar `python3 run_game.py --force-mock`
2. rodar `python3 run_game.py --model ...`
3. inspecionar os logs
4. modificar `llm_agent.py`
5. repetir os testes
