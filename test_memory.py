import sys
import os
import logging
import traceback

# Setup basic logging
logging.basicConfig(level=logging.DEBUG)

# Add project root to path
sys.path.insert(0, os.path.abspath(r"E:\Projeto_Hana_AI"))

try:
    from src.memory.memory_manager import HanaMemoryManager
    print("=== Testando Inicialização do Memory Manager ===")
    manager = HanaMemoryManager(db_path=r"E:\Projeto_Hana_AI\data\hana_memory.db")
    print("Inicialização OK.\n")
    
    print("=== Testando Adição de Interação ===")
    manager.add_interaction("nakamura", "Oi Hana, meu nome é Mestre Nakamura e minha cor favorita é carmesim. Guarda que minha senha é 1234")
    print("Interação adicionada.\n")
    
    print("=== Testando SQLite (Histórico) ===")
    msgs = manager.get_messages(5)
    for msg in msgs:
        print(msg)
    
    print("\n=== Testando RAG & Knowledge Graph (Contexto) ===")
    context = manager.get_context("Qual a minha cor favorita?")
    print("Contexto Recuperado:")
    print(context)
    
    print("\n=== Todos os componentes testados com sucesso! ===")
except Exception as e:
    print(f"\nERRO NO TESTE DE MEMÓRIA: {e}")
    traceback.print_exc()
