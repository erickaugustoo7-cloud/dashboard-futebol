# -*- coding: utf-8 -*-
"""
Supabase Database Client Helper
Loads credentials from .env.local and initializes connection to PostgreSQL.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Carregar variáveis de ambiente
try:
    base_dir = os.path.dirname(__file__)
except NameError:
    base_dir = os.getcwd()
env_path = os.path.join(base_dir, "..", ".env.local")
load_dotenv(dotenv_path=env_path)

url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
# Para scripts Python (backfill), preferimos a SERVICE_ROLE_KEY para ignorar RLS se necessário,
# mas damos fallback para a ANON_KEY caso seja a única disponível.
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

def get_supabase_client() -> Client:
    if not url or not key:
        print("\n" + "="*80)
        print(" ⚠️  ERRO: Configurações do Supabase não encontradas!")
        print(" Por favor, adicione as seguintes variáveis no seu arquivo .env.local:")
        print("   NEXT_PUBLIC_SUPABASE_URL=sua_url_do_supabase")
        print("   SUPABASE_SERVICE_ROLE_KEY=sua_chave_service_role")
        print("="*80 + "\n")
        raise ValueError("Configurações do Supabase (URL e KEY) estão ausentes no .env.local")
    
    return create_client(url, key)

# Exporta uma instância singleton do cliente
try:
    supabase_client = get_supabase_client()
except Exception:
    supabase_client = None
