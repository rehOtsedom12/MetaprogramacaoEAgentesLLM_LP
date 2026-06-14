#!/usr/bin/env python3
"""Implementação de mini-Fire."""

import sys
import inspect
import importlib.util
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class MeuFireParser:
    """Parser de argumentos e executor de funções CLI."""
    
    def __init__(self, modulo):
        """Inicializa o parser com o módulo carregado."""
        self.modulo = modulo
        self.funcoes = self._extrair_funcoes()
        self.modulo_docstring = inspect.getdoc(modulo)
    
    def _extrair_funcoes(self) -> Dict[str, Callable]:
        """Extrai apenas funções definidas no nível global do módulo."""
        funcoes = {}
        for nome, obj in inspect.getmembers(self.modulo):
            # Ignora funções privadas, importadas e classes
            if nome.startswith('_'):
                continue
            if not inspect.isfunction(obj):
                continue
            # Verifica se a função foi definida neste módulo (não importada)
            if obj.__module__ == self.modulo.__name__:
                funcoes[nome] = obj
        return funcoes
    
    def _extrair_docstring_simples(self, docstring: Optional[str]) -> str:
        """Extrai a primeira linha do docstring."""
        if not docstring:
            return "Sem descrição disponível"
        primeira_linha = docstring.split('\n')[0].strip()
        return primeira_linha if primeira_linha else "Sem descrição disponível"
    
    def _extrair_parametros_docstring(self, docstring: Optional[str]) -> Dict[str, str]:
        """Extrai descrição dos parâmetros do docstring (formato Google)."""
        parametros = {}
        if not docstring:
            return parametros
        
        # Procura seção "Args:" (estilo Google)
        match = re.search(r'Args:\s*\n((?:.*\n)*?)(?=\n\s*Returns:|$)', docstring)
        if match:
            args_section = match.group(1)
            # Parse cada linha: "nome: descrição"
            for linha in args_section.split('\n'):
                linha = linha.strip()
                if ':' in linha:
                    nome, desc = linha.split(':', 1)
                    parametros[nome.strip()] = desc.strip()
        
        return parametros
    
    def _extrair_return_docstring(self, docstring: Optional[str]) -> Optional[str]:
        """Extrai descrição do retorno do docstring (formato Google)."""
        if not docstring:
            return None
        
        match = re.search(r'Returns:\s*\n((?:.*\n)*?)(?=\n\s*\w+:|$)', docstring)
        if match:
            return match.group(1).strip()
        
        return None
    
    def _obter_info_parametros(self, funcao: Callable) -> List[Tuple[str, type, bool, Any]]:
        """Retorna lista de (nome, tipo, é_obrigatório, valor_padrão)."""
        sig = inspect.signature(funcao)
        parametros = []
        
        for param_name, param in sig.parameters.items():
            # Tipo padrão é str se não estiver anotado
            param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
            
            # Verifica se é obrigatório (sem valor padrão)
            eh_obrigatorio = param.default == inspect.Parameter.empty
            valor_padrao = param.default if not eh_obrigatorio else None
            
            parametros.append((param_name, param_type, eh_obrigatorio, valor_padrao))
        
        return parametros
    
    def _converter_argumento(self, valor_str: str, tipo: type) -> Any:
        """Converte string de argumento para o tipo correto."""
        if tipo == int:
            try:
                return int(valor_str)
            except ValueError:
                raise TypeError(f"Esperava int, recebeu '{valor_str}'")
        elif tipo == float:
            try:
                return float(valor_str)
            except ValueError:
                raise TypeError(f"Esperava float, recebeu '{valor_str}'")
        elif tipo == bool:
            if valor_str.lower() in ('true', 'yes', '1'):
                return True
            elif valor_str.lower() in ('false', 'no', '0'):
                return False
            else:
                raise TypeError(f"Esperava bool (true/false/yes/no/1/0), recebeu '{valor_str}'")
        else:  # str
            return valor_str
    
    def _exibir_ajuda_geral(self):
        """Exibe ajuda geral com todos os comandos."""
        print(f"\nMódulo: {self.modulo.__name__}")
        if self.modulo_docstring:
            print(f"Descrição: {self.modulo_docstring}\n")
        
        print("Comandos disponíveis:")
        for nome_funcao in sorted(self.funcoes.keys()):
            funcao = self.funcoes[nome_funcao]
            docstring = inspect.getdoc(funcao)
            descricao = self._extrair_docstring_simples(docstring)
            print(f"  {nome_funcao:<10} - {descricao}")
            
            # Exibe parâmetros
            parametros = self._obter_info_parametros(funcao)
            for param_name, param_type, eh_obrigatorio, valor_padrao in parametros:
                tipo_nome = param_type.__name__ if hasattr(param_type, '__name__') else str(param_type)
                
                if eh_obrigatorio:
                    print(f"      --{param_name} ({tipo_nome}, obrigatório): {param_name}")
                elif param_type == bool:
                    print(f"      --{param_name} ({tipo_nome}, padrão={valor_padrao})")
                else:
                    print(f"      --{param_name} ({tipo_nome}, padrão={valor_padrao}): {param_name}")
            print()
    
    def _exibir_ajuda_funcao(self, nome_funcao: str):
        """Exibe ajuda específica de uma função."""
        if nome_funcao not in self.funcoes:
            print(f"Erro: Comando '{nome_funcao}' não encontrado. Use --help para listar.")
            sys.exit(1)
        
        funcao = self.funcoes[nome_funcao]
        docstring = inspect.getdoc(funcao)
        descricao = self._extrair_docstring_simples(docstring)
        parametros = self._obter_info_parametros(funcao)
        params_desc = self._extrair_parametros_docstring(docstring)
        return_desc = self._extrair_return_docstring(docstring)
        
        # Construir linha de uso
        obrigatorios = [p[0] for p in parametros if p[2]]
        opcionais = [p[0] for p in parametros if not p[2]]
        uso = f"{nome_funcao}"
        if obrigatorios:
            uso += " " + " ".join(f"--{p}" for p in obrigatorios)
        if opcionais:
            uso += " " + " ".join(f"[--{p}]" for p in opcionais)
        
        print(f"\nComando: {nome_funcao}")
        print(f"Descrição: {descricao}")
        print(f"\nUso: {uso}\n")
        
        print("Parâmetros:")
        for param_name, param_type, eh_obrigatorio, valor_padrao in parametros:
            tipo_nome = param_type.__name__ if hasattr(param_type, '__name__') else str(param_type)
            param_desc = params_desc.get(param_name, "")
            
            if eh_obrigatorio:
                status = "obrigatório"
            else:
                status = f"padrão={valor_padrao}"
            
            print(f"  --{param_name} ({tipo_nome}, {status}): {param_desc}")
        
        if return_desc:
            print(f"\nRetorna: {return_desc}")
    
    def executar(self, args: List[str]):
        """Executa o comando com os argumentos fornecidos."""
        if not args or args[0] in ('--help', 'ajuda'):
            self._exibir_ajuda_geral()
            return
        
        nome_funcao = args[0]
        
        if nome_funcao not in self.funcoes:
            print(f"Erro: Comando '{nome_funcao}' não encontrado. Use --help para listar.")
            sys.exit(1)
        
        # Verifica se pede ajuda do comando específico
        if len(args) > 1 and args[1] in ('--help', 'ajuda'):
            self._exibir_ajuda_funcao(nome_funcao)
            return
        
        funcao = self.funcoes[nome_funcao]
        parametros = self._obter_info_parametros(funcao)
        
        # Parse dos argumentos
        kwargs = {}
        args_restantes = args[1:]
        posicionais_esperados = [p for p in parametros if p[2]]  # (nome, tipo, obrig, default)
        pos_idx = 0  # quantos posicionais já foram consumidos

        i = 0
        while i < len(args_restantes):
            arg = args_restantes[i]
            
            if arg.startswith('--'):
                param_name = arg[2:]
                
                # Encontra o parâmetro
                param_info = None
                for pname, ptype, eh_obrigatorio, pvalue in parametros:
                    if pname == param_name:
                        param_info = (pname, ptype, eh_obrigatorio, pvalue)
                        break
                
                if not param_info:
                    print(f"Erro: Parâmetro desconhecido '{param_name}'")
                    sys.exit(1)
                
                pname, ptype, eh_obrigatorio, pvalue = param_info
                
                # Para bool, pode ser um flag
                if ptype == bool:
                    if i + 1 < len(args_restantes) and not args_restantes[i + 1].startswith('--'):
                        # Valor explícito
                        try:
                            kwargs[pname] = self._converter_argumento(args_restantes[i + 1], ptype)
                            i += 2
                        except TypeError as e:
                            print(f"Erro: {e}")
                            sys.exit(1)
                    else:
                        # Flag sem valor = True
                        kwargs[pname] = True
                        i += 1
                else:
                    # Outros tipos precisam de valor
                    if i + 1 >= len(args_restantes) or args_restantes[i + 1].startswith('--'):
                        print(f"Erro: Parâmetro '{param_name}' requer valor")
                        sys.exit(1)
                    
                    try:
                        kwargs[pname] = self._converter_argumento(args_restantes[i + 1], ptype)
                        i += 2
                    except TypeError as e:
                        print(f"Erro: {e}")
                        sys.exit(1)
            else:
                if pos_idx >= len(posicionais_esperados):
                    print(f"Erro: Argumento posicional inesperado '{arg}'")
                    sys.exit(1)
                pname, ptype, _, _ = posicionais_esperados[pos_idx]
                try:
                    kwargs[pname] = self._converter_argumento(arg, ptype)
                    pos_idx += 1
                    i += 1
                except TypeError as e:
                    print(f"Erro: Parâmetro '{pname}' esperava {ptype.__name__}, recebeu '{arg}'")
                    sys.exit(1)
        
        # Valida obrigatórios
        for pname, ptype, eh_obrigatorio, pvalue in parametros:
            if eh_obrigatorio and pname not in kwargs:
                print(f"Erro: Parâmetro obrigatório '{pname}' não fornecido")
                sys.exit(1)
        
        # Executa função
        try:
            resultado = funcao(**kwargs)
            if resultado is not None:
                print(f"Pela funcao 'executar', resultado = {resultado}")
        except Exception as e:
            print(f"Erro ao executar '{nome_funcao}': {e}")
            sys.exit(1)


def meu_fire(caminho_modulo: str):
    """
    Transforma funções Python em interface CLI.
    
    Args:
        caminho_modulo: Caminho para arquivo .py a ser carregado
    """
    # Valida arquivo
    caminho = Path(caminho_modulo)
    if not caminho.exists():
        print(f"Erro: Arquivo '{caminho_modulo}' não encontrado")
        sys.exit(1)
    
    if not caminho.suffix == '.py':
        print(f"Erro: Arquivo deve ser .py, recebido '{caminho.suffix}'")
        sys.exit(1)
    
    # Carrega módulo dinamicamente
    spec = importlib.util.spec_from_file_location("modulo_dinamico", caminho)
    modulo = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(modulo)
    except Exception as e:
        print(f"Erro ao carregar módulo: {e}")
        sys.exit(1)
    
    # Cria parser e executa
    parser = MeuFireParser(modulo)
    
    # Argumentos da CLI (ignora primeiro que é o nome do script)
    cli_args = sys.argv[2:] if len(sys.argv) > 2 else ['--help']
    parser.executar(cli_args)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python meu_fire.py <arquivo.py> [comando] [args...]")
        sys.exit(1)
    
    caminho = sys.argv[1]
    meu_fire(caminho)
