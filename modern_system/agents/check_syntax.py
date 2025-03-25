#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import ast

def check_syntax(filename):
    """Verifica a sintaxe de um arquivo Python linha por linha."""
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()
    
    try:
        ast.parse(content)
        print(f"Arquivo {filename} está sintaticamente correto!")
        return True
    except SyntaxError as e:
        print(f"Erro de sintaxe em {filename} na linha {e.lineno}, coluna {e.offset}")
        print(f"Detalhes: {e}")
        
        # Mostra a linha com o erro
        with open(filename, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            if e.lineno <= len(lines):
                print(f"Linha {e.lineno}: {lines[e.lineno-1].rstrip()}")
                if e.offset:
                    print(" " * (e.offset + 7) + "^")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python check_syntax.py <arquivo.py>")
        sys.exit(1)
    
    filename = sys.argv[1]
    if not check_syntax(filename):
        sys.exit(1)
