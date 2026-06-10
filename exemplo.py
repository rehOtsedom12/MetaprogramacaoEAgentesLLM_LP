"""Módulo de exemplo com operações matemáticas e utilitárias."""

def ola(nome: str, saudacao="Olá"):
    """Exibe uma saudação personalizada.
    
    Args:
        nome: Nome da pessoa a ser saudada.
        saudacao: Palavra de saudação (padrão: 'Olá').
    """
    print(f"{saudacao}, {nome}!")

def soma(a: int, b: int = 0) -> int:
    """Retorna a soma de dois números inteiros.
    
    Args:
        a: Primeiro número
        b: Segundo número (padrão = 0)

    Returns:
        Soma calculada
    """
    resultado = a + b
    print(resultado)
    return resultado

def ativo(debug: bool = False):
    """Controla o modo de depuração do sistema."""
    print("Debug ativado" if debug else "Modo normal")
